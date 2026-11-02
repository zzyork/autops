from copy import deepcopy
from uuid import uuid4

from sqlalchemy import select, update
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


def history(session: Session, session_id: str) -> list[AIToolHistory]:
    return list(session.scalars(select(AIToolHistory).where(AIToolHistory.session_id == session_id)
                                .order_by(AIToolHistory.id)))


def messages(session: Session, session_id: str) -> list[AIMessage]:
    return list(session.scalars(select(AIMessage).where(AIMessage.session_id == session_id)
                                .order_by(AIMessage.id)))


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
             calls: list[dict], pending: list[dict]) -> None:
    user = session.get(AIMessage, user_id)
    user.status = "completed"
    user.in_flight = False
    session.add(AIMessage(session_id=conversation.id, role="assistant", content=content))
    for call in calls:
        session.add(AIToolHistory(session_id=conversation.id, message_id=user_id, **call))
    for proposal in pending:
        session.add(AIProposal(session_id=conversation.id, **proposal))
    conversation.updated_at = utc_now()
    session.commit()


def interrupt_unfinished(session: Session) -> None:
    session.execute(update(AIMessage).where(AIMessage.role == "user", AIMessage.in_flight.is_(True))
                    .values(status="interrupted", in_flight=False))
    session.commit()
