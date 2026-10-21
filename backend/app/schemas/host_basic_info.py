import ipaddress
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator

MAX_BASIC_INFO_ADDRESSES = 256
BasicInfoName = Annotated[str, Field(min_length=1, max_length=100, pattern=r"^[^\s\x00-\x1f\x7f-\x9f]+$")]


def validate_basic_info_ip(value: str) -> str:
    if "%" in value:
        raise ValueError("请选择有效的网卡 IP")
    address = ipaddress.ip_address(value)
    if address.is_loopback or address.is_link_local or address.is_unspecified or address.is_multicast:
        raise ValueError("请选择有效的网卡 IP")
    return str(address)


class HostBasicInfoCollect(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    version: int = Field(gt=0)


class HostBasicInfoAddress(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    interface: str = Field(min_length=1, max_length=253, pattern=r"^[^\s\x00-\x1f\x7f-\x9f]+$")
    address: str = Field(min_length=1, max_length=253)

    @field_validator("address")
    @classmethod
    def validate_ip(cls, value: str) -> str:
        return validate_basic_info_ip(value)


class HostBasicInfoResponse(HostBasicInfoCollect):
    host_id: int = Field(gt=0)
    name: BasicInfoName
    addresses: list[HostBasicInfoAddress] = Field(max_length=MAX_BASIC_INFO_ADDRESSES)


class HostBasicInfoUpdate(HostBasicInfoCollect):
    name: BasicInfoName
    lan_ip: str = Field(min_length=1, max_length=253)

    @field_validator("lan_ip")
    @classmethod
    def validate_ip(cls, value: str) -> str:
        return validate_basic_info_ip(value)
