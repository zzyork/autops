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
    def __init__(self, code: str, stage: str):
        self.code = code
        self.stage = stage
        super().__init__(code)


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


def _connect(endpoint: SSHEndpoint, deadline: NetworkDeadline, stage: str, sock: paramiko.Channel | None = None) -> paramiko.SSHClient:
    client = paramiko.SSHClient()
    try:
        deadline.register(client.close)
        client.set_missing_host_key_policy(VerifyHostKey(endpoint))
        pkey = load_private_key(endpoint.private_key) if endpoint.private_key is not None else None
    except TimeoutError as exc:
        raise SSHConnectionError("timeout", stage) from exc
    except (ValueError, TypeError, paramiko.SSHException) as exc:
        raise SSHConnectionError("configuration", stage) from exc
    try:
        if sock is None:
            sock = open_socket(endpoint.address, endpoint.port, deadline, PHASE_TIMEOUT_SECONDS)
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
            raise SSHConnectionError("connection", stage)
        deadline.remaining()
        return client
    except HostKeyRequired:
        raise
    except paramiko.AuthenticationException as exc:
        expired = deadline.expired.is_set() or time.monotonic() >= deadline.end
        raise SSHConnectionError("timeout" if expired else "authentication", stage) from exc
    except (TimeoutError, socket.timeout) as exc:
        raise SSHConnectionError("timeout", stage) from exc
    except (OSError, EOFError, paramiko.SSHException) as exc:
        raise SSHConnectionError("timeout" if deadline.expired.is_set() else "connection", stage) from exc


@contextmanager
def open_ssh_connection(target: SSHEndpoint, jump: SSHEndpoint | None = None) -> Iterator[paramiko.SSHClient]:
    deadline = NetworkDeadline(CONNECTION_TIMEOUT_SECONDS)
    try:
        tunnel = None
        if jump is not None:
            proxy = _connect(jump, deadline, "jump_host")
            transport = proxy.get_transport()
            if transport is None:
                raise SSHConnectionError("connection", "jump_host")
            try:
                remaining = deadline.remaining()
                tunnel = transport.open_channel("direct-tcpip", (target.address, target.port), ("127.0.0.1", 0), timeout=min(PHASE_TIMEOUT_SECONDS, remaining))
                deadline.register(tunnel.close)
            except (TimeoutError, socket.timeout) as exc:
                raise SSHConnectionError("timeout", "jump_host") from exc
            except (OSError, EOFError, paramiko.SSHException) as exc:
                raise SSHConnectionError("timeout" if deadline.expired.is_set() else "connection", "jump_host") from exc
        client = _connect(target, deadline, "target", tunnel)
        try:
            deadline.stop_timer()
        except TimeoutError as exc:
            raise SSHConnectionError("timeout", "target") from exc
        yield client
    finally:
        deadline.close()
        if deadline.timer is not threading.current_thread():
            deadline.timer.join()
