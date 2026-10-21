import ipaddress
import logging
import threading
import time

from cryptography.fernet import Fernet
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy.orm import Session, sessionmaker

from ..core.ssh import HostKeyRequired, SSHConnectionError, open_ssh_connection
from ..core.ssh_commands import CommandExecutionError, CommandResult, run_command
from ..schemas.host_basic_info import (
    MAX_BASIC_INFO_ADDRESSES, HostBasicInfoAddress, HostBasicInfoResponse,
)
from .inspection_checks import InspectionCheckError
from .inspection_checks.basic import collect_identity
from .ssh_assets import resolve_plan

logger = logging.getLogger(__name__)
MAX_BASIC_INFO_WORKERS = 4
BASIC_INFO_TIMEOUT_SECONDS = 60
BASIC_INFO_COMMAND_TIMEOUT_SECONDS = 10


class HostBasicInfoManager:
    def __init__(self, sessions: sessionmaker[Session], cipher: Fernet):
        self.sessions = sessions
        self.cipher = cipher
        self.condition = threading.Condition()
        self.active: dict[int, threading.Event] = {}
        self.closed = False

    def close(self) -> None:
        with self.condition:
            self.closed = True
            for cancel in self.active.values():
                cancel.set()
            self.condition.wait_for(lambda: not self.active)

    def collect(self, host_id: int, version: int) -> HostBasicInfoResponse:
        cancel = threading.Event()
        with self.condition:
            if self.closed:
                raise HTTPException(503, "基础信息采集暂不可用")
            if host_id in self.active:
                raise HTTPException(409, "该主机正在采集基础信息")
            if len(self.active) >= MAX_BASIC_INFO_WORKERS:
                raise HTTPException(503, "基础信息采集暂不可用")
            self.active[host_id] = cancel
        try:
            return self._collect(host_id, version, cancel)
        except HostKeyRequired as exc:
            raise HTTPException(409, {
                "code": "ssh_identity_required",
                "target": {"target_type": exc.endpoint.target_type, "target_id": exc.endpoint.target_id},
            }) from None
        except SSHConnectionError as exc:
            raise HTTPException(504 if exc.code == "timeout" else 502, "基础信息采集连接失败") from None
        except CommandExecutionError as exc:
            status = 502
            if exc.code == "timeout":
                status = 504
            elif exc.code == "interrupted":
                status = 503
            raise HTTPException(status, "基础信息采集未完成") from None
        except (InspectionCheckError, ValidationError, ValueError):
            raise HTTPException(502, "服务器基础信息无效或不完整") from None
        except HTTPException:
            raise
        except Exception as exc:
            logger.error("Host basic info collection failed for %s: %s", host_id, type(exc).__name__)
            raise HTTPException(500, "基础信息采集失败") from None
        finally:
            with self.condition:
                self.active.pop(host_id, None)
                self.condition.notify_all()

    def _collect(self, host_id: int, version: int, cancel: threading.Event) -> HostBasicInfoResponse:
        deadline = time.monotonic() + BASIC_INFO_TIMEOUT_SECONDS
        with self.sessions() as session:
            plan = resolve_plan(session, self.cipher, "host", host_id)
            if plan.version != version:
                raise HTTPException(409, "主机已变更，请刷新后重新获取")
        if cancel.is_set():
            raise HTTPException(503, "基础信息采集已中断")

        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise HTTPException(504, "基础信息采集超时")
        with open_ssh_connection(plan.target, plan.jump, timeout_seconds=remaining) as client:
            def runner(command: str) -> CommandResult:
                return run_command(client, command, BASIC_INFO_COMMAND_TIMEOUT_SECONDS, deadline, cancel=cancel)

            name, ipv4, ipv6 = collect_identity(runner)

        candidates: list[HostBasicInfoAddress] = []
        seen: set[tuple[str, str]] = set()
        for interface, network in [*ipv4, *ipv6]:
            address = ipaddress.ip_interface(network).ip
            if address.is_loopback or address.is_link_local or address.is_unspecified or address.is_multicast:
                continue
            identity = (interface, str(address))
            if identity in seen:
                continue
            seen.add(identity)
            if len(candidates) >= MAX_BASIC_INFO_ADDRESSES:
                raise InspectionCheckError("output_limit")
            candidates.append(HostBasicInfoAddress(interface=interface, address=str(address)))

        if cancel.is_set():
            raise HTTPException(503, "基础信息采集已中断")
        if time.monotonic() >= deadline:
            raise HTTPException(504, "基础信息采集超时")
        with self.sessions() as session:
            current = resolve_plan(session, self.cipher, "host", host_id)
            if current.snapshot != plan.snapshot or current.target != plan.target or current.jump != plan.jump:
                raise HTTPException(409, "主机、凭据或服务器信任已变更，请重新获取")
        return HostBasicInfoResponse(host_id=host_id, version=version, name=name, addresses=candidates)
