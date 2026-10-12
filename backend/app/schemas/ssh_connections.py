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


class HostKeyChallenge(BaseModel):
    target_type: TargetType
    target_id: int
    address: str
    port: int
    key_type: str
    fingerprint: str
    previous_fingerprint: str | None


class ConnectionTestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    target_type: TargetType
    target_id: int
    target_name: str
    address: str
    port: int
    username: str
    via_jump_host: str | None
    status: TestStatus
    stage: Literal["target", "jump_host"] | None
    failure_code: Literal["authentication", "timeout", "connection", "configuration", "internal"] | None
    failure_message: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    duration_ms: int | None
    challenge: HostKeyChallenge | None

    @field_validator("created_at", "started_at", "finished_at")
    @classmethod
    def utc_timestamp(cls, value: datetime | None) -> datetime | None:
        return value.replace(tzinfo=timezone.utc) if value is not None and value.tzinfo is None else value
