from sqlalchemy import select, text, update
from sqlalchemy.orm import Session

from ..inspection_models import InspectionAIReport, InspectionTask
from ..models import utc_now

ACTIVE = ("queued", "running")


def read(session: Session, task_id: str) -> InspectionAIReport | None:
    return session.get(InspectionAIReport, task_id)


def claim(session: Session, task_id: str, generation_id: str, model_name: str | None,
          model_version: int | None, status: str, automatic: bool, transaction_started: bool = False) -> str:
    if not transaction_started:
        begin_claim(session)
    try:
        task_status = session.scalar(select(InspectionTask.status).where(InspectionTask.id == task_id))
        if task_status is None:
            session.rollback()
            return "missing"
        if task_status in ACTIVE:
            session.rollback()
            return "active"
        row = read(session, task_id)
        if row is not None and (automatic or row.status in ACTIVE):
            session.rollback()
            return "duplicate"
        if row is None:
            row = InspectionAIReport(task_id=task_id)
            session.add(row)
        row.generation_id, row.status = generation_id, status
        row.model_name, row.model_version = model_name, model_version
        row.started_at = None
        row.finished_at = None if status == "queued" else utc_now()
        row.error_code = "model_unavailable" if status == "unavailable" else None
        session.commit()
        return "claimed"
    except Exception:
        session.rollback()
        raise


def begin_claim(session: Session) -> None:
    session.rollback()
    session.execute(text("BEGIN IMMEDIATE"))


def running(session: Session, task_id: str, generation_id: str) -> bool:
    result = session.execute(update(InspectionAIReport).where(
        InspectionAIReport.task_id == task_id, InspectionAIReport.generation_id == generation_id,
        InspectionAIReport.status == "queued").values(status="running", started_at=utc_now()))
    session.commit()
    return result.rowcount == 1


def finish(session: Session, task_id: str, generation_id: str, status: str,
           error_code: str | None = None, report: dict | None = None) -> None:
    values = {"status": status, "error_code": error_code, "finished_at": utc_now()}
    if report is not None:
        values["report"] = report
    # 删除或更换批次后，旧结果不能重新创建记录或覆盖新结果。
    session.execute(update(InspectionAIReport).where(
        InspectionAIReport.task_id == task_id, InspectionAIReport.generation_id == generation_id,
        InspectionAIReport.status.in_(ACTIVE)).values(**values))
    session.commit()


def interrupt_unfinished(session: Session) -> None:
    session.execute(update(InspectionAIReport).where(InspectionAIReport.status.in_(ACTIVE)).values(
        status="interrupted", error_code="interrupted", finished_at=utc_now()))
    session.commit()
