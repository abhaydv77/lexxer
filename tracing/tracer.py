"""Tracer: lightweight internal tracing for Lexxer agent runs.

The tracer is an **observability layer**.  It observes the system from the
side — it records events but does *not* control agent logic, tool execution,
validation, memory management, or context construction.

Design goals
------------
* Simple Python — no decorators, no metaprogramming, no event buses.
* Clear names and type hints so the architecture is easy to explain.
* In-memory storage only (replaces trivially for a future frontend).
* Never crash the agent loop: every public method guards against errors.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


# ── Event ──────────────────────────────────────────────────────────────────


@dataclass
class TraceEvent:
    """A single observation recorded during an agent run."""

    timestamp: datetime
    event_type: str
    message: str | None = None
    metadata: dict[str, Any] | None = None
    duration_ms: float | None = None
    status: str | None = None

    @classmethod
    def now(
        cls,
        event_type: str,
        *,
        message: str | None = None,
        metadata: dict[str, Any] | None = None,
        duration_ms: float | None = None,
        status: str | None = None,
    ) -> TraceEvent:
        """Create an event stamped with the current UTC time."""
        return cls(
            timestamp=datetime.now(timezone.utc),
            event_type=event_type,
            message=message,
            metadata=metadata or {},
            duration_ms=duration_ms,
            status=status,
        )


# ── Run ────────────────────────────────────────────────────────────────────


@dataclass
class TraceRun:
    """A complete recorded agent run."""

    run_id: str
    started_at: datetime
    ended_at: datetime | None = None
    duration_ms: float | None = None
    status: str = "running"
    events: list[TraceEvent] = field(default_factory=list)

    @property
    def run_id_short(self) -> str:
        """First 8 chars of the run ID for compact display."""
        return self.run_id[:8]


# ── Tracer ─────────────────────────────────────────────────────────────────


class Tracer:
    """
    Records structured trace events for agent runs.

    Usage::

        tracer = Tracer()
        run = tracer.start_run()

        tracer.log("context_built", metadata={"message_count": 3})

        tracer.log(
            "tool_call",
            metadata={"tool": "run_query"},
            status="success",
            duration_ms=42.0,
        )

        tracer.end_run(status="success")

        # retrieve
        runs = tracer.get_runs()
        one = tracer.get_run(run_id)
    """

    def __init__(self) -> None:
        self._runs: list[TraceRun] = []
        self._current: TraceRun | None = None

    # ── run lifecycle ───────────────────────────────────────────────────

    def start_run(self, run_id: str | None = None) -> TraceRun:
        """Begin a new traced run and return the ``TraceRun`` object."""
        run_id = run_id or self._generate_run_id()
        run = TraceRun(
            run_id=run_id,
            started_at=datetime.now(timezone.utc),
        )
        self._current = run
        self._runs.append(run)
        self.log("run_started", metadata={"run_id": run_id})
        return run

    def end_run(self, status: str = "success") -> TraceRun | None:
        """End the current run with *status* and compute duration."""
        if self._current is None:
            return None

        run = self._current
        ended_at = datetime.now(timezone.utc)
        duration_ms = (ended_at - run.started_at).total_seconds() * 1000.0

        run.ended_at = ended_at
        run.duration_ms = round(duration_ms, 2)
        run.status = status

        self.log(
            "run_completed",
            metadata={"run_id": run.run_id, "status": status},
            duration_ms=round(duration_ms, 2),
            status=status,
        )
        self._current = None
        return run

    # ── event recording ─────────────────────────────────────────────────

    def log(
        self,
        event_type: str,
        *,
        message: str | None = None,
        metadata: dict[str, Any] | None = None,
        duration_ms: float | None = None,
        status: str | None = None,
    ) -> TraceEvent:
        """Record a single event on the current run."""
        event = TraceEvent.now(
            event_type,
            message=message,
            metadata=metadata,
            duration_ms=duration_ms,
            status=status,
        )
        if self._current is not None:
            self._current.events.append(event)
        return event

    # ── retrieval ───────────────────────────────────────────────────────

    def get_run(self, run_id: str) -> TraceRun | None:
        """Return the run with *run_id*, or ``None`` if not found."""
        for run in self._runs:
            if run.run_id == run_id:
                return run
        return None

    def get_runs(self) -> list[TraceRun]:
        """Return all completed-and-active runs (snapshot copy)."""
        return list(self._runs)

    @property
    def current_run(self) -> TraceRun | None:
        """The run that is currently open, if any."""
        return self._current

    # ── internals ───────────────────────────────────────────────────────

    @staticmethod
    def _generate_run_id() -> str:
        """Generate a human-readable unique run ID."""
        suffix = uuid.uuid4().hex[:8]
        return f"lexxer-run-{suffix}"
