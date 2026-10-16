import hashlib
import logging
import re
import shlex
import threading
from concurrent.futures import ThreadPoolExecutor

from cryptography.fernet import Fernet
from fastapi import HTTPException
from sqlalchemy.orm import Session, sessionmaker

from ..core.ssh import HostKeyRequired, SSHConnectionError, open_ssh_connection
from ..core.ssh_commands import CommandExecutionError, CommandResult, run_command
from ..repositories import operations as repository
from ..schemas.operations import InspectInput, Inspection, PlanInput
from .operation_commands import MODULES, build_operation, inspect_command
from .ssh_assets import resolve_plan

logger = logging.getLogger(__name__)
MAX_ACTIVE_HOSTS = 32
MAX_VISIBLE_OUTPUT = 8192
URL_PATTERN = re.compile(r"(?i)https?://[^\s\"'<>]+")


def visible_output(value: str) -> str:
    # Repository configurations can include authentication in URLs; never expose them in task history.
    cleaned = URL_PATTERN.sub("[URL 已隐藏]", value)
    return cleaned[:MAX_VISIBLE_OUTPUT] + ("\n[输出已截断]" if len(cleaned) > MAX_VISIBLE_OUTPUT else "")


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def command(client, body: str, sudo: bool, timeout: float = 60) -> CommandResult:
    script = "sudo -n -- bash -c " + shlex.quote(body) if sudo else body
    return run_command(client, script, timeout)


def privilege(client, sudo_requested: bool) -> bool:
    uid = run_command(client, "id -u", 15)
    if uid.exit_status != 0:
        raise ValueError("无法验证远端权限")
    if uid.stdout.strip() == "0":
        return False
    if not sudo_requested:
        raise ValueError("写操作需要 root 或显式选择免密 sudo")
    result = run_command(client, "sudo -n -- id -u", 15)
    if result.exit_status != 0 or result.stdout.strip() != "0":
        raise ValueError("免密 sudo 权限检查未通过")
    return True


