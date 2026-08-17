"""Integration tests for the Lexxer REST API (FastAPI layer).

The Groq client is mocked in every test; the rest of the harness
(Working Memory, Context Builder, Agent Loop, Tool Runtime, Validator,
Tracer) runs for real.
"""

import uuid
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

import api.service
from api.main import app

CLIENT = "agent.loop.client"


def _make_mock_response(content: str, tool_calls=None):
    """Create a mock Groq chat completion response."""
    msg = MagicMock()
    msg.content = content
    msg.tool_calls = tool_calls
    msg.model_dump = MagicMock(
        return_value={"content": content, "tool_calls": tool_calls or []}
    )
    resp = MagicMock()
    resp.choices = [MagicMock(message=msg)]
    return resp


def _make_tool_call(name: str, arguments: str, call_id: str = "tc1"):
    fn = MagicMock()
    fn.name = name
    fn.arguments = arguments
    tc = MagicMock(id=call_id, function=fn)
    return tc


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def reset_service():
    """Give each test a fresh AgentService (fresh tracer + run history)."""
    api.service._service = None
    yield
    api.service._service = None


# ── 1. Health ──────────────────────────────────────────────────────────────


def test_health(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "service": "lexxer"}


# ── 2. Chat ────────────────────────────────────────────────────────────────


def test_chat_returns_response_and_run_id(client):
    with patch(CLIENT) as mock_client:
        mock_client.chat.completions.create = MagicMock(
            return_value=_make_mock_response("Hello from the agent.", tool_calls=[])
        )
        resp = client.post("/api/chat", json={"message": "Hello"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "success"
    assert body["message"] == "Hello from the agent."
    assert uuid.UUID(body["run_id"])  # run_id is a valid UUID


def test_chat_empty_message_rejected(client):
    resp = client.post("/api/chat", json={"message": ""})
    assert resp.status_code == 422


def test_chat_agent_failure(client):
    with patch(CLIENT) as mock_client:
        mock_client.chat.completions.create = MagicMock(
            side_effect=RuntimeError("boom")
        )
        resp = client.post("/api/chat", json={"message": "do something"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "failed"
    assert body["message"] == "Agent execution failed."
    assert uuid.UUID(body["run_id"])

    # The failure is recorded in the trace, not exposed to the client.
    detail = client.get(f"/api/runs/{body['run_id']}").json()
    assert detail["status"] == "failed"
    assert any(e["event_type"] == "error" for e in detail["events"])


# ── 3. Run history ─────────────────────────────────────────────────────────


def test_runs_history_newest_first(client):
    with patch(CLIENT) as mock_client:
        mock_client.chat.completions.create = MagicMock(
            return_value=_make_mock_response("one", tool_calls=[])
        )
        client.post("/api/chat", json={"message": "first query"})
        mock_client.chat.completions.create = MagicMock(
            return_value=_make_mock_response("two", tool_calls=[])
        )
        client.post("/api/chat", json={"message": "second query"})

    resp = client.get("/api/runs")
    assert resp.status_code == 200
    runs = resp.json()["runs"]
    assert len(runs) == 2
    assert runs[0]["query"] == "second query"
    assert runs[1]["query"] == "first query"
    for run in runs:
        assert run["status"] == "success"
        assert run["started_at"] is not None
        assert run["ended_at"] is not None
        assert run["duration_ms"] is not None


def test_runs_history_limit(client):
    with patch(CLIENT) as mock_client:
        mock_client.chat.completions.create = MagicMock(
            return_value=_make_mock_response("ok", tool_calls=[])
        )
        for i in range(5):
            client.post("/api/chat", json={"message": f"query {i}"})

    resp = client.get("/api/runs", params={"limit": 3})
    assert resp.status_code == 200
    assert len(resp.json()["runs"]) == 3


# ── 4. Run details ─────────────────────────────────────────────────────────


def test_run_details(client):
    with patch(CLIENT) as mock_client:
        mock_client.chat.completions.create = MagicMock(
            return_value=_make_mock_response("final answer", tool_calls=[])
        )
        run_id = client.post("/api/chat", json={"message": "my query"}).json()["run_id"]

    resp = client.get(f"/api/runs/{run_id}")
    assert resp.status_code == 200
    detail = resp.json()
    assert detail["run_id"] == run_id
    assert detail["status"] == "success"
    assert detail["query"] == "my query"
    assert detail["response"] == "final answer"
    assert detail["started_at"] is not None
    assert detail["ended_at"] is not None
    assert detail["duration_ms"] is not None

    event_types = [e["event_type"] for e in detail["events"]]
    assert event_types[0] == "run_started"
    assert event_types[-1] == "run_completed"


def test_run_details_not_found(client):
    resp = client.get("/api/runs/does-not-exist")
    assert resp.status_code == 404
    assert resp.json() == {"detail": "Run not found"}


# ── 5. Real tool-using request ─────────────────────────────────────────────


def test_chat_with_tool_call_and_validation(client):
    """A real request that uses run_query: the tool runs against the loaded
    dataset, the validator recomputes the aggregate, and the trace records
    tool_call, tool_completed and validation events."""
    tool_call = _make_tool_call(
        "run_query",
        '{"query": "SELECT AVG(Average_income) FROM df"}',
        call_id="tc1",
    )
    with patch(CLIENT) as mock_client:
        mock_client.chat.completions.create = MagicMock(
            side_effect=[
                _make_mock_response(None, tool_calls=[tool_call]),
                _make_mock_response("The average income is 38,200.", tool_calls=[]),
            ]
        )
        resp = client.post(
            "/api/chat",
            json={"message": "Show me the average of Average_income"},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "success"
    assert body["message"] == "The average income is 38,200."
    assert uuid.UUID(body["run_id"])

    detail = client.get(f"/api/runs/{body['run_id']}").json()
    assert detail["status"] == "success"

    events = {e["event_type"]: e for e in detail["events"]}
    assert "context_built" in events
    assert "llm_call" in events

    tool_call_event = events["tool_call"]
    assert tool_call_event["metadata"]["tool"] == "run_query"

    tool_completed = events["tool_completed"]
    assert tool_completed["status"] == "success"
    assert tool_completed["duration_ms"] is not None

    validation = events["validation"]
    assert validation["status"] == "passed"
    assert validation["metadata"]["validator"] == "run_query_validator"

    assert "response_generated" in events
    assert events["run_completed"]["status"] == "success"


# ── 6. Dataset ─────────────────────────────────────────────────────────────


def test_dataset_info(client):
    resp = client.get("/api/dataset")
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "cities.csv"
    assert body["rows"] > 0
    assert "Average_income" in body["columns"]