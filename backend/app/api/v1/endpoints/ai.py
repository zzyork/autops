import asyncio
import json
import logging
import queue
import threading
import time

import anyio
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from starlette.concurrency import run_in_threadpool
from starlette.background import BackgroundTask

from ...dependencies import Database, commit
from ....ai_models import AIConnection, AIProposal, AISession
from ....repositories import ai as repository
from ....schemas.ai import (ConnectionInput, ConnectionResponse, DecisionInput, Detail,
                             FeatureModels, MessageInput, OperationRegistration, SessionActivity, Summary)
from ....schemas.pagination import DEFAULT_PAGE_SIZE, PageNumber, PageResponse, PageSize
from ....services.ai_feature_models import (config_guard, feature_connection, load_feature_models,
                                           save_feature_models)
from ....schemas.inspections import InspectionInput
from ....services.inspection_rules import load_rules
from ....services.ai_provider import MAX_TOTAL_SECONDS

router = APIRouter(prefix="/ai", tags=["AI 运维"])
logger = logging.getLogger(__name__)


def require_connection(session: Database, connection_id: int) -> AIConnection:
    record = repository.connection(session, connection_id)
    if record is None:
        raise HTTPException(404, "模型连接不存在")
    return record


def require_session(session: Database, session_id: UUID) -> AISession:
    conversation = repository.get_session(session, str(session_id))
    if conversation is None:
        raise HTTPException(404, "会话不存在")
    return conversation


@router.get("/connections", response_model=list[ConnectionResponse] | PageResponse[ConnectionResponse])
def list_connections(session: Database, page: PageNumber = None,
                     page_size: PageSize = DEFAULT_PAGE_SIZE) -> list[AIConnection] | PageResponse[ConnectionResponse]:
    result = repository.connections(session, page, page_size)
    if page is None:
        return result
    items, total = result
    return PageResponse[ConnectionResponse](items=[ConnectionResponse.model_validate(item) for item in items], total=total)


@router.get("/feature-models", response_model=FeatureModels)
def read_feature_models(request: Request) -> FeatureModels:
    return load_feature_models(request.app.state.data_dir)


@router.put("/feature-models", response_model=FeatureModels)
def update_feature_models(data: FeatureModels, request: Request, session: Database) -> FeatureModels:
    return save_feature_models(request.app.state.data_dir, data, session)


@router.post("/connections", response_model=ConnectionResponse, status_code=201)
def create_connection(data: ConnectionInput, request: Request, session: Database) -> AIConnection:
    encrypted = request.app.state.cipher.encrypt(data.api_key.encode()).decode() if data.api_key else None
    try:
        return repository.save_connection(session, data, encrypted)
    except IntegrityError:
        session.rollback()
        raise HTTPException(409, "连接名称重复") from None


@router.put("/connections/{connection_id}", response_model=ConnectionResponse)
def update_connection(connection_id: int, data: ConnectionInput, request: Request, session: Database) -> AIConnection:
    record = require_connection(session, connection_id)
    encrypted = request.app.state.cipher.encrypt(data.api_key.encode()).decode() if data.api_key else None
    if data.api_key and record.api_key_encrypted and request.app.state.cipher.decrypt(record.api_key_encrypted.encode()).decode() == data.api_key:
        encrypted = None
    try:
        return repository.save_connection(session, data, encrypted, record)
    except IntegrityError:
        session.rollback()
        raise HTTPException(409, "连接名称重复") from None


@router.delete("/connections/{connection_id}", status_code=204)
def delete_connection(connection_id: int, request: Request, session: Database) -> Response:
    with config_guard:
        record = require_connection(session, connection_id)
        config = load_feature_models(request.app.state.data_dir)
        if connection_id in (config.chat_connection_id, config.inspection_report_connection_id):
            raise HTTPException(409, "连接已被 AI 功能模型配置引用")
        if session.scalar(select(func.count()).select_from(AISession).where(AISession.connection_id == record.id)):
            raise HTTPException(409, "连接已关联会话")
        session.delete(record)
        commit(session)
    return Response(status_code=204)


