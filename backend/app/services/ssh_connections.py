import logging
import threading

from cryptography.fernet import Fernet
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from ..core.ssh import HostKeyRequired, SSHConnectionError, open_ssh_connection
from ..models import Host, JumpHost
from ..repositories.ssh_connections import set_host_status
from ..schemas.ssh_connections import ConnectionTestInput, ConnectionTestResponse, TestStatus
from .ssh_assets import ConnectionPlan, resolve_plan

logger = logging.getLogger(__name__)
MAX_CONNECTION_WORKERS = 4


class ConnectionTestManager:
    def __init__(self, sessions: sessionmaker[Session], cipher: Fernet):
        self.sessions = sessions
        self.cipher = cipher
        self.condition = threading.Condition()
        self.active: set[tuple[str, int]] = set()
        self.closed = False

    def close(self) -> None:
        with self.condition:
            self.closed = True
            self.condition.wait_for(lambda: not self.active)

    def start(self, data: ConnectionTestInput) -> ConnectionTestResponse:
        identity = (data.target_type, data.target_id)
        with self.condition:
            if self.closed:
                raise HTTPException(503, "连接测试暂不可用")
            if identity in self.active:
                raise HTTPException(409, "该资产已有连接测试正在执行")
            if len(self.active) >= MAX_CONNECTION_WORKERS:
                raise HTTPException(503, "连接测试暂不可用")
            self.active.add(identity)
        try:
            with self.sessions() as db:
                db.execute(text("BEGIN IMMEDIATE"))
                plan = resolve_plan(db, self.cipher, *identity)
                if plan.version != data.version:
                    raise HTTPException(409, "资产已变更，请刷新后重试")
                asset = db.get(Host if data.target_type == "host" else JumpHost, data.target_id)
                created_at = asset.created_at
                host = asset if isinstance(asset, Host) else None
                if host is not None:
                    if not set_host_status(db, host.id, created_at, plan.version, "running"):
                        raise HTTPException(409, "资产已变更，请刷新后重试")
                db.commit()

            try:
                with open_ssh_connection(plan.target, plan.jump):
                    pass
                status: TestStatus = "succeeded"
            except HostKeyRequired:
                status = "awaiting_trust"
            except SSHConnectionError:
                status = "failed"
            except Exception as exc:
                logger.error("SSH connection test failed for %s %s: %s", *identity, type(exc).__name__)
                status = "failed"

            if data.target_type == "host":
                status = self._finish_host(data, plan, created_at, status)
            else:
                status = self._finish_jump(data, plan, created_at, status)
            return ConnectionTestResponse(target_type=data.target_type, target_id=data.target_id, status=status)
        finally:
            with self.condition:
                self.active.discard(identity)
                self.condition.notify_all()

    def _finish_host(self, data: ConnectionTestInput, plan: ConnectionPlan, created_at,
                     status: TestStatus) -> TestStatus:
        with self.sessions() as db:
            db.execute(text("BEGIN IMMEDIATE"))
            host = db.get(Host, data.target_id)
            if host is None or host.created_at != created_at or host.connection_status != "running":
                return "interrupted"
            current = None
            if host.version == plan.version:
                try:
                    current = resolve_plan(db, self.cipher, "host", data.target_id)
                except HTTPException:
                    pass
            if (current is None or current.snapshot != plan.snapshot or current.target != plan.target or
                    current.jump != plan.jump):
                # Only this in-process test can still own 'running'; do not touch a reset or reused host.
                if set_host_status(db, host.id, created_at, host.version, "interrupted", expected_status="running"):
                    db.commit()
                return "interrupted"
            if not set_host_status(db, host.id, created_at, plan.version, status, expected_status="running"):
                return "interrupted"
            db.commit()
        return status

    def _finish_jump(self, data: ConnectionTestInput, plan: ConnectionPlan, created_at,
                     status: TestStatus) -> TestStatus:
        with self.sessions() as db:
            db.execute(text("BEGIN IMMEDIATE"))
            asset = db.get(JumpHost, data.target_id)
            if asset is None or asset.created_at != created_at or asset.version != plan.version:
                return "interrupted"
            try:
                current = resolve_plan(db, self.cipher, "jump_host", data.target_id)
            except HTTPException:
                return "interrupted"
            if current.snapshot != plan.snapshot or current.target != plan.target:
                return "interrupted"
        return status
