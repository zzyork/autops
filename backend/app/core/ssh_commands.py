import codecs
import logging
import shlex
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

import paramiko

logger = logging.getLogger(__name__)
MAX_OUTPUT_BYTES = 256 * 1024
READ_SIZE = 32 * 1024
READ_POLL_SECONDS = 0.05
OutputStream = Literal["stdout", "stderr"]
ERROR_MESSAGES = {
    "timeout": "SSH 命令执行超时",
    "connection": "SSH 连接已断开",
    "output_limit": "SSH 命令输出超出限制",
    "internal": "SSH 命令执行失败",
    "unknown": "SSH 命令执行结果未知",
    "interrupted": "SSH 命令采集已中断",
}


@dataclass(frozen=True)
class CommandResult:
    stdout: str
    stderr: str
    exit_status: int


class CommandExecutionError(Exception):
    def __init__(self, code: str, connected: bool, *, dispatched: bool = True,
                 exit_status: int | None = None):
        self.code = code
        self.connected = connected
        # 尝试发送 exec 请求就可能产生副作用，未收到应答也不能视为未执行。
        self.dispatched = dispatched
        self.exit_status = exit_status
        super().__init__(ERROR_MESSAGES[code])


def _connected(client: paramiko.SSHClient) -> bool:
    try:
        transport = client.get_transport()
        return transport is not None and transport.is_active()
    except Exception:
        return False


def _close_channel(channel: paramiko.Channel) -> None:
    try:
        channel.close()
    except Exception as exc:
        logger.warning("SSH channel cleanup failed: %s", type(exc).__name__)


def run_command(
    client: paramiko.SSHClient, command: str, timeout_seconds: float = 30,
    deadline: float | None = None, *,
    on_output: Callable[[OutputStream, str], None] | None = None,
    cancel: threading.Event | None = None,
) -> CommandResult:
    end = time.monotonic() + timeout_seconds
    if deadline is not None:
        end = min(end, deadline)
    channel: paramiko.Channel | None = None
    timer: threading.Timer | None = None
    expired = threading.Event()
    output_limited = threading.Event()
    output_lock = threading.Lock()
    output_size = 0
    stdout = bytearray()
    stderr = bytearray()
    reader_errors: list[type[Exception]] = []
    readers: list[threading.Thread] = []
    watcher: threading.Thread | None = None
    watcher_done = threading.Event()
    dispatched = False
    exit_status: int | None = None
    offsets = {"stdout": 0, "stderr": 0}
    decoders = {name: codecs.getincrementaldecoder("utf-8")(errors="replace")
                for name in ("stdout", "stderr")}
    output_finalized = False
    callback_failed = False

    def execution_error(code: str, connected: bool | None = None) -> CommandExecutionError:
        return CommandExecutionError(code, _connected(client) if connected is None else connected,
                                     dispatched=dispatched, exit_status=exit_status)

    def remaining() -> float:
        if cancel is not None and cancel.is_set():
            raise execution_error("interrupted")
        value = end - time.monotonic()
        if expired.is_set() or value <= 0:
            raise TimeoutError
        return value

    def expire() -> None:
        expired.set()
        if channel is not None:
            _close_channel(channel)

    def watch_cancel() -> None:
        while not watcher_done.wait(READ_POLL_SECONDS):
            if cancel is not None and cancel.is_set():
                if channel is None:
                    # 尚在等待 open_session 时没有 Channel 可关；该调用方拥有此连接。
                    try:
                        client.close()
                    except Exception as exc:
                        logger.warning("SSH cancellation cleanup failed: %s", type(exc).__name__)
                else:
                    _close_channel(channel)
                return

    def flush_output(*, final: bool = False) -> None:
        nonlocal output_finalized, callback_failed
        if on_output is None or output_finalized or callback_failed:
            return
        for name, buffer in (("stdout", stdout), ("stderr", stderr)):
            with output_lock:
                chunk = bytes(buffer[offsets[name]:])
                offsets[name] = len(buffer)
            value = decoders[name].decode(chunk, final=final)
            if value:
                # 只在执行调用线程通知消费者，避免数据库会话跨读取线程共享。
                try:
                    on_output(name, value)
                except Exception:
                    callback_failed = True
                    raise
        output_finalized = final

    def read_stream(recv: Callable[[int], bytes], output: bytearray) -> None:
        nonlocal output_size
        try:
            while True:
                chunk = recv(READ_SIZE)
                if not chunk:
                    return
                with output_lock:
                    available = MAX_OUTPUT_BYTES - output_size
                    accepted = chunk[:available]
                    if len(chunk) > available:
                        output_limited.set()
                    if accepted:
                        output.extend(accepted)
                        output_size += len(accepted)
                if output_limited.is_set():
                    _close_channel(channel)
                    return
        except Exception as exc:
            reader_errors.append(type(exc))
            _close_channel(channel)

    try:
        remaining()
        transport = client.get_transport()
        if transport is None or not transport.is_active():
            raise execution_error("connection", False)
        if cancel is not None:
            watcher = threading.Thread(target=watch_cancel, name="ssh-command-cancel", daemon=True)
            watcher.start()
        channel = transport.open_session(timeout=remaining())
        # exec_command and both blocking readers are released by closing this channel.
        timer = threading.Timer(remaining(), expire)
        timer.daemon = True
        timer.start()
        channel.settimeout(remaining())
        dispatched = True
        channel.exec_command("LC_ALL=C LANG=C bash -c " + shlex.quote(command))
        remaining()
        readers = [
            threading.Thread(target=read_stream, args=(channel.recv, stdout), daemon=True),
            threading.Thread(target=read_stream, args=(channel.recv_stderr, stderr), daemon=True),
        ]
        for reader in readers:
            reader.start()
        while any(reader.is_alive() for reader in readers):
            for reader in readers:
                reader.join(timeout=READ_POLL_SECONDS)
            flush_output()
            remaining()
        flush_output(final=True)
        remaining()
        if output_limited.is_set():
            raise execution_error("output_limit")
        if reader_errors:
            connected = _connected(client)
            code = "timeout" if issubclass(reader_errors[0], TimeoutError) else (
                "connection" if not connected or issubclass(reader_errors[0], (OSError, EOFError, paramiko.SSHException)) else "internal"
            )
            raise execution_error(code, connected)
        status = channel.recv_exit_status()
        if status >= 0:
            exit_status = status
        if not _connected(client):
            raise execution_error("connection", False)
        if exit_status is None:
            raise execution_error("unknown")
        result = CommandResult(stdout.decode("utf-8", errors="replace"), stderr.decode("utf-8", errors="replace"), status)
        timer.cancel()
        timer.join()
        remaining()
        return result
    except CommandExecutionError:
        raise
    except Exception as exc:
        code = "interrupted" if cancel is not None and cancel.is_set() else "timeout" if expired.is_set() or time.monotonic() >= end or isinstance(exc, TimeoutError) else (
            "connection" if not _connected(client) or isinstance(exc, (OSError, EOFError, paramiko.SSHException)) else "internal"
        )
        raise execution_error(code) from None
    finally:
        if timer is not None:
            timer.cancel()
            if timer is not threading.current_thread():
                timer.join()
        if channel is not None:
            _close_channel(channel)
        for reader in readers:
            if reader.ident is not None:
                reader.join(timeout=1)
        watcher_done.set()
        if watcher is not None:
            watcher.join(timeout=1)
        flush_output(final=True)
