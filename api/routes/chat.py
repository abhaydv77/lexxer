"""Chat endpoint: send a user query through the Lexxer agent."""

from fastapi import APIRouter, status

from api.schemas import ChatRequest, ChatResponse
from api.service import get_agent_service

router = APIRouter()

AGENT_FAILURE_MESSAGE = "Agent execution failed."


@router.post("/chat", response_model=ChatResponse, status_code=status.HTTP_200_OK, tags=["chat"])
def chat(request: ChatRequest) -> ChatResponse:
    """Run a single user query through the agent and return its response.

    The run_id links the response to its trace (see GET /api/runs/{run_id}).
    If the agent fails, the response still carries the run_id with
    ``status: "failed"`` and a generic message; details remain server-side.
    """
    result = get_agent_service().run(request.message)
    return ChatResponse(
        run_id=result["run_id"],
        message=result.get("response") or AGENT_FAILURE_MESSAGE,
        status=result["status"],
    )