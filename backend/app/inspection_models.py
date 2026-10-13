from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .models import Base, utc_now


class InspectionTask(Base):
    __tablename__ = "inspection_tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str]
    status: Mapped[str] = mapped_column(default="queued")
    check_ids: Mapped[list[str]] = mapped_column(JSON)
    config: Mapped[dict] = mapped_column(JSON)
    rule_version: Mapped[str] = mapped_column(default="1")
    host_count: Mapped[int]
    completed_hosts: Mapped[int] = mapped_column(default=0)
    failed_hosts: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(default=utc_now, index=True)
    started_at: Mapped[datetime | None]
    finished_at: Mapped[datetime | None]
    hosts: Mapped[list[InspectionHostRun]] = relationship(order_by="InspectionHostRun.position", lazy="selectin")


class InspectionHostRun(Base):
    __tablename__ = "inspection_host_runs"
    __table_args__ = (UniqueConstraint("task_id", "host_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    task_id: Mapped[str] = mapped_column(ForeignKey("inspection_tasks.id", ondelete="CASCADE"), index=True)
    position: Mapped[int]
    host_id: Mapped[int]
    host_name: Mapped[str]
    address: Mapped[str]
    port: Mapped[int]
    username: Mapped[str]
    group_name: Mapped[str]
    asset_snapshot: Mapped[str]
    status: Mapped[str] = mapped_column(default="queued")
    failure_code: Mapped[str | None]
    started_at: Mapped[datetime | None]
    finished_at: Mapped[datetime | None]
    checks: Mapped[list[InspectionCheckRun]] = relationship(order_by="InspectionCheckRun.position", lazy="selectin")


class InspectionCheckRun(Base):
    __tablename__ = "inspection_check_runs"
    __table_args__ = (UniqueConstraint("host_run_id", "check_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    host_run_id: Mapped[str] = mapped_column(ForeignKey("inspection_host_runs.id", ondelete="CASCADE"), index=True)
    position: Mapped[int]
    check_id: Mapped[str]
    title: Mapped[str]
    status: Mapped[str] = mapped_column(default="queued")
    conclusion: Mapped[str] = mapped_column(default="unknown")
    payload: Mapped[dict] = mapped_column(JSON)
    error_code: Mapped[str | None]
    started_at: Mapped[datetime | None]
    finished_at: Mapped[datetime | None]


class InspectionAIReport(Base):
    __tablename__ = "inspection_ai_reports"

    task_id: Mapped[str] = mapped_column(ForeignKey("inspection_tasks.id", ondelete="CASCADE"), primary_key=True)
    status: Mapped[str]
    generation_id: Mapped[str] = mapped_column(String(36))
    model_name: Mapped[str | None]
    model_version: Mapped[int | None]
    started_at: Mapped[datetime | None]
    finished_at: Mapped[datetime | None]
    error_code: Mapped[str | None]
    report: Mapped[dict | None] = mapped_column(JSON)
