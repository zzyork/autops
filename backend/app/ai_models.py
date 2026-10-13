from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Index, JSON, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .models import Base, utc_now


class AIConnection(Base):
    __tablename__ = "ai_connections"
    __table_args__ = (
        CheckConstraint("NOT (is_default = 1 AND is_backup = 1)", name="ck_ai_connections_distinct_roles"),
        Index("uq_ai_connections_primary", "is_default", unique=True, sqlite_where=text("is_default = 1")),
        Index("uq_ai_connections_backup", "is_backup", unique=True, sqlite_where=text("is_backup = 1")),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    protocol: Mapped[str] = mapped_column(String(20))
    base_url: Mapped[str] = mapped_column(String(2048))
    model: Mapped[str] = mapped_column(String(200))
    api_key_encrypted: Mapped[str | None]
    is_default: Mapped[bool] = mapped_column(default=False)
    is_backup: Mapped[bool] = mapped_column(default=False)
    chat_status: Mapped[str] = mapped_column(default="untested")
    tool_status: Mapped[str] = mapped_column(default="untested")
    config_version: Mapped[int] = mapped_column(default=1)
    version: Mapped[int] = mapped_column(default=1)
    __mapper_args__ = {"version_id_col": version}

    @property
    def has_api_key(self) -> bool:
        return self.api_key_encrypted is not None


class AISession(Base):
    __tablename__ = "ai_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    title: Mapped[str] = mapped_column(String(100))
    connection_id: Mapped[int] = mapped_column(ForeignKey("ai_connections.id", ondelete="RESTRICT"))
    connection_version: Mapped[int]
    created_at: Mapped[datetime] = mapped_column(default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(default=utc_now)
    messages: Mapped[list["AIMessage"]] = relationship(cascade="all, delete-orphan", order_by="AIMessage.id")
    proposals: Mapped[list["AIProposal"]] = relationship(cascade="all, delete-orphan", order_by="AIProposal.id")
    tool_history: Mapped[list["AIToolHistory"]] = relationship(cascade="all, delete-orphan", order_by="AIToolHistory.id")


class AIMessage(Base):
    __tablename__ = "ai_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("ai_sessions.id", ondelete="CASCADE"))
    role: Mapped[str] = mapped_column(String(12))
    content: Mapped[str]
    status: Mapped[str] = mapped_column(default="completed")
    in_flight: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(default=utc_now)


class AIProposal(Base):
    __tablename__ = "ai_proposals"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("ai_sessions.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(100))
    hosts: Mapped[list] = mapped_column(JSON)
    checks: Mapped[list] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(default="pending")
    task_id: Mapped[str | None] = mapped_column(ForeignKey("inspection_tasks.id", ondelete="SET NULL"))


class AIToolHistory(Base):
    __tablename__ = "ai_tool_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("ai_sessions.id", ondelete="CASCADE"))
    message_id: Mapped[int] = mapped_column(ForeignKey("ai_messages.id", ondelete="CASCADE"))
    call_id: Mapped[str] = mapped_column(String(200))
    round_index: Mapped[int] = mapped_column(default=0)
    call_index: Mapped[int] = mapped_column(default=0)
    assistant_text: Mapped[str] = mapped_column(default="")
    name: Mapped[str] = mapped_column(String(80))
    arguments: Mapped[dict] = mapped_column(JSON)
    result: Mapped[dict] = mapped_column(JSON)
