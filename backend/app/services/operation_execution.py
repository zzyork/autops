import logging

from fastapi import HTTPException

from ..core.ssh import HostKeyRequired, SSHConnectionError, open_ssh_connection
from ..core.ssh_commands import CommandExecutionError, OutputObservationError
from ..operation_models import OperationHost
from ..repositories import operations as repository
from .operation_output import OperationOutput
from .operations import command, digest, privilege
from .ssh_assets import resolve_plan

logger = logging.getLogger(__name__)


def execute_host(manager, task_id: str, run_id: str, host_id: int) -> None:
    with manager.sessions() as session:
        host = session.get(OperationHost, run_id)
        task = repository.get_task(session, task_id)
        if host is None or task is None:
            raise ValueError("运维记录不存在")
        if manager.stopping.is_set() or manager.persistence_failed.is_set():
            host.status, host.error = "interrupted", "任务在执行前已停止"
            session.commit()
            repository.summarize(session, task_id)
            return
        host.status = "running"
        session.commit()
        repository.summarize(session, task_id)
        # Keep only scalar execution inputs across the remote command; no stale ORM object may flush its output.
        snapshot, preflight_hash = host.asset_snapshot, host.preflight_hash
        destructive, preflight = task.destructive, task.preflight_command
        steps = [(step.id, step.position, step.command, step.timeout_seconds) for step in host.steps]
    status, reason, identity_required = "failed", "远端检查未通过", False
    try:
        with manager.sessions() as session:
            plan = resolve_plan(session, manager.cipher, "host", host_id)
            if plan.snapshot != snapshot:
                raise ValueError("asset_changed")
        with open_ssh_connection(plan.target, plan.jump) as client:
            if destructive:
                privilege(client)
            if manager.stopping.is_set() or manager.persistence_failed.is_set():
                status, reason = "interrupted", "任务已停止"
            else:
                pre = command(client, preflight)
                if pre.exit_status != 0 or digest(pre.stdout) != preflight_hash:
                    raise ValueError("preflight_changed")
                for step_id, position, body, timeout in steps:
                    if manager.stopping.is_set() or manager.persistence_failed.is_set():
                        status, reason = "interrupted", "任务已停止"
                        break
                    with manager.sessions() as session:
                        repository.update_step(session, step_id, status="running")
                    output = OperationOutput()
                    last_version = 0

                    def flush() -> None:
                        nonlocal last_version
                        version, stdout, stderr = output.snapshot()
                        if version != last_version:
                            with manager.sessions() as session:
                                repository.update_step(session, step_id, stdout=stdout, stderr=stderr)
                            last_version = version

                    result = None
                    remote_error = None
                    try:
                        result = command(client, body, timeout,
                                         on_output=output.feed, flush_output=flush)
                    except CommandExecutionError as exc:
                        remote_error = exc
                    finally:
                        output.finish()
                    _, stdout, stderr = output.snapshot()
                    if remote_error is not None:
                        try:
                            with manager.sessions() as session:
                                repository.update_step(session, step_id, status="unknown", stdout=stdout, stderr=stderr)
                        except Exception as exc:
                            raise OutputObservationError from exc
                        status, reason = "unknown", "命令超时、断连或输出超限，执行结果未知"
                        break
                    try:
                        with manager.sessions() as session:
                            repository.update_step(session, step_id, status="succeeded" if result.exit_status == 0 else "failed",
                                                   stdout=stdout, stderr=stderr, exit_status=result.exit_status,
                                                   run_id=run_id if position == len(steps) - 1 else None)
                    except Exception as exc:
                        raise OutputObservationError from exc
                    if result.exit_status != 0:
                        status, reason = "failed", "执行步骤或结果核验失败"
                        break
                else:
                    status, reason = "succeeded", None
    except HostKeyRequired:
        identity_required = True
        status, reason = "failed", "服务器身份需确认，写入命令未开始"
    except (SSHConnectionError, CommandExecutionError) as exc:
        logger.warning("Operation host %s remote failure: %s", run_id, type(exc).__name__)
        status, reason = "failed", "连接或预检中断，写入命令未开始"
    except (ValueError, HTTPException) as exc:
        logger.warning("Operation host %s validation failure: %s", run_id, type(exc).__name__)
        status, reason = "failed", "资产、权限或远端状态已变化"
    except OutputObservationError:
        manager.persistence_failed.set()
        try:
            _, stdout, stderr = output.snapshot()
            with manager.sessions() as session:
                repository.update_step(session, step_id, status="unknown", stdout=stdout, stderr=stderr)
                host = session.get(OperationHost, run_id)
                host.status, host.error = "unknown", "输出保存失败，执行结果未知"
                session.commit()
                repository.summarize(session, task_id)
        except Exception as exc:
            logger.error("Operation host %s unknown result could not be persisted: %s", run_id, type(exc).__name__)
        raise
    with manager.sessions() as session:
        host = session.get(OperationHost, run_id)
        host.status, host.error, host.identity_required = status, reason, identity_required
        session.commit()
        repository.summarize(session, task_id)
