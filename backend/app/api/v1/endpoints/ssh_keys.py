from datetime import timezone

from fastapi import APIRouter, HTTPException, Query, Request, Response
from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session

from ...dependencies import Database, commit
from ....core.ssh_keys import parse_private_key, validate_public_key
from ....models import Host, JumpHost, SSHKey
from ....repositories import assets as repository
from ....schemas.pagination import DEFAULT_PAGE_SIZE, PageNumber, PageResponse, PageSize
from ....schemas.ssh_keys import SSHKeyInput, SSHKeyReference, SSHKeyReferences, SSHKeyResponse, SSHKeySummary, SSHKeyUpdate

router = APIRouter(tags=["SSH 密钥管理"])
STALE_MESSAGE = "密钥已被修改，请重新打开编辑页面"


def find_key(session: Session, key_id: int) -> SSHKey:
    key = session.get(SSHKey, key_id)
    if key is None:
        raise HTTPException(404, "SSH 密钥不存在")
    return key


def key_summary(session: Session, key: SSHKey) -> SSHKeySummary:
    return SSHKeySummary(
        id=key.id, name=key.name, remark=key.remark, key_type=key.key_type,
        fingerprint=key.fingerprint, version=key.version,
        created_at=key.created_at.replace(tzinfo=timezone.utc), updated_at=key.updated_at.replace(tzinfo=timezone.utc),
        host_count=session.scalar(select(func.count()).select_from(Host).where(Host.ssh_key_id == key.id)),
        jump_host_count=session.scalar(select(func.count()).select_from(JumpHost).where(JumpHost.ssh_key_id == key.id)),
    )


def key_response(session: Session, key: SSHKey) -> SSHKeyResponse:
    return SSHKeyResponse(**key_summary(session, key).model_dump(), public_key=key.public_key)


@router.get("/ssh-keys", response_model=list[SSHKeyResponse] | PageResponse[SSHKeySummary])
def list_keys(session: Database, q: str = Query(default="", max_length=253),
              page: PageNumber = None,
               page_size: PageSize = DEFAULT_PAGE_SIZE) -> list[SSHKeyResponse] | PageResponse[SSHKeySummary]:
    result = repository.keys(session, q, page, page_size)
    if page is None:
        return [key_response(session, key) for key in result]
    items, total = result
    return PageResponse[SSHKeySummary](items=[key_summary(session, key) for key in items], total=total)


@router.get("/ssh-keys/{key_id}", response_model=SSHKeyResponse)
def get_key(key_id: int, session: Database) -> SSHKeyResponse:
    return key_response(session, find_key(session, key_id))


@router.get("/ssh-keys/{key_id}/references", response_model=SSHKeyReferences)
def get_references(key_id: int, session: Database) -> SSHKeyReferences:
    find_key(session, key_id)
    return SSHKeyReferences(
        hosts=[SSHKeyReference.model_validate(host) for host in session.scalars(select(Host).where(Host.ssh_key_id == key_id).order_by(Host.id))],
        jump_hosts=[SSHKeyReference.model_validate(host) for host in session.scalars(select(JumpHost).where(JumpHost.ssh_key_id == key_id).order_by(JumpHost.id))],
    )


@router.post("/ssh-keys", response_model=SSHKeyResponse, status_code=201)
def create_key(data: SSHKeyInput, request: Request, session: Database) -> SSHKeyResponse:
    raw, algorithm, fingerprint, public = parse_private_key(data.private_key.get_secret_value())
    public_key = validate_public_key(data.public_key, public)
    key = SSHKey(name=data.name, remark=data.remark, key_type=algorithm, fingerprint=fingerprint,
                 public_key=public_key, private_key_encrypted=request.app.state.cipher.encrypt(raw).decode())
    session.add(key)
    commit(session, STALE_MESSAGE)
    return key_response(session, key)


@router.put("/ssh-keys/{key_id}", response_model=SSHKeyResponse)
def update_key(key_id: int, data: SSHKeyUpdate, request: Request, session: Database) -> SSHKeyResponse:
    key = find_key(session, key_id)
    if key.version != data.version:
        raise HTTPException(409, STALE_MESSAGE)
    if "private_key" in data.model_fields_set:
        if data.private_key is None:
            raise HTTPException(422, "替换私钥时不能为空")
        if data.public_key is None:
            raise HTTPException(422, "替换私钥时须同时提供公钥")
        raw, algorithm, fingerprint, public = parse_private_key(data.private_key.get_secret_value())
        public_key = validate_public_key(data.public_key, public)
        key.private_key_encrypted = request.app.state.cipher.encrypt(raw).decode()
        key.key_type, key.fingerprint = algorithm, fingerprint
        key.public_key = public_key
    elif "public_key" in data.model_fields_set:
        if data.public_key is None:
            raise HTTPException(422, "上传公钥时不能为空")
        raw = request.app.state.cipher.decrypt(key.private_key_encrypted.encode())
        _, _, _, public = parse_private_key(raw.decode())
        key.public_key = validate_public_key(data.public_key, public)
    key.name, key.remark = data.name, data.remark
    connection_changed = "private_key" in data.model_fields_set
    jump_ids = select(JumpHost.id).where(JumpHost.ssh_key_id == key_id)
    affected = update(Host).where(or_(Host.ssh_key_id == key_id, Host.jump_host_id.in_(jump_ids)))
    if not connection_changed:
        affected = affected.where(Host.connection_status == "running")
    session.execute(affected.values(
        connection_status="untested" if connection_changed else "interrupted",
        updated_at=Host.updated_at).execution_options(synchronize_session=False))
    commit(session, STALE_MESSAGE)
    return key_response(session, key)


@router.delete("/ssh-keys/{key_id}", status_code=204)
def delete_key(key_id: int, session: Database) -> Response:
    key = find_key(session, key_id)
    for model in (Host, JumpHost):
        if session.scalar(select(model.id).where(model.ssh_key_id == key_id).limit(1)) is not None:
            raise HTTPException(409, "密钥仍被资产引用，请先解除关联")
    session.delete(key)
    commit(session, STALE_MESSAGE)
    return Response(status_code=204)
