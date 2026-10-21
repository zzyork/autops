import threading

from ..schemas.inspection_analysis import AnalysisEvidence
from ..schemas.inspections import HostRunResponse, ResultTable, TaskDetail
from .inspection_analysis_groups import diagnostic_records
from .inspection_analysis_input import build_input


def display_log_table(table: ResultTable, evidence: list[AnalysisEvidence]) -> ResultTable:
    if not evidence:
        return table

    by_id = {item.id: item for item in evidence}
    grouped_rows: dict[int, list[str]] = {}
    covered_indices: set[int] = set()
    for record in diagnostic_records(evidence, threading.Event()):
        indices = [index for evidence_id in record.evidence_ids
                   for index in by_id[evidence_id].original_indices]
        first_index = min(indices)
        covered_indices.update(indices)
        # 输入限定为同一主机、同一来源表，沿用原逻辑的唯一来源观察与时间统计。
        observation = record.group.observations[0]
        grouped_rows[first_index] = [
            *table.rows[first_index - 1],
            str(record.group.occurrences),
            observation.first_time or "未记录",
            observation.last_time or "未记录",
        ]

    rows: list[list[str]] = []
    for index, row in enumerate(table.rows, 1):
        if index in grouped_rows:
            rows.append(grouped_rows[index])
        elif index not in covered_indices:
            rows.append([*row, "", "", ""])
    return table.model_copy(update={
        "columns": [*table.columns, "出现次数", "首次时间", "末次时间"],
        "rows": rows,
    })


def display_task_logs(task: TaskDetail) -> TaskDetail:
    hosts: list[HostRunResponse] = []
    for host in task.hosts:
        log_check = next((check for check in host.checks if check.check_id == "log_error"), None)
        if log_check is None or log_check.status != "completed":
            hosts.append(host)
            continue

        # 每个主机独立构建原有证据，避免同名、同地址的不同资产共享分组上下文。
        data = build_input(task.model_copy(update={"hosts": [host]}))
        by_table: dict[int, list[AnalysisEvidence]] = {}
        for item in data.evidence:
            if item.kind == "log" and item.source_table_index is not None:
                by_table.setdefault(item.source_table_index, []).append(item)
        tables = [display_log_table(table, by_table.get(index, []))
                  for index, table in enumerate(log_check.payload.tables, 1)]
        payload = log_check.payload.model_copy(update={"tables": tables})
        merged_check = log_check.model_copy(update={"payload": payload})
        checks = [merged_check if check is log_check else check for check in host.checks]
        hosts.append(host.model_copy(update={"checks": checks}))
    return task.model_copy(update={"hosts": hosts})
