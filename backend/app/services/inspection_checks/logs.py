import re
import shlex

from ...schemas.inspections import (
    MAX_LOG_QUERY_DAYS,
    UNASSESSED_LOG_TIME_METRIC,
    CheckPayload,
    Finding,
    InspectionConfig,
    Metric,
)
from . import InspectionCheckError, Runner, query, table
from .log_window import TIME_FILTER

KEYWORDS = "error|failed|fatal|panic|crit|critical|异常"
EXCLUSIONS = "systemd-coredump|ldapdb_canonuser_plug_init"


def collect(runner: Runner, config: InspectionConfig) -> CheckPayload:
    days, lines = min(config.logs.days, MAX_LOG_QUERY_DAYS), config.logs.lines
    # 取目标主机时钟，所有来源共用绝对窗口，避免本机时区/时钟和执行先后的偏差。
    clock = query(runner, "command -v date >/dev/null 2>&1 || exit 127; date +%s").strip()
    if not re.fullmatch(r"[0-9]{1,12}", clock):
        raise InspectionCheckError("invalid_output")
    finish = int(clock)
    start = finish - days * 24 * 60 * 60
    sources = [("systemd journal", "command -v journalctl >/dev/null 2>&1 || exit 3; "
                "set -o pipefail; "
                f"journalctl --since @{start} --until @{finish} --output=short-iso -p err..alert --no-pager --quiet "
                f"| {{ grep -viE {shlex.quote(EXCLUSIONS)} || [ \"$?\" -eq 1 ]; }} "
                f"| {{ printf '%s\\n' 'AUTOPS_LOG_WINDOW 0'; tail -n {lines}; }}; "
                "status=$?; if [ \"$status\" -eq 3 ]; then exit 4; fi; exit \"$status\"")]
    for path in config.logs.paths:
        quoted = shlex.quote(path)
        sources.append((path, "command -v readlink >/dev/null 2>&1 || exit 127; "
                       f"path={quoted}; remaining=${{path#/}}; parent=; "
                       "while [[ $remaining == */* ]]; do "
                       "parent=$parent/${remaining%%/*}; remaining=${remaining#*/}; "
                       "if [ ! -e \"$parent\" ]; then "
                       "if [ -L \"$parent\" ]; then exit 4; fi; exit 3; fi; "
                       "if [ ! -d \"$parent\" ] || [ ! -x \"$parent\" ]; then exit 4; fi; "
                       "done; "
                       "if [ ! -e \"$path\" ]; then "
                       "if [ -L \"$path\" ]; then exit 4; fi; exit 3; fi; "
                       "resolved=$(readlink -e -- \"$path\") || exit 4; "
                       "case $resolved in /var/log/*) ;; *) exit 4 ;; esac; "
                       "if [ ! -f \"$resolved\" ] || [ ! -r \"$resolved\" ]; then exit 4; fi; "
                       "command -v awk >/dev/null 2>&1 || exit 127; "
                       f"awk -v start={start} -v finish={finish} -v limit={lines} "
                       f"-v keywords={shlex.quote(KEYWORDS)} {shlex.quote(TIME_FILTER)} \"$resolved\""))

    tables = []
    findings = []
    available = 0
    matched = 0
    unassessed = 0
    for name, command in sources:
        result = runner(command)
        if result.exit_status == 3:
            rows = [["不适用", "journalctl 未安装" if name == "systemd journal" else "日志文件不存在"]]
        elif result.exit_status != 0:
            raise InspectionCheckError("tool_missing" if result.exit_status == 127 else "command_failed")
        else:
            available += 1
            header, separator, content = result.stdout.partition("\n")
            metadata = re.fullmatch(r"AUTOPS_LOG_WINDOW ([0-9]{1,18})", header)
            if not separator or metadata is None:
                raise InspectionCheckError("invalid_output")
            unknown = int(metadata[1])
            entries = content.splitlines()
            if len(entries) > lines:
                raise InspectionCheckError("output_limit")
            matched += len(entries)
            unassessed += unknown
            rows = [["匹配", entry] for entry in entries]
            if entries:
                findings.append(Finding(severity="warning", message=f"{name} 匹配到 {len(entries)} 行错误日志"))
            if unknown:
                message = f"{unknown} 行关键词匹配日志的时间或年份无法确认，未纳入最近 {days} 天的错误日志，不能据此判定无错误"
                rows.append(["时间未判定", message])
                findings.append(Finding(severity="warning", message=f"{name}：{message}"))
            if not rows:
                rows = [["未匹配", f"最近 {days} 天内无符合条件的日志"]]
        tables.append(table(name, ["状态", "日志"], rows))
    if matched:
        conclusion = "warning"
    elif unassessed:
        conclusion = "unknown"
    else:
        conclusion = "normal" if available else "not_applicable"
    metrics = [Metric(name=UNASSESSED_LOG_TIME_METRIC, value=unassessed, unit="行")] if unassessed else []
    return CheckPayload(conclusion=conclusion, findings=findings, tables=tables, metrics=metrics)
