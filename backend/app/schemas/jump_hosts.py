from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator, model_validator

from .assets import validate_network_address


class JumpHostInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=100)
    address: str = Field(min_length=1, max_length=253)
    username: str = Field(min_length=1, max_length=100)
    port: int = Field(default=22, ge=1, le=65535)
    auth_type: Literal["password", "key"]
    password: SecretStr | None = None
    key_path: str | None = Field(default=None, max_length=4096)
    remark: str = Field(default="", max_length=2000)

    @field_validator("name", "address", "username", "key_path")
    @classmethod
    def clean_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("字段不能为空白，请对可选字段使用 null")
        return value

    @field_validator("address")
    @classmethod
    def validate_address(cls, value: str) -> str:
        return validate_network_address(value)

    @model_validator(mode="after")
    def validate_connection(self) -> "JumpHostInput":
        if self.auth_type == "key" and not self.key_path:
            raise ValueError("私钥认证需要私钥路径")
        if self.password is not None and not 1 <= len(self.password.get_secret_value()) <= 4096:
            raise ValueError("密码长度应为 1 至 4096 个字符")
        return self


class JumpHostUpdate(JumpHostInput):
    version: int = Field(gt=0)


class JumpHostResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    address: str
    username: str
    port: int
    auth_type: Literal["password", "key"]
    key_path: str | None
    remark: str
    has_password: bool
    created_at: datetime
    updated_at: datetime
    version: int
    host_count: int

    @field_validator("created_at", "updated_at")
    @classmethod
    def utc_timestamp(cls, value: datetime) -> datetime:
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value
