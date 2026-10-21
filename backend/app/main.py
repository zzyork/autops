from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware

from .api.v1.router import api_router
from .core.config import Settings, get_settings
from .core.storage import initialize_storage
from .schemas.health import HealthResponse
from .services.ssh_connections import ConnectionTestManager
from .services.inspection_tasks import InspectionManager
from .services.ai_chat import ChatManager
from .services.inspection_analysis import InspectionAnalysisManager
from .services.host_basic_info import HostBasicInfoManager


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings if settings is not None else get_settings()

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        engine, sessions, cipher = await run_in_threadpool(initialize_storage, settings.data_dir)
        application.state.sessions = sessions
        application.state.cipher = cipher
        manager = None
        inspections = None
        ai = None
        analysis = None
        host_basic_info = None
        try:
            manager = await run_in_threadpool(ConnectionTestManager, sessions, cipher)
            application.state.connection_tests = manager
            host_basic_info = HostBasicInfoManager(sessions, cipher)
            application.state.host_basic_info = host_basic_info
            analysis = await run_in_threadpool(InspectionAnalysisManager, sessions, cipher, settings.data_dir)
            application.state.inspection_analysis = analysis
            inspections = await run_in_threadpool(InspectionManager, sessions, cipher, analysis.automatic)
            application.state.inspections = inspections
            ai = await run_in_threadpool(ChatManager, sessions, cipher)
            application.state.ai = ai
            yield
        finally:
            if analysis is not None:
                analysis.stop_accepting()
            try:
                try:
                    try:
                        if ai is not None:
                            await run_in_threadpool(ai.close)
                    finally:
                        try:
                            if inspections is not None:
                                await run_in_threadpool(inspections.close)
                        finally:
                            if analysis is not None:
                                await run_in_threadpool(analysis.close)
                finally:
                    try:
                        if host_basic_info is not None:
                            await run_in_threadpool(host_basic_info.close)
                    finally:
                        if manager is not None:
                            await run_in_threadpool(manager.close)
            finally:
                await run_in_threadpool(engine.dispose)

    application = FastAPI(title=settings.app_name, version="0.1.0", debug=settings.debug, lifespan=lifespan)
    application.state.data_dir = settings.data_dir

    @application.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        # 默认校验响应含 input，可能回显密码；仅返回字段定位及错误类型。
        errors = [{"loc": error["loc"], "type": error["type"], "msg": "参数格式不正确，请检查该字段"} for error in exc.errors()]
        return JSONResponse(status_code=422, content={"detail": errors})
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization"],
    )
    application.include_router(api_router, prefix="/api/v1")

    @application.get("/", tags=["基础接口"])
    async def root() -> dict[str, str]:
        return {"message": "Hello, FastAPI!"}

    @application.get("/health", response_model=HealthResponse, tags=["健康检查"])
    async def health() -> HealthResponse:
        return HealthResponse()

    return application


app = create_app()
