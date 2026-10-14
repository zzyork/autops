import base64
import hashlib
import io
import socket
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from collections.abc import Iterator

import paramiko
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519
from .ssh_network import NetworkDeadline, open_socket

CONNECTION_TIMEOUT_SECONDS = 30
PHASE_TIMEOUT_SECONDS = 10
MAX_FAILURE_MESSAGE_LENGTH = 1000
FAILURE_MESSAGE_TRUNCATION_MARKER = "\n[错误内容已截断]"


@dataclass(frozen=True)
class SSHEndpoint:
    target_type: str
    target_id: int
    address: str
    port: int
    username: str
    password: str | None = field(default=None, repr=False)
    private_key: str | None = field(default=None, repr=False)
    trusted_key: str | None = None


class HostKeyRequired(Exception):
    def __init__(self, endpoint: SSHEndpoint, key: paramiko.PKey):
        self.endpoint = endpoint
        self.public_key = key.get_base64()
        self.key_type = key.get_name()
        self.fingerprint = fingerprint(key.asbytes())
        super().__init__("服务器身份需要确认")


class SSHConnectionError(Exception):
    def __init__(self, code: str, stage: str, message: str):
        self.code = code
        self.stage = stage
        self.message = message
        super().__init__(message)


def failure_message(cause: Exception, *endpoints: SSHEndpoint) -> str:
    """使用原始异常文本，过滤已知凭据及控制字符，超长时标记截断。"""
    message = str(cause) or type(cause).__name__
    for endpoint in endpoints:
        for secret in (endpoint.password, endpoint.private_key):
            if secret:
                message = message.replace(secret, "[REDACTED]")
                message = message.replace(repr(secret)[1:-1], "[REDACTED]")
                if secret == endpoint.private_key:
                    for line in secret.splitlines():
                        if line.strip():
                            message = message.replace(line.strip(), "[REDACTED]")
    message = "".join(character for character in message if character.isprintable() or character in "\n\t")
    if len(message) > MAX_FAILURE_MESSAGE_LENGTH:
        message = message[:MAX_FAILURE_MESSAGE_LENGTH - len(FAILURE_MESSAGE_TRUNCATION_MARKER)] + FAILURE_MESSAGE_TRUNCATION_MARKER
    return message


def connection_error(code: str, stage: str, endpoint: SSHEndpoint, cause: Exception) -> SSHConnectionError:
    return SSHConnectionError(code, stage, failure_message(cause, endpoint))


def fingerprint(raw: bytes) -> str:
    return "SHA256:" + base64.b64encode(hashlib.sha256(raw).digest()).decode().rstrip("=")


class VerifyHostKey(paramiko.MissingHostKeyPolicy):
    def __init__(self, endpoint: SSHEndpoint):
        self.endpoint = endpoint

    def missing_host_key(self, client: paramiko.SSHClient, hostname: str, key: paramiko.PKey) -> None:
        # 未校验服务器身份之前，Paramiko 不得进入用户认证阶段。
        if self.endpoint.trusted_key != key.get_base64():
            raise HostKeyRequired(self.endpoint, key)


def load_private_key(content: str) -> paramiko.PKey:
    raw = content.encode()
    loader = serialization.load_ssh_private_key if raw.lstrip().startswith(b"-----BEGIN OPENSSH") else serialization.load_pem_private_key
    key = loader(raw, password=None)
    # 资产允许 PKCS8；Paramiko 文件解析器使用 OpenSSH 或传统 PEM。
    form = serialization.PrivateFormat.OpenSSH if isinstance(key, ed25519.Ed25519PrivateKey) else serialization.PrivateFormat.TraditionalOpenSSL
    normalized = key.private_bytes(serialization.Encoding.PEM, form, serialization.NoEncryption()).decode()
    for key_class in (paramiko.Ed25519Key, paramiko.ECDSAKey, paramiko.RSAKey):
        try:
            return key_class.from_private_key(io.StringIO(normalized))
        except paramiko.SSHException:
            continue
    raise ValueError("私钥类型不受支持")


