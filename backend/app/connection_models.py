from datetime import datetime

from sqlalchemy import JSON, String, UniqueConstraint, ForeignKey, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .models import Base, utc_now


class KnownHostKey(Base):
    __tablename__ = "known_host_keys"
    __table_args__ = (
        UniqueConstraint("target_type", "target_id", "address", "port"),
        CheckConstraint("(target_type = 'host' AND host_id = target_id AND jump_host_id IS NULL) OR (target_type = 'jump_host' AND jump_host_id = target_id AND host_id IS NULL)"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    target_type: Mapped[str] = mapped_column(String(16))
    target_id: Mapped[int]
    host_id: Mapped[int | None] = mapped_column(ForeignKey("hosts.id", ondelete="CASCADE"))
    jump_host_id: Mapped[int | None] = mapped_column(ForeignKey("jump_hosts.id", ondelete="CASCADE"))
    address: Mapped[str]
    port: Mapped[int]
    key_type: Mapped[str]
    public_key: Mapped[str]
    fingerprint: Mapped[str]
    updated_at: Mapped[datetime] = mapped_column(default=utc_now, onupdate=utc_now)
    version: Mapped[int] = mapped_column(default=1)
    __mapper_args__ = {"version_id_col": version}


class ConnectionTest(Base):
    __tablename__ = "ssh_connection_tests"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    target_type: Mapped[str] = mapped_column(String(16), index=True)
    target_id: Mapped[int] = mapped_column(index=True)
    target_name: Mapped[str]
    address: Mapped[str]
    port: Mapped[int]
    username: Mapped[str]
    via_jump_host: Mapped[str | None]
    snapshot: Mapped[str]
    host_key_policy: Mapped[str] = mapped_column(String(16), default="accept_new")
    auto_trusted_keys: Mapped[list[dict[str, str | int | None]]] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(default="queued")
    stage: Mapped[str | None]
    failure_code: Mapped[str | None]
    failure_message: Mapped[str | None]
    challenge: Mapped[dict | None] = mapped_column(JSON)
    candidate_key: Mapped[str | None]
    created_at: Mapped[datetime] = mapped_column(default=utc_now)
    started_at: Mapped[datetime | None]
    finished_at: Mapped[datetime | None]
    duration_ms: Mapped[int | None]
    version: Mapped[int] = mapped_column(default=1)
    __mapper_args__ = {"version_id_col": version}
