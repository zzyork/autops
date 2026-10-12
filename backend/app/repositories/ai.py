from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ..ai_models import AIConnection, AIMessage, AIProposal, AISession, AIToolHistory
from ..models import utc_now
from ..schemas.ai import ConnectionInput


def connections(session: Session) -> list[AIConnection]:
    return list(session.scalars(select(AIConnection).order_by(AIConnection.id)))


def connection(session: Session, connection_id: int) -> AIConnection | None:
    return session.get(AIConnection, connection_id)


def save_connection(session: Session, data: ConnectionInput, encrypted: str | None,
                    record: AIConnection | None = None) -> AIConnection:
    if data.is_default:
        previous = update(AIConnection).where(AIConnection.is_default.is_(True))
        if record is not None:
            previous = previous.where(AIConnection.id != record.id)
        session.execute(previous.values(is_default=False))
    if record is None:
        record = AIConnection()
        session.add(record)
    else:
        changed = any(getattr(record, field) != getattr(data, field)
                      for field in ("protocol", "base_url", "model")) or encrypted is not None
        if changed:
            record.config_version += 1
            record.chat_status = record.tool_status = "untested"
    for field in ("name", "protocol", "base_url", "model", "is_default"):
        setattr(record, field, getattr(data, field))
    if encrypted is not None:
        record.api_key_encrypted = encrypted
    session.commit()
    session.refresh(record)
    return record


def sessions(session: Session) -> list[AISession]:
    return list(session.scalars(select(AISession).order_by(AISession.updated_at.desc(), AISession.id.desc()).limit(100)))


def create_session(session: Session, record: AIConnection) -> AISession:
    conversation = AISession(id=str(uuid4()), title="新会话", connection_id=record.id,
                             connection_version=record.config_version)
    session.add(conversation)
    session.commit()
    return conversation


def get_session(session: Session, session_id: str) -> AISession | None:
    return session.get(AISession, session_id)


def history(session: Session, session_id: str) -> list[AIToolHistory]:
    return list(session.scalars(select(AIToolHistory).where(AIToolHistory.session_id == session_id)
                                .order_by(AIToolHistory.id)))


def messages(session: Session, session_id: str) -> list[AIMessage]:
    return list(session.scalars(select(AIMessage).where(AIMessage.session_id == session_id)
                                .order_by(AIMessage.id)))


def proposals(session: Session, session_id: str) -> list[AIProposal]:
    return list(session.scalars(select(AIProposal).where(AIProposal.session_id == session_id)
                                .order_by(AIProposal.id)))


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
