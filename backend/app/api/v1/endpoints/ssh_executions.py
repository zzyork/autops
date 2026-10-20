import asyncio
import json
import threading
import time
from collections.abc import AsyncIterator
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request, Response
from fastapi.responses import StreamingResponse
from starlette.background import BackgroundTask
from starlette.concurrency import run_in_threadpool

from ...dependencies import Database
from ....repositories import ssh_executions as repository
from ....schemas.pagination import DEFAULT_PAGE_SIZE, PageNumber, PageResponse, PageSize
from ....schemas.ssh_executions import ExecutionDetail, ExecutionInput, ExecutionSummary

router = APIRouter(prefix="/ssh/executions", tags=["SSH 执行"])
HEARTBEAT_SECONDS = 10


@router.post("", response_model=ExecutionDetail, status_code=202)
def create(data: ExecutionInput, request: Request) -> ExecutionDetail:
    return request.app.state.ssh_executions.start(data)


@router.get("", response_model=PageResponse[ExecutionSummary])
def list_executions(request: Request, session: Database,
                    page: PageNumber = 1, page_size: PageSize = DEFAULT_PAGE_SIZE) -> PageResponse[ExecutionSummary]:
    manager = request.app.state.ssh_executions
    manager.ensure_available()
    try:
        items, total = repository.page(session, page_size, (page - 1) * page_size)
    except Exception:
        manager.storage_failed()
        raise HTTPException(503, "SSH 执行记录暂不可用") from None
    return PageResponse[ExecutionSummary](items=items, total=total)


@router.get("/{execution_id}", response_model=ExecutionDetail)
def read_execution(execution_id: UUID, request: Request, session: Database) -> ExecutionDetail:
    manager = request.app.state.ssh_executions
    manager.ensure_available()
    try:
        result = repository.detail(session, str(execution_id))
    except Exception:
        manager.storage_failed()
        raise HTTPException(503, "SSH 执行记录暂不可用") from None
    if result is None:
        raise HTTPException(404, "SSH 执行记录不存在")
    return result


@router.delete("/{execution_id}", status_code=204)
def delete_execution(execution_id: UUID, request: Request, session: Database) -> Response:
    manager = request.app.state.ssh_executions
    manager.ensure_available()
    try:
        result = repository.delete_execution(session, str(execution_id))
    except Exception:
        manager.storage_failed()
        raise HTTPException(503, "SSH 执行记录暂不可用") from None
    if result == "missing":
        raise HTTPException(404, "SSH 执行记录不存在")
    if result == "active":
        raise HTTPException(409, "SSH 执行尚未结束")
    return Response(status_code=204)


def _event(name: str, data: dict) -> str:
    return f"event: {name}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.get("/{execution_id}/events", response_class=StreamingResponse)
def stream_events(execution_id: UUID, request: Request,
                  after: Annotated[int, Query(ge=0)] = 0) -> StreamingResponse:
    manager = request.app.state.ssh_executions
    manager.subscribe()
    try:
        with manager.sessions() as session:
            execution = repository.get_execution(session, str(execution_id))
            if execution is None:
                raise HTTPException(404, "SSH 执行记录不存在")
            if after > execution.sequence:
                raise HTTPException(422, "事件游标超出当前序号")
    except HTTPException:
        manager.unsubscribe()
        raise
    except Exception:
        manager.unsubscribe()
        manager.storage_failed()
        raise HTTPException(503, "SSH 执行记录暂不可用") from None
    release_lock = threading.Lock()
    released = False

    def release() -> None:
        nonlocal released
        with release_lock:
            if not released:
                released = True
                manager.unsubscribe()

    def read_batch(cursor: int) -> tuple[list[tuple[int, str, dict]], dict, int]:
        with manager.sessions() as session:
            return repository.events(session, str(execution_id), cursor)

    async def stream() -> AsyncIterator[str]:
        cursor = after
        last_activity = time.monotonic()
        try:
            while True:
                if manager.persistence_failed.is_set():
                    yield _event("error", {})
                    return
                try:
                    batch, execution_state, sequence = await run_in_threadpool(read_batch, cursor)
                except Exception as exc:
                    if not isinstance(exc, LookupError):
                        manager.storage_failed()
                    yield _event("error", {})
                    return
                for number, kind, payload in batch:
                    yield _event(kind, payload)
                    cursor = number
                if batch:
                    last_activity = time.monotonic()
                if execution_state["status"] in repository.TERMINAL and cursor >= sequence:
                    yield _event("done", {"sequence": sequence, "execution": execution_state})
                    return
                if not batch and time.monotonic() - last_activity >= HEARTBEAT_SECONDS:
                    yield ": heartbeat\n\n"
                    last_activity = time.monotonic()
                if not batch:
                    await asyncio.sleep(1)
        finally:
            release()

    return StreamingResponse(stream(), media_type="text/event-stream", headers={
        "Cache-Control": "no-cache", "X-Accel-Buffering": "no",
    }, background=BackgroundTask(release))
