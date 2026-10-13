import json
from dataclasses import dataclass
from datetime import datetime, timezone

from ..inspection_models import InspectionTask
from ..schemas.inspection_analysis import AnalysisEvidence
from ..schemas.inspections import CheckPayload

MAX_BATCH_CHARACTERS = 24_000
MAX_BATCH_RECORDS = 40
MAX_RECORD_CHARACTERS = 8000


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


def serialize(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def build_input(task: InspectionTask) -> AnalysisInput:
    evidence: list[AnalysisEvidence] = []
    finding_count = log_count = incomplete_count = unassessed_count = 0

    def add(host, kind: str, title: str, source: str, content: str, severity: str = "info",
            incomplete: bool = False, limited: bool = False) -> None:
        # 上下文分段只改变模型输入组织，保留全部字符与结果序号。
        parts = [content[index:index + MAX_RECORD_CHARACTERS]
                 for index in range(0, len(content), MAX_RECORD_CHARACTERS)] or [""]
        for index, part in enumerate(parts):
            evidence.append(AnalysisEvidence(
                id=f"E{len(evidence) + 1}", kind=kind, host_name=host.host_name, address=host.address,
                check_title=title, source=source + (f"（片段 {index + 1}/{len(parts)}）" if len(parts) > 1 else ""),
                content=part, severity=severity, incomplete=incomplete, limited=limited))

    for host in task.hosts:
        add(host, "host", "服务器执行", "执行范围", serialize({
            "status": host.status, "failure_code": host.failure_code,
            "started_at": str(host.started_at), "finished_at": str(host.finished_at)}),
            incomplete=host.status != "completed")
        for check in host.checks:
            payload = CheckPayload.model_validate(check.payload)
            incomplete_count += check.status != "completed"
            limited = check.status == "completed" and check.conclusion in ("not_applicable", "unknown")
            unassessed_count += limited
            context = {"status": check.status, "conclusion": check.conclusion, "error_code": check.error_code,
                       "started_at": str(check.started_at), "finished_at": str(check.finished_at),
                       "metrics": [metric.model_dump() for metric in payload.metrics]}
            if check.check_id == "log_error":
                context["scan_scope"] = task.config.get("logs")
            if check.check_id != "log_error":
                context["tables"] = [table.model_dump() for table in payload.tables]
            add(host, "check", check.title, "检查上下文", serialize(context),
                check.conclusion if check.conclusion in ("critical", "warning") else "info",
                incomplete=check.status != "completed", limited=limited)
            for index, finding in enumerate(payload.findings):
                finding_count += 1
                add(host, "finding", check.title, f"发现 {index + 1}", finding.message, finding.severity)
            if check.check_id == "log_error":
                for table in payload.tables:
                    for index, row in enumerate(table.rows):
                        matched = len(row) >= 2 and row[0] == "匹配"
                        log_count += matched
                        add(host, "log" if matched else "check", check.title,
                            f"{table.name} · 结果序号 {index + 1}", serialize({"columns": table.columns, "row": row}))
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
