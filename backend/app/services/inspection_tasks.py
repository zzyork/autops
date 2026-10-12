import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from cryptography.fernet import Fernet
from fastapi import HTTPException
from sqlalchemy.orm import Session, sessionmaker

from ..core.ssh import HostKeyRequired, SSHConnectionError, open_ssh_connection
from ..core.ssh_commands import CommandExecutionError, run_command
from ..inspection_models import InspectionTask
from ..models import Host, utc_now
from ..repositories import inspections as repository
from ..repositories.ssh_connections import get_asset
from ..schemas.inspections import CheckPayload, InspectionConfig, InspectionInput
from .inspection_checks import InspectionCheckError, collect
from .ssh_assets import resolve_plan

logger = logging.getLogger(__name__)
MAX_INSPECTION_WORKERS = 4
MAX_PENDING_HOSTS = 64


class InspectionManager:
    def __init__(self, sessions: sessionmaker[Session], cipher: Fernet):
        self.sessions = sessions
        self.cipher = cipher
        self.lock = threading.Lock()
        self.stopping = threading.Event()
        self.active: set[int] = set()
        self.persistence_failed = threading.Event()
        with sessions() as session:
            repository.interrupt_unfinished(session)
        self.executor = ThreadPoolExecutor(max_workers=MAX_INSPECTION_WORKERS, thread_name_prefix="inspection")

    def start(self, session: Session, data: InspectionInput, config: InspectionConfig) -> InspectionTask:
        snapshots = []
        for selected in data.hosts:
            asset = get_asset(session, "host", selected.id)
            if not isinstance(asset, Host):
                raise HTTPException(404, "主机不存在")
            if asset.version != selected.version:
                raise HTTPException(409, "主机已变更，请刷新后重试")
            plan = resolve_plan(session, self.cipher, "host", selected.id)
            snapshots.append({"host_id": asset.id, "host_name": asset.name, "address": plan.target.address,
                              "port": asset.port, "username": asset.username,
                              "group_name": repository.get_group_name(session, asset.group_id),
                              "asset_snapshot": plan.snapshot})
        host_ids = {item.id for item in data.hosts}
        with self.lock:
            if self.stopping.is_set() or self.persistence_failed.is_set() or len(self.active) + len(host_ids) > MAX_PENDING_HOSTS:
                raise HTTPException(503, "巡检队列不可用")
            if self.active & host_ids:
                raise HTTPException(409, "所选主机已有巡检正在执行")
            task = repository.create_task(session, data, snapshots, config)
            self.active.update(host_ids)
            for host in task.hosts:
                self.executor.submit(self._run_host, task.id, host.id, host.host_id)
        return task

    def close(self) -> None:
        with self.lock:
            self.stopping.set()
        self.executor.shutdown(wait=True, cancel_futures=True)
        with self.sessions() as session:
            repository.interrupt_unfinished(session)

    def _run_host(self, task_id: str, run_id: str, host_id: int) -> None:
        def save(session: Session) -> None:
            try:
                session.commit()
            except Exception:
                self.persistence_failed.set()
                raise

        try:
            with self.sessions() as session:
                host = repository.get_host_run(session, run_id)
                task = repository.get_task(session, task_id)
                if host is None or task is None:
                    raise ValueError("巡检记录不存在")
                host.status = "running"
                host.started_at = utc_now()
                save(session)
                repository.summarize_task(session, task_id)
                config = InspectionConfig.model_validate(task.config)
                deadline = time.monotonic() + config.host_timeout_seconds
                failure_code = None
                interrupted = False
                try:
                    plan = resolve_plan(session, self.cipher, "host", host_id)
                    if plan.snapshot != host.asset_snapshot:
                        raise HTTPException(409, "资产已变更")
                    session.rollback()
                    with open_ssh_connection(plan.target, plan.jump, timeout_seconds=config.host_timeout_seconds) as client:
                        for check in host.checks:
                            if self.stopping.is_set() or self.persistence_failed.is_set():
                                failure_code, interrupted = "interrupted", True
                                break
                            if time.monotonic() >= deadline:
                                failure_code = "timeout"
                                break
                            check.status = "running"
                            check.started_at = utc_now()
                            save(session)
                            try:
                                runner = lambda command: run_command(client, command, config.command_timeout_seconds, deadline)
                                payload = collect(check.check_id, runner, config)
                                check.payload = payload.model_dump(mode="json")
                                check.conclusion = payload.conclusion
                                check.status = "completed"
                            except CommandExecutionError as exc:
                                check.status, check.error_code = "failed", exc.code
                                if not exc.connected:
                                    failure_code = "connection"
                            except InspectionCheckError as exc:
                                check.status, check.error_code = "failed", exc.code
                            except Exception as exc:
                                check.status, check.error_code = "failed", "internal"
                                logger.error("Inspection check %s/%s failed: %s", run_id, check.check_id, type(exc).__name__)
                            check.finished_at = utc_now()
                            save(session)
                            # 不对断开的会话自动重连，剩余检查明确标记为未执行。
                            if failure_code is not None:
                                break
                except HostKeyRequired:
                    failure_code = "host_key_required"
                except SSHConnectionError as exc:
                    failure_code = exc.code
                except HTTPException:
                    failure_code = "asset_changed"
                except Exception as exc:
                    if self.persistence_failed.is_set():
                        raise
                    failure_code = "internal"
                    logger.error("Inspection host %s failed: %s", run_id, type(exc).__name__)
                for check in host.checks:
                    if check.status in ("queued", "running"):
                        check.status = "interrupted" if interrupted else "skipped"
                        check.error_code = failure_code or "not_executed"
                        check.finished_at = utc_now()
                successes = sum(check.status == "completed" for check in host.checks)
                host.status = "interrupted" if interrupted else (
                    "completed" if successes == len(host.checks) else "partial" if successes else "failed")
                host.failure_code = failure_code or ("check_failed" if host.status != "completed" else None)
                host.finished_at = utc_now()
                save(session)
                repository.summarize_task(session, task_id)
        except Exception as exc:
            # 落库失败后不继续接受任务或展示陈旧状态；恢复数据库并重启后标记未完成项中断。
            self.persistence_failed.set()
            logger.error("Inspection host %s persistence failed: %s", run_id, type(exc).__name__)
        finally:
            with self.lock:
                self.active.discard(host_id)

    def ensure_available(self) -> None:
        if self.persistence_failed.is_set():
            raise HTTPException(503, "巡检记录持久化失败")
