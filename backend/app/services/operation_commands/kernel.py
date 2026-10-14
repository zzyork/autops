from .common import OperationSpec, OperationStep, action, choice, field, fields, quote, restore_new, selinux_context_check, shell, text, tools

TITLE = "内核与资源限制"
SYSCTL = "/etc/sysctl.d/90-autops.conf"
LIMITS = "/etc/security/limits.d/90-autops.conf"
ACTIONS = [
    action("set_sysctl", "设置 sysctl 参数", "仅维护 autops 专属 sysctl 文件的一项", True, [
        field("key", "参数名"), field("value", "数值（多个值用空格分隔）"),
    ]),
    action("set_limit", "设置资源限制", "仅维护 autops 专属 limits 文件的一项", True, [
        field("domain", "用户、@组或 *"),
        field("type", "软/硬限制", "select", options=[{"label": "soft", "value": "soft"}, {"label": "hard", "value": "hard"}]),
        field("item", "限制项", "select", options=[{"label": x, "value": x} for x in ("nofile", "nproc", "core", "memlock", "stack")]),
        field("value", "数值或 unlimited"),
    ]),
]


def inspect() -> str:
    return shell(tools("cat", "sysctl") + f"""
for file in {SYSCTL} {LIMITS}; do
  if test -f "$file"; then printf '\n%s\n' "$file"; cat -- "$file"; fi
done
sysctl -a 2>/dev/null""")


def managed(path: str, match: str, new_line: str) -> str:
    # Only the selected entry is replaced; unrelated lines and comments survive.
    return f"""test -d {quote(path.rsplit('/', 1)[0])} && test ! -L {quote(path.rsplit('/', 1)[0])}
test ! -L {quote(path)}
if test -e {quote(path)}; then test -f {quote(path)} && test -r {quote(path)}; fi
tmp=$(mktemp {quote(path.rsplit('/', 1)[0] + '/.autops-config.XXXXXX')})
trap 'rm -f -- "$tmp"' EXIT
was_new=0
if test -f {quote(path)}; then
  awk {match} {quote(path)} > "$tmp"
else
  was_new=1
  chmod 0644 "$tmp"
fi
printf '%s\\n' {quote(new_line)} >> "$tmp"
if test "$was_new" -eq 0; then cp --attributes-only --preserve=all -- {quote(path)} "$tmp"; fi
mv -f -- "$tmp" {quote(path)}
if test "$was_new" -eq 1; then {restore_new(path)}; fi"""


def build(name: str, params: dict) -> OperationSpec:
    if name == "set_sysctl":
        fields(params, {"key", "value"}, {"key", "value"})
        key = text(params, "key", r"[a-z][a-z0-9_]*(?:\.[a-z0-9_]+)+", "sysctl 参数名", 128)
        value = text(params, "value", r"-?[0-9]+(?: +-?[0-9]+)*", "sysctl 数值", 128)
        value = " ".join(value.split())
        proc = "/proc/sys/" + key.replace(".", "/")
        prerequisites = tools("sysctl", "awk", "mktemp", "sha256sum", "chmod", "cp", "mv") + "\n" + selinux_context_check() + f"\ntest -f {quote(proc)} && test -r {quote(proc)} && test -w {quote(proc)}"
        pre = prerequisites + f"\nif test -e {SYSCTL}; then test -f {SYSCTL} && test ! -L {SYSCTL}; sha256sum {SYSCTL}; fi\nsysctl -n {quote(key)}"
        # AWK compares the key as a string rather than inserting it into a regex.
        match = (f"-v key={quote(key)} " +
                 "'$0 !~ /^[[:space:]]*#/ && index($0, \"=\") > 0 { split($0, a, \"=\"); gsub(/[[:space:]]/, \"\", a[1]); if (a[1] == key) next } {print}'")
        cmd = prerequisites + "\n" + managed(SYSCTL, match, f"{key} = {value}")
        verify = f"actual=$(sysctl -n {quote(key)} | awk '{{$1=$1; print}}')\ntest \"$actual\" = {quote(value)}\ngrep -Fx -- {quote(key + ' = ' + value)} {SYSCTL} >/dev/null"
        # Let the kernel reject invalid values before touching persistent configuration.
        return OperationSpec("设置 sysctl 参数", True, shell(pre), (
            OperationStep("应用运行态 sysctl（持久化失败时运行态仍可能已变更）", shell(f"sysctl -w {quote(key + '=' + value)}")),
            OperationStep("保存已应用的 sysctl 配置", shell(cmd)),
        ), shell(verify))
    fields(params, {"domain", "type", "item", "value"}, {"domain", "type", "item", "value"})
    domain = text(params, "domain", r"\*|@?[A-Za-z_][A-Za-z0-9_.-]*", "限制对象", 64)
    kind = choice(params, "type", {"soft", "hard"}, "限制类型")
    item = choice(params, "item", {"nofile", "nproc", "core", "memlock", "stack"}, "限制项")
    value = text(params, "value", r"[0-9]{1,12}|unlimited", "资源限制值", 12)
    if value.isdigit() and int(value) > 1_000_000_000:
        raise ValueError("资源限制值超出允许范围")
    prerequisites = tools("awk", "mktemp", "sha256sum", "chmod", "cp", "mv") + "\n" + selinux_context_check() + "\ntest -d /etc/security/limits.d"
    pre = prerequisites + f"\nif test -e {LIMITS}; then test -f {LIMITS} && test ! -L {LIMITS}; sha256sum {LIMITS}; fi"
    match = f"-v domain={quote(domain)} -v kind={quote(kind)} -v item={quote(item)} '$0 !~ /^[[:space:]]*#/ && $1 == domain && $2 == kind && $3 == item {{next}} {{print}}'"
    cmd = prerequisites + "\n" + managed(LIMITS, match, f"{domain} {kind} {item} {value}")
    verify = f"grep -Fx -- {quote(f'{domain} {kind} {item} {value}')} {LIMITS} >/dev/null"
    return OperationSpec("设置资源限制", True, shell(pre), (OperationStep("写入 limits 规则", shell(cmd)),), shell(verify))
