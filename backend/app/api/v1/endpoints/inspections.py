from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request

from ...dependencies import Database
from ....repositories import inspections as repository
from ....schemas.inspections import InspectionCatalog, InspectionConfig, InspectionInput, ReportResponse, TaskDetail, TaskPage, TaskSummary
from ....services.inspection_checks import CHECK_DEFINITIONS
from ....services.inspection_reports import render_report

router = APIRouter(prefix="/inspections", tags=["巡检"])


@router.get("/catalog", response_model=InspectionCatalog)
def catalog() -> InspectionCatalog:
    return InspectionCatalog(checks=CHECK_DEFINITIONS, defaults=InspectionConfig())


@router.post("/tasks", response_model=TaskDetail, status_code=202)
def start_task(data: InspectionInput, request: Request, session: Database) -> TaskDetail:
    task = request.app.state.inspections.start(session, data)
    return TaskDetail.model_validate(task)


@router.get("/tasks", response_model=TaskPage)
def list_tasks(request: Request, session: Database, limit: Annotated[int, Query(ge=1, le=50)] = 20,
               offset: Annotated[int, Query(ge=0)] = 0) -> TaskPage:
    request.app.state.inspections.ensure_available()
    items, total = repository.page_tasks(session, limit, offset)
    return TaskPage(items=[TaskSummary.model_validate(item) for item in items], total=total)


@router.get("/tasks/{task_id}", response_model=TaskDetail)
def read_task(task_id: UUID, request: Request, session: Database) -> TaskDetail:
    request.app.state.inspections.ensure_available()
    task = repository.get_task(session, str(task_id))
    if task is None:
        raise HTTPException(404, "巡检任务不存在")
    return TaskDetail.model_validate(task)


@router.get("/tasks/{task_id}/report", response_model=ReportResponse)
def report(task_id: UUID, request: Request, session: Database) -> ReportResponse:
    detail = read_task(task_id, request, session)
    if detail.status in ("queued", "running"):
        raise HTTPException(409, "巡检尚未结束")
    return ReportResponse(filename=f"inspection-{detail.id}.md", content=render_report(detail))
