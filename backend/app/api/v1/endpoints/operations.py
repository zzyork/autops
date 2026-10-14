import logging
from collections.abc import Callable
from typing import Annotated, TypeVar
from uuid import UUID

from fastapi import APIRouter, HTTPException, Path, Query, Request

from ...dependencies import Database
from ....repositories import operations as repository
from ....schemas.operations import (ConfirmInput, InspectInput, Inspection, ModuleId, OperationCatalog,
                                     PlanInput, ResolveInput, TaskPage, TaskResponse)
from ....services.operation_commands import catalog as command_catalog

router = APIRouter(prefix="/operations", tags=["服务器运维"])
logger = logging.getLogger(__name__)
T = TypeVar("T")


def safe(request: Request, operation: Callable[[], T]) -> T:
    try:
        return operation()
    except HTTPException:
        raise
    except Exception as exc:
        request.app.state.operations.persistence_failed.set()
        logger.error("Operation API failure: %s", type(exc).__name__)
        raise HTTPException(503, "运维服务不可用") from None


@router.get("/catalog", response_model=OperationCatalog)
def catalog() -> OperationCatalog:
    return OperationCatalog(modules=command_catalog())


@router.post("/inspect", response_model=Inspection)
def inspect(data: InspectInput, request: Request, session: Database) -> Inspection:
    return safe(request, lambda: request.app.state.operations.inspect(session, data))


@router.post("/plans", response_model=TaskResponse, status_code=201)
def prepare(data: PlanInput, request: Request, session: Database) -> TaskResponse:
    return safe(request, lambda: TaskResponse.model_validate(request.app.state.operations.prepare(session, data)))


@router.post("/tasks/{task_id}/confirm", response_model=TaskResponse, status_code=202)
def confirm(task_id: UUID, data: ConfirmInput, request: Request) -> TaskResponse:
    if data.confirmation != str(task_id) or data.impact_ack is not True:
        raise HTTPException(422, "确认内容与任务不符")
    return safe(request, lambda: TaskResponse.model_validate(request.app.state.operations.confirm(str(task_id))))


@router.post("/tasks/{task_id}/hosts/{host_id}/resolve", response_model=TaskResponse)
def resolve(task_id: UUID, host_id: Annotated[int, Path(gt=0)], data: ResolveInput, request: Request) -> TaskResponse:
    if data.confirmation != str(task_id) or data.remote_stopped is not True:
        raise HTTPException(422, "请在带外核对远端进程已停止，并确认任务 ID")
    return safe(request, lambda: TaskResponse.model_validate(
        request.app.state.operations.resolve(str(task_id), host_id, data.note)))


@router.get("/tasks", response_model=TaskPage)
def list_tasks(request: Request, session: Database, module: ModuleId | None = None,
               page: Annotated[int, Query(ge=1)] = 1,
               page_size: Annotated[int, Query(ge=1, le=50)] = 20) -> TaskPage:
    def load() -> TaskPage:
        request.app.state.operations.ensure_available()
        repository.expire_plans(session)
        items, total = repository.page_tasks(session, module, page, page_size)
        return TaskPage(items=[TaskResponse.model_validate(item) for item in items], total=total,
                        page=page, page_size=page_size)
    return safe(request, load)


@router.get("/tasks/{task_id}", response_model=TaskResponse)
def read_task(task_id: UUID, request: Request, session: Database) -> TaskResponse:
    def load() -> TaskResponse:
        request.app.state.operations.ensure_available()
        repository.expire_plans(session)
        task = repository.get_task(session, str(task_id))
        if task is None:
            raise HTTPException(404, "运维任务不存在")
        return TaskResponse.model_validate(task)
    return safe(request, load)
