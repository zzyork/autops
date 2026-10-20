from datetime import datetime, timezone
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, field_validator

ExecutionStatus = Literal["queued", "running", "succeeded", "failed", "unknown"]
StepStatus = Literal["queued", "running", "succeeded", "failed", "unknown", "skipped"]


def _strip_name(value: object) -> object:
    return value.strip() if isinstance(value, str) else value


ExecutionName = Annotated[str, Field(min_length=1, max_length=100), BeforeValidator(_strip_name)]


class HostSelection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: int = Field(gt=0, strict=True)
    version: int = Field(gt=0, strict=True)


class StepInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: ExecutionName
    command: str = Field(min_length=1, max_length=8192)
    success_exit_codes: list[Annotated[int, Field(strict=True, ge=0, le=255)]] = Field(default_factory=lambda: [0], min_length=1, max_length=16)
    timeout_seconds: int = Field(default=30, strict=True, ge=1, le=600)

    @field_validator("command")
    @classmethod
    def valid_command(cls, value: str) -> str:
        if "\0" in value or not value.strip():
            raise ValueError("命令不得为空或包含 NUL")
        return value

    @field_validator("success_exit_codes")
    @classmethod
    def unique_codes(cls, value: list[int]) -> list[int]:
        if len(set(value)) != len(value):
            raise ValueError("成功退出码不能重复")
        return value


class ExecutionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: UUID
    name: ExecutionName
    host: HostSelection
    timeout_seconds: int = Field(default=900, strict=True, ge=10, le=1800)
    steps: list[StepInput] = Field(min_length=1, max_length=20)


class TimestampResponse(BaseModel):
    @field_validator("created_at", "started_at", "finished_at", check_fields=False)
    @classmethod
    def utc_timestamp(cls, value: datetime | None) -> datetime | None:
        return value.replace(tzinfo=timezone.utc) if value is not None and value.tzinfo is None else value


class ExecutionState(TimestampResponse):
    id: str
    status: ExecutionStatus
    error_code: str | None
    started_at: datetime | None
    finished_at: datetime | None


class StepState(TimestampResponse):
    id: int
    status: StepStatus
    exit_status: int | None
    error_code: str | None
    started_at: datetime | None
    finished_at: datetime | None


class ExecutionSummary(ExecutionState):
    name: str
    host_id: int
    host_name: str
    address: str
    step_count: int
    created_at: datetime


class StepDetail(StepState):
    position: int
    name: str
    command: str
    success_exit_codes: list[int]
    timeout_seconds: int
    stdout: str
    stderr: str


class ExecutionDetail(ExecutionSummary):
    timeout_seconds: int
    sequence: int
    steps: list[StepDetail]
