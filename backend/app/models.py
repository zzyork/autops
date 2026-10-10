from datetime import datetime, timezone

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class HostGroup(Base):
    __tablename__ = "host_groups"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    remark: Mapped[str] = mapped_column(default="")


class Host(Base):
    __tablename__ = "hosts"
    __table_args__ = (UniqueConstraint("address", "port"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    address: Mapped[str]
    group_id: Mapped[int] = mapped_column(ForeignKey("host_groups.id", ondelete="RESTRICT"))
    username: Mapped[str]
    port: Mapped[int]
    auth_type: Mapped[str]
    key_path: Mapped[str | None]
    password_encrypted: Mapped[str | None]
    vip: Mapped[str | None]
    proxy_address: Mapped[str | None]
    proxy_username: Mapped[str | None]
    proxy_port: Mapped[int | None]
    proxy_auth_type: Mapped[str | None]
    proxy_key_path: Mapped[str | None]
    proxy_password_encrypted: Mapped[str | None]
    remark: Mapped[str] = mapped_column(default="")
    created_at: Mapped[datetime] = mapped_column(default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(default=utc_now, onupdate=utc_now)
    version: Mapped[int] = mapped_column(default=1)
    __mapper_args__ = {"version_id_col": version}

    @property
    def has_password(self) -> bool:
        return self.password_encrypted is not None

    @property
    def has_proxy_password(self) -> bool:
        return self.proxy_password_encrypted is not None
