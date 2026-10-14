import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4

import httpx
from cryptography.fernet import Fernet
from fastapi import HTTPException
from sqlalchemy.orm import Session, sessionmaker

from ..repositories import inspection_analysis as repository, inspections
from ..schemas.inspection_analysis import AnalysisProgress, AnalysisResponse
from .ai_provider import ProviderError
from .inspection_analysis_engine import ModelSnapshot, analyze
from .inspection_analysis_input import build_input
from .ai_feature_models import feature_connection

logger = logging.getLogger(__name__)
MAX_ANALYSIS_WORKERS = 2
MAX_PENDING_ANALYSES = 8


class InspectionAnalysisManager:
    def __init__(self, sessions: sessionmaker[Session], cipher: Fernet, data_dir: Path):
        self.sessions, self.cipher = sessions, cipher
        self.data_dir = data_dir
        self.guard = threading.Lock()
        self.stopping = threading.Event()
        self.persistence_failed = threading.Event()
        self.pending = 0
        self.cancellations: dict[str, threading.Event] = {}
        self.progress: dict[str, tuple[str, AnalysisProgress]] = {}
        self.client = httpx.Client(timeout=httpx.Timeout(20, connect=5), follow_redirects=False,
                                   limits=httpx.Limits(max_connections=MAX_ANALYSIS_WORKERS), trust_env=False)
        with sessions() as session:
            repository.interrupt_unfinished(session)
        self.executor = ThreadPoolExecutor(max_workers=MAX_ANALYSIS_WORKERS, thread_name_prefix="ai-report")

    def ensure_available(self) -> None:
        if self.persistence_failed.is_set():
            raise HTTPException(503, "AI汇报持久化不可用")

    def read(self, session: Session, task_id: str) -> AnalysisResponse:
        self.ensure_available()
        task = inspections.get_task(session, task_id)
        if task is None:
            raise HTTPException(404, "巡检任务不存在")
        row = repository.read(session, task_id)
        connection = feature_connection(session, self.data_dir, "inspection_report")
        ready = connection is not None and connection.chat_status == "passed"
        with self.guard:
            can_generate = (ready and task.status not in inspections.ACTIVE and not self.stopping.is_set()
                            and self.pending < MAX_PENDING_ANALYSES and (row is None or row.status not in repository.ACTIVE))
            current = self.progress.get(task_id)
            progress = (current[1] if row is not None and row.status == "running"
                        and current is not None and current[0] == row.generation_id else None)
        if row is None:
            return AnalysisResponse(task_id=task_id, status="not_generated", can_generate=can_generate)
        return AnalysisResponse(task_id=task_id, status=row.status, model_name=row.model_name,
                                model_version=row.model_version, started_at=row.started_at,
                                finished_at=row.finished_at, error_code=row.error_code,
                                report=row.report, can_generate=can_generate, progress=progress)

    def automatic(self, task_id: str) -> None:
        try:
            self.start(task_id, automatic=True)
        except HTTPException as exc:
            # 自动提交的业务拒绝已有明确状态或任务已删除，不影响巡检状态。
            logger.info("Inspection AI report %s not submitted: HTTP %s", task_id, exc.status_code)
        except Exception as exc:
            self.persistence_failed.set()
            logger.error("Inspection AI report %s submission failed: %s", task_id, type(exc).__name__)

    def start(self, task_id: str, automatic: bool = False) -> None:
        try:
            self._start(task_id, automatic)
        except HTTPException:
            raise
        except Exception as exc:
            self.persistence_failed.set()
            logger.error("Inspection AI report %s claim failed: %s", task_id, type(exc).__name__)
            raise HTTPException(503, "AI汇报持久化不可用") from None

    def _start(self, task_id: str, automatic: bool) -> None:
        self.ensure_available()
        generation_id = str(uuid4())
        with self.guard:
            if self.stopping.is_set():
                raise HTTPException(503, "AI汇报服务已停止")
            with self.sessions() as session:
                # 在同一写事务内验证模型资格与认领，已接受批次随后固定使用此快照。
                repository.begin_claim(session)
                connection = feature_connection(session, self.data_dir, "inspection_report")
                snapshot = ModelSnapshot(connection.protocol, connection.base_url, connection.model,
                                         connection.api_key_encrypted, f"{connection.name} / {connection.model}",
                                         connection.config_version) if connection is not None and connection.chat_status == "passed" else None
                status = "queued" if snapshot is not None else "unavailable"
                full = self.pending >= MAX_PENDING_ANALYSES
                if full and snapshot is not None:
                    status = "failed"
                result = repository.claim(session, task_id, generation_id,
                                          snapshot.name if snapshot else None,
                                          snapshot.version if snapshot else None, status, automatic, transaction_started=True)
                if result == "missing":
                    raise HTTPException(404, "巡检任务不存在")
                if result == "active":
                    raise HTTPException(409, "巡检尚未结束")
                if result == "duplicate":
                    if automatic:
                        return
                    raise HTTPException(409, "AI汇报正在生成")
                if snapshot is None:
                    if automatic:
                        return
                    raise HTTPException(409, "巡检 AI 汇报模型未配置或未通过对话测试")
                if full:
                    row = repository.read(session, task_id)
                    row.error_code = "queue_full"
                    session.commit()
                    raise HTTPException(503, "AI汇报队列已满")
                self.pending += 1
                cancel = threading.Event()
                self.cancellations[task_id] = cancel
                try:
                    self.executor.submit(self._run, task_id, generation_id, snapshot, cancel)
                except Exception:
                    self.pending -= 1
                    self.cancellations.pop(task_id, None)
                    repository.finish(session, task_id, generation_id, "failed", "dispatch_failed")
                    raise HTTPException(503, "AI汇报队列不可用") from None

    def _run(self, task_id: str, generation_id: str, snapshot: ModelSnapshot, cancel: threading.Event) -> None:
        started = time.monotonic()

        def update_progress(value: AnalysisProgress) -> None:
            with self.guard:
                if self.cancellations.get(task_id) is cancel:
                    self.progress[task_id] = (generation_id, value)
            logger.info("Inspection AI report %s generation %s progress: %s, batches %s/%s, elapsed %.1fs",
                        task_id, generation_id, value.current_step, value.completed_batches,
                        value.total_batches, time.monotonic() - started)

        try:
            with self.sessions() as session:
                if not repository.running(session, task_id, generation_id):
                    return
                task = inspections.get_task(session, task_id)
                if task is None:
                    return
                data = build_input(task)
            key = self.cipher.decrypt(snapshot.encrypted_key.encode()).decode() if snapshot.encrypted_key else None
            report = analyze(self.client, snapshot, key, data, cancel, on_progress=update_progress)
            with self.sessions() as session:
                if cancel.is_set():
                    repository.finish(session, task_id, generation_id, "interrupted", "interrupted")
                else:
                    repository.finish(session, task_id, generation_id, "completed", report=report.model_dump(mode="json"))
            logger.info("Inspection AI report %s generation %s finished in %.1fs",
                        task_id, generation_id, time.monotonic() - started)
        except Exception as exc:
            # ProviderError 的原因由适配器和分析校验生成；其他异常不输出可能含凭据的原文。
            reason = str(exc) if isinstance(exc, ProviderError) else type(exc).__name__
            logger.warning("Inspection AI report %s generation %s failed: %s: %s",
                           task_id, generation_id, type(exc).__name__, reason)
            try:
                with self.sessions() as session:
                    interrupted = cancel.is_set()
                    repository.finish(session, task_id, generation_id, "interrupted" if interrupted else "failed",
                                      "interrupted" if interrupted else "analysis_failed")
            except Exception as persistence_error:
                self.persistence_failed.set()
                logger.error("Inspection AI report %s persistence failed: %s", task_id, type(persistence_error).__name__)
        finally:
            with self.guard:
                self.pending -= 1
                if self.cancellations.get(task_id) is cancel:
                    self.cancellations.pop(task_id, None)
                current = self.progress.get(task_id)
                if current is not None and current[0] == generation_id:
                    self.progress.pop(task_id, None)

    def cancel(self, task_id: str) -> None:
        with self.guard:
            event = self.cancellations.get(task_id)
            if event is not None:
                event.set()

    def stop_accepting(self) -> None:
        with self.guard:
            self.stopping.set()
            for event in self.cancellations.values():
                event.set()

    def close(self) -> None:
        self.stop_accepting()
        try:
            self.executor.shutdown(wait=True, cancel_futures=True)
            with self.sessions() as session:
                repository.interrupt_unfinished(session)
        finally:
            self.client.close()