class OperationManager:
    def __init__(self, sessions: sessionmaker[Session], cipher: Fernet):
        self.sessions = sessions
        self.cipher = cipher
        self.lock = threading.Lock()
        self.stopping = threading.Event()
        self.persistence_failed = threading.Event()
        self.active: set[int] = set()
        self.remaining: dict[str, int] = {}
        self.task_hosts: dict[str, set[int]] = {}
        with sessions() as session:
            repository.interrupt_unfinished(session)
        self.executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="operation")

    def ensure_available(self) -> None:
        if self.persistence_failed.is_set():
            raise HTTPException(503, "运维记录持久化失败")

    def stop_accepting(self) -> None:
        with self.lock:
            self.stopping.set()

    def close(self) -> None:
        self.stop_accepting()
        self.executor.shutdown(wait=True)
        if not self.persistence_failed.is_set():
            with self.sessions() as session:
                repository.interrupt_unfinished(session)

    def inspect(self, session: Session, data: InspectInput) -> Inspection:
        self.ensure_available()
        try:
            plan = resolve_plan(session, self.cipher, "host", data.host_id)
            body = inspect_command(data.module)
            session.rollback()
            with open_ssh_connection(plan.target, plan.jump) as client:
                use_sudo = privilege(client, True) if data.sudo else False
                result = command(client, body, use_sudo)
            if result.exit_status != 0:
                raise HTTPException(409, "远端读取失败")
            return Inspection(host_id=data.host_id, host_name=plan.name, module=data.module,
                              output=visible_output(result.stdout))
        except HostKeyRequired:
            raise HTTPException(409, {"code": "ssh_identity_required", "target": {
                "target_type": "host", "target_id": data.host_id}}) from None
        except (SSHConnectionError, CommandExecutionError) as exc:
            logger.warning("Operation inspect failed: %s", type(exc).__name__)
            raise HTTPException(409, "主机信任、连接或读取检查失败") from None
        except ValueError:
            raise HTTPException(409, "读取权限检查失败") from None

    def prepare(self, session: Session, data: PlanInput):
        self.ensure_available()
        if self.stopping.is_set():
            raise HTTPException(503, "运维队列已关闭")
        definition = next((item for item in MODULES[data.module].ACTIONS if item["id"] == data.action), None)
        if definition is None:
            raise HTTPException(422, "不支持的运维操作")
        optional = {field["key"] for field in definition["fields"] if not field["required"]}
        params = {key: value for key, value in data.params.items()
                  if not (key in optional and (value is None or value == ""))}
        try:
            spec = build_operation(data.module, data.action, params)
        except ValueError:
            raise HTTPException(422, "运维参数无效") from None
        snapshots = []
        for host_id in data.host_ids:
            try:
                plan = resolve_plan(session, self.cipher, "host", host_id)
                session.rollback()
                with open_ssh_connection(plan.target, plan.jump) as client:
                    use_sudo = privilege(client, data.sudo) if spec.destructive else False
                    result = command(client, spec.preflight, use_sudo)
                if result.exit_status != 0:
                    raise ValueError("远端预检未通过")
                snapshots.append(dict(host_id=host_id, host_name=plan.name, address=plan.target.address,
                                      asset_snapshot=plan.snapshot, use_sudo=use_sudo,
                                      preflight_stdout=visible_output(result.stdout), preflight_hash=digest(result.stdout),
                                      before=visible_output(result.stdout), after=None, error=None))
            except HostKeyRequired:
                raise HTTPException(409, {"code": "ssh_identity_required", "target": {
                    "target_type": "host", "target_id": host_id}}) from None
            except (SSHConnectionError, CommandExecutionError, ValueError) as exc:
                logger.warning("Operation prepare preflight failed for host %s: %s", host_id, type(exc).__name__)
                raise HTTPException(409, "主机权限、信任、连接或预检失败") from None
        if self.stopping.is_set() or self.persistence_failed.is_set():
            raise HTTPException(503, "运维队列不可用")
        try:
            return repository.create_plan(session, data, params, spec, snapshots)
        except Exception as exc:
            self.persistence_failed.set()
            logger.error("Operation plan persistence failed: %s", type(exc).__name__)
            raise HTTPException(503, "运维记录持久化失败") from None

    def confirm(self, task_id: str):
        self.ensure_available()
        with self.lock:
            if self.stopping.is_set() or self.persistence_failed.is_set():
                raise HTTPException(503, "运维队列不可用")
            with self.sessions() as session:
                task = repository.get_task(session, task_id)
                if task is None:
                    raise HTTPException(404, "运维任务不存在")
                if task.module not in MODULES or task.action not in {
                    item["id"] for item in MODULES[task.module].ACTIONS
                }:
                    raise HTTPException(409, "运维操作已移除")
                host_ids = {host.host_id for host in task.hosts}
                if self.active & host_ids:
                    raise HTTPException(409, "所选主机有未完成的运维任务")
                if len(self.active) + len(host_ids) > MAX_ACTIVE_HOSTS:
                    raise HTTPException(503, "运维队列已满")
                try:
                    outcome = repository.claim_plan(session, task_id)
                except Exception as exc:
                    self.persistence_failed.set()
                    logger.error("Operation confirmation persistence failed: %s", type(exc).__name__)
                    raise HTTPException(503, "运维记录持久化失败") from None
                if outcome != "claimed":
                    if outcome == "missing":
                        raise HTTPException(404, "运维任务不存在")
                    if outcome == "blocked":
                        raise HTTPException(409, "主机存在未解除的未知执行结果，请先在带外核对远端进程已停止")
                    raise HTTPException(409, "任务已确认或计划已过期")
                self.active.update(host_ids)
                self.remaining[task_id] = len(host_ids)
                self.task_hosts[task_id] = host_ids
                for index, host in enumerate(task.hosts):
                    try:
                        self.executor.submit(self._run_host, task_id, host.id, host.host_id)
                    except RuntimeError:
                        unsubmitted = task.hosts[index:]
                        try:
                            with self.sessions() as recovery:
                                repository.interrupt_unsubmitted(recovery, task_id, [item.id for item in unsubmitted])
                        except Exception as exc:
                            self.persistence_failed.set()
                            logger.error("Operation dispatch recovery persistence failed: %s", type(exc).__name__)
                            raise HTTPException(503, "运维记录持久化失败") from None
                        self.remaining[task_id] -= len(unsubmitted)
                        if self.remaining[task_id] == 0:
                            self.active.difference_update(host_ids)
                            del self.remaining[task_id]
                            del self.task_hosts[task_id]
                        break
                with self.sessions() as result_session:
                    return repository.get_task(result_session, task_id)

    def resolve(self, task_id: str, host_id: int, note: str):
        self.ensure_available()
        with self.lock:
            with self.sessions() as session:
                try:
                    outcome = repository.resolve_host(session, task_id, host_id, note)
                except Exception as exc:
                    self.persistence_failed.set()
                    logger.error("Operation resolution persistence failed: %s", type(exc).__name__)
                    raise HTTPException(503, "运维记录持久化失败") from None
                if outcome == "missing":
                    raise HTTPException(404, "运维任务不存在")
                if outcome == "missing_host":
                    raise HTTPException(404, "任务主机不存在")
                if outcome == "conflict":
                    raise HTTPException(409, "任务尚未结束、主机结果并非未知或已解除阻塞")
                return repository.get_task(session, task_id)

    def _run_host(self, task_id: str, run_id: str, host_id: int) -> None:
        from .operation_execution import execute_host

        try:
            execute_host(self, task_id, run_id, host_id)
        except Exception as exc:
            self.persistence_failed.set()
            logger.error("Operation host %s persistence or execution failed: %s", run_id, type(exc).__name__)
        finally:
            with self.lock:
                self.remaining[task_id] -= 1
                if self.remaining[task_id] == 0:
                    if not self.persistence_failed.is_set():
                        with self.sessions() as session:
                            try:
                                repository.summarize(session, task_id)
                            except Exception:
                                self.persistence_failed.set()
                                logger.error("Operation task %s summary persistence failed", task_id)
                    self.active.difference_update(self.task_hosts.pop(task_id))
                    del self.remaining[task_id]
