import re

from .common import OperationSpec, OperationStep, action, choice, field, fields, quote, shell, tools

TITLE = "防火墙"
SCOPE = ["runtime", "permanent"]
ACTIONS = [
    action("start", "启动 firewalld", "检查默认及已绑定 zone 的持久 SSH 通路；复杂规则需人工核验", True, []),
    action("stop", "停止 firewalld", "仅停止本次运行", True, []),
    action("enable", "启用开机自启", "停止状态也检查持久 SSH 通路；复杂规则需人工核验", True, []),
    action("disable", "关闭开机自启", "不改变运行状态", True, []),
    action("add_service", "开放服务", "指定 zone 与生效范围", True, [
        field("zone", "Zone"), field("service", "服务"),
        field("scope", "生效范围", "select", options=[{"label": "运行态", "value": "runtime"}, {"label": "持久态", "value": "permanent"}]),
    ]),
    action("remove_service", "移除服务", "禁止移除 SSH 服务或 SSH 监听端口", True, [
        field("zone", "Zone"), field("service", "服务"),
        field("scope", "生效范围", "select", options=[{"label": "运行态", "value": "runtime"}, {"label": "持久态", "value": "permanent"}]),
    ]),
    action("add_port", "开放端口", "端口格式如 443/tcp", True, [
        field("zone", "Zone"), field("port", "端口/协议"), field("scope", "生效范围", "select", options=[{"label": "运行态", "value": "runtime"}, {"label": "持久态", "value": "permanent"}]),
    ]),
    action("remove_port", "移除端口", "禁止移除 SSH 监听端口", True, [
        field("zone", "Zone"), field("port", "端口/协议"), field("scope", "生效范围", "select", options=[{"label": "运行态", "value": "runtime"}, {"label": "持久态", "value": "permanent"}]),
    ]),
    action("reload", "重载防火墙", "丢弃仅运行态规则，检查持久 SSH 通路", True, []),
]


def inspect() -> str:
    return shell(firewall_state() + """
systemctl show firewalld -p ActiveState -p UnitFileState
""" + permanent_snapshot() + """
if test "$fw_state" = active; then firewall-cmd --list-all-zones; fi""")


def firewall_state() -> str:
    return """command -v systemctl >/dev/null || exit 1
fw_state=$(systemctl show firewalld -p ActiveState --value)
case "$fw_state" in
  active) command -v firewall-cmd >/dev/null || { echo '缺少 firewall-cmd' >&2; exit 1; }
          fw_perm=(firewall-cmd --permanent) ;;
  inactive) command -v firewall-offline-cmd >/dev/null || { echo '缺少 firewall-offline-cmd' >&2; exit 1; }
            fw_perm=(firewall-offline-cmd) ;;
  *) echo "不支持的 firewalld 状态: $fw_state" >&2; exit 1 ;;
esac"""


def default_zone() -> str:
    return 'if test "$fw_state" = active; then firewall-cmd --get-default-zone; else firewall-offline-cmd --get-default-zone; fi'


def permanent_snapshot() -> str:
    return """unit_state=$(systemctl show firewalld -p UnitFileState --value)
test -n "$unit_state" || { echo '无法读取 firewalld 开机状态' >&2; exit 1; }
printf 'state=%s unit=%s\\n' "$fw_state" "$unit_state"
""" + default_zone() + """
"${fw_perm[@]}" --list-all-zones"""


def ssh_port() -> str:
    return """command -v sshd >/dev/null || { echo '无法检查 SSH 监听端口' >&2; exit 1; }
ssh_ports=$(sshd -T | awk '$1 == "port" {print $2}')
test -n "$ssh_ports" || exit 1
for p in $ssh_ports; do [[ "$p" =~ ^[0-9]+$ ]] && ((p >= 1 && p <= 65535)) || exit 1; done"""


