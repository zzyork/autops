from collections.abc import Callable
import math

from ...core.ssh_commands import CommandResult
from ...schemas.inspections import CheckDefinition, CheckId, CheckPayload, InspectionConfig, ResultTable

Runner = Callable[[str], CommandResult]
MAX_ROWS = 256
MAX_CELL = 500


class InspectionCheckError(Exception):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def query(runner: Runner, command: str) -> str:
    result = runner(command)
    if result.exit_status == 127:
        raise InspectionCheckError("tool_missing")
    if result.exit_status != 0:
        raise InspectionCheckError("command_failed")
    return result.stdout


def table(name: str, columns: list[str], rows: list[list[str]]) -> ResultTable:
    if len(rows) > MAX_ROWS or any(
        len(row) != len(columns) or any(len(cell) > MAX_CELL for cell in row) for row in rows
    ):
        raise InspectionCheckError("output_limit")
    return ResultTable(name=name, columns=columns, rows=rows)


def percentage(value: float) -> float:
    if not math.isfinite(value) or not 0 <= value <= 100:
        raise InspectionCheckError("invalid_output")
    return value


CHECK_DEFINITIONS = [
    CheckDefinition(id="server_info", title="系统基础信息", description="主机、系统版本、运行时长与地址"),
    CheckDefinition(id="system_resources", title="系统资源", description="CPU、内存、磁盘与进程资源"),
    CheckDefinition(id="service_status", title="服务状态", description="配置服务的安装与运行状态"),
    CheckDefinition(id="network_info", title="网络信息", description="网卡地址及本机监听套接字"),
    CheckDefinition(id="log_error", title="错误日志", description="journal 错误级别与日志文件关键词"),
]
CHECK_TITLES = {definition.id: definition.title for definition in CHECK_DEFINITIONS}


def collect(check_id: CheckId, runner: Runner, config: InspectionConfig) -> CheckPayload:
    from . import basic, logs, network, resources, services

    collectors = {
        "server_info": basic.collect,
        "system_resources": resources.collect,
        "service_status": services.collect,
        "network_info": network.collect,
        "log_error": logs.collect,
    }
    try:
        collector = collectors[check_id]
    except KeyError:
        raise InspectionCheckError("unsupported_check") from None
    return collector(runner, config)
