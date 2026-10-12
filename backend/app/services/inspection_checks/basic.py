import ipaddress
import re
import shlex

from ...schemas.inspections import CheckPayload, InspectionConfig, Metric
from . import InspectionCheckError, Runner, query, table


def addresses(output: str, family: int) -> list[list[str]]:
    rows = []
    token = "inet" if family == 4 else "inet6"
    for line in output.splitlines():
        parts = line.split()
        if len(parts) < 4 or not parts[0].rstrip(":").isdigit() or parts[2] != token:
            raise InspectionCheckError("invalid_output")
        try:
            address = ipaddress.ip_interface(parts[3])
        except ValueError:
            raise InspectionCheckError("invalid_output") from None
        if address.version != family:
            raise InspectionCheckError("invalid_output")
        rows.append([parts[1], str(address)])
    return rows


def collect(runner: Runner, config: InspectionConfig) -> CheckPayload:
    hostname = query(runner, "hostname").strip()
    release = query(runner, "cat /etc/os-release")
    kernel = query(runner, "uname -r").strip()
    uptime = query(runner, "cat /proc/uptime").split()
    if not hostname or not kernel or not uptime:
        raise InspectionCheckError("invalid_output")
    try:
        seconds = float(uptime[0])
        if seconds < 0 or seconds == float("inf") or seconds != seconds:
            raise ValueError
    except ValueError:
        raise InspectionCheckError("invalid_output") from None
    pretty_name = None
    for line in release.splitlines():
        if line.startswith("PRETTY_NAME="):
            try:
                fields = shlex.split(line.partition("=")[2])
            except ValueError:
                raise InspectionCheckError("invalid_output") from None
            if len(fields) != 1 or not fields[0]:
                raise InspectionCheckError("invalid_output")
            pretty_name = fields[0]
    if pretty_name is None or not re.fullmatch(r"[^\r\n]+", pretty_name):
        raise InspectionCheckError("invalid_output")
    ipv4 = addresses(query(runner, "ip -o -4 addr show"), 4)
    ipv6 = addresses(query(runner, "ip -o -6 addr show"), 6)
    return CheckPayload(
        metrics=[Metric(name="主机名", value=hostname), Metric(name="操作系统", value=pretty_name),
                 Metric(name="内核", value=kernel), Metric(name="运行时长", value=round(seconds), unit="秒")],
        tables=[table("IPv4 地址", ["网卡", "地址/前缀"], ipv4),
                table("IPv6 地址", ["网卡", "地址/前缀"], ipv6)],
    )
