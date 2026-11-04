"""执行用户已确认的非巡检命令计划；计划本身由 AI 对话持久化。"""

import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict

from cryptography.fernet import Fernet
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy.orm import Session, sessionmaker

from ..ai_models import AIProposal
from ..core.ssh import HostKeyRequired, SSHConnectionError, open_ssh_connection
from ..core.ssh_workflows import CommandStep, WorkflowEvent, run_workflow
from ..repositories import ai as repository
from ..schemas.ai import OperationExecution, OperationHostResult, OperationInput, OperationStepResult
from .ssh_assets import ConnectionPlan, resolve_plan

logger = logging.getLogger(__name__)
MAX_OPERATION_WORKERS = 4


class AIOperationManager:
    def __init__(self, sessions: sessionmaker[Session], cipher: Fernet):
        self.sessions, self.cipher = sessions, cipher
        self.guard = threading.Lock()
        self.stopping = threading.Event()
        self.persistence_failed = threading.Event()
        self.tasks: dict[str, tuple[str, threading.Event, set[int]]] = {}
        with sessions() as session:
            repository.interrupt_operations(session)
        self.executor = ThreadPoolExecutor(max_workers=MAX_OPERATION_WORKERS, thread_name_prefix="ai-operation")

    def ensure_available(self) -> None:
        if self.persistence_failed.is_set():
            raise HTTPException(503, "运维执行记录保存失败，结果尚未确认，请恢复存储后重启服务")

    def activity(self, session_id: str) -> tuple[bool, bool]:
        self.ensure_available()
        with self.guard:
            events = [cancel for owner, cancel, _ in self.tasks.values() if owner == session_id]
            return bool(events), any(cancel.is_set() for cancel in events)

    def ensure_idle(self, session_id: str) -> None:
        if self.activity(session_id)[0]:
            raise HTTPException(409, "会话的运维命令仍在执行，请等待执行结束")

    def cancel(self, session_id: str) -> None:
        with self.guard:
            for owner, cancel, _ in self.tasks.values():
                if owner == session_id:
                    cancel.set()

    def close(self) -> None:
        with self.guard:
            self.stopping.set()
            for _, cancel, _ in self.tasks.values():
                cancel.set()
        self.executor.shutdown(wait=True)
        with self.sessions() as session:
            repository.interrupt_operations(session)

    def start(self, session: Session, proposal: AIProposal, cancelled: threading.Event) -> None:
        try:
            data = OperationInput(name=proposal.name, host_ids=[host["id"] for host in proposal.hosts],
                                  commands=proposal.commands)
        except (KeyError, ValidationError):
            raise HTTPException(409, "运维计划无效，请重新准备") from None
        plans: list[ConnectionPlan] = []
        for host in proposal.hosts:
            plan = resolve_plan(session, self.cipher, "host", host["id"])
            if plan.version != host["version"]:
                raise HTTPException(409, "主机已变更，请重新准备运维计划")
            for endpoint in (plan.jump, plan.target):
                if endpoint is not None and endpoint.trusted_key is None:
                    raise HTTPException(409, {"code": "ssh_identity_required", "target": {
                        "target_type": endpoint.target_type, "target_id": endpoint.target_id}})
            plans.append(plan)
        secrets = tuple(secret for plan in plans for endpoint in (plan.target, plan.jump) if endpoint is not None
                        for secret in (endpoint.password, endpoint.private_key) if secret)
        secret_parts = set(secrets)
        secret_parts.update(line for secret in secrets for line in secret.splitlines() if len(line) > 3)
        if any(secret in command.command for secret in secret_parts for command in data.commands):
            raise HTTPException(422, "运维命令不能包含连接凭据")
        execution = OperationExecution(hosts=[OperationHostResult(
            id=host["id"], name=host["name"], address=host["address"],
            steps=[OperationStepResult(name=command.name) for command in data.commands])
            for host in proposal.hosts]).model_dump(mode="json")
        proposal_id, session_id = proposal.id, proposal.session_id
        host_ids = set(data.host_ids)
        with self.guard:
            self.ensure_available()
            if self.stopping.is_set() or len(self.tasks) >= MAX_OPERATION_WORKERS:
                raise HTTPException(503, "运维执行器不可用")
            if any(owner == session_id or targets & host_ids for owner, _, targets in self.tasks.values()):
                raise HTTPException(409, "会话或目标主机已有运维命令正在执行")
            if cancelled.is_set():
                raise HTTPException(409, "请求已取消")
            cancel = threading.Event()
            # 后台取消信号独立于确认 HTTP 请求，断开确认响应不会重复提交或重跑命令。
            self.tasks[proposal_id] = (session_id, cancel, host_ids)
            proposal.status = "confirmed"
            proposal.execution = execution
            try:
                session.commit()
            except Exception:
                self.tasks.pop(proposal_id)
                raise
            try:
                self.executor.submit(self._run, proposal_id, plans, data, execution, secrets, cancel)
            except Exception as exc:
                self.tasks.pop(proposal_id)
                self._skip_remaining(execution, "dispatch_failed")
                execution["status"], execution["error_code"] = "failed", "dispatch_failed"
                self._save(proposal_id, execution)
                logger.error("AI operation %s dispatch failed: %s", proposal_id, type(exc).__name__)

    def _save(self, proposal_id: str, execution: dict) -> None:
        try:
            with self.sessions() as session:
                repository.save_operation_execution(session, proposal_id, execution)
        except Exception:
            self.persistence_failed.set()
            raise

    @staticmethod
    def _skip_remaining(execution: dict, code: str) -> None:
        for host in execution["hosts"]:
            if host["status"] == "queued":
                host["status"], host["error_code"] = "skipped", code
            for step in host["steps"]:
                if step["status"] == "queued":
                    step["status"], step["error_code"] = "skipped", "not_executed"

    def _check_plan(self, expected: ConnectionPlan) -> None:
        with self.sessions() as session:
            current = resolve_plan(session, self.cipher, "host", expected.target.target_id)
            if current.snapshot != expected.snapshot or current.target != expected.target or current.jump != expected.jump:
                raise HTTPException(409, "资产、凭据或服务器信任已变更")

    def _run_host(self, proposal_id: str, execution: dict, host: dict, plan: ConnectionPlan,
                  data: OperationInput, secrets: tuple[str, ...], cancel: threading.Event) -> None:
        host["status"] = "running"
        self._save(proposal_id, execution)

        def record(event: WorkflowEvent) -> None:
            if self.persistence_failed.is_set():
                raise RuntimeError("执行记录保存失败")
            if event.kind == "step_start":
                self._check_plan(plan)
                host["steps"][event.step_index]["status"] = "running"
                # 派发前落库；服务崩溃后对未取得退出码的步骤保守标记为未知，绝不重跑。
                self._save(proposal_id, execution)
            elif event.kind == "output":
                host["steps"][event.step_index][event.stream] += event.text
            elif event.kind == "step_end":
                host["steps"][event.step_index].update(
                    status=event.status, exit_status=event.exit_status, error_code=event.error_code)
                self._save(proposal_id, execution)

        try:
            self._check_plan(plan)
            if cancel.is_set():
                host["status"], host["error_code"] = "failed", "interrupted"
                return
            with open_ssh_connection(plan.target, plan.jump) as client:
                result = run_workflow(client, [CommandStep(command.name, command.command, command.timeout_seconds)
                                              for command in data.commands],
                                      on_event=record, cancel=cancel, secrets=secrets)
            host["status"], host["error_code"] = result.status, result.error_code
            host["steps"] = [asdict(step) for step in result.steps]
        except HostKeyRequired:
            host["status"], host["error_code"] = "failed", "host_key_required"
        except SSHConnectionError as exc:
            host["status"], host["error_code"] = "failed", exc.code
        except HTTPException as exc:
            host["status"], host["error_code"] = "failed", "configuration" if exc.status_code == 422 else "asset_changed"
        except Exception as exc:
            if self.persistence_failed.is_set():
                raise
            host["status"], host["error_code"] = "failed", "internal"
            logger.error("AI operation %s host failed: %s", proposal_id, type(exc).__name__)
        finally:
            # 异常发生在派发标记之后时，无法证明命令没有执行。
            for step in host["steps"]:
                if step["status"] == "running":
                    step["status"], step["error_code"] = "unknown", host["error_code"] or "unknown"
                    host["status"] = "unknown"

    def _run(self, proposal_id: str, plans: list[ConnectionPlan], data: OperationInput,
             execution: dict, secrets: tuple[str, ...], cancel: threading.Event) -> None:
        try:
            execution["status"] = "running"
            self._save(proposal_id, execution)
            for host, plan in zip(execution["hosts"], plans):
                if cancel.is_set() or self.stopping.is_set():
                    execution["status"], execution["error_code"] = "interrupted", "interrupted"
                    break
                self._run_host(proposal_id, execution, host, plan, data, secrets, cancel)
                self._save(proposal_id, execution)
                if host["status"] != "succeeded":
                    execution["status"] = host["status"]
                    if host["error_code"] == "interrupted" and host["status"] != "unknown":
                        execution["status"] = "interrupted"
                    execution["error_code"] = host["error_code"]
                    break
            else:
                execution["status"] = "succeeded"
            self._skip_remaining(execution, execution["error_code"] or "not_executed")
            self._save(proposal_id, execution)
        except Exception as exc:
            self.persistence_failed.set()
            logger.error("AI operation %s persistence failed: %s", proposal_id, type(exc).__name__)
        finally:
            with self.guard:
                self.tasks.pop(proposal_id, None)
