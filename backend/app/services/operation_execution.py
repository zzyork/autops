import logging

from fastapi import HTTPException

from ..core.ssh import HostKeyRequired, SSHConnectionError, open_ssh_connection
from ..core.ssh_commands import CommandExecutionError
from ..operation_models import OperationHost
from ..repositories import operations as repository
from .operations import command, digest, privilege, visible_output
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
        status, reason = "failed", "远端检查未通过"
        try:
            plan = resolve_plan(session, manager.cipher, "host", host_id)
            if plan.snapshot != host.asset_snapshot:
                raise ValueError("asset_changed")
            session.rollback()
            with open_ssh_connection(plan.target, plan.jump) as client:
                if task.destructive:
                    if privilege(client, task.sudo) != host.use_sudo:
                        raise ValueError("privilege_changed")
                if manager.stopping.is_set() or manager.persistence_failed.is_set():
                    status, reason = "interrupted", "任务已停止"
                else:
                    pre = command(client, task.preflight_command, host.use_sudo)
                    if pre.exit_status != 0 or digest(pre.stdout) != host.preflight_hash:
                        raise ValueError("preflight_changed")
                    for step in host.steps:
                        if manager.stopping.is_set() or manager.persistence_failed.is_set():
                            status, reason = "interrupted", "任务已停止"
                            break
                        step.status = "running"
                        session.commit()
                        try:
                            result = command(client, step.command, host.use_sudo, step.timeout_seconds)
                        except CommandExecutionError as exc:
                            step.status = "unknown"
                            status, reason = "unknown", "命令超时、断连或输出超限，执行结果未知"
                            session.commit()
                            break
                        step.stdout = visible_output(result.stdout)
                        step.stderr = visible_output(result.stderr)
                        step.exit_status = result.exit_status
                        step.status = "succeeded" if result.exit_status == 0 else "failed"
                        if step.position == len(host.steps) - 1:
                            host.after = step.stdout
                        session.commit()
                        if result.exit_status != 0:
                            status, reason = "failed", "执行步骤或结果核验失败"
                            break
                    else:
                        status, reason = "succeeded", None
        except (HostKeyRequired, SSHConnectionError, CommandExecutionError) as exc:
            logger.warning("Operation host %s remote failure: %s", run_id, type(exc).__name__)
            status, reason = "failed", "连接或预检中断，写入命令未开始"
        except (ValueError, HTTPException) as exc:
            logger.warning("Operation host %s validation failure: %s", run_id, type(exc).__name__)
            status, reason = "failed", "资产、权限或远端状态已变化"
        host.status, host.error = status, reason
        session.commit()
        repository.summarize(session, task_id)
