"""Operational health and readiness endpoints."""

from fastapi import APIRouter, Request, status
from pydantic import BaseModel
from sqlalchemy import text
from starlette.responses import JSONResponse

from ..core.config import Settings

router = APIRouter(prefix="/health", tags=["health"])


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    environment: str


def _response(settings: Settings, state: str) -> HealthResponse:
    return HealthResponse(
        status=state,
        service=settings.app_name,
        version=settings.app_version,
        environment=settings.environment.value,
    )


@router.get("/live", response_model=HealthResponse)
async def live(request: Request) -> HealthResponse:
    """Process-level liveness check; it does not require the database."""
    return _response(request.app.state.settings, "ok")


@router.get("/ready", response_model=HealthResponse)
async def ready(request: Request) -> HealthResponse | JSONResponse:
    """Readiness check; verifies startup completed and the database is reachable."""
    settings: Settings = request.app.state.settings
    if not getattr(request.app.state, "startup_complete", False):
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=_response(settings, "not_ready").model_dump(),
        )
    try:
        async with request.app.state.db_engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    except Exception:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=_response(settings, "not_ready").model_dump(),
        )
    return _response(settings, "ready")


@router.get("", response_model=HealthResponse)
async def health(request: Request) -> HealthResponse:
    """Human-friendly process health endpoint."""
    return await live(request)
