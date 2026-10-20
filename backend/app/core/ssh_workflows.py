"""在调用方管理的 SSH 连接上顺序执行命令，并同步报告步骤与输出。"""

import re
import threading
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Literal

import paramiko

from .ssh_commands import MAX_OUTPUT_BYTES, CommandExecutionError, OutputStream, run_command

MAX_STEPS = 20
MAX_STEP_NAME_LENGTH = 100
MAX_COMMAND_LENGTH = 8192
MAX_SUCCESS_EXIT_CODES = 16
MAX_STEP_TIMEOUT_SECONDS = 600
MAX_WORKFLOW_TIMEOUT_SECONDS = 1800

StepStatus = Literal["succeeded", "failed", "unknown", "skipped"]
WorkflowStatus = Literal["succeeded", "failed", "unknown"]


@dataclass(frozen=True)
class CommandStep:
    name: str
    command: str = field(repr=False)
    timeout_seconds: float = 30
    success_exit_codes: Sequence[int] = (0,)


@dataclass(frozen=True)
class StepResult:
    name: str
    status: StepStatus
    exit_status: int | None = None
    error_code: str | None = None
    stdout: str = field(default="", repr=False)
    stderr: str = field(default="", repr=False)


@dataclass(frozen=True)
class WorkflowResult:
    status: WorkflowStatus
    steps: tuple[StepResult, ...]
    error_code: str | None = None


@dataclass(frozen=True)
class WorkflowEvent:
    kind: Literal["step_start", "output", "step_end", "workflow_end"]
    step_index: int | None = None  # 从 0 开始；workflow_end 无步骤编号。
    stream: OutputStream | None = None
    text: str = field(default="", repr=False)
    status: StepStatus | WorkflowStatus | None = None
    exit_status: int | None = None
    error_code: str | None = None


class _OutputFilter:
    def __init__(self, secrets: tuple[str, ...]):
        values = tuple(sorted(set(filter(None, secrets)), key=len, reverse=True))
        self.pending = ""
        self.pattern = re.compile("|".join(re.escape(value) for value in values)) if values else None
        self.by_initial = {char: tuple(value for value in values if value.startswith(char))
                           for char in {value[0] for value in values}}
        self.longest = max((len(value) for value in values), default=0)

    def feed(self, value: str, *, final: bool = False) -> str:
        self.pending += value
        if self.pattern is None:
            result, self.pending = self.pending, ""
        else:
            boundary = len(self.pending)
            if not final:
                for start in range(max(0, boundary - self.longest + 1), boundary):
                    suffix = self.pending[start:]
                    if any(len(suffix) < len(secret) and secret.startswith(suffix)
                           for secret in self.by_initial.get(suffix[0], ())):
                        boundary = start
                        break
                for match in self.pattern.finditer(self.pending):
                    if match.start() < boundary < match.end():
                        boundary = match.end()
            result = self.pattern.sub("[REDACTED]", self.pending[:boundary])
            self.pending = self.pending[boundary:]
        return "".join(char if char.isprintable() or char in "\n\t" else "\ufffd" for char in result)


class _OutputLimit(Exception):
    pass


