from datetime import datetime

from sqlalchemy import ForeignKey, Index, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .models import Base, utc_now


class SSHExecutionRequest(Base):
    __tablename__ = "ssh_execution_requests"

    # 删除业务记录后仍保留已用标识，防止迟到的创建请求再次派发远端命令。
    id: Mapped[str] = mapped_column(String(36), primary_key=True)


class SSHExecution(Base):
    __tablename__ = "ssh_executions"
    __table_args__ = (Index("ix_ssh_executions_host_status", "host_id", "status"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    digest: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(100))
    host_id: Mapped[int]
    host_name: Mapped[str]
    address: Mapped[str]
    asset_snapshot: Mapped[str] = mapped_column(String(64))
    timeout_seconds: Mapped[int]
    step_count: Mapped[int]
    status: Mapped[str] = mapped_column(String(20))
    error_code: Mapped[str | None] = mapped_column(String(40))
    sequence: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(default=utc_now, index=True)
    started_at: Mapped[datetime | None]
    finished_at: Mapped[datetime | None]


class SSHExecutionStep(Base):
    __tablename__ = "ssh_execution_steps"
    __table_args__ = (UniqueConstraint("execution_id", "position"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    execution_id: Mapped[str] = mapped_column(ForeignKey("ssh_executions.id", ondelete="CASCADE"), index=True)
    position: Mapped[int]
    name: Mapped[str] = mapped_column(String(100))
    command: Mapped[str]
    success_exit_codes: Mapped[list[int]] = mapped_column(JSON)
    timeout_seconds: Mapped[int]
    status: Mapped[str] = mapped_column(String(20))
    exit_status: Mapped[int | None]
    error_code: Mapped[str | None] = mapped_column(String(40))
    started_at: Mapped[datetime | None]
    finished_at: Mapped[datetime | None]


class SSHExecutionEvent(Base):
    __tablename__ = "ssh_execution_events"
    __table_args__ = (UniqueConstraint("execution_id", "sequence"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    execution_id: Mapped[str] = mapped_column(ForeignKey("ssh_executions.id", ondelete="CASCADE"), index=True)
    sequence: Mapped[int]
    kind: Mapped[str] = mapped_column(String(10))
    payload: Mapped[dict] = mapped_column(JSON)
