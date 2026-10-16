from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

TargetType = Literal["host", "jump_host"]
TestStatus = Literal["untested", "running", "succeeded", "failed", "awaiting_trust", "interrupted"]


class ConnectionTestInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    target_type: TargetType
    target_id: int = Field(gt=0)
    version: int = Field(gt=0)


class ConnectionTestResponse(BaseModel):
    target_type: TargetType
    target_id: int
    status: TestStatus