def ssh_zones() -> str:
    return ssh_port() + r"""
check_scope() {
  local zone port target rich policies direct names zones default definition rc active interfaces sources
  local -a fw=("$@")
  policies=$("${fw[@]}" --get-policies)
  case "$policies" in
    '') ;;
    allow-host-ipv6)
      # Only the shipped INPUT ICMPv6 policy is understood; overrides fail closed.
      definition=$("${fw[@]}" --info-policy=allow-host-ipv6)
      printf '%s\n' "$definition" | awk '
        NR == 1 {if ($1 != "allow-host-ipv6" || (NF != 1 && !(NF == 2 && $2 ~ /^\((active|inactive)\)$/))) bad=1; next}
        {sub(/^[[:space:]]+/, ""); sub(/[[:space:]]+$/, "")}
        /^rich rules:$/ {rich=1; next}
        rich {
          if ($0 == "rule family=\"ipv6\" icmp-type name=\"neighbour-advertisement\" accept") seen["na"]++
          else if ($0 == "rule family=\"ipv6\" icmp-type name=\"neighbour-solicitation\" accept") seen["ns"]++
          else if ($0 == "rule family=\"ipv6\" icmp-type name=\"router-advertisement\" accept") seen["ra"]++
          else if ($0 == "rule family=\"ipv6\" icmp-type name=\"redirect\" accept") seen["rd"]++
          else bad=1
          next
        }
        /^priority: -15000$/ {priority++; next}
        /^target: CONTINUE$/ {target++; next}
        /^ingress-zones: ANY$/ {ingress++; next}
        /^egress-zones: HOST$/ {egress++; next}
        /^(services|ports|protocols|forward-ports|source-ports|icmp-blocks):$/ {empty[$1]++; next}
        /^masquerade: no$/ {masquerade++; next}
        {bad=1}
        END {
          if (bad || priority != 1 || target != 1 || ingress != 1 || egress != 1 || masquerade != 1 ||
              seen["na"] != 1 || seen["ns"] != 1 || seen["ra"] != 1 || seen["rd"] != 1 ||
              empty["services:"] != 1 || empty["ports:"] != 1 || empty["protocols:"] != 1 ||
              empty["forward-ports:"] != 1 || empty["source-ports:"] != 1 || empty["icmp-blocks:"] != 1) exit 1
        }' || { echo '内置 IPv6 policy 内容无法核验' >&2; return 1; } ;;
    *) echo '存在未核验的防火墙 policy' >&2; return 1 ;;
  esac
  direct=$("${fw[@]}" --direct --get-all-rules)
  test -z "$direct" || { echo '存在 direct rules' >&2; return 1; }
  direct=$("${fw[@]}" --direct --get-all-chains)
  test -z "$direct" || { echo '存在 direct chains' >&2; return 1; }
  direct=$("${fw[@]}" --direct --get-all-passthroughs)
  test -z "$direct" || { echo '存在 direct passthroughs' >&2; return 1; }
  zones=$("${fw[@]}" --get-zones)
  default=$(""" + default_zone() + r""")
  test -n "$zones" && test -n "$default" || return 1
  [[ "$default" =~ ^[A-Za-z0-9_.-]+$ ]] || return 1
  names="$default"
  for zone in $zones; do
    [[ "$zone" =~ ^[A-Za-z0-9_.-]+$ ]] || return 1
    interfaces=$("${fw[@]}" --zone="$zone" --list-interfaces)
    sources=$("${fw[@]}" --zone="$zone" --list-sources)
    if test -n "$interfaces" || test -n "$sources"; then
      names="$names $zone"
    fi
  done
  if test "$fw_state" = active; then
    active=$(firewall-cmd --get-active-zones)
    if test -n "$active"; then
      active=$(printf '%s\n' "$active" | awk '
        NF == 1 && $1 ~ /^[A-Za-z0-9_.-]+$/ {zone=1; print $1; next}
        zone && NF >= 2 && ($1 == "interfaces:" || $1 == "sources:") {next}
        {bad=1}
        END {if (bad || !zone) exit 1}') || return 1
      names="$names $active"
    fi
  fi
  names=$(printf '%s\n' $names | sort -u)
  for zone in $names; do
    case " $zones " in *" $zone "*) ;; *) echo "未知活动 zone: $zone" >&2; return 1 ;; esac
    target=$("${fw[@]}" --zone="$zone" --get-target)
    test "$target" = default || { echo "zone $zone 存在非默认 target" >&2; return 1; }
    rich=$("${fw[@]}" --zone="$zone" --list-rich-rules)
    test -z "$rich" || { echo "zone $zone 存在 rich rules" >&2; return 1; }
    for port in $ssh_ports; do
      if test "$port" = 22; then
        if "${fw[@]}" --zone="$zone" --query-service=ssh >/dev/null; then
          definition=$("${fw[@]}" --info-service=ssh)
          if printf '%s\n' "$definition" | grep -Eq '^[[:space:]]*ports:.*[[:space:]]22/tcp([[:space:]]|$)' &&
             printf '%s\n' "$definition" | awk '$1 ~ /^(protocols:|source-ports:|includes:|destination:|modules:|helpers:)$/ && NF > 1 {exit 1}'; then
            continue
          fi
        else
          rc=$?; test "$rc" -eq 1 || return 1
        fi
      fi
      if "${fw[@]}" --zone="$zone" --query-port="$port/tcp" >/dev/null; then
        :
      else
        rc=$?; echo "zone $zone 未核验 SSH 端口 $port/tcp (查询码 $rc)" >&2; return 1
      fi
    done
  done
}
check_scope "${fw_perm[@]}"
if test "$fw_state" = active; then check_scope firewall-cmd; fi"""


