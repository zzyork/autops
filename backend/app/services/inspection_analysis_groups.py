"""任务内模板提取；只有显式非诊断字段可以变化，原始证据不进入模型压缩逻辑。"""

import re
import threading
from dataclasses import dataclass, field

from drain3 import TemplateMiner
from drain3.template_miner_config import TemplateMinerConfig
from pydantic import BaseModel, ConfigDict, Field

from ..schemas.inspection_analysis import AnalysisEvidence, DiagnosticGroup, DiagnosticObservation
from .ai_provider import ProviderError
from .inspection_analysis_input import log_message

MAX_SAMPLES = 3
PROCESS_HEADER = re.compile(r"^(?P<service>[A-Za-z0-9_.@/-]+)\[(?P<pid>\d+)\]:\s*")
SYSLOG_HEADER = re.compile(r"^(?P<host>\S+)\s+(?P<service>[A-Za-z0-9_.@/-]+)(?:\[(?P<pid>\d+)\])?:\s*")
SERVICE_FIELD = re.compile(r"\b(?:service|logger|unit)=(?P<service>[A-Za-z0-9_.@/-]+)(?=\s|$)")
NGINX_HEADER = re.compile(r"^(?P<level>\[(?:emerg|alert|crit|error|warn|notice|info|debug)\])\s+\d+#\d+:\s+(?:\*\d+\s+)?")
VOLATILE_FIELDS = re.compile(
    r"(?P<label>\b(?:pid|tid|thread_id|request_id|requestId|trace_id|traceId|span_id))"
    r"(?P<separator>\s*[=:]\s*)(?P<value>[A-Za-z0-9_-]+)(?=\s|[,;]|$)"
)


class LogMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    message: str
    occurrences: int = Field(ge=1)
    first_time: str | None
    last_time: str | None
    result_indices: list[int]


@dataclass
class DiagnosticRecord:
    group: DiagnosticGroup
    evidence_ids: list[str] = field(default_factory=list)
    samples: list[str] = field(default_factory=list)

    def model_input(self) -> dict:
        # 不发送原始行号、逐行原文和完整证据编号；组编号由后端映射。
        return {"id": self.group.id, "template": self.group.template, "service": self.group.service,
                "occurrences": self.group.occurrences, "host_count": self.group.host_count,
                "observations": [item.model_dump() for item in self.group.observations],
                "samples": [sample for sample in self.samples if sample != self.group.template]}


def normalize(item: AnalysisEvidence, message: str) -> tuple[str | None, str, tuple]:
    service = None
    body = message
    # 时间头加已知主机或标准进程 PID 才足以识别 syslog 头，避免剥离普通报错句子。
    stamp = log_message(item.original_lines[0])[1] if item.original_lines else None
    header = SYSLOG_HEADER.match(body) if stamp and (item.source == "systemd journal" or stamp[2] == "syslog") else None
    if header and header["pid"] is None and header["host"] not in (item.host_name, item.address):
        header = None
    if header:
        service = header["service"]
        body = body[header.end():]
    else:
        header = PROCESS_HEADER.match(body)
        if header:
            service = header["service"]
            body = body[header.end():]
        else:
            nginx = NGINX_HEADER.match(body) if "nginx" in item.source.lower() else None
            if nginx:
                service = "nginx"
                body = nginx["level"] + " " + body[nginx.end():]
            else:
                explicit = SERVICE_FIELD.search(body)
                service = explicit["service"] if explicit else None

    pieces: list[tuple[str, str]] = []
    position = 0
    for match in VOLATILE_FIELDS.finditer(body):
        label = match["label"]
        value = match["value"]
        if label in ("pid", "tid", "thread_id") and not value.isdecimal():
            continue
        pieces.append(("text", body[position:match.start("value")]))
        pieces.append(("parameter", label))
        position = match.end("value")
    pieces.append(("text", body[position:]))
    template = "".join(value if kind == "text" else f"<{value}>" for kind, value in pieces)
    # 类型化的保护键避免原文中的 '<pid>' 与真实参数占位符碰撞。
    return service, template, tuple(pieces)


