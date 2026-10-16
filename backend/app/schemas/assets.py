import ipaddress
import re
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator, model_validator
from .ssh_connections import TestStatus


def validate_network_address(value: str) -> str:
    try:
        return str(ipaddress.ip_address(value))
    except ValueError:
        labels = value.rstrip(".").split(".")
        if all(re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?", label) for label in labels) and not all(label.isdigit() for label in labels):
            return value.rstrip(".").lower()
        raise ValueError("请输入有效 IP 地址或主机名") from None


class GroupInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=100)
    remark: str = Field(default="", max_length=2000)


class GroupResponse(GroupInput):
    id: int
    host_count: int


class HostInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=100)
    address: str = Field(min_length=1, max_length=253)
    group_id: int = Field(gt=0)
    username: str = Field(min_length=1, max_length=100)
    port: int = Field(default=22, ge=1, le=65535)
    auth_type: Literal["password", "key"]
    password: SecretStr | None = None
    ssh_key_id: int | None = Field(default=None, gt=0)
    vip: str | None = Field(default=None, max_length=253)
    jump_host_id: int | None = Field(default=None, gt=0)
    remark: str = Field(default="", max_length=2000)

    @field_validator("name", "address", "username", "vip")
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
    def validate_host_ip(cls, value: str) -> str:
        if "%" in value:
            raise ValueError("主机地址须为有效 IPv4 或 IPv6 地址")
        try:
            return str(ipaddress.ip_address(value))
        except ValueError:
            raise ValueError("主机地址须为有效 IPv4 或 IPv6 地址") from None

    @field_validator("vip")
    @classmethod
    def validate_address(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return validate_network_address(value)

    @model_validator(mode="after")
    def validate_connection(self) -> "HostInput":
        if self.auth_type == "key" and self.ssh_key_id is None:
            raise ValueError("私钥认证需要选择密钥")
        if self.auth_type == "password" and self.ssh_key_id is not None:
            raise ValueError("密码认证不能关联密钥")
        if self.password is not None and not 1 <= len(self.password.get_secret_value()) <= 4096:
            raise ValueError("密码长度应为 1 至 4096 个字符")
        return self


class HostUpdate(HostInput):
    version: int = Field(gt=0)


class HostResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    address: str
    group_id: int
    username: str
    port: int
    auth_type: Literal["password", "key"]
    ssh_key_id: int | None
    vip: str | None
    jump_host_id: int | None
    remark: str
    has_password: bool
    connection_status: TestStatus
    created_at: datetime
    updated_at: datetime
    version: int

    @field_validator("created_at", "updated_at")
    @classmethod
    def utc_timestamp(cls, value: datetime) -> datetime:
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value
