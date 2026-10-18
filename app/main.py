import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.db import create_engine, create_session_factory
from app.logging_config import configure_logging
from app.metrics import APP_INFO, MetricsMiddleware
from app.routes import ships, system

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level)

    engine = create_engine(settings)
    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = create_session_factory(engine)

    APP_INFO.labels(version=settings.app_version, git_sha=settings.git_sha).set(1)
    logger.info(
        "application startup complete",
        extra={"app_version": settings.app_version, "git_sha": settings.git_sha},
    )

    yield

    logger.info("application shutdown initiated")
    await engine.dispose()
    logger.info("application shutdown complete")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name.capitalize(),
        version=settings.app_version,
        lifespan=lifespan,
    )

    app.add_middleware(MetricsMiddleware)

    app.include_router(system.router)
    app.include_router(ships.router)

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.error("unhandled exception", exc_info=exc, extra={"path": request.url.path})
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "internal server error"},
        )

    return app


app = create_app()
