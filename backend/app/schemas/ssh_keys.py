from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator


class SSHKeyMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=100)
    remark: str = Field(default="", max_length=2000)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("密钥名称不能为空")
        return value


class SSHKeyInput(SSHKeyMetadata):
    private_key: SecretStr
    public_key: str


class SSHKeyUpdate(SSHKeyMetadata):
    version: int = Field(gt=0)
    private_key: SecretStr | None = None
    public_key: str | None = None


class SSHKeyResponse(SSHKeyMetadata):
    id: int
    key_type: str
    fingerprint: str
    public_key: str | None
    created_at: datetime
    updated_at: datetime
    version: int
    host_count: int
    jump_host_count: int


class SSHKeyReference(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str


class SSHKeyReferences(BaseModel):
    hosts: list[SSHKeyReference]
    jump_hosts: list[SSHKeyReference]
