from dataclasses import replace
from datetime import timedelta, timezone
from uuid import uuid4

from cryptography.fernet import Fernet
from fastapi import HTTPException
from sqlalchemy import delete, text, update
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from ..connection_models import IdentityChallengeRecord, KnownHostKey
from ..core.ssh import HostKeyRequired, SSHConnectionError, fingerprint, probe_host_key
from ..models import Host, utc_now
from ..repositories.ssh_connections import get_asset, get_trust
from ..schemas.ssh_identities import IdentityCheckInput, IdentityCheckResponse, IdentityChallenge
from .ssh_assets import resolve_plan

CHALLENGE_TTL = timedelta(minutes=10)
CHALLENGE_RETENTION = timedelta(days=1)


def _previous(known: KnownHostKey | None) -> dict | None:
    if known is None:
        return None
    return {"id": known.id, "version": known.version, "key_type": known.key_type,
            "public_key": known.public_key, "fingerprint": known.fingerprint}


def _probe(session: Session, cipher: Fernet, target_type: str, target_id: int):
    plan = resolve_plan(session, cipher, target_type, target_id, identity_probe=True)
    target = replace(plan.target, username="", password=None, private_key=None)
    proxy = plan.jump
    if proxy is not None and proxy.trusted_key is None:
        proxy = replace(proxy, username="", password=None, private_key=None)
    session.rollback()
    try:
        endpoint, key = probe_host_key(target, proxy)
    except HostKeyRequired as exc:
        endpoint, key = exc.endpoint, exc
        # The exception carries the exact wire key even when a trusted jump changed.
        public_key, key_type, key_fingerprint = exc.public_key, exc.key_type, exc.fingerprint
    else:
        public_key, key_type, key_fingerprint = key.get_base64(), key.get_name(), fingerprint(key.asbytes())
    return plan, endpoint, public_key, key_type, key_fingerprint


def _network_error(exc: SSHConnectionError) -> HTTPException:
    return HTTPException(504 if exc.code == "timeout" else 409 if exc.code == "authentication" else 502,
                         "服务器身份探测失败")


def check_identity(session: Session, cipher: Fernet, data: IdentityCheckInput) -> IdentityCheckResponse:
    asset = get_asset(session, data.target_type, data.target_id)
    if asset is None:
        raise HTTPException(404, "资产不存在")
    if data.version is not None and data.version != asset.version:
        raise HTTPException(409, "资产已变更，请刷新后重试")
    session.rollback()
    try:
        plan, endpoint, public_key, key_type, key_fingerprint = _probe(
            session, cipher, data.target_type, data.target_id)
    except SSHConnectionError as exc:
        raise _network_error(exc) from None
    if data.version is not None and data.version != plan.version:
        raise HTTPException(409, "资产已变更，请刷新后重试")
    # Network I/O is complete; serialize the snapshot and trust comparison with writes.
    session.execute(text("BEGIN IMMEDIATE"))
    current = resolve_plan(session, cipher, data.target_type, data.target_id, identity_probe=True)
    if current.snapshot != plan.snapshot or current.target != plan.target or current.jump != plan.jump:
        raise HTTPException(409, "资产或凭据已变更，请重新检查")
    known = get_trust(session, endpoint.target_type, endpoint.target_id, endpoint.address, endpoint.port)
    jump_known = (get_trust(session, "jump_host", current.jump.target_id, current.jump.address, current.jump.port)
                  if current.jump is not None else None)
    if known is not None and known.public_key == public_key and known.key_type == key_type:
        session.rollback()
        return IdentityCheckResponse(trusted=True, challenge=None)
    # 仅清理失效超过一天的握手挑战；持久信任和业务执行记录不受影响。
    session.execute(delete(IdentityChallengeRecord).where(
        IdentityChallengeRecord.expires_at < utc_now() - CHALLENGE_RETENTION))
    asset = get_asset(session, endpoint.target_type, endpoint.target_id)
    if asset is None:
        raise HTTPException(409, "资产已变更")
    record = IdentityChallengeRecord(
        id=str(uuid4()), target_type=endpoint.target_type, target_id=endpoint.target_id,
        target_name=asset.name or asset.address, address=endpoint.address, port=endpoint.port,
        key_type=key_type, public_key=public_key, fingerprint=key_fingerprint,
        previous_fingerprint=known.fingerprint if known else None, previous_state=_previous(known),
        jump_state=_previous(jump_known),
        requested_type=data.target_type, requested_id=data.target_id, snapshot=plan.snapshot,
        expires_at=utc_now() + CHALLENGE_TTL, consumed_at=None,
    )
    session.add(record)
    session.commit()
    return IdentityCheckResponse(trusted=False, challenge=IdentityChallenge.model_validate({
        column: getattr(record, column) for column in IdentityChallenge.model_fields
    }))


def trust_identity(session: Session, cipher: Fernet, challenge_id: str) -> None:
    record = session.get(IdentityChallengeRecord, challenge_id)
    if record is None:
        raise HTTPException(404, "身份挑战不存在")
    if record.consumed_at is not None or record.expires_at.replace(tzinfo=timezone.utc) <= utc_now():
        raise HTTPException(409, "身份挑战已失效，请重新检查")
    try:
        plan, endpoint, public_key, key_type, _ = _probe(session, cipher, record.requested_type, record.requested_id)
    except SSHConnectionError as exc:
        raise _network_error(exc) from None
    if (plan.snapshot != record.snapshot or (endpoint.target_type, endpoint.target_id, endpoint.address, endpoint.port,
            key_type, public_key) != (record.target_type, record.target_id, record.address, record.port,
                                     record.key_type, record.public_key)):
        raise HTTPException(409, "身份或资产已变更，请重新检查")
    try:
        session.execute(text("BEGIN IMMEDIATE"))
        record = session.get(IdentityChallengeRecord, challenge_id, populate_existing=True)
        if record is None or record.consumed_at is not None or record.expires_at.replace(tzinfo=timezone.utc) <= utc_now():
            raise HTTPException(409, "身份挑战已失效，请重新检查")
        current = resolve_plan(session, cipher, record.requested_type, record.requested_id, identity_probe=True)
        if current.snapshot != record.snapshot or current.target != plan.target or current.jump != plan.jump:
            raise HTTPException(409, "资产或凭据已变更，请重新检查")
        known = get_trust(session, record.target_type, record.target_id, record.address, record.port)
        jump_known = (get_trust(session, "jump_host", current.jump.target_id, current.jump.address, current.jump.port)
                      if current.jump is not None else None)
        if _previous(known) != record.previous_state or _previous(jump_known) != record.jump_state:
            raise HTTPException(409, "服务器信任已变更，请重新检查")
        if known is None:
            known = KnownHostKey(target_type=record.target_type, target_id=record.target_id,
                                 host_id=record.target_id if record.target_type == "host" else None,
                                 jump_host_id=record.target_id if record.target_type == "jump_host" else None,
                                 address=record.address, port=record.port)
            session.add(known)
        known.key_type = record.key_type
        known.public_key = record.public_key
        known.fingerprint = record.fingerprint
        record.consumed_at = utc_now()
        if record.target_type == "host":
            session.execute(update(Host).where(Host.id == record.target_id).values(
                connection_status="untested", updated_at=Host.updated_at).execution_options(synchronize_session=False))
        else:
            session.execute(update(Host).where(Host.jump_host_id == record.target_id).values(
                connection_status="untested", updated_at=Host.updated_at).execution_options(synchronize_session=False))
        session.commit()
    except (IntegrityError, StaleDataError, OperationalError):
        session.rollback()
        raise HTTPException(409, "服务器信任已变更，请重新检查") from None
