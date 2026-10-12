from typing import Callable, Literal
from uuid import uuid4

from sqlalchemy import delete, func, select, text, update
from sqlalchemy.orm import Session, noload, selectinload

from ..inspection_models import InspectionCheckRun, InspectionHostRun, InspectionTask
from ..models import HostGroup, utc_now
from ..schemas.inspections import CheckPayload, InspectionConfig, InspectionInput
from ..services.inspection_checks import CHECK_TITLES

ACTIVE = ("queued", "running")
TERMINAL = ("completed", "partial", "failed", "interrupted")


def get_task(session: Session, task_id: str) -> InspectionTask | None:
    return session.get(InspectionTask, task_id)


def get_host_run(session: Session, run_id: str) -> InspectionHostRun | None:
    return session.get(InspectionHostRun, run_id)


def get_group_name(session: Session, group_id: int) -> str:
    name = session.scalar(select(HostGroup.name).where(HostGroup.id == group_id))
    if name is None:
        raise ValueError("资产分组不存在")
    return name


def create_task(session: Session, data: InspectionInput, snapshots: list[dict], config: InspectionConfig,
                before_commit: Callable[[InspectionTask], None] | None = None) -> InspectionTask:
    task = InspectionTask(id=str(uuid4()), name=data.name, status="queued", host_count=len(data.hosts),
                           check_ids=data.checks, config=config.model_dump(mode="json"), rule_version="1")
    for position, snapshot in enumerate(snapshots):
        run = InspectionHostRun(id=str(uuid4()), position=position, status="queued", **snapshot)
        run.checks = [InspectionCheckRun(position=index, check_id=check_id, title=CHECK_TITLES[check_id],
                                       status="queued", conclusion="unknown",
                                       payload=CheckPayload(conclusion="unknown").model_dump(mode="json"))
                      for index, check_id in enumerate(data.checks)]
        task.hosts.append(run)
    session.add(task)
    if before_commit is not None:
        # The proposal has a foreign key to the task; insert the task before updating that key.
        session.flush()
        before_commit(task)
    session.commit()
    session.refresh(task)
    return task


def interrupt_unsubmitted(session: Session, task_id: str, run_ids: list[str]) -> None:
    if not run_ids:
        return
    now = utc_now()
    session.execute(update(InspectionCheckRun).where(InspectionCheckRun.host_run_id.in_(run_ids),
                                                   InspectionCheckRun.status == "queued").values(
        status="interrupted", conclusion="unknown", error_code="dispatch_failed", finished_at=now))
    session.execute(update(InspectionHostRun).where(InspectionHostRun.id.in_(run_ids),
                                                  InspectionHostRun.status == "queued").values(
        status="interrupted", failure_code="dispatch_failed", finished_at=now))
    session.commit()
    summarize_task(session, task_id)


def page_tasks(session: Session, limit: int, offset: int) -> tuple[list[InspectionTask], int]:
    # 列表只读取任务摘要，不将所有检查结果随分页重复加载。
    query = select(InspectionTask).options(noload(InspectionTask.hosts)).order_by(
        InspectionTask.created_at.desc(), InspectionTask.id.desc()).limit(limit).offset(offset)
    total = session.scalar(select(func.count()).select_from(InspectionTask))
    return list(session.scalars(query)), total


def delete_task(session: Session, task_id: str) -> Literal["missing", "active", "deleted"]:
    session.rollback()
    session.execute(text("BEGIN IMMEDIATE"))
    try:
        status = session.scalar(select(InspectionTask.status).where(InspectionTask.id == task_id))
        if status is None:
            session.rollback()
            return "missing"
        if status not in TERMINAL:
            session.rollback()
            return "active"
        # SQLite foreign keys are enabled by storage; deleting the parent cascades to runs and checks.
        session.execute(delete(InspectionTask).where(InspectionTask.id == task_id))
        session.commit()
        return "deleted"
    except Exception:
        session.rollback()
        raise


def summarize_task(session: Session, task_id: str) -> None:
    session.rollback()
    # 各主机并发结束时串行汇总，避免较旧统计覆盖最新结果。
    session.execute(text("BEGIN IMMEDIATE"))
    task = session.get(InspectionTask, task_id, options=[selectinload(InspectionTask.hosts)])
    if task is None:
        raise ValueError("巡检任务不存在")
    statuses = [host.status for host in task.hosts]
    task.completed_hosts = sum(status in TERMINAL for status in statuses)
    task.failed_hosts = sum(status in ("partial", "failed", "interrupted") for status in statuses)
    if any(status in ACTIVE for status in statuses):
        task.status = "running" if any(status != "queued" for status in statuses) else "queued"
    elif all(status == "completed" for status in statuses):
        task.status = "completed"
    elif all(status == "interrupted" for status in statuses):
        task.status = "interrupted"
    elif all(status == "failed" for status in statuses):
        task.status = "failed"
    else:
        task.status = "partial"
    if task.started_at is None:
        starts = [host.started_at for host in task.hosts if host.started_at is not None]
        if starts:
            task.started_at = min(starts)
    if task.status in TERMINAL:
        task.finished_at = utc_now()
    session.commit()


def interrupt_unfinished(session: Session) -> None:
    session.execute(update(InspectionCheckRun).where(InspectionCheckRun.status.in_(ACTIVE)).values(
        status="interrupted", conclusion="unknown", error_code="interrupted", finished_at=utc_now()))
    session.execute(update(InspectionHostRun).where(InspectionHostRun.status.in_(ACTIVE)).values(
        status="interrupted", failure_code="interrupted", finished_at=utc_now()))
    ids = list(session.scalars(select(InspectionTask.id).where(InspectionTask.status.in_(ACTIVE))))
    session.commit()
    for task_id in ids:
        summarize_task(session, task_id)
