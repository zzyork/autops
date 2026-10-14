from datetime import timedelta, timezone
from uuid import uuid4

from sqlalchemy import select, text, update
from sqlalchemy.orm import Session

from ..models import utc_now
from ..operation_models import OperationHost, OperationStepRun, OperationTask
from ..schemas.operations import PlanInput
from ..services.operation_commands.common import OperationSpec

PLAN_LIFETIME = timedelta(minutes=30)


def get_task(session: Session, task_id: str) -> OperationTask | None:
    return session.get(OperationTask, task_id)


def create_plan(session: Session, data: PlanInput, params: dict, spec: OperationSpec, snapshots: list[dict]) -> OperationTask:
    task = OperationTask(id=str(uuid4()), module=data.module, action=data.action, title=spec.title,
                         params=params, sudo=data.sudo, destructive=spec.destructive, preflight_command=spec.preflight,
                         verify_command=spec.verify, status="planned")
    for position, snapshot in enumerate(snapshots):
        host = OperationHost(id=str(uuid4()), position=position, status="planned", **snapshot)
        host.steps = [OperationStepRun(position=index, title=step.title, command=step.command,
                                       timeout_seconds=step.timeout_seconds, status="pending")
                      for index, step in enumerate(spec.steps)]
        host.steps.append(OperationStepRun(position=len(spec.steps), title="结果核验", command=spec.verify,
                                           timeout_seconds=60, status="pending"))
        task.hosts.append(host)
    session.add(task)
    session.commit()
    return task


def claim_plan(session: Session, task_id: str) -> str:
    session.rollback()
    session.execute(text("BEGIN IMMEDIATE"))
    try:
        task = get_task(session, task_id)
        if task is None:
            result = "missing"
        elif task.status != "planned":
            result = "already_confirmed"
        elif utc_now() - task.created_at.replace(tzinfo=timezone.utc) >= PLAN_LIFETIME:
            task.status = "expired"
            task.completed_at = utc_now()
            result = "expired"
        elif task.destructive and session.scalar(select(OperationHost.id).where(
                OperationHost.host_id.in_(host.host_id for host in task.hosts),
                OperationHost.status == "unknown", OperationHost.resolved_at.is_(None)).limit(1)) is not None:
            result = "blocked"
        else:
            task.status = "queued"
            task.confirmed_at = utc_now()
            for host in task.hosts:
                host.status = "queued"
            result = "claimed"
        session.commit()
        return result
    except Exception:
        session.rollback()
        raise


def summarize(session: Session, task_id: str) -> bool:
    session.rollback()
    session.execute(text("BEGIN IMMEDIATE"))
    try:
        task = get_task(session, task_id)
        if task is None:
            raise ValueError("任务不存在")
        statuses = [host.status for host in task.hosts]
        if any(status in ("queued", "running") for status in statuses):
            task.status = "running" if any(status != "queued" for status in statuses) else "queued"
            finished = False
        else:
            succeeded = statuses.count("succeeded")
            if "unknown" in statuses:
                task.status = "unknown"
            elif succeeded == len(statuses):
                task.status = "succeeded"
            elif succeeded:
                task.status = "partial"
            elif any(status == "interrupted" for status in statuses):
                task.status = "interrupted"
            else:
                task.status = "failed"
            task.completed_at = utc_now()
            finished = True
        session.commit()
        return finished
    except Exception:
        session.rollback()
        raise


def interrupt_unfinished(session: Session) -> None:
    now = utc_now()
    session.execute(update(OperationStepRun).where(OperationStepRun.status == "running").values(status="unknown"))
    session.execute(update(OperationHost).where(OperationHost.status == "running").values(
        status="unknown", error="执行进程中断，结果未知"))
    session.execute(update(OperationHost).where(OperationHost.status == "queued").values(
        status="interrupted", error="任务未开始即中断"))
    unfinished = OperationTask.status.in_(("queued", "running"))
    session.execute(update(OperationTask).where(unfinished, select(OperationHost.id).where(
        OperationHost.task_id == OperationTask.id, OperationHost.status == "unknown").exists()).values(
        status="unknown", completed_at=now))
    session.execute(update(OperationTask).where(unfinished).values(status="interrupted", completed_at=now))
    session.commit()


def resolve_host(session: Session, task_id: str, host_id: int, note: str) -> str:
    session.rollback()
    session.execute(text("BEGIN IMMEDIATE"))
    try:
        task = get_task(session, task_id)
        if task is None:
            outcome = "missing"
        else:
            host = next((item for item in task.hosts if item.host_id == host_id), None)
            if host is None:
                outcome = "missing_host"
            elif task.status in ("queued", "running") or host.status != "unknown" or host.resolved_at is not None:
                outcome = "conflict"
            else:
                host.resolution_note = note
                host.resolved_at = utc_now()
                outcome = "resolved"
        session.commit()
        return outcome
    except Exception:
        session.rollback()
        raise


def expire_plans(session: Session) -> None:
    cutoff = utc_now() - PLAN_LIFETIME
    session.execute(update(OperationTask).where(OperationTask.status == "planned", OperationTask.created_at <= cutoff).values(
        status="expired", completed_at=utc_now()))
    session.commit()


def interrupt_unsubmitted(session: Session, task_id: str, host_ids: list[str]) -> None:
    if not host_ids:
        return
    session.execute(update(OperationHost).where(OperationHost.id.in_(host_ids), OperationHost.status == "queued").values(
        status="interrupted", error="任务调度失败"))
    session.commit()
    summarize(session, task_id)
