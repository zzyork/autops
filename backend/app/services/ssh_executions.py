import hashlib
import json
import logging
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from cryptography.fernet import Fernet
from fastapi import HTTPException
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from ..core.ssh import HostKeyRequired, SSHConnectionError, open_ssh_connection
from ..core.ssh_commands import MAX_OUTPUT_BYTES, CommandExecutionError, run_command
from ..models import utc_now
from ..repositories import ssh_executions as repository
from ..schemas.ssh_executions import ExecutionDetail, ExecutionInput
from .ssh_assets import ConnectionPlan, resolve_plan

logger = logging.getLogger(__name__)
MAX_WORKERS = 4
MAX_PENDING = 16
MAX_SUBSCRIBERS = 32


def plan_identity(plan: ConnectionPlan) -> str:
    keys = (plan.snapshot, plan.target.trusted_key, plan.jump.trusted_key if plan.jump else None)
    return hashlib.sha256(json.dumps(keys).encode()).hexdigest()


def secrets_for(plan: ConnectionPlan) -> tuple[str, ...]:
    values = set()
    for endpoint in (plan.target, plan.jump):
        if endpoint is None:
            continue
        if endpoint.password:
            values.add(endpoint.password)
        if endpoint.private_key:
            values.add(endpoint.private_key)
            values.update(line for line in endpoint.private_key.splitlines() if len(line) > 3)
    return tuple(sorted(values, key=len, reverse=True))


class OutputFilter:
    def __init__(self, secrets: tuple[str, ...]):
        self.secrets = tuple(sorted(set(filter(None, secrets)), key=len, reverse=True))
        self.pending = ""
        self.pattern = re.compile("|".join(re.escape(secret) for secret in self.secrets)) if self.secrets else None
        self.by_initial = {char: tuple(secret for secret in self.secrets if secret.startswith(char))
                           for char in {secret[0] for secret in self.secrets}}
        self.longest = max((len(secret) for secret in self.secrets), default=0)

    def feed(self, value: str, *, final: bool = False) -> str:
        self.pending += value
        if self.pattern is None:
            result, self.pending = self.pending, ""
        else:
            boundary = len(self.pending)
            if not final:
                # Keep only a suffix that can still become a secret on the next chunk.
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
        return "".join(char if char.isprintable() or char in "\n\t" else "�" for char in result)


def _identity_error(plan: ConnectionPlan) -> HTTPException | None:
    endpoint = plan.jump if plan.jump is not None and plan.jump.trusted_key is None else plan.target
    if endpoint.trusted_key is not None:
        return None
    return HTTPException(409, {"code": "ssh_identity_required", "target": {
        "target_type": endpoint.target_type, "target_id": endpoint.target_id,
    }})


