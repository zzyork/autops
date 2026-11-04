from datetime import datetime, timezone
from typing import Annotated, Literal
from urllib.parse import urlsplit
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator

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


class RegenerateInput(MessageInput):
    expected_updated_at: AwareDatetime


class BranchInput(Input):
    include_message: bool = Field(default=True, strict=True)


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


class OperationCommand(Input):
    name: str = Field(min_length=1, max_length=100)
    command: str = Field(min_length=1, max_length=8192)
    timeout_seconds: int = Field(default=30, gt=0, le=600, strict=True)

    @field_validator("name", "command")
    @classmethod
    def valid_text(cls, value: str) -> str:
        if not value.strip() or any(not char.isprintable() and char not in "\n\t" for char in value):
            raise ValueError("名称和命令须填写且不能含控制字符")
        return value


class OperationInput(Input):
    name: str = Field(min_length=1, max_length=100)
    host_ids: list[Annotated[int, Field(gt=0, strict=True)]] = Field(min_length=1, max_length=8)
    commands: list[OperationCommand] = Field(min_length=1, max_length=10)

    @model_validator(mode="after")
    def valid_plan(self) -> "OperationInput":
        if not self.name.strip() or len(set(self.host_ids)) != len(self.host_ids):
            raise ValueError("计划名称须填写且主机不能重复")
        return self


OperationResultStatus = Literal["queued", "running", "succeeded", "failed", "unknown", "skipped"]


class OperationStepResult(BaseModel):
    name: str
    status: OperationResultStatus = "queued"
    exit_status: int | None = None
    error_code: str | None = None
    stdout: str = ""
    stderr: str = ""


class OperationHostResult(BaseModel):
    id: int
    name: str
    address: str
    status: OperationResultStatus = "queued"
    error_code: str | None = None
    steps: list[OperationStepResult]


class OperationExecution(BaseModel):
    status: Literal["queued", "running", "succeeded", "failed", "unknown", "interrupted"] = "queued"
    error_code: str | None = None
    hosts: list[OperationHostResult]


class Proposal(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    kind: Literal["inspection", "operation"]
    name: str
    hosts: list[HostSnapshot]
    checks: list[CheckId]
    status: Literal["pending", "confirmed", "cancelled"]
    task_id: str | None
    commands: list[OperationCommand]
    execution: OperationExecution | None


class Detail(Summary):
    messages: list[Message]
    proposals: list[Proposal]
    proposal_message_ids: dict[str, str]
