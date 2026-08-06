"""Health and version endpoints."""

from datetime import UTC, datetime

from fastapi import APIRouter
from pydantic import BaseModel

from config.settings import get_settings

router = APIRouter()


class HealthResponse(BaseModel):
    """Health check response payload."""

    status: str
    timestamp: str
    env: str


class VersionResponse(BaseModel):
    """Version information response payload."""

    version: str
    service: str
    env: str


@router.get("/health", response_model=HealthResponse, summary="Liveness check")
async def health() -> HealthResponse:
    """Return 200 when the service is reachable and the event loop is running."""
    settings = get_settings()
    return HealthResponse(
        status="ok",
        timestamp=datetime.now(UTC).isoformat(),
        env=settings.env.value,
    )


@router.get("/version", response_model=VersionResponse, summary="Service version")
async def version() -> VersionResponse:
    """Return service name and version string."""
    settings = get_settings()
    return VersionResponse(
        version=settings.observability.service_version,
        service=settings.observability.service_name,
        env=settings.env.value,
    )
