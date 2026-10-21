import ipaddress
import math
import re
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

CheckId = Literal["server_info", "system_resources", "service_status", "network_info", "log_error"]
RunStatus = Literal["queued", "running", "completed", "partial", "failed", "interrupted"]
CheckStatus = Literal["queued", "running", "completed", "failed", "skipped", "interrupted"]
Conclusion = Literal["normal", "warning", "critical", "not_applicable", "unknown"]
MAX_LOG_QUERY_DAYS = 30
UNASSESSED_LOG_TIME_METRIC = "时间未判定的错误日志行数"


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


def default_log_paths() -> list[str]:
    return [
        "/var/log/messages", "/var/log/secure", "/var/log/nginx/error.log",
        "/var/log/mysql/error.log", "/var/log/mysqld.log",
        "/var/log/rabbitmq/rabbitmqd-error.log",
    ]


class LogRules(InputModel):
    # 保留历史任务快照的读取范围；新规则保存及实际查询另限最多 30 天。
    days: int = Field(default=MAX_LOG_QUERY_DAYS, ge=1, le=365, strict=True)
    lines: int = Field(default=200, ge=1, le=200, strict=True)
    paths: list[str] = Field(default_factory=default_log_paths, max_length=12)

    @field_validator("paths")
    @classmethod
    def valid_paths(cls, value: list[str]) -> list[str]:
        if len(set(value)) != len(value) or any(
            len(path) > 240 or not path.startswith("/var/log/") or
            any(part in ("", ".", "..") for part in path[len("/var/log/"):].split("/")) or
            any(ord(char) < 32 or ord(char) == 127 for char in path)
            for path in value
        ):
            raise ValueError("日志路径须为 /var/log/ 下不重复的规范路径，不得包含控制字符或相对路径段")
        return value


class InspectionConfig(InputModel):
    thresholds: Thresholds = Field(default_factory=Thresholds)
    services: list[ServiceSpec] = Field(default_factory=default_services, max_length=30)
    logs: LogRules = Field(default_factory=LogRules)
    command_timeout_seconds: int = Field(default=30, ge=2, le=120)
    host_timeout_seconds: int = Field(default=180, ge=10, le=600)

    @model_validator(mode="after")
    def valid_config(self) -> "InspectionConfig":
        if self.command_timeout_seconds > self.host_timeout_seconds:
            raise ValueError("命令时限不能超过主机时限")
        if len({item.name for item in self.services}) != len(self.services):
            raise ValueError("服务名称重复")
        return self


class LogRulesSave(LogRules):
    days: int = Field(default=MAX_LOG_QUERY_DAYS, ge=1, le=MAX_LOG_QUERY_DAYS, strict=True)


class InspectionConfigSave(InspectionConfig):
    logs: LogRulesSave = Field(default_factory=LogRulesSave)

    @model_validator(mode="before")
    @classmethod
    def complete_rules(cls, value: object) -> object:
        if not isinstance(value, dict):
            return value
        missing = cls.model_fields.keys() - value.keys()
        if missing:
            raise ValueError(f"保存规则缺少字段: {', '.join(sorted(missing))}")
        thresholds = value["thresholds"]
        if isinstance(thresholds, dict):
            missing = Thresholds.model_fields.keys() - thresholds.keys()
            if missing:
                raise ValueError(f"保存规则缺少阈值: {', '.join(sorted(missing))}")
        services = value["services"]
        if isinstance(services, list) and any(isinstance(item, dict) and "required" not in item for item in services):
            raise ValueError("保存规则缺少服务 required 字段")
        logs = value["logs"]
        if isinstance(logs, dict):
            missing = LogRules.model_fields.keys() - logs.keys()
            if missing:
                raise ValueError(f"保存规则缺少日志字段: {', '.join(sorted(missing))}")
        return value


class HostSelection(InputModel):
    id: int = Field(gt=0)
    version: int = Field(gt=0)


class InspectionInput(InputModel):
    name: str = Field(min_length=1, max_length=100)
    hosts: list[HostSelection] = Field(min_length=1, max_length=32)
    checks: list[CheckId] = Field(min_length=1, max_length=5)

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


def is_loopback_listener(endpoint: str) -> bool:
    host, separator, _port = endpoint.rpartition(":")
    if not separator:
        return False
    try:
        address = ipaddress.ip_address(host[1:-1] if host.startswith("[") and host.endswith("]") else host)
    except ValueError:
        return False
    return address.is_loopback or (address.version == 6 and address.ipv4_mapped is not None
                                   and address.ipv4_mapped.is_loopback)


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

    @model_validator(mode="after")
    def display_payload(self) -> "CheckResponse":
        if self.check_id not in ("service_status", "network_info"):
            return self
        tables: list[ResultTable] = []
        for item in self.payload.tables:
            if self.check_id == "service_status" and item.name == "服务状态":
                rows = [row for row in item.rows if not (len(row) >= 3 and row[1] == "未安装" and row[2] == "not-found")]
            elif self.check_id == "network_info" and item.name == "本机监听 TCP/UDP":
                rows = [row for row in item.rows if not (len(row) >= 3 and is_loopback_listener(row[2]))]
            else:
                rows = item.rows
            tables.append(item.model_copy(update={"rows": rows}))
        metrics = self.payload.metrics
        if self.check_id == "network_info":
            listeners = next((item for item in tables if item.name == "本机监听 TCP/UDP"), None)
            if listeners is not None:
                metrics = [metric.model_copy(update={"value": len(listeners.rows)})
                           if metric.name == "本机监听数量" else metric for metric in metrics]
        self.payload = self.payload.model_copy(update={"tables": tables, "metrics": metrics})
        return self


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