@router.post("/connections/{connection_id}/test", response_model=ConnectionResponse)
def test_connection(connection_id: int, request: Request, session: Database) -> AIConnection:
    record = require_connection(session, connection_id)
    original_version = record.version
    session.expunge(record)
    session.rollback()
    chat, tool = request.app.state.ai.test(record)
    record = require_connection(session, connection_id)
    if record.version != original_version:
        raise HTTPException(409, "连接已修改，请重新测试")
    record.chat_status, record.tool_status = chat, tool
    commit(session)
    return record


@router.get("/sessions", response_model=list[Summary] | PageResponse[Summary])
def list_sessions(session: Database, page: PageNumber = None,
                   page_size: PageSize = DEFAULT_PAGE_SIZE) -> list[AISession] | PageResponse[Summary]:
    result = repository.sessions(session, page, page_size)
    if page is None:
        return result
    items, total = result
    return PageResponse[Summary](items=[Summary.model_validate(item) for item in items], total=total)


@router.post("/sessions", response_model=Summary, status_code=201)
def create_session(request: Request, session: Database) -> AISession:
    with config_guard:
        record = feature_connection(session, request.app.state.data_dir, "chat")
        if record is None:
            raise HTTPException(409, "请先配置可用的 AI 对话模型")
        return repository.create_session(session, record)


@router.get("/sessions/{session_id}", response_model=Detail)
def read_session(session_id: UUID, session: Database) -> AISession:
    return require_session(session, session_id)


def session_activity(session_id: UUID, request: Request, session: Database) -> SessionActivity:
    session.rollback()
    # 先观察决策执行器，再读取关联，避免决策刚提交任务并释放锁时漏报活动。
    chat_running, chat_stopping = request.app.state.ai.activity(str(session_id))
    task_ids = repository.linked_task_ids(session, str(session_id))
    session.rollback()
    inspection_running, inspection_stopping = request.app.state.inspections.activity(task_ids)
    report_running, report_stopping = request.app.state.inspection_analysis.activity(task_ids)
    return SessionActivity(running=chat_running or inspection_running or report_running,
                           stopping=chat_stopping or inspection_stopping or report_stopping)


@router.get("/sessions/{session_id}/activity", response_model=SessionActivity)
def read_session_activity(session_id: UUID, request: Request, session: Database) -> SessionActivity:
    require_session(session, session_id)
    return session_activity(session_id, request, session)


@router.post("/sessions/{session_id}/stop", response_model=SessionActivity)
def stop_session(session_id: UUID, request: Request, session: Database) -> SessionActivity:
    require_session(session, session_id)
    request.app.state.ai.cancel(str(session_id))
    task_ids = repository.linked_task_ids(session, str(session_id))
    session.rollback()
    for task_id in task_ids:
        request.app.state.inspections.cancel(task_id)
    for task_id in task_ids:
        request.app.state.inspection_analysis.cancel(task_id)
    return session_activity(session_id, request, session)


@router.post("/sessions/{session_id}/operations", response_model=OperationRegistration, status_code=201)
def register_operation(session_id: UUID, request: Request, session: Database) -> OperationRegistration:
    require_session(session, session_id)
    return OperationRegistration(operation_id=request.app.state.ai.reserve(str(session_id)))


@router.delete("/sessions/{session_id}", status_code=204)
def delete_session(session_id: UUID, request: Request, session: Database) -> Response:
    ai = request.app.state.ai
    ai.acquire(str(session_id))
    try:
        conversation = require_session(session, session_id)
        session.delete(conversation)
        commit(session)
        return Response(status_code=204)
    finally:
        ai.release(str(session_id))


def event(name: str, data: dict) -> str:
    return f"event: {name}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("/sessions/{session_id}/messages", response_class=StreamingResponse)
