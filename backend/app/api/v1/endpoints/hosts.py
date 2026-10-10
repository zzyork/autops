from fastapi import APIRouter, HTTPException, Query, Request, Response
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ...dependencies import Database, commit, find_group
from ....models import Host, JumpHost
from ....schemas.assets import HostInput, HostResponse, HostUpdate
from .credentials import apply_connection

router = APIRouter(tags=["资产管理"])


def find_host(session: Session, host_id: int) -> Host:
    host = session.get(Host, host_id)
    if host is None:
        raise HTTPException(404, "主机不存在")
    return host


@router.get("/hosts", response_model=list[HostResponse])
def list_hosts(session: Database, q: str = Query(default="", max_length=253), group_id: int | None = Query(default=None, gt=0)) -> list[Host]:
    statement = select(Host).order_by(Host.id.desc())
    if group_id is not None:
        statement = statement.where(Host.group_id == group_id)
    if q.strip():
        statement = statement.where(or_(Host.name.contains(q.strip(), autoescape=True), Host.address.contains(q.strip(), autoescape=True)))
    return list(session.scalars(statement))


@router.get("/hosts/{host_id}", response_model=HostResponse)
def get_host(host_id: int, session: Database) -> Host:
    return find_host(session, host_id)


def apply_host(data: HostInput, host: Host, request: Request, session: Session) -> None:
    find_group(session, data.group_id)
    if data.jump_host_id is not None and session.get(JumpHost, data.jump_host_id) is None:
        raise HTTPException(404, "跳板机不存在")
    apply_connection(data, host, request, "请填写 SSH 密码")


@router.post("/hosts", response_model=HostResponse, status_code=201)
def create_host(data: HostInput, request: Request, session: Database) -> Host:
    host = Host()
    apply_host(data, host, request, session)
    session.add(host)
    commit(session)
    return host


@router.put("/hosts/{host_id}", response_model=HostResponse)
def update_host(host_id: int, data: HostUpdate, request: Request, session: Database) -> Host:
    host = find_host(session, host_id)
    if host.version != data.version:
        raise HTTPException(409, "主机已被修改，请重新打开编辑页面")
    apply_host(data, host, request, session)
    commit(session)
    return host


@router.delete("/hosts/{host_id}", status_code=204)
def delete_host(host_id: int, session: Database) -> Response:
    session.delete(find_host(session, host_id))
    commit(session)
    return Response(status_code=204)
