from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..models import Host, HostGroup, JumpHost, SSHKey
from .pagination import fetch_rows


def hosts(session: Session, q: str, group_id: int | None, page: int | None,
          page_size: int) -> list[Host] | tuple[list[Host], int]:
    query = select(Host).order_by(Host.id.desc())
    if group_id is not None:
        query = query.where(Host.group_id == group_id)
    if q.strip():
        query = query.where(or_(Host.name.contains(q.strip(), autoescape=True),
                                Host.address.contains(q.strip(), autoescape=True)))
    return fetch_rows(session, query, page, page_size)


def groups(session: Session, page: int | None, page_size: int) -> list[HostGroup] | tuple[list[HostGroup], int]:
    return fetch_rows(session, select(HostGroup).order_by(HostGroup.id), page, page_size)


def jump_hosts(session: Session, q: str, page: int | None,
               page_size: int) -> list[JumpHost] | tuple[list[JumpHost], int]:
    query = select(JumpHost).order_by(JumpHost.id.desc())
    if q.strip():
        query = query.where(or_(JumpHost.name.contains(q.strip(), autoescape=True),
                                JumpHost.address.contains(q.strip(), autoescape=True)))
    return fetch_rows(session, query, page, page_size)


def keys(session: Session, q: str, page: int | None,
         page_size: int) -> list[SSHKey] | tuple[list[SSHKey], int]:
    query = select(SSHKey).order_by(SSHKey.id.desc())
    if q.strip():
        query = query.where(or_(SSHKey.name.contains(q.strip(), autoescape=True),
                                SSHKey.fingerprint.contains(q.strip(), autoescape=True)))
    return fetch_rows(session, query, page, page_size)
