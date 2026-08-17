"""Health endpoint: basic liveness check."""

from fastapi import APIRouter

from api.schemas import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse, tags=["health"])
def health() -> HealthResponse:
    """Return service liveness information."""
    return HealthResponse()