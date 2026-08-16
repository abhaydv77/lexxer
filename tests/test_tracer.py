"""Tests for tracing.tracer.Tracer."""

from datetime import datetime

import pytest

from tracing.tracer import Tracer, TraceEvent, TraceRun


# ── Test 1: Start run ────────────────────────────────────────────────────

def test_start_run():
    tracer = Tracer()
    run = tracer.start_run()

    assert run.run_id is not None
    assert run.run_id.startswith("lexxer-run-")
    assert run.status == "running"
    assert run.started_at is not None
    assert isinstance(run.started_at, datetime)
    assert run.ended_at is None
    assert run.duration_ms is None
    # start_run logs 'run_started' as the first event
    assert len(run.events) == 1
    assert run.events[0].event_type == "run_started"
    assert run.events[0].metadata["run_id"] == run.run_id


def test_start_run_custom_id():
    tracer = Tracer()
    run = tracer.start_run(run_id="my-run-001")
    assert run.run_id == "my-run-001"


# ── Test 2: Log event ────────────────────────────────────────────────────

def test_log_event():
    tracer = Tracer()
    tracer.start_run()
    event = tracer.log("context_built")

    assert event.event_type == "context_built"
    assert event.timestamp is not None
    assert isinstance(event.timestamp, datetime)

    run = tracer.current_run
    # start_run logs 'run_started', then 'context_built'
    assert len(run.events) == 2
    assert run.events[0].event_type == "run_started"
    assert run.events[1].event_type == "context_built"
    assert run.events[1] is event


def test_log_event_with_metadata():
    tracer = Tracer()
    tracer.start_run()
    tracer.log(
        "context_built",
        message="Context ready",
        metadata={"message_count": 3, "tool_count": 3},
    )
    event = tracer.current_run.events[-1]
    assert event.message == "Context ready"
    assert event.metadata["message_count"] == 3
    assert event.metadata["tool_count"] == 3


# ── Test 3: Tool event (duration & status preserved) ─────────────────────

def test_log_tool_event():
    tracer = Tracer()
    tracer.start_run()
    tracer.log(
        "tool_call",
        metadata={"tool": "calculate_average"},
    )
    tracer.log(
        "tool_completed",
        metadata={"tool": "calculate_average", "success": True},
        duration_ms=120.0,
        status="success",
    )

    events = tracer.current_run.events
    assert events[-2].event_type == "tool_call"
    assert events[-2].metadata["tool"] == "calculate_average"

    completed = events[-1]
    assert completed.event_type == "tool_completed"
    assert completed.duration_ms == 120.0
    assert completed.status == "success"
    assert completed.metadata["success"] is True


# ── Test 4: Validation event ──────────────────────────────────────────────

def test_log_validation_event():
    tracer = Tracer()
    tracer.start_run()
    tracer.log(
        "validation",
        metadata={
            "validator": "average_validator",
            "valid": True,
            "expected": 38200,
            "actual": 38200,
        },
        status="passed",
    )

    event = tracer.current_run.events[-1]
    assert event.event_type == "validation"
    assert event.status == "passed"
    assert event.metadata["validator"] == "average_validator"
    assert event.metadata["expected"] == 38200
    assert event.metadata["actual"] == 38200


# ── Test 5: End run ───────────────────────────────────────────────────────

def test_end_run():
    tracer = Tracer()
    run = tracer.start_run()
    tracer.log("context_built")
    ended = tracer.end_run(status="success")

    assert ended is not None
    assert ended.status == "success"
    assert ended.ended_at is not None
    assert ended.duration_ms is not None
    assert ended.duration_ms >= 0

    # 'run_completed' event should be the final event
    assert run.events[-1].event_type == "run_completed"
    assert run.events[-1].status == "success"
    assert run.events[-1].duration_ms is not None


def test_end_run_sets_status():
    tracer = Tracer()
    tracer.start_run()
    tracer.end_run("failed")
    assert tracer.current_run is None
    run = tracer.get_runs()[-1]
    assert run.status == "failed"


# ── Test 6: Failed run ───────────────────────────────────────────────────

def test_run_with_error():
    tracer = Tracer()
    tracer.start_run()
    tracer.log("tool_call", metadata={"tool": "run_query"})
    tracer.log(
        "error",
        metadata={
            "error_type": "ToolExecutionError",
            "message": "Column not found",
        },
    )
    tracer.end_run(status="failed")

    run = tracer.get_runs()[-1]
    assert run.status == "failed"

    error_events = [e for e in run.events if e.event_type == "error"]
    assert len(error_events) == 1
    assert error_events[0].metadata["error_type"] == "ToolExecutionError"
    assert error_events[0].metadata["message"] == "Column not found"


# ── Test 7: Retrieve runs ─────────────────────────────────────────────────

def test_get_runs_and_get_run():
    tracer = Tracer()
    run1 = tracer.start_run()
    tracer.end_run("success")

    run2 = tracer.start_run()
    tracer.end_run("failed")

    all_runs = tracer.get_runs()
    assert len(all_runs) == 2

    found = tracer.get_run(run1.run_id)
    assert found is run1
    assert found.status == "success"

    found2 = tracer.get_run(run2.run_id)
    assert found2 is run2
    assert found2.status == "failed"

    assert tracer.get_run("nonexistent") is None


def test_get_runs_returns_copy():
    tracer = Tracer()
    tracer.start_run()
    runs = tracer.get_runs()
    assert len(runs) == 1
    # Mutating the returned list must not mutate the tracer's internal state
    runs.clear()
    assert len(tracer.get_runs()) == 1


# ── Edge cases ────────────────────────────────────────────────────────────

def test_end_run_without_start():
    tracer = Tracer()
    result = tracer.end_run("success")
    assert result is None


def test_log_without_run_is_safe():
    """Logging without an active run should not crash."""
    tracer = Tracer()
    tracer.log("context_built", metadata={"x": 1})
    # No run active → event is silently dropped, no crash
    assert tracer.get_runs() == []


def test_run_id_is_unique():
    tracer = Tracer()
    ids = {tracer.start_run().run_id for _ in range(100)}
    assert len(ids) == 100
