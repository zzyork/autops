import math
import re
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

CheckId = Literal["server_info", "system_resources", "service_status", "network_info"]
RunStatus = Literal["queued", "running", "completed", "partial", "failed", "interrupted"]
CheckStatus = Literal["queued", "running", "completed", "failed", "skipped", "interrupted"]
Conclusion = Literal["normal", "warning", "critical", "not_applicable", "unknown"]


class InputModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Thresholds(InputModel):
    cpu_warning: float = Field(default=80, ge=0, le=100, allow_inf_nan=False)
    cpu_critical: float = Field(default=95, ge=0, le=100, allow_inf_nan=False)
    mem_warning: float = Field(default=80, ge=0, le=100, allow_inf_nan=False)
    mem_critical: float = Field(default=95, ge=0, le=100, allow_inf_nan=False)
    disk_warning: float = Field(default=80, ge=0, le=100, allow_inf_nan=False)
    disk_critical: float = Field(default=90, ge=0, le=100, allow_inf_nan=False)
    swap_warning: float = Field(default=50, ge=0, le=100, allow_inf_nan=False)
    swap_critical: float = Field(default=80, ge=0, le=100, allow_inf_nan=False)

    @model_validator(mode="after")
    def threshold_order(self) -> "Thresholds":
        for prefix in ("cpu", "mem", "disk", "swap"):
            if getattr(self, f"{prefix}_warning") > getattr(self, f"{prefix}_critical"):
                raise ValueError("警告阈值不能高于严重阈值")
        return self


class ServiceSpec(InputModel):
    name: str = Field(min_length=1, max_length=100)
    candidates: list[str] = Field(min_length=1, max_length=5)
    required: bool = False

    @field_validator("candidates")
    @classmethod
    def valid_units(cls, value: list[str]) -> list[str]:
        if len(set(value)) != len(value) or any(not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.@-]{0,127}", item) for item in value):
            raise ValueError("服务候选名称无效或重复")
        return value


def default_services() -> list[ServiceSpec]:
    return [ServiceSpec(name=name, candidates=candidates) for name, candidates in (
        ("sshd", ["sshd"]), ("crond", ["crond"]), ("chronyd", ["chronyd"]),
        ("firewalld", ["firewalld"]), ("NetworkManager", ["NetworkManager"]),
        ("nginx", ["nginx"]), ("mysqld", ["mysqld"]), ("redis", ["redis"]),
        ("rabbitmq", ["rabbitmqd", "rabbitmq-server", "rabbitmq"]),
        ("docker", ["docker", "dockerd"]), ("minio", ["minio"]),
        ("supervisord", ["supervisord"]), ("prometheus", ["prometheus"]),
        ("node-exporter", ["node-exporter"]), ("mysqld-exporter", ["mysqld-exporter"]),
        ("keepalived", ["keepalived"]), ("DmServiceDMSERVER", ["DmServiceDMSERVER"]),
    )]


class InspectionConfig(InputModel):
    thresholds: Thresholds = Field(default_factory=Thresholds)
    services: list[ServiceSpec] = Field(default_factory=default_services, max_length=30)
    command_timeout_seconds: int = Field(default=30, ge=2, le=120)
    host_timeout_seconds: int = Field(default=180, ge=10, le=600)

    @model_validator(mode="after")
    def valid_config(self) -> "InspectionConfig":
        if self.command_timeout_seconds > self.host_timeout_seconds:
            raise ValueError("命令时限不能超过主机时限")
        if len({item.name for item in self.services}) != len(self.services):
            raise ValueError("服务名称重复")
        return self


class HostSelection(InputModel):
    id: int = Field(gt=0)
    version: int = Field(gt=0)


class InspectionInput(InputModel):
    name: str = Field(min_length=1, max_length=100)
    hosts: list[HostSelection] = Field(min_length=1, max_length=32)
    checks: list[CheckId] = Field(min_length=1, max_length=4)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("任务名称不能为空白")
        return value.strip()

    @model_validator(mode="after")
    def no_duplicates(self) -> "InspectionInput":
        if len({item.id for item in self.hosts}) != len(self.hosts) or len(set(self.checks)) != len(self.checks):
            raise ValueError("主机与检查项不能重复")
        return self


class Metric(BaseModel):
    name: str = Field(max_length=200)
    value: str | float | int | None
    unit: str | None = Field(default=None, max_length=50)

    @field_validator("value")
    @classmethod
    def bounded_value(cls, value: str | float | int | None) -> str | float | int | None:
        if isinstance(value, str) and len(value) > 500:
            raise ValueError("指标文本超出限制")
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("指标必须为有限数值")
        return value


class ResultTable(BaseModel):
    name: str
    columns: list[str]
    rows: list[list[str]]


class Finding(BaseModel):
    severity: Literal["warning", "critical"]
    message: str


class CheckPayload(BaseModel):
    conclusion: Conclusion = "normal"
    metrics: list[Metric] = Field(default_factory=list)
    tables: list[ResultTable] = Field(default_factory=list)
    findings: list[Finding] = Field(default_factory=list)


class TimestampResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    @field_validator("created_at", "started_at", "finished_at", check_fields=False)
    @classmethod
    def utc_timestamp(cls, value: datetime | None) -> datetime | None:
        return value.replace(tzinfo=timezone.utc) if value is not None and value.tzinfo is None else value


class CheckResponse(TimestampResponse):
    check_id: CheckId
    title: str
    status: CheckStatus
    conclusion: Conclusion
    started_at: datetime | None
    finished_at: datetime | None
    error_code: str | None
    payload: CheckPayload


class HostRunResponse(TimestampResponse):
    id: str
    host_id: int
    host_name: str
    address: str
    port: int
    username: str
    group_name: str
    status: RunStatus
    failure_code: str | None
    started_at: datetime | None
    finished_at: datetime | None
    checks: list[CheckResponse]


class TaskSummary(TimestampResponse):
    id: str
    name: str
    status: RunStatus
    check_ids: list[CheckId]
    host_count: int
    completed_hosts: int
    failed_hosts: int
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class TaskDetail(TaskSummary):
    rule_version: str
    config: InspectionConfig
    hosts: list[HostRunResponse]


class TaskPage(BaseModel):
    items: list[TaskSummary]
    total: int


class CheckDefinition(BaseModel):
    id: CheckId
    title: str
    description: str


class InspectionCatalog(BaseModel):
    checks: list[CheckDefinition]
    defaults: InspectionConfig


class ReportResponse(BaseModel):
    filename: str
    content: str