class SSHExecutionManager:
    def __init__(self, sessions: sessionmaker[Session], cipher: Fernet):
        self.sessions = sessions
        self.cipher = cipher
        self.lock = threading.RLock()
        self.stopping = threading.Event()
        self.persistence_failed = threading.Event()
        self.active: dict[int, threading.Event] = {}
        self.subscribers = threading.BoundedSemaphore(MAX_SUBSCRIBERS)
        with sessions() as session:
            repository.recover_unfinished(session)
        self.executor = ThreadPoolExecutor(max_workers=MAX_WORKERS, thread_name_prefix="ssh-execution")

    def ensure_available(self) -> None:
        if self.persistence_failed.is_set():
            raise HTTPException(503, "SSH 执行记录暂不可用")

    def storage_failed(self) -> None:
        self.persistence_failed.set()
        with self.lock:
            for cancelled in self.active.values():
                cancelled.set()

    def subscribe(self) -> None:
        self.ensure_available()
        if not self.subscribers.acquire(blocking=False):
            raise HTTPException(503, "SSH 订阅数量已达上限")

    def unsubscribe(self) -> None:
        self.subscribers.release()

    def start(self, data: ExecutionInput) -> ExecutionDetail:
        self.ensure_available()
        digest = hashlib.sha256(json.dumps(data.model_dump(mode="json", exclude={"id"}),
                                           sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        execution_id = str(data.id)
        with self.lock:
            if self.stopping.is_set() or self.persistence_failed.is_set():
                raise HTTPException(503, "SSH 执行队列不可用")
            try:
                with self.sessions() as session:
                    repository.begin_write(session)
                    existing = repository.get_execution(session, execution_id)
                    if existing is not None:
                        if existing.digest != digest:
                            raise HTTPException(409, "执行标识已用于不同请求")
                        return repository.detail(session, execution_id)
                    if repository.request_used(session, execution_id):
                        raise HTTPException(409, "该执行标识的记录已删除，不能再次执行")
                    if len(self.active) >= MAX_PENDING:
                        raise HTTPException(503, "SSH 执行队列已满")
                    if data.host.id in self.active:
                        raise HTTPException(409, "该主机已有执行任务")
                    plan = resolve_plan(session, self.cipher, "host", data.host.id)
                    if plan.version != data.host.version:
                        raise HTTPException(409, "主机已变更，请刷新后重试")
                    identity_error = _identity_error(plan)
                    if identity_error:
                        raise identity_error
                    secrets = secrets_for(plan)
                    if any(secret in step.command for step in data.steps for secret in secrets):
                        raise HTTPException(422, "命令包含已知资产凭据")
                    repository.create_execution(session, data, digest, plan.name, plan.target.address, plan_identity(plan))
                cancelled = threading.Event()
                self.active[data.host.id] = cancelled
                try:
                    self.executor.submit(self._run, execution_id, data.host.id, cancelled)
                except Exception:
                    self.active.pop(data.host.id, None)
                    with self.sessions() as session:
                        repository.change_state(session, execution_id, lambda execution, items: self._finish(
                            execution, items, None, "failed", "dispatch_failed"))
                with self.sessions() as session:
                    return repository.detail(session, execution_id)
            except HTTPException:
                raise
            except Exception as exc:
                self.storage_failed()
                logger.error("SSH execution create/storage failed: %s", type(exc).__name__)
                raise HTTPException(503, "SSH 执行记录暂不可用") from None

    @staticmethod
    def _finish(execution, items, step, status: str, code: str | None = None,
                exit_status: int | None = None) -> None:
        now = utc_now()
        if step is not None:
            step.status = status
            step.error_code = code
            step.exit_status = exit_status
            step.finished_at = now
        execution.status = status
        execution.error_code = code
        execution.finished_at = now
        for item in items:
            if item.status == "queued":
                item.status = "skipped"
                item.error_code = code or "not_executed"
                item.finished_at = now

    def _change(self, execution_id: str, change) -> None:
        with self.sessions() as session:
            try:
                repository.change_state(session, execution_id, change)
            except Exception:
                self.storage_failed()
                raise

    def _plan(self, execution_id: str, host_id: int) -> ConnectionPlan:
        with self.sessions() as session:
            execution = repository.get_execution(session, execution_id)
            plan = resolve_plan(session, self.cipher, "host", host_id)
            if plan_identity(plan) != execution.asset_snapshot or _identity_error(plan):
                raise HTTPException(409, "资产或服务器信任已变更")
            return plan

    def _run(self, execution_id: str, host_id: int, cancelled: threading.Event) -> None:
        current = None
        dispatched = False
        try:
            with self.sessions() as session:
                execution = repository.get_execution(session, execution_id)
                timeout = execution.timeout_seconds
                items = repository.steps(session, execution_id)
                selected = [(item.id, item.command, item.timeout_seconds, item.success_exit_codes) for item in items]
            deadline = time.monotonic() + timeout
            if cancelled.is_set():
                self._change(execution_id, lambda execution, items: self._finish(execution, items, None, "failed", "interrupted"))
                return
            plan = self._plan(execution_id, host_id)
            self._change(execution_id, lambda execution, items: (
                setattr(execution, "status", "running"), setattr(execution, "started_at", utc_now())))
            with open_ssh_connection(plan.target, plan.jump, timeout_seconds=max(0.001, deadline - time.monotonic())) as client:
                for step_id, command, step_timeout, accepted in selected:
                    current = None
                    if cancelled.is_set() or self.persistence_failed.is_set():
                        raise CommandExecutionError("interrupted", False, dispatched=False)
                    if time.monotonic() >= deadline:
                        raise CommandExecutionError("timeout", True, dispatched=False)
                    plan = self._plan(execution_id, host_id)
                    self._change(execution_id, lambda execution, items: self._start_step(items, step_id))
                    current = step_id
                    filters = {stream: OutputFilter(secrets_for(plan)) for stream in ("stdout", "stderr")}
                    output_bytes = 0
                    output_exceeded = False
                    dispatched = True  # Conservative if the call fails before core can report dispatch.

                    def save_text(stream: str, filtered: str) -> None:
                        nonlocal output_bytes, output_exceeded
                        if output_exceeded or not filtered:
                            return
                        encoded = filtered.encode("utf-8")
                        available = MAX_OUTPUT_BYTES - output_bytes
                        if len(encoded) > available:
                            filtered = encoded[:available].decode("utf-8", errors="ignore")
                            encoded = filtered.encode("utf-8")
                            output_exceeded = True
                            cancelled.set()
                        output_bytes += len(encoded)
                        if filtered:
                            with self.sessions() as session:
                                try:
                                    repository.save_output(session, execution_id, step_id, stream, filtered)
                                except Exception:
                                    self.storage_failed()
                                    raise

                    def output(stream: str, value: str) -> None:
                        save_text(stream, filters[stream].feed(value))

                    error = None
                    result = None
                    try:
                        result = run_command(client, command, step_timeout, deadline, on_output=output, cancel=cancelled)
                    except CommandExecutionError as exc:
                        error = exc
                    finally:
                        if not self.persistence_failed.is_set() and not output_exceeded:
                            for stream, filter_ in filters.items():
                                save_text(stream, filter_.feed("", final=True))
                    if self.persistence_failed.is_set():
                        return
                    if output_exceeded:
                        status_code = result.exit_status if result is not None else error.exit_status if error else None
                        self._change(execution_id, lambda execution, items: self._finish(
                            execution, items, next(item for item in items if item.id == step_id),
                            "failed" if status_code is not None and status_code >= 0 else "unknown",
                            "output_limit", status_code if status_code is not None and status_code >= 0 else None))
                        return
                    status_code = result.exit_status if result is not None else error.exit_status if error else None
                    if error is not None and error.code in ("timeout", "output_limit", "interrupted", "internal"):
                        known = status_code is not None and status_code >= 0
                        self._change(execution_id, lambda execution, items: self._finish(
                            execution, items, next(item for item in items if item.id == step_id),
                            "failed" if known or not error.dispatched else "unknown",
                            error.code, status_code if known else None))
                        return
                    if status_code is not None and status_code >= 0:
                        if status_code in accepted:
                            self._change(execution_id, lambda execution, items: self._complete_step(items, step_id, status_code))
                            dispatched = False
                            current = None
                            if error is not None and not error.connected and step_id != selected[-1][0]:
                                self._change(execution_id, lambda execution, items: self._finish(
                                    execution, items, None, "failed", "connection"))
                                return
                            continue
                        self._change(execution_id, lambda execution, items: self._finish(
                            execution, items, items[next(i for i, item in enumerate(items) if item.id == step_id)],
                            "failed", "exit_status", status_code))
                        return
                    code = error.code if error else "unknown"
                    status = "unknown" if error is None or error.dispatched else "failed"
                    self._change(execution_id, lambda execution, items: self._finish(
                        execution, items, next(item for item in items if item.id == step_id), status, code))
                    return
            self._change(execution_id, lambda execution, items: self._finish(execution, items, None, "succeeded"))
        except (HostKeyRequired, SSHConnectionError, HTTPException, CommandExecutionError) as exc:
            if isinstance(exc, SSHConnectionError):
                code = exc.code
            elif isinstance(exc, HostKeyRequired):
                code = "host_key_required"
            elif isinstance(exc, CommandExecutionError):
                code = exc.code
            else:
                code = "asset_changed"
            if not self.persistence_failed.is_set():
                try:
                    self._change(execution_id, lambda execution, items: self._finish(
                        execution, items, next((item for item in items if item.id == current), None),
                        "unknown" if dispatched else "failed", code))
                except Exception as finish_error:
                    logger.error("SSH execution %s could not persist terminal state: %s",
                                 execution_id, type(finish_error).__name__)
        except Exception as exc:
            logger.error("SSH execution %s failed: %s", execution_id, type(exc).__name__)
            if isinstance(exc, SQLAlchemyError):
                self.storage_failed()
            if not self.persistence_failed.is_set():
                try:
                    self._change(execution_id, lambda execution, items: self._finish(
                        execution, items, next((item for item in items if item.id == current), None),
                        "unknown" if dispatched else "failed", "internal"))
                except Exception as finish_error:
                    logger.error("SSH execution %s could not persist terminal state: %s",
                                 execution_id, type(finish_error).__name__)
        finally:
            with self.lock:
                self.active.pop(host_id, None)

    @staticmethod
    def _start_step(items, step_id: int) -> None:
        item = next(item for item in items if item.id == step_id)
        item.status = "running"
        item.started_at = utc_now()

    @staticmethod
    def _complete_step(items, step_id: int, exit_status: int) -> None:
        item = next(item for item in items if item.id == step_id)
        item.status = "succeeded"
        item.exit_status = exit_status
        item.finished_at = utc_now()

    def stop_accepting(self) -> None:
        with self.lock:
            self.stopping.set()
            for cancelled in self.active.values():
                cancelled.set()

    def close(self) -> None:
        self.stop_accepting()
        self.executor.shutdown(wait=True)
        if not self.persistence_failed.is_set():
            with self.sessions() as session:
                repository.recover_unfinished(session)