def send_message(session_id: UUID, data: MessageInput, request: Request, session: Database) -> StreamingResponse:
    ai = request.app.state.ai
    cancelled = ai.acquire(str(session_id), data.operation_id.hex if data.operation_id is not None else None)
    try:
        conversation = require_session(session, session_id)
        record = require_connection(session, conversation.connection_id)
        if conversation.connection_version != record.config_version:
            raise HTTPException(409, "模型连接已修改，请新建会话")
        session.rollback()
    except Exception:
        ai.release(str(session_id))
        raise
    deadline = time.monotonic() + MAX_TOTAL_SECONDS
    release_guard = threading.Lock()
    released = False
    output: queue.Queue[tuple[str, object]] = queue.Queue(maxsize=16)
    stream_started = threading.Event()

    def release_once() -> None:
        nonlocal released
        with release_guard:
            if not released:
                released = True
                ai.release(str(session_id))

    def enqueue(kind: str, payload: object) -> None:
        while not cancelled.is_set() and time.monotonic() < deadline:
            try:
                output.put((kind, payload), timeout=0.2)
                return
            except queue.Full:
                continue
        raise RuntimeError("客户端已断开或请求超时")

    def work() -> None:
        try:
            detail = ai.send(str(session_id), data.content,
                             on_token=lambda text_value: enqueue("token", text_value), cancel=cancelled,
                             deadline=deadline)
            enqueue("done", detail)
        except Exception as exc:
            logger.error("AI session %s failed: %s", session_id, type(exc).__name__)
            try:
                enqueue("error", None)
            except RuntimeError:
                pass
        finally:
            release_once()

    async def stream():
        producer = asyncio.create_task(run_in_threadpool(work))
        stream_started.set()
        try:
            while True:
                try:
                    kind, payload = await run_in_threadpool(output.get, True, 0.2)
                except queue.Empty:
                    if producer.done() and output.empty():
                        yield event("error", {})
                        break
                    continue
                if kind == "token":
                    yield event("token", {"text": payload})
                elif kind == "done":
                    yield event("done", {"session": payload.model_dump(mode="json")})
                    break
                else:
                    yield event("error", {})
                    break
        finally:
            cancelled.set()
            with anyio.CancelScope(shield=True):
                await producer
            release_once()

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
                             background=BackgroundTask(lambda: release_once() if not stream_started.is_set() else None))


@router.post("/sessions/{session_id}/proposals/{proposal_id}/decision", response_model=Detail)
def decide(session_id: UUID, proposal_id: UUID, data: DecisionInput, request: Request, session: Database) -> AISession:
    ai = request.app.state.ai
    cancelled = ai.acquire(str(session_id), data.operation_id.hex if data.operation_id is not None else None)
    try:
        session.rollback()
        session.execute(text("BEGIN IMMEDIATE"))
        conversation = require_session(session, session_id)
        proposal = session.get(AIProposal, str(proposal_id))
        if proposal is None or proposal.session_id != conversation.id:
            raise HTTPException(404, "巡检计划不存在")
        if proposal.status == ("confirmed" if data.approve else "cancelled"):
            return conversation
        if proposal.status != "pending":
            raise HTTPException(409, "巡检计划已处理")
        if cancelled.is_set():
            raise HTTPException(409, "请求已取消")
        if not data.approve:
            proposal.status = "cancelled"
            commit(session)
            return conversation
        record = require_connection(session, conversation.connection_id)
        if conversation.connection_version != record.config_version:
            raise HTTPException(409, "模型连接已修改，请新建会话")
        if record.chat_status != "passed" or record.tool_status != "passed":
            raise HTTPException(409, "模型测试未通过，不能执行 AI 运维计划")
        selected = InspectionInput(name=proposal.name,
                                   hosts=[{"id": item["id"], "version": item["version"]} for item in proposal.hosts],
                                   checks=proposal.checks)
        config = load_rules(request.app.state.data_dir)
        if cancelled.is_set():
            raise HTTPException(409, "请求已取消")

        def link(task):
            if cancelled.is_set():
                raise HTTPException(409, "请求已取消")
            proposal.status = "confirmed"
            proposal.task_id = task.id

        task = request.app.state.inspections.start(session, selected, config, before_commit=link)
        if cancelled.is_set():
            request.app.state.inspections.cancel(task.id)
            request.app.state.inspection_analysis.cancel(task.id)
            raise HTTPException(409, "请求已取消")
        return conversation
    except Exception:
        session.rollback()
        raise
    finally:
        ai.release(str(session_id))