def time_bounds(values: list[str | None]) -> tuple[str | None, str | None]:
    stamps = [(value, log_message(value + " x")[1]) for value in values if value is not None]
    if not stamps:
        return None, None
    if all(stamp is not None for _, stamp in stamps) and len({stamp[2] for _, stamp in stamps}) == 1:
        return min(stamps, key=lambda pair: pair[1][0])[0], max(stamps, key=lambda pair: pair[1][0])[0]
    return stamps[0][0], stamps[-1][0]


def diagnostic_records(evidence: list[AnalysisEvidence], cancel: threading.Event) -> list[DiagnosticRecord]:
    fragments: dict[str, list[AnalysisEvidence]] = {}
    for item in evidence:
        fragments.setdefault(item.group_id or item.id, []).append(item)
    config = TemplateMinerConfig()
    config.drain_sim_th = 1.0
    config.parametrize_numeric_tokens = False
    # 不加载外部配置、持久化状态或设置 LRU 淘汰；每个任务的全部模板都参与覆盖。
    miner = TemplateMiner(config=config)
    prepared = []
    for parts in fragments.values():
        if cancel.is_set():
            raise ProviderError("分析已中断")
        item = parts[0]
        try:
            metadata = LogMetadata.model_validate_json("".join(part.content for part in parts))
        except ValueError as exc:
            raise ProviderError("日志证据结构无效") from exc
        service, template, signature = normalize(item, metadata.message)
        miner.add_log_message(template)
        prepared.append((parts, metadata, service, template, signature))

    grouped: dict[tuple, DiagnosticRecord] = {}
    observation_times: dict[tuple[str, int], list[str | None]] = {}
    for parts, metadata, service, template, signature in prepared:
        if cancel.is_set():
            raise ProviderError("分析已中断")
        cluster = miner.match(template)
        if cluster is None:
            raise ProviderError("日志模板匹配不完整")
        item = parts[0]
        # Drain 的候选簇必须再通过精确保护键，错误码、IP、路径与未知字段不可泛化。
        key = (service, None if service else item.source, signature, cluster.cluster_id)
        if key not in grouped:
            grouped[key] = DiagnosticRecord(DiagnosticGroup(
                id=f"D{len(grouped) + 1}", template=template, service=service,
                occurrences=metadata.occurrences, host_count=1, observations=[]))
        record = grouped[key]
        record.evidence_ids.extend(part.id for part in parts)
        if metadata.message not in record.samples and len(record.samples) < MAX_SAMPLES:
            record.samples.append(metadata.message)
        observation = next((entry for entry in record.group.observations
                            if (entry.host_name, entry.address, entry.source) ==
                            (item.host_name, item.address, item.source)), None)
        if observation is None:
            observation = DiagnosticObservation(host_name=item.host_name, address=item.address,
                                                source=item.source, occurrences=metadata.occurrences)
            record.group.observations.append(observation)
        else:
            observation.occurrences += metadata.occurrences
        index = record.group.observations.index(observation)
        times = observation_times.setdefault((record.group.id, index), [])
        times.extend((metadata.first_time, metadata.last_time))
    for record in grouped.values():
        for index, observation in enumerate(record.group.observations):
            observation.first_time, observation.last_time = time_bounds(observation_times[(record.group.id, index)])
        record.group.occurrences = sum(item.occurrences for item in record.group.observations)
        record.group.host_count = len({(item.host_name, item.address) for item in record.group.observations})
    ids = [item for record in grouped.values() for item in record.evidence_ids]
    if len(ids) != len(evidence) or len(set(ids)) != len(ids) or set(ids) != {item.id for item in evidence}:
        raise ProviderError("诊断组证据覆盖不完整")
    return list(grouped.values())
