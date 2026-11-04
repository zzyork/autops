from copy import deepcopy
from uuid import uuid4

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from ..ai_models import AIConnection, AIMessage, AIProposal, AISession, AIToolHistory
from ..models import utc_now
from ..schemas.ai import ConnectionInput
from ..schemas.pagination import DEFAULT_PAGE_SIZE
from .pagination import fetch_rows


def connections(session: Session, page: int | None = None,
                 page_size: int = DEFAULT_PAGE_SIZE) -> list[AIConnection] | tuple[list[AIConnection], int]:
    return fetch_rows(session, select(AIConnection).order_by(AIConnection.id), page, page_size)


def connection(session: Session, connection_id: int) -> AIConnection | None:
    return session.get(AIConnection, connection_id)


def primary_connection(session: Session) -> AIConnection | None:
    return session.scalar(select(AIConnection).where(AIConnection.is_default.is_(True)))


def save_connection(session: Session, data: ConnectionInput, encrypted: str | None,
                    record: AIConnection | None = None) -> AIConnection:
    for field in ("is_default", "is_backup"):
        if getattr(data, field):
            previous = update(AIConnection).where(getattr(AIConnection, field).is_(True))
            if record is not None:
                previous = previous.where(AIConnection.id != record.id)
            session.execute(previous.values({field: False}))
    if record is None:
        record = AIConnection()
        session.add(record)
    else:
        changed = any(getattr(record, field) != getattr(data, field)
                      for field in ("protocol", "base_url", "model")) or encrypted is not None
        if changed:
            record.config_version += 1
            record.chat_status = record.tool_status = "untested"
    for field in ("name", "protocol", "base_url", "model", "is_default", "is_backup"):
        setattr(record, field, getattr(data, field))
    if encrypted is not None:
        record.api_key_encrypted = encrypted
    session.commit()
    session.refresh(record)
    return record


def sessions(session: Session, page: int | None = None,
              page_size: int = DEFAULT_PAGE_SIZE) -> list[AISession] | tuple[list[AISession], int]:
    query = select(AISession).order_by(AISession.updated_at.desc(), AISession.id.desc())
    return fetch_rows(session, query, page, page_size, legacy_limit=100)


def create_session(session: Session, record: AIConnection) -> AISession:
    conversation = AISession(id=str(uuid4()), title="新会话", connection_id=record.id,
                             connection_version=record.config_version)
    session.add(conversation)
    session.commit()
    return conversation


def get_session(session: Session, session_id: str) -> AISession | None:
    return session.get(AISession, session_id)


def branch_session(session: Session, source: AISession, message_id: int, include_message: bool) -> AISession:
    """Stage the branch in the caller's transaction without copying executable plans."""
    cutoff = AIMessage.id <= message_id if include_message else AIMessage.id < message_id
    prior = list(session.scalars(select(AIMessage).where(AIMessage.session_id == source.id, cutoff)
                                 .order_by(AIMessage.id)))
    suffix = "（分支）"
    branch = AISession(id=str(uuid4()), title=source.title[:100 - len(suffix)] + suffix,
                       connection_id=source.connection_id, connection_version=source.connection_version,
                       messages=[AIMessage(role=item.role, content=item.content, status=item.status,
                                           in_flight=False, created_at=item.created_at) for item in prior],
                       proposals=[])
    session.add(branch)
    session.flush()
    message_ids = {original.id: copied.id for original, copied in zip(prior, branch.messages)}
    # Tool calls belong to the user message, but occur after it and before its assistant reply.
    complete_turns = {user.id for user, assistant in zip(prior, prior[1:])
                      if user.role == "user" and assistant.role == "assistant"
                      and user.status == assistant.status == "completed"}
    for entry in history(session, source.id):
        if entry.message_id in complete_turns:
            session.add(AIToolHistory(session_id=branch.id, message_id=message_ids[entry.message_id],
                                      call_id=entry.call_id, round_index=entry.round_index,
                                      call_index=entry.call_index, assistant_text=entry.assistant_text,
                                      name=entry.name, arguments=deepcopy(entry.arguments), result=deepcopy(entry.result)))
    return branch


def history(session: Session, session_id: str, *, before_message_id: int | None = None) -> list[AIToolHistory]:
    query = select(AIToolHistory).where(AIToolHistory.session_id == session_id)
    if before_message_id is not None:
        query = query.where(AIToolHistory.message_id < before_message_id)
    return list(session.scalars(query.order_by(AIToolHistory.id)))


def messages(session: Session, session_id: str, *, before_message_id: int | None = None) -> list[AIMessage]:
    query = select(AIMessage).where(AIMessage.session_id == session_id)
    if before_message_id is not None:
        query = query.where(AIMessage.id < before_message_id)
    return list(session.scalars(query.order_by(AIMessage.id)))


def proposals(session: Session, session_id: str) -> list[AIProposal]:
    return list(session.scalars(select(AIProposal).where(AIProposal.session_id == session_id)
                                .order_by(AIProposal.id)))


