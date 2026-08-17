"""Dataset endpoint: expose basic info about the loaded dataset."""

from fastapi import APIRouter, HTTPException

from api.schemas import DatasetInfo
from api.service import get_agent_service

router = APIRouter()


@router.get("/dataset", response_model=DatasetInfo, tags=["dataset"])
def get_dataset() -> DatasetInfo:
    """Return basic metadata about the dataset loaded into the agent."""
    info = get_agent_service().get_dataset_info()
    if info is None:
        raise HTTPException(status_code=404, detail="No dataset loaded")
    return info