def build(name: str, params: dict) -> OperationSpec:
    allowed = {"zone", "scope", "service" if name.endswith("service") else "port"} if name.startswith(("add_", "remove_")) else set()
    fields(params, allowed, allowed)
    if name in {"start", "stop", "enable", "disable", "reload"}:
        pre = firewall_state() + "\n" + permanent_snapshot()
        if name in {"start", "enable", "reload"}:
            pre += "\n" + tools("awk", "grep", "sort", "sshd") + "\n" + ssh_zones() + "\nprintf 'ssh_ports=%s\\n' \"$ssh_ports\""
        if name == "reload":
            pre += '\ntest "$fw_state" = active'
        cmd = "firewall-cmd --reload" if name == "reload" else f"systemctl {name} firewalld"
        if name == "reload":
            cmd = 'test "$fw_state" = active\n' + cmd
        if name in {"start", "enable", "reload"}:
            cmd = firewall_state() + "\n" + tools("awk", "grep", "sort", "sshd") + "\n" + ssh_zones() + "\n" + cmd
        verify = ("test \"$(systemctl show firewalld -p ActiveState --value)\" = active" if name == "start" else
                  "test \"$(systemctl show firewalld -p ActiveState --value)\" = inactive" if name == "stop" else
                  "test \"$(systemctl show firewalld -p UnitFileState --value)\" = enabled" if name == "enable" else
                  "test \"$(systemctl show firewalld -p UnitFileState --value)\" = disabled" if name == "disable" else
                  "firewall-cmd --state >/dev/null")
        return OperationSpec(next(item["title"] for item in ACTIONS if item["id"] == name), True,
                             shell(pre), (OperationStep(name, shell(cmd)),), shell(verify))
    zone = params["zone"]
    if not isinstance(zone, str) or not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]{0,63}", zone, re.ASCII):
        raise ValueError("Zone 名称无效")
    scope = choice(params, "scope", set(SCOPE), "生效范围")
    kind = "service" if name.endswith("service") else "port"
    value = params[kind]
    if not isinstance(value, str):
        raise ValueError("服务或端口格式无效")
    if kind == "service":
        if not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.+-]{0,63}", value, re.ASCII):
            raise ValueError("服务名称无效")
    else:
        match = re.fullmatch(r"([0-9]{1,5})(?:-([0-9]{1,5}))?/(tcp|udp)", value, re.ASCII)
        if not match or not 1 <= int(match[1]) <= int(match[2] or match[1]) <= 65535:
            raise ValueError("端口规则无效，应为 1-65535/tcp|udp")
    setup = firewall_state()
    if scope == "runtime":
        setup += '\ntest "$fw_state" = active\nfw=(firewall-cmd)'
    else:
        setup += '\nfw=("${fw_perm[@]}")'
    arg = f"--zone={quote(zone)}"
    test = f'"${{fw[@]}}" {arg} --query-{kind}={quote(value)}'
    pre = setup + "\n" + tools("tr", "grep") + "\n" + permanent_snapshot()
    pre += f"\n\"${{fw[@]}}\" --get-zones | tr ' ' '\\n' | grep -Fx -- {quote(zone)} >/dev/null"
    if name.startswith("remove_"):
        pre += "\n" + tools("awk", "sshd") + "\n" + test + " >/dev/null\n" + ssh_port() + "\nprintf 'ssh_ports=%s\\n' \"$ssh_ports\""
        if kind == "service":
            guard = f'\ninfo=$("${{fw[@]}}" --info-service={quote(value)})\n' + r"""for key in protocols source-ports includes destination modules helpers; do
  extra=$(printf '%s\n' "$info" | awk -v key="$key" '$1 == key ":" { $1=""; print $0 }')
  test -z "${extra//[[:space:]]/}" || { echo '服务定义包含无法验证的附加规则' >&2; exit 1; }
done
service_ports=$(printf '%s\n' "$info" | awk '$1 == "ports:" { $1=""; print $0 }')
for rule in $service_ports; do
  [[ "$rule" =~ ^([0-9]+)(-([0-9]+))?/(tcp|udp)$ ]] || exit 1
  if test "${BASH_REMATCH[4]}" = tcp; then
    lo=${BASH_REMATCH[1]}; hi=${BASH_REMATCH[3]:-${BASH_REMATCH[1]}}
    for p in $ssh_ports; do
      if ((p >= lo && p <= hi)); then echo '服务包含 SSH 端口' >&2; exit 1; fi
    done
  fi
done"""
            pre += guard + "\nprintf '%s\\n' \"$info\""
            if value == "ssh":
                raise ValueError("不允许移除 SSH 服务规则")
        elif match[3] == "tcp" and int(match[1]) <= 22 <= int(match[2] or match[1]):
            raise ValueError("不允许移除 SSH 端口规则")
        if kind == "port" and match[3] == "tcp":
            pre += f"\nfor p in $ssh_ports; do if ((p >= {int(match[1])} && p <= {int(match[2] or match[1])})); then exit 1; fi; done"
    else:
        if kind == "service":
            pre += f"\n\"${{fw[@]}}\" --get-services | tr ' ' '\\n' | grep -Fx -- {quote(value)} >/dev/null"
    pre += f"\ncurrent_rules=$(\"${{fw[@]}}\" {arg} --list-{kind}s)\nprintf '%s\\n' \"$current_rules\""
    command = setup + f"\n\"${{fw[@]}}\" {arg} --{'add' if name.startswith('add_') else 'remove'}-{kind}={quote(value)}"
    if name == "remove_service":
            # Every step runs in a new shell; read the service definition again before deletion.
            command = setup + "\n" + tools("awk", "sshd") + "\n" + ssh_port() + f'\ninfo=$("${{fw[@]}}" --info-service={quote(value)})\n' + guard + f'\n"${{fw[@]}}" {arg} --remove-service={quote(value)}'
    if name == "remove_port" and match[3] == "tcp":
        command = setup + "\n" + tools("awk", "sshd") + "\n" + ssh_port() + f"\nfor p in $ssh_ports; do if ((p >= {int(match[1])} && p <= {int(match[2] or match[1])})); then exit 1; fi; done\n" + f'"${{fw[@]}}" {arg} --remove-port={quote(value)}'
    verify = setup + "\n" + (test + " >/dev/null" if name.startswith("add_") else f"rc=0; {test} >/dev/null || rc=$?\ntest \"$rc\" -eq 1")
    return OperationSpec(next(item["title"] for item in ACTIONS if item["id"] == name), True,
                         shell(pre), (OperationStep(name, shell(command)),), shell(verify))
