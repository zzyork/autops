import re
import shlex
from dataclasses import dataclass


@dataclass(frozen=True)
class OperationStep:
    title: str
    command: str
    timeout_seconds: float = 60


@dataclass(frozen=True)
class OperationSpec:
    title: str
    destructive: bool
    preflight: str
    steps: tuple[OperationStep, ...]
    verify: str


def shell(body: str) -> str:
    return "set -euo pipefail\n" + rhel() + "\n" + body


def quote(value: str) -> str:
    return shlex.quote(value)


def fields(params: dict[str, str | int | bool], allowed: set[str], required: set[str] = frozenset()) -> None:
    if not isinstance(params, dict) or any(not isinstance(key, str) for key in params):
        raise ValueError("参数必须是字段名到值的映射")
    if extra := params.keys() - allowed:
        raise ValueError("存在不支持的参数：" + ", ".join(sorted(extra)))
    if missing := required - params.keys():
        raise ValueError("缺少必填参数：" + ", ".join(sorted(missing)))


def text(params: dict, key: str, pattern: str, label: str, limit: int = 253) -> str:
    value = params.get(key)
    if not isinstance(value, str) or not 0 < len(value) <= limit or not re.fullmatch(pattern, value, re.ASCII):
        raise ValueError(f"{label}格式或长度无效")
    return value


def choice(params: dict, key: str, options: set[str], label: str) -> str:
    value = params.get(key)
    if not isinstance(value, str) or value not in options:
        raise ValueError(f"{label}只能是：" + "、".join(sorted(options)))
    return value


def boolean(params: dict, key: str, default: bool = False) -> bool:
    value = params.get(key, default)
    if type(value) is not bool:
        raise ValueError(f"{key}必须是布尔值")
    return value


def tools(*names: str) -> str:
    return "\n".join(f"command -v {quote(name)} >/dev/null || exit 1" for name in names)


def selinux_context_check() -> str:
    return """command -v getenforce >/dev/null || exit 1
selinux_state=$(getenforce)
case "$selinux_state" in
  Enforcing|Permissive) command -v restorecon >/dev/null || exit 1 ;;
  Disabled) ;;
  *) exit 1 ;;
esac"""


def restore_new(path: str) -> str:
    return f'if test "$selinux_state" != Disabled; then restorecon -- {quote(path)}; fi'


def rhel() -> str:
    return """test -r /etc/os-release
source /etc/os-release
supported=false
for distro in "${ID:-}" ${ID_LIKE:-}; do
  case "$distro" in rhel|fedora|centos|rocky|almalinux|ol) supported=true ;; esac
done
test "$supported" = true || { echo '仅支持 RHEL/DNF 系统' >&2; exit 1; }
command -v dnf >/dev/null || exit 1"""


def field(key: str, label: str, kind: str = "text", required: bool = True, **extra: object) -> dict:
    return {"key": key, "label": label, "kind": kind, "required": required, **extra}


def action(id: str, title: str, description: str, destructive: bool, fields: list[dict]) -> dict:
    return {"id": id, "title": title, "description": description, "destructive": destructive, "fields": fields}


def read_spec(title: str, command: str) -> OperationSpec:
    return OperationSpec(title, False, command, (OperationStep(title, command),), command)
