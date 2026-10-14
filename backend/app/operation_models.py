from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .models import Base, utc_now


class OperationTask(Base):
    __tablename__ = "operation_tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    module: Mapped[str]
    action: Mapped[str]
    title: Mapped[str]
    status: Mapped[str] = mapped_column(default="planned")
    params: Mapped[dict] = mapped_column(JSON)
    sudo: Mapped[bool]
    destructive: Mapped[bool]
    preflight_command: Mapped[str]
    verify_command: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(default=utc_now, index=True)
    confirmed_at: Mapped[datetime | None]
    completed_at: Mapped[datetime | None]
    hosts: Mapped[list[OperationHost]] = relationship(order_by="OperationHost.position", lazy="selectin")


class OperationHost(Base):
    __tablename__ = "operation_hosts"
    __table_args__ = (UniqueConstraint("task_id", "host_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    task_id: Mapped[str] = mapped_column(ForeignKey("operation_tasks.id", ondelete="CASCADE"), index=True)
    position: Mapped[int]
    host_id: Mapped[int]
    host_name: Mapped[str]
    address: Mapped[str]
    asset_snapshot: Mapped[str]
    use_sudo: Mapped[bool]
    preflight_stdout: Mapped[str]
    preflight_hash: Mapped[str]
    status: Mapped[str] = mapped_column(default="planned")
    before: Mapped[str | None]
    after: Mapped[str | None]
    error: Mapped[str | None]
    resolution_note: Mapped[str | None]
    resolved_at: Mapped[datetime | None]
    steps: Mapped[list[OperationStepRun]] = relationship(order_by="OperationStepRun.position", lazy="selectin")


class OperationStepRun(Base):
    __tablename__ = "operation_steps"
    __table_args__ = (UniqueConstraint("host_run_id", "position"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    host_run_id: Mapped[str] = mapped_column(ForeignKey("operation_hosts.id", ondelete="CASCADE"), index=True)
    position: Mapped[int]
    title: Mapped[str]
    command: Mapped[str]
    timeout_seconds: Mapped[float]
    status: Mapped[str] = mapped_column(default="pending")
    stdout: Mapped[str | None]
    stderr: Mapped[str | None]
    exit_status: Mapped[int | None]
