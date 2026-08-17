"""Pydantic response/request schemas for the Lexxer API.

All fields are ``snake_case`` and every response field is present (nullable
where the value may legitimately be absent) so the frontend never has to
guess field names.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# ── health ────────────────────────────────────────────────────────────────


class HealthResponse(BaseModel):
    status: str = "ok"
    service: str = "lexxer"


# ── chat ──────────────────────────────────────────────────────────────────


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="The user's query for the agent.")


class ChatResponse(BaseModel):
    run_id: str
    message: str
    status: str


# ── runs ──────────────────────────────────────────────────────────────────


class RunSummary(BaseModel):
    run_id: str
    status: str
    started_at: datetime
    ended_at: datetime | None = None
    duration_ms: float | None = None
    query: str | None = None


class RunListResponse(BaseModel):
    runs: list[RunSummary]


class TraceEventSchema(BaseModel):
    event_type: str
    timestamp: datetime
    status: str | None = None
    duration_ms: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    message: str | None = None


class RunDetail(BaseModel):
    run_id: str
    status: str
    query: str | None = None
    response: str | None = None
    started_at: datetime
    ended_at: datetime | None = None
    duration_ms: float | None = None
    events: list[TraceEventSchema] = Field(default_factory=list)


# ── dataset ───────────────────────────────────────────────────────────────


class DatasetInfo(BaseModel):
    name: str
    rows: int
    columns: list[str]