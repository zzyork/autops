import base64
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta, timezone
from uuid import uuid4

from cryptography.fernet import Fernet
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from ..api.dependencies import commit
from ..connection_models import ConnectionTest, KnownHostKey
from ..core.ssh import HostKeyRequired, SSHConnectionError, failure_message, fingerprint, open_ssh_connection
from ..models import utc_now
from ..repositories.ssh_connections import get_trust, interrupt_tests
from ..schemas.ssh_connections import ConnectionTestInput
from .ssh_assets import resolve_plan

logger = logging.getLogger(__name__)
MAX_CONNECTION_WORKERS = 4
MAX_PENDING_TESTS = 16
TRUST_CONFIRMATION_TTL = timedelta(minutes=10)


class ConnectionTestManager:
    """单实例执行器；工作线程独立创建数据库会话，不跨线程传递凭据。"""
    def __init__(self, sessions: sessionmaker[Session], cipher: Fernet):
        self.sessions = sessions
        self.cipher = cipher
        self.executor = ThreadPoolExecutor(max_workers=MAX_CONNECTION_WORKERS, thread_name_prefix="ssh-test")
        self.lock = threading.Lock()
        self.active: set[tuple[str, int]] = set()
        self.closed = False
        with sessions() as session:
            interrupt_tests(session)

    def close(self) -> None:
        with self.lock:
            self.closed = True
        self.executor.shutdown(wait=True)

    def start(self, session: Session, data: ConnectionTestInput) -> ConnectionTest:
        plan = resolve_plan(session, self.cipher, data.target_type, data.target_id)
        if plan.version != data.version:
            raise HTTPException(409, "资产已变更，请刷新后重试")
        identity = (data.target_type, data.target_id)
        with self.lock:
            if self.closed or len(self.active) >= MAX_PENDING_TESTS:
                raise HTTPException(503, "连接测试队列不可用")
            if identity in self.active:
                raise HTTPException(409, "该资产已有连接测试正在执行")
            self.active.add(identity)
        record = ConnectionTest(
            id=str(uuid4()), target_type=data.target_type, target_id=data.target_id,
            target_name=plan.name, address=plan.target.address, port=plan.target.port,
            username=plan.target.username, via_jump_host=plan.jump_name, snapshot=plan.snapshot,
            status="queued", stage=None, failure_code=None, failure_message=None, challenge=None, candidate_key=None,
            started_at=None, finished_at=None, duration_ms=None,
        )
        try:
            session.add(record)
            commit(session)
            session.refresh(record)
            with self.lock:
                if self.closed:
                    record.status = "interrupted"
                    record.finished_at = utc_now()
                    commit(session)
                    raise HTTPException(503, "连接测试队列不可用")
                self.executor.submit(self._run, record.id, identity)
        except Exception:
            with self.lock:
                self.active.discard(identity)
            raise
        return record

    def _run(self, test_id: str, identity: tuple[str, int]) -> None:
        started = time.monotonic()
        try:
            with self.sessions() as session:
                record = session.get(ConnectionTest, test_id)
                if record is None:
                    return
                record.status = "running"
                record.started_at = utc_now()
                session.commit()
                plan = None
                try:
                    plan = resolve_plan(session, self.cipher, *identity)
                    if plan.snapshot != record.snapshot:
                        raise HTTPException(409, "资产已变更")
                    # 释放 SQLite 读事务后进行网络 I/O。
                    session.rollback()
                    with open_ssh_connection(plan.target, plan.jump):
                        pass
                    record.status = "succeeded"
                    record.stage = "target"
                except HostKeyRequired as exc:
                    endpoint = exc.endpoint
                    record.status = "awaiting_trust"
                    record.stage = "jump_host" if plan.jump is not None and endpoint == plan.jump else "target"
                    record.candidate_key = exc.public_key
                    record.challenge = {
                        "target_type": endpoint.target_type, "target_id": endpoint.target_id,
                        "address": endpoint.address, "port": endpoint.port,
                        "key_type": exc.key_type, "fingerprint": exc.fingerprint,
                        "previous_fingerprint": fingerprint(base64.b64decode(endpoint.trusted_key)) if endpoint.trusted_key else None,
                    }
                except SSHConnectionError as exc:
                    record.status = "failed"
                    record.failure_code = exc.code
                    endpoints = (plan.target,) + ((plan.jump,) if plan.jump is not None else ())
                    record.failure_message = failure_message(exc, *endpoints)
                    record.stage = exc.stage
                except HTTPException as exc:
                    record.status = "failed"
                    record.failure_code = "configuration"
                    endpoints = (plan.target,) + ((plan.jump,) if plan.jump is not None else ()) if plan is not None else ()
                    record.failure_message = failure_message(Exception(str(exc.detail)), *endpoints)
                except Exception as exc:
                    record.status = "failed"
                    record.failure_code = "internal"
                    endpoints = (plan.target,) + ((plan.jump,) if plan.jump is not None else ()) if plan is not None else ()
                    record.failure_message = failure_message(exc, *endpoints)
                    logger.error("SSH test %s failed: %s", test_id, type(exc).__name__)
                record.finished_at = utc_now()
                record.duration_ms = round((time.monotonic() - started) * 1000)
                session.commit()
        except Exception as exc:
            logger.error("SSH test %s persistence failed: %s", test_id, type(exc).__name__)
        finally:
            with self.lock:
                self.active.discard(identity)


def trust_test_key(session: Session, cipher: Fernet, test_id: str) -> None:
    # 将资产版本检查、当前信任比较和写入串行化，防止确认覆盖并发更新。
    session.execute(text("BEGIN IMMEDIATE"))
    record = session.get(ConnectionTest, test_id)
    if record is None:
        raise HTTPException(404, "连接测试不存在")
    if record.status != "awaiting_trust" or record.challenge is None or record.candidate_key is None:
        raise HTTPException(409, "该测试没有待确认的服务器身份")
    finished = record.finished_at
    if finished is None or utc_now() - finished.replace(tzinfo=timezone.utc) > TRUST_CONFIRMATION_TTL:
        raise HTTPException(409, "身份确认已过期，请重新测试")
    plan = resolve_plan(session, cipher, record.target_type, record.target_id)
    if plan.snapshot != record.snapshot:
        raise HTTPException(409, "资产或凭据已变更，请重新测试")
    challenge = record.challenge
    known = get_trust(session, challenge["target_type"], challenge["target_id"], challenge["address"], challenge["port"])
    if (known.fingerprint if known else None) != challenge["previous_fingerprint"]:
        raise HTTPException(409, "服务器身份信任已变更，请重新测试")
    if known is None:
        known = KnownHostKey(
            target_type=challenge["target_type"], target_id=challenge["target_id"],
            host_id=challenge["target_id"] if challenge["target_type"] == "host" else None,
            jump_host_id=challenge["target_id"] if challenge["target_type"] == "jump_host" else None,
            address=challenge["address"], port=challenge["port"],
        )
        session.add(known)
    known.key_type = challenge["key_type"]
    known.public_key = record.candidate_key
    known.fingerprint = challenge["fingerprint"]
    record.status = "trusted"
    commit(session, "服务器身份信任已变更，请重新测试")