def linked_task_ids(session: Session, session_id: str) -> list[str]:
    return list(session.scalars(select(AIProposal.task_id).where(
        AIProposal.session_id == session_id, AIProposal.task_id.is_not(None)).distinct()))


def add_user(session: Session, conversation: AISession, content: str) -> AIMessage:
    message = AIMessage(session_id=conversation.id, role="user", content=content, status="failed", in_flight=True)
    session.add(message)
    if conversation.title == "新会话":
        conversation.title = content[:100]
    conversation.updated_at = utc_now()
    session.commit()
    return message


def finish_failure(session: Session, user_id: int, status: str) -> None:
    message = session.get(AIMessage, user_id)
    if message is not None and message.in_flight:
        message.status = status
        message.in_flight = False
        session.commit()


def complete(session: Session, user_id: int, conversation: AISession, content: str,
             calls: list[dict], pending: list[dict], *, commit: bool = True) -> AIMessage:
    user = session.get(AIMessage, user_id)
    user.status = "completed"
    user.in_flight = False
    assistant = AIMessage(session_id=conversation.id, role="assistant", content=content)
    session.add(assistant)
    for call in calls:
        session.add(AIToolHistory(session_id=conversation.id, message_id=user_id, **call))
    for proposal in pending:
        session.add(AIProposal(session_id=conversation.id, **proposal))
    conversation.updated_at = utc_now()
    if commit:
        session.commit()
    return assistant


def replace_turn(session: Session, conversation: AISession, user: AIMessage, content: str,
                 reply: str, calls: list[dict], pending: list[dict]) -> None:
    """Stage the replacement in the caller's locked transaction; preserve confirmed tasks."""
    replaced_history = list(session.scalars(select(AIToolHistory).where(
        AIToolHistory.session_id == conversation.id, AIToolHistory.message_id >= user.id)))
    proposal_ids = {entry.result["proposal"]["id"] for entry in replaced_history
                    if entry.name in ("prepare_inspection", "prepare_operation") and isinstance(entry.result.get("proposal"), dict)
                    and isinstance(entry.result["proposal"].get("id"), str)}
    session.execute(delete(AIToolHistory).where(
        AIToolHistory.session_id == conversation.id, AIToolHistory.message_id >= user.id))
    if proposal_ids:
        session.execute(delete(AIProposal).where(
            AIProposal.session_id == conversation.id, AIProposal.id.in_(proposal_ids),
            AIProposal.status.in_(("pending", "cancelled")), AIProposal.task_id.is_(None)))
    user.content = content
    assistant = complete(session, user.id, conversation, reply, calls, pending, commit=False)
    # Allocate the new message ID while the old tail still exists, avoiding SQLite ID reuse.
    session.flush()
    session.execute(delete(AIMessage).where(
        AIMessage.session_id == conversation.id, AIMessage.id > user.id, AIMessage.id != assistant.id))
    session.expire(conversation, ["messages", "proposals", "tool_history"])


def interrupt_unfinished(session: Session) -> None:
    session.execute(update(AIMessage).where(AIMessage.role == "user", AIMessage.in_flight.is_(True))
                    .values(status="interrupted", in_flight=False))
    session.commit()


def save_operation_execution(session: Session, proposal_id: str, execution: dict) -> None:
    proposal = session.get(AIProposal, proposal_id)
    if proposal is None or proposal.kind != "operation" or proposal.status != "confirmed":
        raise ValueError("运维执行记录不存在")
    # JSON 列通过整体替换记录深层变化，避免原地更新未落库。
    proposal.execution = deepcopy(execution)
    session.commit()


def interrupt_operations(session: Session) -> None:
    for proposal in session.scalars(select(AIProposal).where(
            AIProposal.kind == "operation", AIProposal.status == "confirmed")):
        if not proposal.execution or proposal.execution["status"] not in ("queued", "running"):
            continue
        execution = deepcopy(proposal.execution)
        uncertain = False
        for host in execution["hosts"]:
            for step in host["steps"]:
                if step["status"] == "running":
                    step["status"], step["error_code"] = "unknown", "server_restarted"
                elif step["status"] == "queued":
                    step["status"], step["error_code"] = "skipped", "not_executed"
            if any(step["status"] == "unknown" for step in host["steps"]):
                host["status"], host["error_code"] = "unknown", "server_restarted"
                uncertain = True
            elif host["steps"] and all(step["status"] == "succeeded" for step in host["steps"]):
                host["status"], host["error_code"] = "succeeded", None
            elif host["status"] in ("queued", "running"):
                host["status"], host["error_code"] = "skipped", "server_restarted"
        if execution["hosts"] and all(host["status"] == "succeeded" for host in execution["hosts"]):
            execution["status"], execution["error_code"] = "succeeded", None
        else:
            execution["status"] = "unknown" if uncertain else "interrupted"
            execution["error_code"] = "server_restarted"
        proposal.execution = execution
    session.commit()
