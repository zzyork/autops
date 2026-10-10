from fastapi import APIRouter, HTTPException, Query, Request, Response
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ...dependencies import Database, commit
from ....models import Host, JumpHost
from ....schemas.jump_hosts import JumpHostInput, JumpHostResponse, JumpHostUpdate
from .credentials import apply_connection

router = APIRouter(tags=["资产管理"])
STALE_MESSAGE = "跳板机已被修改，请重新打开编辑页面"


def find_jump_host(session: Session, jump_host_id: int) -> JumpHost:
    jump_host = session.get(JumpHost, jump_host_id)
    if jump_host is None:
        raise HTTPException(404, "跳板机不存在")
    return jump_host


def jump_host_response(session: Session, jump_host: JumpHost) -> JumpHostResponse:
    count = session.scalar(select(func.count()).select_from(Host).where(Host.jump_host_id == jump_host.id))
    return JumpHostResponse.model_validate({
        **{field: getattr(jump_host, field) for field in JumpHostResponse.model_fields if field != "host_count"},
        "host_count": count,
    })


@router.get("/jump-hosts", response_model=list[JumpHostResponse])
def list_jump_hosts(session: Database, q: str = Query(default="", max_length=253)) -> list[JumpHostResponse]:
    statement = select(JumpHost).order_by(JumpHost.id.desc())
    if q.strip():
        statement = statement.where(or_(JumpHost.name.contains(q.strip(), autoescape=True), JumpHost.address.contains(q.strip(), autoescape=True)))
    return [jump_host_response(session, jump_host) for jump_host in session.scalars(statement)]


@router.get("/jump-hosts/{jump_host_id}", response_model=JumpHostResponse)
def get_jump_host(jump_host_id: int, session: Database) -> JumpHostResponse:
    return jump_host_response(session, find_jump_host(session, jump_host_id))


@router.post("/jump-hosts", response_model=JumpHostResponse, status_code=201)
def create_jump_host(data: JumpHostInput, request: Request, session: Database) -> JumpHostResponse:
    jump_host = JumpHost()
    apply_connection(data, jump_host, request, "请填写跳板机密码")
    session.add(jump_host)
    commit(session, STALE_MESSAGE)
    return jump_host_response(session, jump_host)


@router.put("/jump-hosts/{jump_host_id}", response_model=JumpHostResponse)
def update_jump_host(jump_host_id: int, data: JumpHostUpdate, request: Request, session: Database) -> JumpHostResponse:
    jump_host = find_jump_host(session, jump_host_id)
    if jump_host.version != data.version:
        raise HTTPException(409, STALE_MESSAGE)
    apply_connection(data, jump_host, request, "请填写跳板机密码")
    commit(session, STALE_MESSAGE)
    return jump_host_response(session, jump_host)


@router.delete("/jump-hosts/{jump_host_id}", status_code=204)
def delete_jump_host(jump_host_id: int, session: Database) -> Response:
    jump_host = find_jump_host(session, jump_host_id)
    if session.scalar(select(Host.id).where(Host.jump_host_id == jump_host_id).limit(1)) is not None:
        raise HTTPException(409, "跳板机仍被主机引用，请先解除关联")
    session.delete(jump_host)
    commit(session, STALE_MESSAGE)
    return Response(status_code=204)
