import ipaddress
import re

from .common import OperationSpec, OperationStep, action, choice, field, fields, quote, restore_new, selinux_context_check, shell, text, tools
from .hostname import HOST_RE

TITLE = "系统优化"
CHRONY = "/etc/chrony.conf"
VIMRC = "/root/.vimrc"
SELINUX = "/etc/selinux/config"
VIM_BLOCK = """\" BEGIN autops vim defaults
set autoindent
set smartindent
set expandtab
set tabstop=4
set shiftwidth=4
set showmatch
\" END autops vim defaults"""
ACTIONS = [
    action("chrony", "配置 chrony 时间同步", "需已安装 chrony；保留已有时间源，添加指定 NTP 服务器并启用 chronyd", True,
           [field("server", "NTP 服务器域名或 IP")]),
    action("vimrc", "设置 Vim 默认配置", "更新 root vimrc 的受管配置段", True, []),
    action("selinux", "设置 SELinux 模式", "运行态与重启后配置（disabled 需重启）", True,
           [field("mode", "模式", "select", options=[{"label": m, "value": m} for m in ("enforcing", "permissive", "disabled")])]),
]


def inspect() -> str:
    return shell(tools("systemctl", "cat", "getenforce") + f"""
systemctl show chronyd -p ActiveState -p UnitFileState
for file in {CHRONY} {VIMRC} {SELINUX}; do
  if test -f "$file"; then printf '\n%s\n' "$file"; cat -- "$file"; fi
done
getenforce""")


def rewrite(path: str, awk: str, content: str) -> str:
    return f"""test -f {path} && test ! -L {path}
tmp=$(mktemp {path.rsplit('/', 1)[0]}/.autops-system.XXXXXX)
trap 'rm -f -- "$tmp"' EXIT
awk {awk} {path} > "$tmp"
printf '%s\\n' {quote(content)} >> "$tmp"
cp --attributes-only --preserve=all -- {path} "$tmp"
mv -f -- "$tmp" {path}"""


