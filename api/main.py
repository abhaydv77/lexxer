"""Lexxer API: FastAPI application entry point.

The API is a thin layer on top of the Lexxer agent harness:

    Frontend → FastAPI → AgentService → Lexxer Harness

No agent logic lives in the route handlers.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.config import get_cors_origins
from api.routes import chat_router, dataset_router, health_router, runs_router
from api.service import get_agent_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialise the shared agent service (pre-loads the default dataset).
    get_agent_service()
    yield


app = FastAPI(
    title="Lexxer API",
    description="REST API exposing the Lexxer Data Analyst Agent harness.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(health_router, prefix="/api")
app.include_router(chat_router, prefix="/api")
app.include_router(runs_router, prefix="/api")
app.include_router(dataset_router, prefix="/api")