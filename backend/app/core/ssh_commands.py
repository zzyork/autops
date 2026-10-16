import logging
import shlex
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass

import paramiko

logger = logging.getLogger(__name__)
MAX_OUTPUT_BYTES = 256 * 1024
READ_SIZE = 32 * 1024
ERROR_MESSAGES = {
    "timeout": "SSH 命令执行超时",
    "connection": "SSH 连接已断开",
    "output_limit": "SSH 命令输出超出限制",
    "internal": "SSH 命令执行失败",
}


@dataclass(frozen=True)
class CommandResult:
    stdout: str
    stderr: str
    exit_status: int


class CommandExecutionError(Exception):
    def __init__(self, code: str, connected: bool):
        self.code = code
        self.connected = connected
        super().__init__(ERROR_MESSAGES[code])


class OutputObservationError(Exception):
    pass


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
    deadline: float | None = None,
    on_output: Callable[[str, bytes], None] | None = None,
    flush_output: Callable[[], None] | None = None,
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
    observation_errors: list[Exception] = []

    def remaining() -> float:
        value = end - time.monotonic()
        if expired.is_set() or value <= 0:
            raise TimeoutError
        return value

    def expire() -> None:
        expired.set()
        if channel is not None:
            _close_channel(channel)

    def read_stream(recv: Callable[[int], bytes], output: bytearray, name: str) -> None:
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
                        if on_output is not None:
                            try:
                                on_output(name, accepted)
                            except Exception as exc:
                                observation_errors.append(exc)
                                _close_channel(channel)
                                return
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
            raise CommandExecutionError("connection", False)
        channel = transport.open_session(timeout=remaining())
        # exec_command and both blocking readers are released by closing this channel.
        timer = threading.Timer(remaining(), expire)
        timer.daemon = True
        timer.start()
        channel.settimeout(remaining())
        channel.exec_command("LC_ALL=C LANG=C bash -c " + shlex.quote(command))
        remaining()
        readers = [
            threading.Thread(target=read_stream, args=(channel.recv, stdout, "stdout"), daemon=True),
            threading.Thread(target=read_stream, args=(channel.recv_stderr, stderr, "stderr"), daemon=True),
        ]
        for reader in readers:
            reader.start()
        while any(reader.is_alive() for reader in readers):
            for reader in readers:
                reader.join(timeout=0.25)
            if observation_errors:
                _close_channel(channel)
            if flush_output is not None:
                try:
                    flush_output()
                except Exception as exc:
                    _close_channel(channel)
                    for reader in readers:
                        reader.join()
                    raise OutputObservationError from exc
        if flush_output is not None:
            try:
                flush_output()
            except Exception as exc:
                raise OutputObservationError from exc
        if observation_errors:
            raise OutputObservationError from observation_errors[0]
        remaining()
        if output_limited.is_set():
            raise CommandExecutionError("output_limit", _connected(client))
        if reader_errors:
            connected = _connected(client)
            code = "timeout" if issubclass(reader_errors[0], TimeoutError) else (
                "connection" if not connected or issubclass(reader_errors[0], (OSError, EOFError, paramiko.SSHException)) else "internal"
            )
            raise CommandExecutionError(code, connected)
        status = channel.recv_exit_status()
        if not _connected(client):
            raise CommandExecutionError("connection", False)
        result = CommandResult(stdout.decode("utf-8", errors="replace"), stderr.decode("utf-8", errors="replace"), status)
        timer.cancel()
        timer.join()
        remaining()
        return result
    except CommandExecutionError:
        raise
    except OutputObservationError:
        raise
    except Exception as exc:
        code = "timeout" if expired.is_set() or time.monotonic() >= end or isinstance(exc, TimeoutError) else (
            "connection" if not _connected(client) or isinstance(exc, (OSError, EOFError, paramiko.SSHException)) else "internal"
        )
        raise CommandExecutionError(code, _connected(client)) from None
    finally:
        if timer is not None:
            timer.cancel()
            if timer is not threading.current_thread():
                timer.join()
        if channel is not None:
            _close_channel(channel)
