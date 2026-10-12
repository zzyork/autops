import ipaddress

from ...schemas.inspections import CheckPayload, InspectionConfig, Metric, is_loopback_listener
from . import InspectionCheckError, Runner, query, table
from .basic import addresses


def collect(runner: Runner, config: InspectionConfig) -> CheckPayload:
    ipv4 = addresses(query(runner, "ip -o -4 addr show"), 4)
    ipv6 = addresses(query(runner, "ip -o -6 addr show"), 6)
    result = runner("ss -H -l -t -u -n")
    if result.exit_status == 127:
        return CheckPayload(
            conclusion="not_applicable", metrics=[Metric(name="监听采集", value="tool_missing")],
            tables=[table("IPv4 地址", ["网卡", "地址/前缀"], ipv4),
                    table("IPv6 地址", ["网卡", "地址/前缀"], ipv6)],
        )
    if result.exit_status != 0:
        raise InspectionCheckError("command_failed")
    rows = []
    for line in result.stdout.splitlines():
        fields = line.split()
        if len(fields) < 6 or fields[0] not in {"tcp", "udp"} or fields[1] not in {"LISTEN", "UNCONN"}:
            raise InspectionCheckError("invalid_output")
        if fields[0] == "tcp" and fields[1] != "LISTEN":
            raise InspectionCheckError("invalid_output")
        endpoint = fields[4]
        try:
            host, port = endpoint.rsplit(":", 1)
            if not host or not port.isdecimal() or not 0 <= int(port) <= 65535:
                raise ValueError
            if host != "*":
                if host.startswith("[") != host.endswith("]"):
                    raise ValueError
                ipaddress.ip_address(host[1:-1] if host.startswith("[") else host)
        except ValueError:
            raise InspectionCheckError("invalid_output") from None
        if not is_loopback_listener(endpoint):
            rows.append([fields[0].upper(), fields[1], endpoint])
    return CheckPayload(
        metrics=[Metric(name="本机监听数量", value=len(rows))],
        tables=[table("IPv4 地址", ["网卡", "地址/前缀"], ipv4),
                table("IPv6 地址", ["网卡", "地址/前缀"], ipv6),
                table("本机监听 TCP/UDP", ["协议", "状态", "本地地址"], rows)],
    )
