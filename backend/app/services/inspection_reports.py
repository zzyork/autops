import html
import re
from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

from ..schemas.inspections import HostRunResponse, TaskDetail

STATUS = {"queued": "等待执行", "running": "执行中", "completed": "完成", "partial": "部分完成",
          "failed": "失败", "interrupted": "中断", "skipped": "未执行"}
CONCLUSION = {"normal": "正常", "warning": "警告", "critical": "严重", "not_applicable": "不适用", "unknown": "无法判定"}


def escape(value: object) -> str:
    text = html.escape("".join(character for character in str(value) if character.isprintable() or character in "\n\t"), quote=True)
    text = re.sub(r"([\\`*_{}\[\]()#+.!|>~-])", r"\\\1", text)
    return text.replace("\r", "").replace("\n", " ")


def render_report(task: TaskDetail, host_run: HostRunResponse | None = None) -> str:
    lines = [f"# 巡检报告：{escape(task.name)}", "", f"- 任务 ID：{task.id}",
             f"- 创建时间：{task.created_at.isoformat()}", f"- 执行状态：{STATUS[task.status]}",
             f"- 已结束主机：{task.completed_hosts}/{task.host_count}",
             f"- 非完整成功主机：{task.failed_hosts}", f"- 规则版本：{escape(task.rule_version)}", "",
             "执行完成不代表健康；失败、未执行及中断的检查无法判定健康。", ""]
    if host_run is not None:
        lines += [f"本报告仅包含主机 {escape(host_run.address)} 的巡检结果，以上统计为整个任务的统计。", ""]
    for host in task.hosts if host_run is None else [host_run]:
        lines += [f"## {escape(host.host_name)}", "", f"- 分组：{escape(host.group_name)}",
                  f"- 目标：{escape(host.address)}:{host.port}", f"- 登录用户：{escape(host.username)}",
                  f"- 执行状态：{STATUS[host.status]}", ""]
        for check in host.checks:
            lines += [f"### {escape(check.title)}", "", f"- 执行：{STATUS[check.status]}",
                      f"- 结论：{CONCLUSION[check.conclusion]}"]
            if check.started_at:
                lines.append(f"- 采集开始：{check.started_at.isoformat()}")
            if check.error_code:
                lines.append(f"- 结果代码：{escape(check.error_code)}")
            lines.append("")
            for finding in check.payload.findings:
                level = "严重" if finding.severity == "critical" else "警告"
                lines.append(f"- {level}：{escape(finding.message)}")
            for metric in check.payload.metrics:
                value = "不适用" if metric.value is None else escape(metric.value)
                lines.append(f"- {escape(metric.name)}：{value} {escape(metric.unit or '')}")
            lines.append("")
            for table in check.payload.tables:
                lines += [f"#### {escape(table.name)}", "", "| " + " | ".join(map(escape, table.columns)) + " |",
                          "| " + " | ".join("---" for _ in table.columns) + " |"]
                lines.extend("| " + " | ".join(map(escape, row)) + " |" for row in table.rows)
                lines.append("")
    # 配置含用户维护的服务显示名称，也不能允许其闭合代码围栏。
    config_json = task.config.model_dump_json(indent=2)
    fence = "~" * max(3, max((len(match) for match in re.findall(r"~+", config_json)), default=0) + 1)
    lines += ["## 本次配置", "", fence + "json", config_json, fence, ""]
    return "\n".join(lines)


def filename_part(value: str, *, directory: bool = False) -> str:
    # ZIP 解压后的路径也须兼容 Windows，不能让动态名称引入目录或控制字符。
    part = re.sub(r'[\\/:*?"<>|\x00-\x1f\x7f]', "_", value.strip()).rstrip(". ")
    if not part:
        raise ValueError("报告路径名称无效")
    if directory and part.split(".")[0].upper() in {
        "CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10)),
    }:
        part = "_" + part
    if len(part.encode("utf-8")) > 255:
        raise ValueError("报告路径名称过长")
    return part


def report_hostname(host: HostRunResponse) -> str:
    for check in host.checks:
        if check.check_id == "server_info" and check.status == "completed":
            for metric in check.payload.metrics:
                if metric.name == "主机名" and isinstance(metric.value, str) and metric.value.strip():
                    return metric.value.strip()
    return host.host_name


def render_report_archive(task: TaskDetail) -> bytes:
    if not task.hosts:
        raise ValueError("没有可导出的主机报告")
    month = task.created_at.strftime("%Y%m")
    paths: set[str] = set()
    buffer = BytesIO()
    with ZipFile(buffer, "w", compression=ZIP_DEFLATED) as archive:
        for host in task.hosts:
            filename = f"{filename_part(host.address)}_{filename_part(report_hostname(host))}.md"
            if len(filename.encode("utf-8")) > 255:
                raise ValueError("报告文件名过长")
            path = f"{filename_part(host.group_name, directory=True)}/{month}/{filename}"
            if path.casefold() in paths:
                raise ValueError("报告文件名重复")
            paths.add(path.casefold())
            archive.writestr(path, render_report(task, host))
    return buffer.getvalue()
