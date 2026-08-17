"""AgentService: the thin service layer between FastAPI routes and the Lexxer agent.

Responsibilities:
  - generate a run_id for each user query
  - run the user message through the existing ``agent.loop.run_agent``
  - keep a run registry (query, response) alongside the Tracer's trace data
  - expose run history and run details for the API

The service does **not** reimplement agent logic; it only orchestrates the
existing harness (Working Memory → Context Builder → Agent Loop → Tool
Runtime → Validator → Tracer).
"""

from __future__ import annotations

import logging
import os
import threading
import uuid
from typing import Any

from agent.loop import run_agent
from tracing.tracer import Tracer, TraceRun
from tools.dataset import load_dataset
import tools.dataset as dataset_module

logger = logging.getLogger(__name__)

DEFAULT_DATASET_PATH = os.environ.get("LEXXER_DATASET", "data/cities.csv")

MAX_RUNS = 20


def _serialize_event(event: Any) -> dict[str, Any]:
    """Convert a TraceEvent into a plain JSON-serialisable dict."""
    return {
        "event_type": event.event_type,
        "timestamp": event.timestamp,
        "status": event.status,
        "duration_ms": event.duration_ms,
        "metadata": event.metadata or {},
        "message": event.message,
    }


class AgentService:
    """Orchestrates agent runs and exposes their history and traces."""

    def __init__(self) -> None:
        self._tracer = Tracer()
        # run_id -> {"query": str, "response": str | None}
        self._records: dict[str, dict[str, Any]] = {}
        # Serialise runs so the single Tracer's active-run slot is never
        # corrupted by concurrent requests.
        self._lock = threading.Lock()
        self._dataset_name: str | None = None
        self._load_default_dataset()

    # ── setup ───────────────────────────────────────────────────────────

    def _load_default_dataset(self) -> None:
        """Pre-load the default dataset so the agent and /api/dataset work."""
        if not os.path.exists(DEFAULT_DATASET_PATH):
            logger.warning("Default dataset not found: %s", DEFAULT_DATASET_PATH)
            return
        result = load_dataset(DEFAULT_DATASET_PATH)
        if result.get("success"):
            self._dataset_name = os.path.basename(DEFAULT_DATASET_PATH)
            logger.info("Loaded default dataset: %s", self._dataset_name)
        else:
            logger.warning("Failed to load default dataset: %s", result.get("error"))

    # ── execution ───────────────────────────────────────────────────────

    def run(self, message: str) -> dict[str, Any]:
        """Send a user query through the Lexxer agent.

        Returns a record dict with keys ``run_id``, ``query``, ``response``
        and ``status``. The status is ``"success"`` when the agent produced
        a final answer, otherwise ``"failed"`` (details are in the trace).
        """
        run_id = str(uuid.uuid4())
        record = {
            "run_id": run_id,
            "query": message,
            "response": None,
            "status": "failed",
        }

        with self._lock:
            self._records[run_id] = record
            try:
                response = run_agent(
                    message,
                    memory=None,
                    trace=self._tracer,
                    run_id=run_id,
                )
                record["response"] = response
                record["status"] = "success"
            except Exception as exc:  # noqa: BLE001 - boundary with the agent
                logger.exception("Agent run %s failed: %s", run_id, exc)
                record["status"] = "failed"

        return dict(record)

    # ── retrieval ───────────────────────────────────────────────────────

    def get_runs(self, limit: int = MAX_RUNS) -> list[dict[str, Any]]:
        """Return recent run summaries, newest first, capped at *limit*."""
        runs = sorted(
            self._tracer.get_runs(),
            key=lambda r: r.started_at,
            reverse=True,
        )[:limit]
        return [self._summarize(run) for run in runs]

    def get_dataset_info(self) -> dict[str, Any] | None:
        """Return basic info about the loaded dataset, or None if none."""
        df = dataset_module._df
        if df is None:
            return None
        return {
            "name": self._dataset_name,
            "rows": len(df),
            "columns": [str(col) for col in df.columns],
        }

    # ── helpers ─────────────────────────────────────────────────────────

    def _summarize(self, run: TraceRun) -> dict[str, Any]:
        record = self._records.get(run.run_id, {})
        return {
            "run_id": run.run_id,
            "status": run.status,
            "started_at": run.started_at,
            "ended_at": run.ended_at,
            "duration_ms": run.duration_ms,
            "query": record.get("query"),
        }

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        """Return full run details (including events), or None if unknown."""
        run = self._tracer.get_run(run_id)
        if run is None:
            return None
        record = self._records.get(run_id, {})
        return {
            "run_id": run.run_id,
            "status": run.status,
            "query": record.get("query"),
            "response": record.get("response"),
            "started_at": run.started_at,
            "ended_at": run.ended_at,
            "duration_ms": run.duration_ms,
            "events": [_serialize_event(e) for e in run.events],
        }


# module-level singleton so routes share one service instance
_service: AgentService | None = None


def get_agent_service() -> AgentService:
    """Return the shared AgentService instance (created lazily)."""
    global _service
    if _service is None:
        _service = AgentService()
    return _service
