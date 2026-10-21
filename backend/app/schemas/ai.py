from datetime import datetime, timezone
from typing import Literal
from urllib.parse import urlsplit
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .inspections import CheckId


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FeatureModels(Input):
    chat_connection_id: int | None = Field(gt=0, strict=True)
    inspection_report_connection_id: int | None = Field(gt=0, strict=True)


class ConnectionInput(Input):
    name: str = Field(min_length=1, max_length=100)
    protocol: Literal["openai_compatible", "anthropic"]
    base_url: str = Field(max_length=2048)
    model: str = Field(min_length=1, max_length=200)
    api_key: str | None = Field(default=None, max_length=4096)
    is_default: bool = False
    is_backup: bool = False

    @model_validator(mode="after")
    def distinct_roles(self) -> "ConnectionInput":
        if self.is_default and self.is_backup:
            raise ValueError("同一连接不能同时作为主模型和备用模型")
        return self

    @field_validator("name", "model")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("不能为空")
        return value.strip()

    @field_validator("base_url")
    @classmethod
    def valid_url(cls, value: str) -> str:
        try:
            if any(ord(char) <= 32 or ord(char) == 127 for char in value):
                raise ValueError("服务地址无效")
            url = urlsplit(value)
            valid = (url.scheme in ("http", "https") and bool(url.hostname) and url.username is None
                     and url.password is None and not url.query and not url.fragment
                     and (url.port is None or 1 <= url.port <= 65535))
        except ValueError:
            valid = False
        if not valid:
            raise ValueError("服务地址无效")
        return value.rstrip("/")


class ConnectionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    protocol: Literal["openai_compatible", "anthropic"]
    base_url: str
    model: str
    has_api_key: bool
    is_default: bool
    is_backup: bool
    chat_status: Literal["untested", "passed", "failed"]
    tool_status: Literal["untested", "passed", "failed"]


class MessageInput(Input):
    content: str = Field(min_length=1, max_length=8000)
    operation_id: UUID | None = None

    @field_validator("content")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("消息不能为空")
        return value.strip()


class DecisionInput(Input):
    approve: bool
    operation_id: UUID | None = None


class OperationRegistration(BaseModel):
    operation_id: UUID


class SessionActivity(BaseModel):
    running: bool
    stopping: bool


class Summary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    title: str
    connection_id: int
    created_at: datetime
    updated_at: datetime

    @field_validator("created_at", "updated_at")
    @classmethod
    def utc(cls, value: datetime) -> datetime:
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


class Message(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    role: Literal["user", "assistant"]
    content: str
    created_at: datetime
    status: Literal["completed", "failed", "interrupted"]

    @field_validator("id", mode="before")
    @classmethod
    def stringify_id(cls, value: int) -> str:
        return str(value)


class HostSnapshot(BaseModel):
    id: int
    version: int
    name: str
    address: str


class Proposal(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    hosts: list[HostSnapshot]
    checks: list[CheckId]
    status: Literal["pending", "confirmed", "cancelled"]
    task_id: str | None


class Detail(Summary):
    messages: list[Message]
    proposals: list[Proposal]
