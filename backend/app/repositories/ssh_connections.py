from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ..connection_models import KnownHostKey
from ..models import Host, JumpHost, SSHKey


def get_asset(session: Session, target_type: str, target_id: int) -> Host | JumpHost | None:
    return session.get(Host if target_type == "host" else JumpHost, target_id)


def get_key(session: Session, key_id: int) -> SSHKey | None:
    return session.get(SSHKey, key_id)


def get_trust(session: Session, target_type: str, target_id: int, address: str, port: int) -> KnownHostKey | None:
    return session.scalar(select(KnownHostKey).where(
        KnownHostKey.target_type == target_type, KnownHostKey.target_id == target_id,
        KnownHostKey.address == address, KnownHostKey.port == port,
    ))


def set_host_status(session: Session, host_id: int, created_at, version: int, status: str,
                    expected_status: str | None = None) -> bool:
    query = update(Host).where(
        Host.id == host_id, Host.created_at == created_at, Host.version == version,
    )
    if expected_status is not None:
        query = query.where(Host.connection_status == expected_status)
    result = session.execute(query.values(
        connection_status=status, updated_at=Host.updated_at).execution_options(synchronize_session=False))
    return result.rowcount == 1
