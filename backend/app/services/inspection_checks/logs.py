import shlex

from ...schemas.inspections import CheckPayload, Finding, InspectionConfig
from . import InspectionCheckError, Runner, table

KEYWORDS = "error|failed|fatal|panic|crit|critical|异常"
EXCLUSIONS = "systemd-coredump|ldapdb_canonuser_plug_init"


def collect(runner: Runner, config: InspectionConfig) -> CheckPayload:
    days, lines = config.logs.days, config.logs.lines
    sources = [("systemd journal", "command -v journalctl >/dev/null 2>&1 || exit 3; "
                "set -o pipefail; "
                f"journalctl --since {shlex.quote(f'{days} days ago')} -p err..alert --no-pager --quiet "
                f"| {{ grep -viE {shlex.quote(EXCLUSIONS)} || [ \"$?\" -eq 1 ]; }} | tail -n {lines}; "
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
                       "set -o pipefail; "
                       f"grep -aiE {shlex.quote(KEYWORDS)} -- \"$resolved\" "
                       f"| tail -n {lines}"))

    tables = []
    findings = []
    available = 0
    for name, command in sources:
        result = runner(command)
        if result.exit_status == 3:
            rows = [["不适用", "journalctl 未安装" if name == "systemd journal" else "日志文件不存在"]]
        elif result.exit_status != 0 and not (name != "systemd journal" and result.exit_status == 1 and not result.stdout and not result.stderr):
            raise InspectionCheckError("tool_missing" if result.exit_status == 127 else "command_failed")
        else:
            available += 1
            entries = result.stdout.splitlines()
            if len(entries) > lines:
                raise InspectionCheckError("output_limit")
            rows = [["匹配", entry] for entry in entries] if entries else [["未匹配", "无符合条件的日志"]]
            if entries:
                findings.append(Finding(severity="warning", message=f"{name} 匹配到 {len(entries)} 行错误日志"))
        tables.append(table(name, ["状态", "日志"], rows))
    return CheckPayload(conclusion="warning" if findings else "normal" if available else "not_applicable",
                        findings=findings, tables=tables)
