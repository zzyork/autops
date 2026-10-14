import hashlib
import json
from dataclasses import dataclass

from cryptography.fernet import Fernet, InvalidToken
from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..core.ssh import SSHEndpoint
from ..models import Host, JumpHost
from ..repositories.ssh_connections import get_asset, get_key, get_trust
from ..schemas.assets import validate_network_address


@dataclass(frozen=True)
class ConnectionPlan:
    target: SSHEndpoint
    jump: SSHEndpoint | None
    name: str
    jump_name: str | None
    version: int
    snapshot: str


def resolve_plan(session: Session, cipher: Fernet, target_type: str, target_id: int, *,
                 identity_probe: bool = False) -> ConnectionPlan:
    record = get_asset(session, target_type, target_id)
    if record is None:
        raise HTTPException(404, "资产不存在")
    versions: list[tuple] = []

    def endpoint(asset: Host | JumpHost, kind: str) -> SSHEndpoint:
        address = asset.vip or asset.address if isinstance(asset, Host) else asset.address
        try:
            address = validate_network_address(address)
            if not 1 <= asset.port <= 65535 or not asset.username.strip():
                raise ValueError("连接配置无效")
            password = None
            private_key = None
            versions.append((kind, asset.id, asset.version, asset.created_at.isoformat()))
            need_credentials = not identity_probe or (
                isinstance(record, Host) and kind == "jump_host" and
                get_trust(session, kind, asset.id, address, asset.port) is not None
            )
            if asset.auth_type == "password":
                if asset.password_encrypted is None:
                    raise ValueError("缺少密码")
                if need_credentials:
                    password = cipher.decrypt(asset.password_encrypted.encode()).decode()
            elif asset.auth_type == "key":
                key = get_key(session, asset.ssh_key_id) if asset.ssh_key_id is not None else None
                if key is None:
                    raise ValueError("缺少密钥")
                versions.append(("ssh_key", key.id, key.version, key.created_at.isoformat()))
                if need_credentials:
                    private_key = cipher.decrypt(key.private_key_encrypted.encode()).decode()
            else:
                raise ValueError("认证方式无效")
        except (ValueError, InvalidToken, UnicodeError):
            raise HTTPException(422, "资产连接配置或凭据无效") from None
        known = get_trust(session, kind, asset.id, address, asset.port)
        return SSHEndpoint(kind, asset.id, address, asset.port, asset.username, password, private_key, known.public_key if known else None)

    target = endpoint(record, target_type)
    jump = None
    jump_name = None
    if isinstance(record, Host) and record.jump_host_id is not None:
        proxy = get_asset(session, "jump_host", record.jump_host_id)
        if not isinstance(proxy, JumpHost):
            raise HTTPException(422, "关联跳板机不存在")
        jump = endpoint(proxy, "jump_host")
        jump_name = proxy.name
    snapshot = hashlib.sha256(json.dumps(versions).encode()).hexdigest()
    return ConnectionPlan(target, jump, record.name, jump_name, record.version, snapshot)