def build(name: str, params: dict) -> OperationSpec:
    if name == "chrony":
        fields(params, {"server"}, {"server"})
        server = text(params, "server", r"[A-Za-z0-9][A-Za-z0-9.:-]{0,252}", "时间服务器", 253)
        try:
            ipaddress.ip_address(server)
        except ValueError:
            if not re.fullmatch(HOST_RE, server, re.ASCII):
                raise ValueError("时间服务器必须是合法的主机名或 IP 地址") from None
        setup = tools("systemctl", "awk", "mktemp", "cp", "mv", "sha256sum", "chronyd", "chronyc")
        pre = setup + f"\ntest -f {CHRONY} && test ! -L {CHRONY}\nsha256sum {CHRONY}\nsystemctl show chronyd -p ActiveState -p UnitFileState"
        awk = "'$0 == \"# BEGIN autops chrony\" {active=1; next} $0 == \"# END autops chrony\" {active=0; next} !active {print} END {if (active) exit 1}'"
        block = f"# BEGIN autops chrony\nserver {server} iburst\n# END autops chrony"
        cmd = rewrite(CHRONY, awk, block) + "\nsystemctl enable --now chronyd\nsystemctl restart chronyd"
        verify = (f"grep -Fx -- {quote('server ' + server + ' iburst')} {CHRONY} >/dev/null\n"
                  "systemctl -q is-active chronyd\nsystemctl -q is-enabled chronyd\n"
                  "printf '%s\\n' 'chrony configuration applied; waiting for synchronization'\n"
                  "chronyc waitsync 6 0 0 5\n"
                   f"sources=$(chronyc -N sources)\nprintf '%s\\n' \"$sources\"\nprintf '%s\\n' \"$sources\" | awk -v server={quote(server)} "
                   "'$1 ~ /^\\^[*+-]$/ && $2 == server && $5 ~ /^[0-7]+$/ && $5 + 0 > 0 {found=1} END {exit !found}'\n"
                   "printf '%s\\n' 'system synchronized; configured source is reachable'")
        return OperationSpec("配置 chrony 时间同步", True, shell(pre), (OperationStep("配置并重启 chronyd", shell(cmd), 120),), shell(verify))
    if name == "vimrc":
        fields(params, set())
        pre = tools("awk", "mktemp", "chmod", "cp", "mv", "sha256sum") + "\n" + selinux_context_check() + f"\ntest -d /root && test ! -L /root\ntest ! -L {VIMRC}\nif test -e {VIMRC}; then test -f {VIMRC} && test -r {VIMRC}; sha256sum {VIMRC}; fi"
        awk = "'$0 == \"\\\" BEGIN autops vim defaults\" {active=1; next} $0 == \"\\\" END autops vim defaults\" {active=0; next} !active {print} END {if (active) exit 1}'"
        cmd = selinux_context_check() + f"""
test ! -L {VIMRC}
tmp=$(mktemp /root/.autops-vimrc.XXXXXX)
trap 'rm -f -- "$tmp"' EXIT
was_new=0
if test -e {VIMRC}; then
  awk {awk} {VIMRC} > "$tmp"
else was_new=1; chmod 0644 "$tmp"; fi
printf '%s\\n' {quote(VIM_BLOCK)} >> "$tmp"
if test "$was_new" -eq 0; then cp --attributes-only --preserve=all -- {VIMRC} "$tmp"; fi
mv -f -- "$tmp" {VIMRC}
if test "$was_new" -eq 1; then {restore_new(VIMRC)}; fi"""
        verify = (f"grep -Fx -- {quote('set showmatch')} {VIMRC} >/dev/null\n"
                  f"grep -Fx -- {quote(chr(34) + ' END autops vim defaults')} {VIMRC} >/dev/null")
        return OperationSpec("设置 Vim 默认配置", True, shell(pre), (OperationStep("更新受管 vimrc 段", shell(cmd)),), shell(verify))
    fields(params, {"mode"}, {"mode"})
    mode = choice(params, "mode", {"enforcing", "permissive", "disabled"}, "SELinux 模式")
    pre = (tools("getenforce", "awk", "sha256sum", "mktemp", "cp", "mv") +
           f'\ntest -f {SELINUX} && test ! -L {SELINUX}\nsha256sum {SELINUX}\ncurrent=$(getenforce); printf "%s\\n" "$current"')
    pre += '\ncase "$current" in Enforcing|Permissive|Disabled) ;; *) exit 1;; esac'
    if mode != "disabled":
        pre += "\ntest \"$current\" != Disabled\n" + tools("setenforce")
    else:
        pre += '\nif test "$current" != Disabled; then command -v setenforce >/dev/null || exit 1; fi'
    # Require an existing single directive; preserve other distribution settings.
    pre += f"\ntest \"$(grep -Ec '^[[:space:]]*SELINUX=' {SELINUX})\" -eq 1"
    awk = "'$0 !~ /^[[:space:]]*SELINUX=/ {print}'"
    cmd = rewrite(SELINUX, awk, "SELINUX=" + mode)
    if mode == "disabled":
        cmd += "\nif test \"$(getenforce)\" != Disabled; then setenforce 0; fi"
        verify = f"grep -Fx 'SELINUX=disabled' {SELINUX} >/dev/null\ncase \"$(getenforce)\" in Permissive|Disabled) ;; *) exit 1;; esac"
    else:
        cmd += f"\nsetenforce {quote('1' if mode == 'enforcing' else '0')}"
        verify = f"grep -Fx -- {quote('SELINUX=' + mode)} {SELINUX} >/dev/null\ntest \"$(getenforce)\" = {quote(mode.capitalize())}"
    return OperationSpec("设置 SELinux 模式", True, shell(pre), (OperationStep("设置持久和运行态 SELinux", shell(cmd)),), shell(verify))