def _timeout(value: object, maximum: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 < value <= maximum:
        raise ValueError("执行时限必须为范围内的有限正数")
    return float(value)


def run_workflow(
    client: paramiko.SSHClient,
    steps: Sequence[CommandStep],
    timeout_seconds: float = 900,
    *,
    on_event: Callable[[WorkflowEvent], None] | None = None,
    cancel: threading.Event | None = None,
    secrets: Sequence[str] = (),
) -> WorkflowResult:
    """在调用方持有且已校验身份的连接上，依次执行全部校验通过的步骤。

    事件回调在调用线程执行，回调异常向上传播并停止流程。派发后的中断不证明
    远端命令已退出或回滚；工具不创建连接、不持久化，也不自动重试或补偿。
    """
    timeout = _timeout(timeout_seconds, MAX_WORKFLOW_TIMEOUT_SECONDS)
    if on_event is not None and not callable(on_event):
        raise ValueError("事件处理器必须为可调用对象")
    if cancel is not None and not isinstance(cancel, threading.Event):
        raise ValueError("取消信号必须为 threading.Event")
    if not isinstance(steps, Sequence) or not 1 <= len(steps) <= MAX_STEPS:
        raise ValueError("流程须包含 1–20 个步骤")
    selected: list[CommandStep] = []
    for step in steps:
        if not isinstance(step, CommandStep):
            raise ValueError("流程步骤必须使用 CommandStep")
        if not isinstance(step.name, str) or not 1 <= len(step.name.strip()) <= MAX_STEP_NAME_LENGTH:
            raise ValueError("步骤名称须填写且不超过 100 字符")
        if (not isinstance(step.command, str) or not step.command.strip()
                or len(step.command) > MAX_COMMAND_LENGTH or "\0" in step.command):
            raise ValueError("完整命令须填写、不超过 8192 字符且不含 NUL")
        duration = _timeout(step.timeout_seconds, MAX_STEP_TIMEOUT_SECONDS)
        if (not isinstance(step.success_exit_codes, Sequence)
                or not 1 <= len(step.success_exit_codes) <= MAX_SUCCESS_EXIT_CODES):
            raise ValueError("预期退出码须为 1–16 个整数")
        codes = tuple(step.success_exit_codes)
        if any(type(code) is not int or not 0 <= code <= 255 for code in codes):
            raise ValueError("预期退出码须为 0–255 的严格整数")
        if len(set(codes)) != len(codes):
            raise ValueError("预期退出码不能重复")
        selected.append(CommandStep(step.name.strip(), step.command, duration, codes))
    if (not isinstance(secrets, Sequence) or isinstance(secrets, (str, bytes))
            or any(not isinstance(value, str) for value in secrets)):
        raise ValueError("已知秘密须为字符串序列")
    secret_values = set(secrets)
    secret_values.update(line for value in secrets for line in value.splitlines() if len(line) > 3)
    secret_snapshot = tuple(secret_values)
    if any(secret and secret in step.command for step in selected for secret in secret_snapshot):
        raise ValueError("命令不得包含已知秘密")

    def emit(event: WorkflowEvent) -> None:
        if on_event is not None:
            on_event(event)

    deadline = time.monotonic() + timeout
    results: list[StepResult] = []
    workflow_error: str | None = None
    workflow_status: WorkflowStatus = "succeeded"
    for index, step in enumerate(selected):
        emit(WorkflowEvent("step_start", index))
        filters = {stream: _OutputFilter(secret_snapshot) for stream in ("stdout", "stderr")}
        output: dict[OutputStream, list[str]] = {"stdout": [], "stderr": []}
        output_bytes = 0
        output_exceeded = False
        callback_error: Exception | None = None

        def save(stream: OutputStream, text: str) -> None:
            nonlocal output_bytes, output_exceeded, callback_error
            if not text or output_exceeded:
                return
            encoded = text.encode("utf-8")
            available = MAX_OUTPUT_BYTES - output_bytes
            if len(encoded) > available:
                text = encoded[:available].decode("utf-8", errors="ignore")
                encoded = text.encode("utf-8")
                output_exceeded = True
            output_bytes += len(encoded)
            if text:
                output[stream].append(text)
                try:
                    emit(WorkflowEvent("output", index, stream, text))
                except Exception as exc:
                    callback_error = exc
                    raise
            if output_exceeded:
                raise _OutputLimit

        def receive(stream: OutputStream, value: str) -> None:
            save(stream, filters[stream].feed(value))

        result = None
        error = None
        if cancel is not None and cancel.is_set():
            error = CommandExecutionError("interrupted", False, dispatched=False)
        elif time.monotonic() >= deadline:
            error = CommandExecutionError("timeout", True, dispatched=False)
        else:
            try:
                result = run_command(client, step.command, step.timeout_seconds, deadline,
                                     on_output=receive, cancel=cancel)
            except CommandExecutionError as exc:
                error = exc
            except Exception:
                if callback_error is not None:
                    raise callback_error
                error = CommandExecutionError("internal", False)
        if callback_error is not None:
            raise callback_error
        for stream, filter_ in filters.items():
            try:
                save(stream, filter_.feed("", final=True))
            except _OutputLimit:
                # 限额已由 save 标记，统一保留部分输出并终止当前流程。
                break

        exit_status = result.exit_status if result is not None else error.exit_status if error else None
        if type(exit_status) is not int or exit_status < 0:
            exit_status = None
        code = "output_limit" if output_exceeded else error.code if error else None
        dispatched = error.dispatched if error is not None else True
        if code is not None and code != "connection":
            status: StepStatus = "failed" if exit_status is not None or not dispatched else "unknown"
        elif exit_status is not None:
            status = "succeeded" if exit_status in step.success_exit_codes else "failed"
            if status == "failed":
                code = "exit_status"
            elif code == "connection":
                code = None
        else:
            status = "unknown" if dispatched else "failed"
            code = code or "unknown"
        item = StepResult(step.name, status, exit_status, code,
                          "".join(output["stdout"]), "".join(output["stderr"]))
        results.append(item)
        emit(WorkflowEvent("step_end", index, status=status, exit_status=exit_status, error_code=code))
        if status != "succeeded" or (error is not None and error.code == "connection" and index < len(selected) - 1):
            workflow_status = status if status == "unknown" else "failed"
            workflow_error = "connection" if status == "succeeded" else code
            break

    for step in selected[len(results):]:
        results.append(StepResult(step.name, "skipped"))
    summary = WorkflowResult(workflow_status, tuple(results), workflow_error)
    emit(WorkflowEvent("workflow_end", status=summary.status, error_code=summary.error_code))
    return summary
