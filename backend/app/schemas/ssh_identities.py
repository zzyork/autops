from pydantic import BaseModel, ConfigDict, Field

from .ssh_connections import TargetType


class IdentityCheckInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    target_type: TargetType
    target_id: int = Field(gt=0)
    version: int | None = Field(default=None, gt=0)


class IdentityTrustInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    confirmed: bool = Field(strict=True)


class IdentityChallenge(BaseModel):
    id: str
    target_type: TargetType
    target_name: str
    address: str
    port: int
    fingerprint: str
    previous_fingerprint: str | None


class IdentityCheckResponse(BaseModel):
    trusted: bool
    challenge: IdentityChallenge | None


class IdentityTrustResponse(BaseModel):
    trusted: bool
