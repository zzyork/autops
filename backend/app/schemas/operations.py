from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, StrictStr, field_validator

ModuleId = Literal["hostname", "packages", "firewall", "kernel", "system", "disk"]
TaskStatus = Literal["planned", "queued", "running", "succeeded", "failed", "partial", "unknown", "interrupted", "expired"]
HostStatus = Literal["planned", "queued", "running", "succeeded", "failed", "unknown", "interrupted"]
StepStatus = Literal["pending", "running", "succeeded", "failed", "unknown"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FieldOption(StrictModel):
    label: str = Field(min_length=1, max_length=100)
    value: StrictStr | StrictInt | StrictBool


class CatalogField(StrictModel):
    key: str = Field(min_length=1, max_length=64)
    label: str = Field(min_length=1, max_length=100)
    kind: Literal["text", "textarea", "number", "boolean", "select"]
    required: bool
    options: list[FieldOption] | None = None
    default: StrictStr | StrictInt | StrictBool | None = None


class CatalogAction(StrictModel):
    id: str
    title: str
    description: str
    destructive: bool
    fields: list[CatalogField]


class CatalogModule(StrictModel):
    id: ModuleId
    title: str
    actions: list[CatalogAction]


class OperationCatalog(StrictModel):
    modules: list[CatalogModule]


class InspectInput(StrictModel):
    module: ModuleId
    host_id: StrictInt = Field(gt=0)
    sudo: StrictBool = False


class Inspection(StrictModel):
    host_id: int
    host_name: str
    module: ModuleId
    output: str


class PlanInput(StrictModel):
    module: ModuleId
    action: StrictStr = Field(min_length=1, max_length=64)
    host_ids: list[StrictInt] = Field(min_length=1, max_length=16)
    params: dict[StrictStr, StrictStr | StrictInt | StrictBool | None] = Field(default_factory=dict, max_length=32)
    sudo: StrictBool = False

    @field_validator("host_ids")
    @classmethod
    def valid_hosts(cls, value: list[int]) -> list[int]:
        if any(host_id <= 0 for host_id in value) or len(set(value)) != len(value):
            raise ValueError("主机 ID 无效或重复")
        return value

    @field_validator("params")
    @classmethod
    def bounded_params(cls, value: dict[str, str | int | bool | None]) -> dict[str, str | int | bool | None]:
        if any(not key or len(key) > 64 or isinstance(item, str) and len(item) > 2048
               or type(item) is int and abs(item) > 1_000_000_000 for key, item in value.items()):
            raise ValueError("参数字段或内容超出限制")
        return value


class ConfirmInput(StrictModel):
    confirmation: StrictStr = Field(min_length=36, max_length=36)
    impact_ack: StrictBool


class ResolveInput(StrictModel):
    confirmation: StrictStr = Field(min_length=36, max_length=36)
    remote_stopped: StrictBool
    note: StrictStr = Field(min_length=5, max_length=500)

    @field_validator("note")
    @classmethod
    def meaningful_note(cls, value: str) -> str:
        if len(value.strip()) < 5:
            raise ValueError("核对说明至少需要 5 个字符")
        return value.strip()


class StepResponse(StrictModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")
    title: str
    status: StepStatus
    stdout: str | None
    stderr: str | None
    exit_status: int | None


class HostResponse(StrictModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")
    host_id: int
    host_name: str
    address: str
    status: HostStatus
    identity_required: bool
    before: str | None
    after: str | None
    error: str | None
    resolved_at: datetime | None
    resolution_note: str | None
    steps: list[StepResponse]

    @field_validator("resolved_at")
    @classmethod
    def utc_timestamp(cls, value: datetime | None) -> datetime | None:
        return value.replace(tzinfo=timezone.utc) if value is not None and value.tzinfo is None else value


class TaskResponse(StrictModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")
    id: str
    module: ModuleId
    action: str
    title: str
    status: TaskStatus
    created_at: datetime
    confirmed_at: datetime | None
    completed_at: datetime | None
    params: dict[str, str | int | bool]
    sudo: bool
    hosts: list[HostResponse]

    @field_validator("created_at", "confirmed_at", "completed_at")
    @classmethod
    def utc_timestamp(cls, value: datetime | None) -> datetime | None:
        return value.replace(tzinfo=timezone.utc) if value is not None and value.tzinfo is None else value


class TaskPage(StrictModel):
    items: list[TaskResponse]
    total: int
    page: int
    page_size: int
