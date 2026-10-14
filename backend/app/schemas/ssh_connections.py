from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

TargetType = Literal["host", "jump_host"]
TestStatus = Literal["queued", "running", "succeeded", "failed", "awaiting_trust", "interrupted", "trusted"]


class ConnectionTestInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    target_type: TargetType
    target_id: int = Field(gt=0)
    version: int = Field(gt=0)


class ConnectionTestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    target_type: TargetType
    target_id: int
    target_name: str
    address: str
    port: int
    username: str
    status: TestStatus
    created_at: datetime
    started_at: datetime | None
    duration_ms: int | None

    @field_validator("created_at", "started_at")
    @classmethod
    def utc_timestamp(cls, value: datetime | None) -> datetime | None:
        return value.replace(tzinfo=timezone.utc) if value is not None and value.tzinfo is None else value