def _connect(endpoint: SSHEndpoint, deadline: NetworkDeadline, stage: str,
             sock: paramiko.Channel | None = None) -> paramiko.SSHClient:
    client = paramiko.SSHClient()
    try:
        client.set_missing_host_key_policy(VerifyHostKey(endpoint))
        pkey = load_private_key(endpoint.private_key) if endpoint.private_key is not None else None
    except TimeoutError as exc:
        raise connection_error("timeout", stage, endpoint, exc) from exc
    except (ValueError, TypeError, paramiko.SSHException) as exc:
        raise connection_error("configuration", stage, endpoint, exc) from exc
    try:
        try:
            if sock is None:
                sock = open_socket(endpoint.address, endpoint.port, deadline, PHASE_TIMEOUT_SECONDS)
        finally:
            # 逆序清理时先停止 SSH Transport，再关闭其底层 Socket，避免接收线程报 10038。
            # 建连失败也登记客户端；超时后 register 会立即清理并阻止继续握手。
            deadline.register(client.close)
        remaining = deadline.remaining()
        client.connect(
            hostname=endpoint.address, port=endpoint.port, username=endpoint.username,
            password=endpoint.password, pkey=pkey, sock=sock,
            allow_agent=False, look_for_keys=False,
            timeout=min(PHASE_TIMEOUT_SECONDS, remaining),
            banner_timeout=min(PHASE_TIMEOUT_SECONDS, remaining),
            # 认证等待统一受整体截止时间控制，避免 Paramiko 将较早的阶段超时归为认证拒绝。
            auth_timeout=remaining,
            channel_timeout=min(PHASE_TIMEOUT_SECONDS, remaining),
        )
        transport = client.get_transport()
        if transport is None or not transport.is_authenticated():
            raise connection_error("connection", stage, endpoint, paramiko.SSHException("SSH transport is not authenticated"))
        deadline.remaining()
        return client
    except HostKeyRequired:
        raise
    except paramiko.AuthenticationException as exc:
        expired = deadline.expired.is_set() or time.monotonic() >= deadline.end
        raise connection_error("timeout" if expired else "authentication", stage, endpoint, exc) from exc
    except (TimeoutError, socket.timeout) as exc:
        raise connection_error("timeout", stage, endpoint, exc) from exc
    except (OSError, EOFError, paramiko.SSHException) as exc:
        raise connection_error("timeout" if deadline.expired.is_set() else "connection", stage, endpoint, exc) from exc


@contextmanager
def open_ssh_connection(target: SSHEndpoint, jump: SSHEndpoint | None = None, *, timeout_seconds: float | None = None,
                        deadline: NetworkDeadline | None = None) -> Iterator[paramiko.SSHClient]:
    seconds = CONNECTION_TIMEOUT_SECONDS if timeout_seconds is None else min(CONNECTION_TIMEOUT_SECONDS, timeout_seconds)
    if seconds <= 0:
        raise ValueError("连接时限必须大于零")
    if deadline is None:
        deadline = NetworkDeadline(seconds)
    try:
        tunnel = None
        if jump is not None:
            proxy = _connect(jump, deadline, "jump_host")
            transport = proxy.get_transport()
            if transport is None:
                raise connection_error("connection", "jump_host", jump, paramiko.SSHException("Jump host SSH transport is unavailable"))
            try:
                remaining = deadline.remaining()
                tunnel = transport.open_channel("direct-tcpip", (target.address, target.port), ("127.0.0.1", 0), timeout=min(PHASE_TIMEOUT_SECONDS, remaining))
                deadline.register(tunnel.close)
            except (TimeoutError, socket.timeout) as exc:
                raise connection_error("timeout", "jump_host", jump, exc) from exc
            except (OSError, EOFError, paramiko.SSHException) as exc:
                raise connection_error("timeout" if deadline.expired.is_set() else "connection", "jump_host", jump, exc) from exc
        client = _connect(target, deadline, "target", tunnel)
        try:
            deadline.stop_timer()
        except TimeoutError as exc:
            raise connection_error("timeout", "target", target, exc) from exc
        yield client
    finally:
        deadline.close()
        if deadline.timer is not threading.current_thread():
            deadline.timer.join()


def probe_host_key(target: SSHEndpoint, proxy: SSHEndpoint | None = None) -> tuple[SSHEndpoint, paramiko.PKey]:
    """Perform key exchange only; target authentication is never attempted."""
    deadline = NetworkDeadline(CONNECTION_TIMEOUT_SECONDS)
    stage = "jump_host" if proxy is not None and proxy.trusted_key is None else "target"
    endpoint = proxy if stage == "jump_host" else target
    assert endpoint is not None
    try:
        sock = None
        if proxy is not None and proxy.trusted_key is not None:
            client = _connect(proxy, deadline, "jump_host")
            transport = client.get_transport()
            if transport is None:
                raise SSHConnectionError("connection", "jump_host", "跳板机连接不可用")
            remaining = deadline.remaining()
            sock = transport.open_channel("direct-tcpip", (target.address, target.port),
                                          ("127.0.0.1", 0), timeout=min(PHASE_TIMEOUT_SECONDS, remaining))
            deadline.register(sock.close)
        if sock is None:
            sock = open_socket(endpoint.address, endpoint.port, deadline, PHASE_TIMEOUT_SECONDS)
        transport = paramiko.Transport(sock)
        deadline.register(transport.close)
        transport.start_client(timeout=min(PHASE_TIMEOUT_SECONDS, deadline.remaining()))
        key = transport.get_remote_server_key()
        deadline.remaining()
        return endpoint, key
    except HostKeyRequired:
        raise
    except (TimeoutError, socket.timeout) as exc:
        raise connection_error("timeout", stage, endpoint, exc) from exc
    except (OSError, EOFError, paramiko.SSHException) as exc:
        raise connection_error("timeout" if deadline.expired.is_set() else "connection", stage, endpoint, exc) from exc
    finally:
        deadline.close()
        if deadline.timer is not threading.current_thread():
            deadline.timer.join()
