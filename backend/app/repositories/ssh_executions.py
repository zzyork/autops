from collections.abc import Callable
from typing import Literal

from sqlalchemy import delete, func, select, text
from sqlalchemy.orm import Session

from ..execution_models import SSHExecution, SSHExecutionEvent, SSHExecutionRequest, SSHExecutionStep
from ..models import utc_now
from ..schemas.ssh_executions import (ExecutionDetail, ExecutionInput, ExecutionState,
                                      ExecutionSummary, StepDetail, StepState)

ACTIVE = ("queued", "running")
TERMINAL = ("succeeded", "failed", "unknown")


def begin_write(session: Session) -> None:
    session.rollback()
    session.execute(text("BEGIN IMMEDIATE"))


def get_execution(session: Session, execution_id: str) -> SSHExecution | None:
    return session.get(SSHExecution, execution_id)


def request_used(session: Session, execution_id: str) -> bool:
    return session.get(SSHExecutionRequest, execution_id) is not None


def steps(session: Session, execution_id: str) -> list[SSHExecutionStep]:
    return list(session.scalars(select(SSHExecutionStep).where(
        SSHExecutionStep.execution_id == execution_id).order_by(SSHExecutionStep.position)))


def state(execution: SSHExecution, items: list[SSHExecutionStep]) -> dict:
    return {
        "execution": ExecutionState.model_validate(execution, from_attributes=True).model_dump(mode="json"),
        "steps": [StepState.model_validate(step, from_attributes=True).model_dump(mode="json") for step in items],
    }


def append_event(session: Session, execution: SSHExecution, kind: str, payload: dict) -> None:
    execution.sequence += 1
    session.add(SSHExecutionEvent(execution_id=execution.id, sequence=execution.sequence,
                                  kind=kind, payload={"sequence": execution.sequence, **payload}))


def create_execution(session: Session, data: ExecutionInput, digest: str, host_name: str,
                      address: str, snapshot: str) -> None:
    session.add(SSHExecutionRequest(id=str(data.id)))
    execution = SSHExecution(id=str(data.id), digest=digest, name=data.name, host_id=data.host.id,
                             host_name=host_name, address=address, asset_snapshot=snapshot,
                             timeout_seconds=data.timeout_seconds, step_count=len(data.steps),
                             status="queued", error_code=None, sequence=0, started_at=None, finished_at=None)
    session.add(execution)
    session.flush()
    items = []
    for position, selected in enumerate(data.steps):
        step = SSHExecutionStep(execution_id=execution.id, position=position, name=selected.name,
                                command=selected.command, success_exit_codes=selected.success_exit_codes,
                                timeout_seconds=selected.timeout_seconds, status="queued", exit_status=None,
                                error_code=None, started_at=None, finished_at=None)
        session.add(step)
        items.append(step)
    session.flush()
    append_event(session, execution, "state", state(execution, items))
    session.commit()


def change_state(session: Session, execution_id: str,
                 change: Callable[[SSHExecution, list[SSHExecutionStep]], None]) -> None:
    begin_write(session)
    try:
        execution = get_execution(session, execution_id)
        if execution is None or execution.status in TERMINAL:
            raise ValueError("SSH 执行记录已结束或不存在")
        items = steps(session, execution_id)
        change(execution, items)
        append_event(session, execution, "state", state(execution, items))
        session.commit()
    except Exception:
        session.rollback()
        raise


def save_output(session: Session, execution_id: str, step_id: int, stream: str, value: str) -> None:
    if not value:
        return
    begin_write(session)
    try:
        execution = get_execution(session, execution_id)
        if execution is None or execution.status != "running":
            raise ValueError("SSH 执行记录已结束或不存在")
        append_event(session, execution, "output", {"step_id": step_id, "stream": stream, "text": value})
        session.commit()
    except Exception:
        session.rollback()
        raise


def detail(session: Session, execution_id: str) -> ExecutionDetail | None:
    session.rollback()
    # A real SQLite read transaction pins the sequence, steps and output to one snapshot.
    session.execute(text("BEGIN"))
    try:
        execution = get_execution(session, execution_id)
        if execution is None:
            return None
        items = steps(session, execution_id)
        output = {item.id: {"stdout": [], "stderr": []} for item in items}
        for event in session.scalars(select(SSHExecutionEvent).where(
            SSHExecutionEvent.execution_id == execution_id, SSHExecutionEvent.kind == "output",
            SSHExecutionEvent.sequence <= execution.sequence).order_by(SSHExecutionEvent.sequence)):
            part = event.payload
            if part["step_id"] in output:
                output[part["step_id"]][part["stream"]].append(part["text"])
        summary = ExecutionSummary.model_validate(execution, from_attributes=True).model_dump()
        result = ExecutionDetail(**summary, timeout_seconds=execution.timeout_seconds,
                                 sequence=execution.sequence, steps=[
            StepDetail(**StepState.model_validate(item, from_attributes=True).model_dump(),
                       position=item.position, name=item.name, command=item.command,
                       success_exit_codes=item.success_exit_codes, timeout_seconds=item.timeout_seconds,
                       stdout="".join(output[item.id]["stdout"]), stderr="".join(output[item.id]["stderr"]))
            for item in items])
        return result
    finally:
        session.rollback()


def page(session: Session, limit: int, offset: int) -> tuple[list[ExecutionSummary], int]:
    total = session.scalar(select(func.count()).select_from(SSHExecution)) or 0
    rows = session.scalars(select(SSHExecution).order_by(
        SSHExecution.created_at.desc(), SSHExecution.id.desc()).limit(limit).offset(offset))
    return [ExecutionSummary.model_validate(row, from_attributes=True) for row in rows], total


def events(session: Session, execution_id: str, after: int) -> tuple[list[tuple[int, str, dict]], dict, int]:
    session.execute(text("BEGIN"))
    try:
        execution = get_execution(session, execution_id)
        if execution is None:
            raise LookupError("SSH 执行记录不存在")
        rows = list(session.scalars(select(SSHExecutionEvent).where(
            SSHExecutionEvent.execution_id == execution_id, SSHExecutionEvent.sequence > after
        ).order_by(SSHExecutionEvent.sequence).limit(100)))
        return ([(row.sequence, row.kind, row.payload) for row in rows],
                ExecutionState.model_validate(execution, from_attributes=True).model_dump(mode="json"),
                execution.sequence)
    finally:
        session.rollback()


def delete_execution(session: Session, execution_id: str) -> Literal["missing", "active", "deleted"]:
    begin_write(session)
    try:
        execution = get_execution(session, execution_id)
        if execution is None:
            return "missing"
        if execution.status in ACTIVE:
            return "active"
        session.execute(delete(SSHExecution).where(SSHExecution.id == execution_id))
        session.commit()
        return "deleted"
    finally:
        session.rollback()


def recover_unfinished(session: Session) -> None:
    begin_write(session)
    try:
        ids = list(session.scalars(select(SSHExecution.id).where(SSHExecution.status.in_(ACTIVE))))
        for execution_id in ids:
            execution = get_execution(session, execution_id)
            items = steps(session, execution_id)
            was_running = execution.status == "running"
            execution.status = "unknown" if was_running else "failed"
            execution.error_code = "interrupted"
            execution.finished_at = utc_now()
            for item in items:
                if item.status == "running":
                    item.status = "unknown"
                    item.error_code = "interrupted"
                    item.finished_at = utc_now()
                elif item.status == "queued":
                    item.status = "skipped"
                    item.error_code = "interrupted"
                    item.finished_at = utc_now()
            append_event(session, execution, "state", state(execution, items))
        session.commit()
    except Exception:
        session.rollback()
        raise
