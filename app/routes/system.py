import logging

from fastapi import APIRouter, Request, Response, status
from sqlalchemy import text

from app.metrics import DB_UP, metrics_response

logger = logging.getLogger(__name__)

router = APIRouter(tags=["system"])


@router.get("/health")
async def health() -> dict:
    """Liveness probe: process is running and able to handle requests."""
    return {"status": "ok"}


@router.get("/ready")
async def ready(request: Request, response: Response) -> dict:
    """Readiness probe: process plus its required dependencies (database)."""
    engine = request.app.state.engine
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        DB_UP.set(1)
        return {"status": "ok", "checks": {"database": "ok"}}
    except Exception as exc:
        logger.warning("readiness check failed: database unreachable", exc_info=exc)
        DB_UP.set(0)
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "unavailable", "checks": {"database": "failed"}}


@router.get("/version")
async def version(request: Request) -> dict:
    """Release identification: application version and git commit SHA."""
    settings = request.app.state.settings
    return {"version": settings.app_version, "git_sha": settings.git_sha}


@router.get("/metrics")
async def metrics() -> Response:
    """Prometheus exposition endpoint."""
    return metrics_response()
