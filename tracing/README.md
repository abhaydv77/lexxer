# Tracing

A lightweight internal tracing system that records the lifecycle of an agent run.

> Tracing is an **observability layer**. It observes the system from the side — it records events but does *not* control agent logic, tool execution, validation, memory management, or context construction.

## Structure

| File | Purpose |
|------|---------|
| `tracer.py` | `TraceEvent`, `TraceRun`, `Tracer` classes |

## Core Concepts

### `TraceEvent`

A single observation recorded during a run:

```text
timestamp          — UTC datetime of the event
event_type         — what kind of event (run_started, tool_call, etc.)
message            — optional human-readable note
metadata           — structured dict of extra context (tool name, validator, etc.)
duration_ms        — optional elapsed time (reused from ToolResult, not re-timed)
status             — optional pass/fail/success indicator
```

### `TraceRun`

A complete recorded agent run:

```text
run_id         — unique identifier (e.g. "lexxer-run-a1b2c3d4")
started_at     — when the run began
ended_at       — when the run ended (None until end_run)
duration_ms    — total run duration
status         — "running" | "success" | "failed"
events[]       — ordered list of TraceEvent
```

### `Tracer`

The in-memory trace store. API:

```python
tracer = Tracer()

run = tracer.start_run()           # begin a new run → TraceRun

tracer.log("context_built",        # record an event
           metadata={"message_count": 5},
           duration_ms=None,
           status=None)

tracer.log("tool_call",
           metadata={"tool": "run_query"},
           duration_ms=None)      # just the request

tracer.log("tool_completed",
           metadata={"tool": "run_query", "success": True},
           duration_ms=42.0,
           status="success")

tracer.log("validation",
           metadata={"validator": "run_query_validator",
                     "valid": True,
                     "expected": 38200,
                     "actual": 38200},
           status="passed")

tracer.end_run(status="success")   # finalize the run

# retrieval
all_runs = tracer.get_runs()
one_run = tracer.get_run(run_id)
current = tracer.current_run
```

## Event Types

| Event | When | Key Metadata |
|-------|------|--------------|
| `run_started` | Agent run begins | `run_id` |
| `context_built` | ContextBuilder finishes | `message_count`, `tool_count`, `dataset_available` |
| `llm_call` | LLM request emitted | `provider`, `model`, `duration_ms` |
| `tool_call` | Tool invoked | `tool`, `arguments` |
| `tool_completed` | Tool finished | `tool`, `success`, `error_type`, `duration_ms` |
| `validation` | Validator ran | `validator`, `valid`, `expected`, `actual` |
| `response_generated` | Final response returned | `length` |
| `run_completed` | Run finalized | `run_id`, `status`, `duration_ms` |
| `error` | Exception caught | `error_type`, `message` |

## Design Principles

- **No duplicate timers**: durations are reused from `ToolResult.duration_ms` and measured once for LLM calls — the tracer does not re-time what the runtime already timed.
- **Never crashes**: every tracer method guards against errors; logging failures do not affect agent behavior.
- **In-memory storage**: runs are stored in a list inside the `Tracer` object. No external services.
- **Simple Python**: no decorators, no metaprogramming, no event buses — easy to explain.

## Agent Loop Integration

The tracer is used as an optional parameter to `run_agent`:

```python
from tracing.tracer import Tracer

tracer = Tracer()
response = run_agent("Show me the average of Average_income", memory, trace=tracer)

# Inspect the trace
run = tracer.get_runs()[0]
for event in run.events:
    print(event.event_type, event.status, event.duration_ms)
```

If `trace` is not provided, a local `Tracer` is created so the agent still works without one.

## Example Trace

For `User: Show me the average of Average_income.`:

```text
RUN #abc123

run_started
    ↓
context_built           (message_count=4, tool_count=3, dataset_available=True)
    ↓
llm_call                (provider=groq, model=openai/gpt-oss-20b, duration_ms=890)
    ↓
tool_call               (tool=run_query)
    ↓
tool_completed          (tool=run_query, status=success, duration_ms=42)
    ↓
validation              (validator=run_query_validator, valid=True)
          expected=38200, actual=38200
    ↓
llm_call                (duration_ms=210)
    ↓
response_generated
    ↓
run_completed           (status=success, total_duration=1850ms)

Total events: 8
```
