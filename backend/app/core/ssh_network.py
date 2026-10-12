import ipaddress
import logging
import queue
import socket
import threading
import time
from collections.abc import Callable

logger = logging.getLogger(__name__)
DNS_SLOTS = threading.BoundedSemaphore(4)


class NetworkDeadline:
    """总时限覆盖 DNS、TCP、握手、认证和隧道；到期主动关闭网络资源。"""
    def __init__(self, seconds: float):
        self.end = time.monotonic() + seconds
        self.expired = threading.Event()
        self.lock = threading.Lock()
        self.closers: list[Callable[[], None]] = []
        self.timer = threading.Timer(seconds, self._expire)
        self.timer.daemon = True
        self.timer.start()

    def remaining(self) -> float:
        value = self.end - time.monotonic()
        if self.expired.is_set() or value <= 0:
            raise TimeoutError("SSH 连接总时限已到")
        return value

    def register(self, closer: Callable[[], None]) -> None:
        with self.lock:
            if not self.expired.is_set():
                self.closers.append(closer)
                return
        self._close_one(closer)
        raise TimeoutError("SSH 连接总时限已到")

    @staticmethod
    def _close_one(closer: Callable[[], None]) -> None:
        try:
            closer()
        except Exception as exc:
            logger.warning("SSH resource cleanup failed: %s", type(exc).__name__)

    def _expire(self) -> None:
        self.expired.set()
        self.close()

    def stop_timer(self) -> None:
        self.timer.cancel()
        self.timer.join()
        self.remaining()

    def close(self) -> None:
        self.timer.cancel()
        with self.lock:
            closers, self.closers = self.closers, []
        for closer in reversed(closers):
            self._close_one(closer)


def _resolve(address: str, port: int, deadline: NetworkDeadline) -> list[tuple]:
    try:
        parsed = ipaddress.ip_address(address)
    except ValueError:
        parsed = None
    if parsed is not None:
        family = socket.AF_INET6 if parsed.version == 6 else socket.AF_INET
        return socket.getaddrinfo(address, port, family, socket.SOCK_STREAM, flags=socket.AI_NUMERICHOST)
    if not DNS_SLOTS.acquire(timeout=deadline.remaining()):
        raise TimeoutError("DNS 等待超时")
    results: queue.Queue = queue.Queue(maxsize=1)

    def lookup() -> None:
        try:
            results.put(socket.getaddrinfo(address, port, type=socket.SOCK_STREAM))
        except Exception as exc:
            results.put(exc)
        finally:
            DNS_SLOTS.release()

    # 系统解析无法取消；至多四个无凭据的守护线程，不阻塞任务或应用关闭。
    threading.Thread(target=lookup, name="ssh-dns", daemon=True).start()
    try:
        result = results.get(timeout=deadline.remaining())
    except queue.Empty:
        raise TimeoutError("DNS 查询超时") from None
    if isinstance(result, Exception):
        raise result
    return result


def open_socket(address: str, port: int, deadline: NetworkDeadline, phase_seconds: float) -> socket.socket:
    addresses = _resolve(address, port, deadline)
    errors: list[OSError] = []
    for family, socktype, protocol, _, sockaddr in addresses:
        connection = socket.socket(family, socktype, protocol)
        deadline.register(connection.close)
        try:
            connection.settimeout(min(phase_seconds, deadline.remaining()))
            connection.connect(sockaddr)
            deadline.remaining()
            return connection
        except OSError as exc:
            connection.close()
            errors.append(exc)
            deadline.remaining()
    if errors:
        raise errors[-1]
    raise OSError("未解析出可用地址")
