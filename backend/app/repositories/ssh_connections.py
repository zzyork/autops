from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ..connection_models import ConnectionTest, KnownHostKey
from ..models import Host, JumpHost, SSHKey, utc_now


def get_asset(session: Session, target_type: str, target_id: int) -> Host | JumpHost | None:
    return session.get(Host if target_type == "host" else JumpHost, target_id)


def get_key(session: Session, key_id: int) -> SSHKey | None:
    return session.get(SSHKey, key_id)


def get_trust(session: Session, target_type: str, target_id: int, address: str, port: int) -> KnownHostKey | None:
    return session.scalar(select(KnownHostKey).where(
        KnownHostKey.target_type == target_type, KnownHostKey.target_id == target_id,
        KnownHostKey.address == address, KnownHostKey.port == port,
    ))


def list_tests(session: Session, target_type: str, target_id: int) -> list[ConnectionTest]:
    query = select(ConnectionTest).where(
        ConnectionTest.target_type == target_type, ConnectionTest.target_id == target_id,
    )
    asset = get_asset(session, target_type, target_id)
    if asset is not None:
        # SQLite 可能复用已删除的资产 ID；新资产不能继承旧资产的测试历史。
        query = query.where(ConnectionTest.created_at >= asset.created_at)
    return list(session.scalars(query.order_by(ConnectionTest.created_at.desc(), ConnectionTest.id.desc()).limit(20)))


def interrupt_tests(session: Session) -> None:
    session.execute(update(ConnectionTest).where(ConnectionTest.status.in_(("queued", "running"))).values(
        status="interrupted", finished_at=utc_now(), version=ConnectionTest.version + 1,
    ))
    session.commit()
