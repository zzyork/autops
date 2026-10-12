import shlex

from ...schemas.inspections import CheckPayload, Finding, InspectionConfig
from . import InspectionCheckError, Runner, table


def collect(runner: Runner, config: InspectionConfig) -> CheckPayload:
    rows = []
    findings = []
    installed = 0
    for service in config.services:
        selected = None
        load_state = "not-found"
        active_state = "unknown"
        for candidate in service.candidates:
            result = runner(f"systemctl show -p LoadState -p ActiveState -- {shlex.quote(candidate)}")
            if result.exit_status == 127:
                raise InspectionCheckError("tool_missing")
            if result.exit_status not in (0, 1):
                raise InspectionCheckError("command_failed")
            output = result.stdout
            fields = output.splitlines()
            if len(fields) != 2 or any("=" not in field for field in fields):
                raise InspectionCheckError("invalid_output")
            states = dict(field.split("=", 1) for field in fields)
            if set(states) != {"LoadState", "ActiveState"}:
                raise InspectionCheckError("invalid_output")
            load_state, active_state = states["LoadState"], states["ActiveState"]
            # systemctl 对不存在的 unit 可返回 1；仅明确的 not-found 可作为未安装处理。
            if result.exit_status != 0 and not (result.exit_status == 1 and load_state == "not-found"):
                raise InspectionCheckError("tool_missing" if result.exit_status == 127 else "command_failed")
            if load_state not in {"loaded", "not-found", "masked", "bad-setting", "error", "merged", "stub"} or not active_state:
                raise InspectionCheckError("invalid_output")
            if load_state != "not-found":
                selected = candidate
                installed += 1
                break
        if selected is None:
            if service.required:
                findings.append(Finding(severity="warning", message=f"必需服务 {service.name} 未安装"))
        elif load_state != "loaded" or active_state != "active":
            findings.append(Finding(severity="warning", message=f"服务 {service.name} 状态: {load_state}/{active_state}"))
        if selected is not None:
            rows.append([service.name, selected, load_state, active_state, "是" if service.required else "否"])
    return CheckPayload(
        conclusion="warning" if findings else "not_applicable" if installed == 0 else "normal",
        findings=findings,
        tables=[table("服务状态", ["服务", "匹配单元", "加载状态", "运行状态", "必需"], rows)],
    )
