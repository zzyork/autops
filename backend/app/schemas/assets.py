import ipaddress
import re
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator, model_validator


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
    key_path: str | None = Field(default=None, max_length=4096)
    vip: str | None = Field(default=None, max_length=253)
    proxy_address: str | None = Field(default=None, max_length=253)
    proxy_username: str | None = Field(default=None, max_length=100)
    proxy_port: int | None = Field(default=None, ge=1, le=65535)
    proxy_auth_type: Literal["password", "key"] | None = None
    proxy_password: SecretStr | None = None
    proxy_key_path: str | None = Field(default=None, max_length=4096)
    remark: str = Field(default="", max_length=2000)

    @field_validator("name", "address", "username", "key_path", "vip", "proxy_address", "proxy_username", "proxy_key_path")
    @classmethod
    def clean_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("字段不能为空白，请对可选字段使用 null")
        return value

    @field_validator("address", "vip", "proxy_address")
    @classmethod
    def validate_address(cls, value: str | None) -> str | None:
        if value is None:
            return None
        try:
            return str(ipaddress.ip_address(value))
        except ValueError:
            labels = value.rstrip(".").split(".")
            if all(re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?", label) for label in labels) and not all(label.isdigit() for label in labels):
                return value.rstrip(".").lower()
            raise ValueError("请输入有效 IP 地址或主机名") from None

    @model_validator(mode="after")
    def validate_connection(self) -> "HostInput":
        if self.auth_type == "key" and not self.key_path:
            raise ValueError("私钥认证需要私钥路径")
        if self.proxy_address:
            if not self.proxy_username or not self.proxy_port or not self.proxy_auth_type:
                raise ValueError("请完整填写跳板机用户名、端口和认证方式")
            if self.proxy_auth_type == "key" and not self.proxy_key_path:
                raise ValueError("跳板机私钥认证需要私钥路径")
        elif any(value is not None for value in (
            self.proxy_username, self.proxy_port, self.proxy_auth_type,
            self.proxy_password, self.proxy_key_path,
        )):
            raise ValueError("未启用跳板机时，其配置应为空")
        for password in (self.password, self.proxy_password):
            if password is not None and not 1 <= len(password.get_secret_value()) <= 4096:
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
    key_path: str | None
    vip: str | None
    proxy_address: str | None
    proxy_username: str | None
    proxy_port: int | None
    proxy_auth_type: Literal["password", "key"] | None
    proxy_key_path: str | None
    remark: str
    has_password: bool
    has_proxy_password: bool
    created_at: datetime
    updated_at: datetime
    version: int

    @field_validator("created_at", "updated_at")
    @classmethod
    def utc_timestamp(cls, value: datetime) -> datetime:
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value
