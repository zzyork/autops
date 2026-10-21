import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone

from ..inspection_models import InspectionTask
from ..schemas.inspection_analysis import AnalysisEvidence
from ..schemas.inspections import UNASSESSED_LOG_TIME_METRIC, CheckPayload, TaskDetail

MAX_BATCH_CHARACTERS = 24_000
MAX_BATCH_RECORDS = 40
MAX_RECORD_CHARACTERS = 8000
LOG_TIMESTAMP = re.compile(
    r"^\[?(?:(?P<iso>\d{4}[-/]\d{2}[-/]\d{2}[T ]\d{2}:\d{2}:\d{2}"
    r"(?:[.,]\d+)?(?:Z|[+-]\d{2}:?\d{2})?)|"
    r"(?P<syslog>(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
    r"\s{1,2}\d{1,2}\s+\d{2}:\d{2}:\d{2}))\]?\s+"
)
LOG_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


@dataclass
class AnalysisInput:
    evidence: list[AnalysisEvidence]
    host_count: int
    finding_count: int
    log_count: int
    incomplete_count: int
    unassessed_count: int
    task_name: str
    task_status: str
    started_at: datetime | None
    finished_at: datetime | None
    check_ids: list[str]


@dataclass
class LogGroup:
    source: str
    message: str
    result_indices: list[int]
    source_table_index: int
    original_lines: list[str] = field(default_factory=list)
    timestamps: list[tuple[datetime, str, str]] = field(default_factory=list)


def serialize(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def log_message(value: str) -> tuple[str, tuple[datetime, str, str] | None]:
    match = LOG_TIMESTAMP.match(value)
    if match is None:
        return value, None
    stamp = match.group("iso") or match.group("syslog")
    try:
        if match.group("iso"):
            parsed = datetime.fromisoformat(stamp.replace("Z", "+00:00").replace(",", ".").replace("/", "-"))
            parsed = parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)
        else:
            month, day, clock = stamp.split()
            parsed = datetime(1900, LOG_MONTHS.index(month) + 1, int(day),
                              *(int(part) for part in clock.split(":")), tzinfo=timezone.utc)
    except ValueError:
        return value, None
    return value[match.end():], (parsed, stamp, "iso" if match.group("iso") else "syslog")


def build_input(task: InspectionTask | TaskDetail) -> AnalysisInput:
    evidence: list[AnalysisEvidence] = []
    finding_count = log_count = incomplete_count = unassessed_count = 0

    def add(host, kind: str, title: str, source: str, content: str, severity: str = "info",
            incomplete: bool = False, limited: bool = False,
            original_lines: list[str] | None = None, source_table_index: int | None = None,
            original_indices: list[int] | None = None) -> None:
        # 分段只改变报告证据组织，诊断组构建时还原，原文与位置保留在首片段。
        parts = [content[index:index + MAX_RECORD_CHARACTERS]
                  for index in range(0, len(content), MAX_RECORD_CHARACTERS)] or [""]
        group_id = f"E{len(evidence) + 1}"
        for index, part in enumerate(parts):
            evidence.append(AnalysisEvidence(
                id=f"E{len(evidence) + 1}", kind=kind, host_name=host.host_name, address=host.address,
                check_title=title, source=source,
                content=part, severity=severity, incomplete=incomplete, limited=limited, group_id=group_id,
                original_lines=original_lines if index == 0 and original_lines is not None else [],
                original_indices=original_indices if index == 0 and original_indices is not None else [],
                source_table_index=source_table_index))

    for host in task.hosts:
        for check in host.checks:
            payload = CheckPayload.model_validate(check.payload)
            incomplete_count += check.status != "completed"
            limited = check.status == "completed" and check.conclusion in ("not_applicable", "unknown")
            unassessed_logs = check.status == "completed" and check.check_id == "log_error" and any(
                metric.name == UNASSESSED_LOG_TIME_METRIC and isinstance(metric.value, (int, float)) and metric.value > 0
                for metric in payload.metrics
            )
            unassessed_count += limited or unassessed_logs
            if unassessed_logs:
                add(host, "check", check.title, "日志时间范围",
                    "部分关键词匹配日志的时间或年份无法确认，未纳入本次时间窗口，不能作为无错误依据。",
                    limited=True)
            if check.check_id == "log_error":
                log_count += sum(1 for table in payload.tables for row in table.rows
                                 if len(row) >= 2 and row[0] == "匹配")
                if check.status != "completed" or limited:
                    continue
                groups: dict[tuple[int, str], LogGroup] = {}
                for table_index, table in enumerate(payload.tables, 1):
                    for index, row in enumerate(table.rows):
                        if len(row) < 2 or row[0] != "匹配":
                            continue
                        message, stamp = log_message(row[1])
                        key = (table_index, message)
                        if key not in groups:
                            groups[key] = LogGroup(table.name, message, [], table_index)
                        group = groups[key]
                        group.result_indices.append(index + 1)
                        group.original_lines.append(row[1])
                        if stamp is not None:
                            group.timestamps.append(stamp)
                for group in groups.values():
                    if group.timestamps and len({item[2] for item in group.timestamps}) == 1:
                        first = min(group.timestamps, key=lambda item: item[0])[1]
                        last = max(group.timestamps, key=lambda item: item[0])[1]
                    else:
                        # syslog 无年份；混合格式时只能保留原始出现顺序。
                        first = group.timestamps[0][1] if group.timestamps else None
                        last = group.timestamps[-1][1] if group.timestamps else None
                    add(host, "log", check.title, group.source, serialize({
                        "occurrences": len(group.result_indices),
                        "first_time": first, "last_time": last,
                        "result_indices": group.result_indices, "message": group.message}),
                        original_lines=group.original_lines, source_table_index=group.source_table_index,
                        original_indices=group.result_indices)
            elif check.status == "completed" and not limited:
                for index, finding in enumerate(payload.findings):
                    finding_count += 1
                    add(host, "finding", check.title, f"发现 {index + 1}", finding.message, finding.severity)
                if not payload.findings and check.conclusion in ("warning", "critical"):
                    finding_count += 1
                    add(host, "finding", check.title, "风险结论", serialize({
                        "conclusion": check.conclusion,
                        "metrics": [metric.model_dump() for metric in payload.metrics]}), check.conclusion)
    def timestamp(value: datetime | None) -> datetime | None:
        return value.replace(tzinfo=timezone.utc) if value is not None and value.tzinfo is None else value

    return AnalysisInput(evidence, len(task.hosts), finding_count, log_count, incomplete_count, unassessed_count,
                         task.name, task.status, timestamp(task.started_at), timestamp(task.finished_at), task.check_ids)


def batches(evidence: list[AnalysisEvidence]) -> list[list[AnalysisEvidence]]:
    result: list[list[AnalysisEvidence]] = []
    current: list[AnalysisEvidence] = []
    size = 2
    for item in evidence:
        item_size = len(serialize(item.model_dump())) + 1
        if item_size > MAX_BATCH_CHARACTERS:
            raise ValueError("单条分析证据超限")
        if current and (size + item_size > MAX_BATCH_CHARACTERS or len(current) >= MAX_BATCH_RECORDS):
            result.append(current)
            current, size = [], 2
        current.append(item)
        size += item_size
    if current:
        result.append(current)
    return result
