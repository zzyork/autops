from .common import OperationSpec, OperationStep
from . import disk, firewall, hostname, kernel, packages, system

MODULES = {
    "hostname": hostname,
    "packages": packages,
    "firewall": firewall,
    "kernel": kernel,
    "system": system,
    "disk": disk,
}


def catalog() -> list[dict]:
    return [{"id": key, "title": module.TITLE, "actions": module.ACTIONS} for key, module in MODULES.items()]


def inspect_command(module: str) -> str:
    if not isinstance(module, str) or module not in MODULES:
        raise ValueError("不支持的运维模块")
    return MODULES[module].inspect()


def build_operation(module: str, action: str, params: dict[str, str | int | bool]) -> OperationSpec:
    if not isinstance(module, str) or module not in MODULES:
        raise ValueError("不支持的运维模块")
    if not isinstance(action, str) or action not in {item["id"] for item in MODULES[module].ACTIONS}:
        raise ValueError("不支持的运维操作")
    return MODULES[module].build(action, params)
