import ipaddress

from .common import OperationSpec, OperationStep, action, boolean, field, fields, quote, read_spec, text, tools

TITLE = "主机名"
ACTIONS = [
    action("query", "查看主机名", "读取当前主机名", False, []),
    action("set", "设置主机名", "可选添加指定 IP 的受管 hosts 条目", True, [
        field("hostname", "新主机名"),
        field("add_hosts", "维护 hosts 条目", "boolean", False, default=False),
        field("ip", "hosts IP 地址", required=False),
    ]),
]
HOST_RE = r"(?=.{1,253}\Z)[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)*"


def hostname_script(body: str) -> str:
    # Hostname operations do not depend on a distribution or package manager.
    return "set -euo pipefail\n" + body


def inspect() -> str:
    return hostname_script("hostname")


def build(name: str, params: dict) -> OperationSpec:
    if name == "query":
        fields(params, set())
        return read_spec("查看主机名", inspect())
    fields(params, {"hostname", "add_hosts", "ip"}, {"hostname"})
    host = text(params, "hostname", HOST_RE, "主机名")
    add = boolean(params, "add_hosts")
    if add:
        raw = params.get("ip")
        if not isinstance(raw, str):
            raise ValueError("添加 hosts 条目需要显式 IP")
        try:
            ip = str(ipaddress.ip_address(raw))
        except ValueError:
            raise ValueError("hosts IP 地址无效") from None
    elif "ip" in params:
        raise ValueError("未启用 hosts 条目时不能提供 IP")
    marker = "# autops hostname"
    pre = tools("hostnamectl", "hostname") + "\nhostnamectl --static\nhostname"
    steps = [OperationStep("设置主机名", hostname_script(f"hostnamectl set-hostname {quote(host)}"))]
    verify = f"test \"$(hostnamectl --static)\" = {quote(host)}\ntest \"$(hostname)\" = {quote(host)}"
    if add:
        check = f"""test -f /etc/hosts && test ! -L /etc/hosts
awk -v host={quote(host)} -v marker={quote(marker)} '
  $0 !~ marker && $0 !~ /^[[:space:]]*#/ {{
    for (i=2; i<=NF; i++) if ($i == host) exit 1
  }}' /etc/hosts"""
        pre += "\n" + tools("mktemp", "cp", "mv", "sha256sum", "awk") + "\n" + check + "\nsha256sum /etc/hosts"
        change = f"""{check}
tmp=$(mktemp /etc/.autops-hosts.XXXXXX)
trap 'rm -f -- "$tmp"' EXIT
awk -v marker={quote(marker)} 'index($0, marker) == 0' /etc/hosts > "$tmp"
printf '%s\\n' {quote(ip + ' ' + host + ' ' + marker)} >> "$tmp"
cp --attributes-only --preserve=all -- /etc/hosts "$tmp"
mv -f -- "$tmp" /etc/hosts"""
        steps.append(OperationStep("更新受管 hosts 条目", hostname_script(change)))
        verify += f"\ngrep -Fx -- {quote(ip + ' ' + host + ' ' + marker)} /etc/hosts >/dev/null"
    return OperationSpec("设置主机名", True, hostname_script(pre), tuple(steps), hostname_script(verify))
