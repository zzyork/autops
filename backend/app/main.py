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


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings if settings is not None else get_settings()

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        engine, sessions, cipher = await run_in_threadpool(initialize_storage, settings.data_dir)
        application.state.sessions = sessions
        application.state.cipher = cipher
        try:
            yield
        finally:
            await run_in_threadpool(engine.dispose)

    application = FastAPI(title=settings.app_name, version="0.1.0", debug=settings.debug, lifespan=lifespan)

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
