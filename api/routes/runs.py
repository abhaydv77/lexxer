"""Run history and trace endpoints."""

from fastapi import APIRouter, HTTPException, Query

from api.schemas import RunDetail, RunListResponse
from api.service import get_agent_service

router = APIRouter()


@router.get("/runs", response_model=RunListResponse, tags=["runs"])
def list_runs(
    limit: int = Query(20, ge=1, le=100, description="Max runs to return, newest first."),
) -> RunListResponse:
    """Return recent agent runs, newest first."""
    runs = get_agent_service().get_runs(limit=limit)
    return RunListResponse(runs=runs)


@router.get("/runs/{run_id}", response_model=RunDetail, tags=["runs"])
def get_run(run_id: str) -> RunDetail:
    """Return full details and trace events for a single run."""
    detail = get_agent_service().get_run(run_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return detail