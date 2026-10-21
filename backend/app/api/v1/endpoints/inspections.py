from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request, Response

from ...dependencies import Database
from ....repositories import inspections as repository
from ....schemas.inspections import InspectionCatalog, InspectionConfig, InspectionConfigSave, InspectionInput, ReportResponse, TaskDetail, TaskPage, TaskSummary
from ....schemas.inspection_analysis import AnalysisResponse
from ....schemas.pagination import DEFAULT_PAGE_SIZE
from ....services.inspection_checks import CHECK_DEFINITIONS
from ....services.inspection_log_display import display_task_logs
from ....services.inspection_reports import render_report, render_report_archive
from ....services.inspection_rules import load_rules, save_rules

router = APIRouter(prefix="/inspections", tags=["巡检"])


@router.get("/catalog", response_model=InspectionCatalog)
def catalog(request: Request) -> InspectionCatalog:
    return InspectionCatalog(checks=CHECK_DEFINITIONS, defaults=load_rules(request.app.state.data_dir))


@router.put("/catalog", response_model=InspectionCatalog)
def update_catalog(data: InspectionConfigSave, request: Request) -> InspectionCatalog:
    config = InspectionConfig.model_validate(data.model_dump())
    return InspectionCatalog(checks=CHECK_DEFINITIONS, defaults=save_rules(request.app.state.data_dir, config))


@router.post("/tasks", response_model=TaskDetail, status_code=202)
def start_task(data: InspectionInput, request: Request, session: Database) -> TaskDetail:
    task = request.app.state.inspections.start(session, data, load_rules(request.app.state.data_dir))
    return TaskDetail.model_validate(task)


@router.get("/tasks", response_model=TaskPage)
def list_tasks(request: Request, session: Database, limit: Annotated[int, Query(ge=1, le=100)] = DEFAULT_PAGE_SIZE,
               offset: Annotated[int, Query(ge=0)] = 0, records_only: bool = False) -> TaskPage:
    request.app.state.inspections.ensure_available()
    items, total = repository.page_tasks(session, limit, offset, records_only)
    return TaskPage(items=[TaskSummary.model_validate(item) for item in items], total=total)


def _read_task_detail(task_id: UUID, request: Request, session: Database) -> TaskDetail:
    request.app.state.inspections.ensure_available()
    task = repository.get_task(session, str(task_id))
    if task is None:
        raise HTTPException(404, "巡检任务不存在")
    return TaskDetail.model_validate(task)


@router.get("/tasks/{task_id}", response_model=TaskDetail)
def read_task(task_id: UUID, request: Request, session: Database) -> TaskDetail:
    return display_task_logs(_read_task_detail(task_id, request, session))


@router.delete("/tasks/{task_id}", status_code=204)
def delete_task(task_id: UUID, request: Request, session: Database) -> Response:
    request.app.state.inspections.ensure_available()
    result = repository.delete_task(session, str(task_id))
    if result == "missing":
        raise HTTPException(404, "巡检任务不存在")
    if result == "active":
        raise HTTPException(409, "巡检尚未结束")
    request.app.state.inspection_analysis.cancel(str(task_id))
    return Response(status_code=204)


@router.get("/tasks/{task_id}/report", response_model=ReportResponse)
def report(task_id: UUID, request: Request, session: Database) -> ReportResponse:
    detail = _read_task_detail(task_id, request, session)
    if detail.status in ("queued", "running"):
        raise HTTPException(409, "巡检尚未结束")
    return ReportResponse(filename=f"inspection-{detail.id}.md", content=render_report(detail))


@router.get("/tasks/{task_id}/reports/archive", response_class=Response,
            responses={200: {"content": {"application/zip": {}}}})
def report_archive(task_id: UUID, request: Request, session: Database) -> Response:
    detail = _read_task_detail(task_id, request, session)
    if detail.status in ("queued", "running"):
        raise HTTPException(409, "巡检尚未结束")
    try:
        content = render_report_archive(detail)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from None
    return Response(content=content, media_type="application/zip", headers={
        "Content-Disposition": f'attachment; filename="inspection-{detail.id}.zip"',
    })


@router.get("/tasks/{task_id}/analysis", response_model=AnalysisResponse)
def read_analysis(task_id: UUID, request: Request, session: Database) -> AnalysisResponse:
    request.app.state.inspections.ensure_available()
    return request.app.state.inspection_analysis.read(session, str(task_id))


@router.post("/tasks/{task_id}/analysis", response_model=AnalysisResponse, status_code=202)
def generate_analysis(task_id: UUID, request: Request, session: Database) -> AnalysisResponse:
    request.app.state.inspections.ensure_available()
    request.app.state.inspection_analysis.start(str(task_id))
    session.expire_all()
    return request.app.state.inspection_analysis.read(session, str(task_id))
