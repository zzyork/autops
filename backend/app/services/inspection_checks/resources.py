import math
import re

from ...schemas.inspections import CheckPayload, Finding, InspectionConfig, Metric
from . import InspectionCheckError, Runner, percentage, query, table

PSEUDO_FILESYSTEMS = {
    "tmpfs", "devtmpfs", "proc", "sysfs", "cgroup", "cgroup2", "devpts",
    "securityfs", "debugfs", "tracefs", "configfs", "pstore", "mqueue", "hugetlbfs", "autofs",
}


def integer(value: str) -> int:
    if not value.isdecimal():
        raise InspectionCheckError("invalid_output")
    return int(value)


def number(value: str) -> float:
    try:
        result = float(value)
    except ValueError:
        raise InspectionCheckError("invalid_output") from None
    if not math.isfinite(result) or result < 0:
        raise InspectionCheckError("invalid_output")
    return result


def cpu_usage(output: str) -> float:
    lines = output.splitlines()
    if len(lines) != 2:
        raise InspectionCheckError("invalid_output")
    samples = []
    for line in lines:
        fields = line.split()
        if len(fields) < 9 or fields[0] != "cpu":
            raise InspectionCheckError("invalid_output")
        samples.append([integer(field) for field in fields[1:9]])
    before, after = samples
    deltas = [end - start for start, end in zip(before, after)]
    total = sum(deltas)
    if min(deltas) < 0 or total <= 0:
        raise InspectionCheckError("invalid_output")
    # /proc/stat 的 guest 字段包含在 user/nice 中，不能重复计入总量。
    return percentage(100 * (total - deltas[3] - deltas[4]) / total)


def memory(output: str) -> dict[str, int]:
    values = {}
    for line in output.splitlines():
        match = re.fullmatch(r"([A-Za-z_()]+):\s+(\d+) kB", line.strip())
        if match:
            values[match[1]] = integer(match[2])
    required = ("MemTotal", "MemAvailable", "SwapTotal", "SwapFree")
    if any(key not in values for key in required):
        raise InspectionCheckError("invalid_output")
    if values["MemTotal"] <= 0 or values["MemAvailable"] > values["MemTotal"] or values["SwapFree"] > values["SwapTotal"]:
        raise InspectionCheckError("invalid_output")
    return values


def disks(output: str) -> list[tuple[list[str], float]]:
    lines = output.splitlines()
    if not lines or not lines[0].startswith("Filesystem "):
        raise InspectionCheckError("invalid_output")
    result = []
    for line in lines[1:]:
        parts = line.split(None, 6)
        if len(parts) != 7 or not parts[6]:
            raise InspectionCheckError("invalid_output")
        device, fs_type, size, used, available, capacity, mount = parts
        size_k, used_k, available_k = integer(size), integer(used), integer(available)
        if size_k <= 0 or used_k > size_k or available_k > size_k or not re.fullmatch(r"\d+%", capacity):
            raise InspectionCheckError("invalid_output")
        value = percentage(float(capacity[:-1]))
        if fs_type not in PSEUDO_FILESYSTEMS:
            result.append(([device, fs_type, mount, size, used, available, capacity], value))
    return result


def processes(output: str) -> list[list[str]]:
    lines = output.splitlines()
    if not lines or lines[0].split() != ["USER", "PID", "%CPU", "%MEM", "COMMAND"]:
        raise InspectionCheckError("invalid_output")
    rows = []
    for line in lines[1:]:
        fields = line.split()
        if len(fields) != 5 or not fields[4] or integer(fields[1]) <= 0:
            raise InspectionCheckError("invalid_output")
        number(fields[2])  # ps 的多核 CPU 百分比可超过 100。
        percentage(number(fields[3]))
        rows.append(fields)
    return rows


def collect(runner: Runner, config: InspectionConfig) -> CheckPayload:
    cpu = cpu_usage(query(runner, "head -n 1 /proc/stat && sleep 1 && head -n 1 /proc/stat"))
    load_fields = query(runner, "cat /proc/loadavg").split()
    if len(load_fields) != 5:
        raise InspectionCheckError("invalid_output")
    loads = [number(value) for value in load_fields[:3]]
    mem = memory(query(runner, "cat /proc/meminfo"))
    mem_percent = percentage(100 * (mem["MemTotal"] - mem["MemAvailable"]) / mem["MemTotal"])
    swap_percent = (percentage(100 * (mem["SwapTotal"] - mem["SwapFree"]) / mem["SwapTotal"])
                    if mem["SwapTotal"] else None)
    disk_rows = disks(query(runner, "df -PT -k"))
    if not disk_rows:
        raise InspectionCheckError("no_monitored_disks")
    cpu_rows = processes(query(runner, "ps -eo user,pid,pcpu,pmem,comm --sort=-pcpu | head -n 11"))
    mem_rows = processes(query(runner, "ps -eo user,pid,pcpu,pmem,comm --sort=-pmem | head -n 11"))
    thresholds = config.thresholds
    findings = []

    def evaluate(label: str, value: float | None, warning: float, critical: float) -> None:
        if value is None:
            return
        if value >= critical:
            findings.append(Finding(severity="critical", message=f"{label} {value}% >= 严重阈值 {critical}%"))
        elif value >= warning:
            findings.append(Finding(severity="warning", message=f"{label} {value}% >= 警告阈值 {warning}%"))

    evaluate("CPU 使用率", cpu, thresholds.cpu_warning, thresholds.cpu_critical)
    evaluate("内存使用率", mem_percent, thresholds.mem_warning, thresholds.mem_critical)
    evaluate("Swap 使用率", swap_percent, thresholds.swap_warning, thresholds.swap_critical)
    for row, value in disk_rows:
        evaluate(f"磁盘 {row[2]} 使用率", value, thresholds.disk_warning, thresholds.disk_critical)
    conclusion = "critical" if any(f.severity == "critical" for f in findings) else "warning" if findings else "normal"
    return CheckPayload(
        conclusion=conclusion, findings=findings,
        metrics=[Metric(name="CPU 使用率", value=cpu, unit="%"),
                 *(Metric(name=f"负载 {period}", value=value) for period, value in zip(("1m", "5m", "15m"), loads)),
                 Metric(name="内存使用率 (MemTotal - MemAvailable)", value=mem_percent, unit="%"),
                 Metric(name="Swap 使用率", value=swap_percent, unit="%"),
                 Metric(name="磁盘数量", value=len(disk_rows))],
        tables=[table("磁盘", ["设备", "类型", "挂载点", "总量 KiB", "已用 KiB", "可用 KiB", "使用率"],
                      [row for row, _ in disk_rows]),
                table("CPU TOP10", ["用户", "PID", "%CPU", "%MEM", "进程名"], cpu_rows),
                table("内存 TOP10", ["用户", "PID", "%CPU", "%MEM", "进程名"], mem_rows)],
    )
