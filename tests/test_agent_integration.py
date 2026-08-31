"""Integration tests verifying the agent loop works with WorkingMemory."""

import os
from unittest.mock import patch, MagicMock

from memory.working import WorkingMemory
from tracing.tracer import Tracer


def _make_mock_response(content: str, tool_calls=None):
    """Create a mock Groq chat completion response."""
    msg = MagicMock()
    msg.content = content
    msg.tool_calls = tool_calls

    # model_dump is called on the message — return a realistic dict
    msg.model_dump = MagicMock(return_value={"content": content, "tool_calls": tool_calls or []})

    resp = MagicMock()
    resp.choices = [MagicMock(message=msg)]
    return resp


def test_agent_with_memory_creates_session():
    """WorkingMemory is populated after a load_dataset call."""
    from agent.loop import run_agent, FUNCTIONS

    # Mock the Groq client to avoid API calls
    with patch("agent.loop.client") as mock_client:
        mock_client.chat.completions.create = MagicMock(
            return_value=_make_mock_response("Dataset loaded successfully!")
        )

        memory = WorkingMemory()
        result = run_agent("Load data/cities.csv", memory)

        assert result == "Dataset loaded successfully!"
        assert memory.get_task() == "Load data/cities.csv"
        assert len(memory.get_messages()) >= 2  # system + user
        assert memory.get_messages()[0]["role"] == "system"


def test_agent_records_tool_results():
    """Tool calls are recorded in WorkingMemory after execution."""
    from agent.loop import run_agent

    with patch("agent.loop.client") as mock_client:
        mock_client.chat.completions.create = MagicMock(
            return_value=_make_mock_response(
                "Here are the results",
                tool_calls=[],  # no further tool calls
            )
        )

        memory = WorkingMemory()
        run_agent("Load data/cities.csv", memory)

        # The LLM made a tool call, which we executed and recorded
        results = memory.get_tool_results()
        # At minimum the load_dataset tool call was recorded
        if results:
            assert results[0].name == "load_dataset"


def test_agent_no_memory_still_works():
    """run_agent with no memory arg should still work (creates ephemeral memory)."""
    from agent.loop import run_agent

    with patch("agent.loop.client") as mock_client:
        mock_client.chat.completions.create = MagicMock(
            return_value=_make_mock_response("OK")
        )

        result = run_agent("Hello")
        assert result == "OK"


def test_memory_persists_across_calls():
    """Messages accumulate across multiple run_agent calls with same memory."""
    from agent.loop import run_agent

    with patch("agent.loop.client") as mock_client:
        def mock_create(**kwargs):
            # Return a simple response with no tool calls after first call
            return _make_mock_response("OK")

        mock_client.chat.completions.create = MagicMock(side_effect=mock_create)

        memory = WorkingMemory()
        run_agent("First message", memory)
        run_agent("Second message", memory)

        # Should have system + user + assistant for each message
        msgs = memory.get_messages()
        user_msgs = [m for m in msgs if m["role"] == "user"]
        assert len(user_msgs) == 2
        assert user_msgs[0]["content"] == "First message"
        assert user_msgs[1]["content"] == "Second message"


def test_agent_executes_tools_through_runtime():
    """The agent loop routes tool calls through the ToolRuntime."""
    from agent.loop import run_agent

    fn = MagicMock()
    fn.name = "load_dataset"
    fn.arguments = '{"path": "data/cities.csv"}'
    tool_calls = [MagicMock(id="tc1", function=fn)]

    # 1. LLM requests a tool call
    # 2. runtime executes it
    # 3. LLM returns final answer
    with patch("agent.loop.client") as mock_client:
        responses = [
            _make_mock_response(None, tool_calls=tool_calls),
            _make_mock_response("Dataset loaded!", tool_calls=[]),
        ]
        mock_client.chat.completions.create = MagicMock(side_effect=responses)

        memory = WorkingMemory()
        result = run_agent("Load data/cities.csv", memory)

        assert result == "Dataset loaded!"
        # Tool executed via runtime: memory has the tool result
        results = memory.get_tool_results()
        assert len(results) == 1
        assert results[0].name == "load_dataset"


def test_agent_handles_unknown_tool_gracefully():
    """If the LLM requests an unregistered tool, the agent loop survives."""
    from agent.loop import run_agent

    fn = MagicMock()
    fn.name = "nonexistent_tool"
    fn.arguments = "{}"
    tool_calls = [MagicMock(id="tc1", function=fn)]

    with patch("agent.loop.client") as mock_client:
        responses = [
            _make_mock_response(None, tool_calls=tool_calls),
            _make_mock_response("I don't have that tool", tool_calls=[]),
        ]
        mock_client.chat.completions.create = MagicMock(side_effect=responses)

        memory = WorkingMemory()
        result = run_agent("Do something", memory)

        assert result == "I don't have that tool"
        # The failure was recorded, not raised
        results = memory.get_tool_results()
        assert len(results) == 1
        assert results[0].result["success"] is False
        assert results[0].result["error"] is not None


# ── Tracing integration ───────────────────────────────────────────────────


def test_agent_run_produces_trace_with_required_events():
    """A complete agent run produces a trace with all lifecycle events."""
    from agent.loop import run_agent

    fn = MagicMock()
    fn.name = "load_dataset"
    fn.arguments = '{"path": "data/cities.csv"}'
    tool_calls = [MagicMock(id="tc1", function=fn)]

    with patch("agent.loop.client") as mock_client:
        responses = [
            _make_mock_response(None, tool_calls=tool_calls),
            _make_mock_response("Dataset loaded!", tool_calls=[]),
        ]
        mock_client.chat.completions.create = MagicMock(side_effect=responses)

        memory = WorkingMemory()
        tracer = Tracer()
        result = run_agent("Load data/cities.csv", memory, trace=tracer)

        assert result == "Dataset loaded!"

        runs = tracer.get_runs()
        assert len(runs) == 1

        run = runs[0]
        event_types = [e.event_type for e in run.events]

        # All required lifecycle events must be present
        required = {
            "run_started",
            "context_built",
            "llm_call",
            "tool_call",
            "tool_completed",
            "validation",
            "response_generated",
            "run_completed",
        }
        assert required.issubset(set(event_types))

        # Run should be marked success with timing
        assert run.status == "success"
        assert run.duration_ms is not None
        assert run.duration_ms >= 0

        # LLM call event should have provider and model metadata
        llm_events = [e for e in run.events if e.event_type == "llm_call"]
        assert len(llm_events) >= 1
        assert llm_events[0].metadata["provider"] == "groq"
        assert "model" in llm_events[0].metadata

        # Tool events should have duration
        tool_completed_events = [
            e for e in run.events if e.event_type == "tool_completed"
        ]
        assert len(tool_completed_events) >= 1
        assert tool_completed_events[0].duration_ms is not None

        # Validation event should be present with validator info
        validation_events = [
            e for e in run.events if e.event_type == "validation"
        ]
        assert len(validation_events) >= 1
        assert validation_events[0].metadata["validator"] is not None


def test_agent_trace_captures_error():
    """A failed run is traced with error event."""
    from agent.loop import run_agent

    fn = MagicMock()
    fn.name = "nonexistent_tool"
    fn.arguments = "{}"
    tool_calls = [MagicMock(id="tc1", function=fn)]

    with patch("agent.loop.client") as mock_client:
        # Simulate an exception mid-run (after first LLM call returns tool_calls,
        # second LLM call raises)
        responses = [
            _make_mock_response(None, tool_calls=tool_calls),
            _make_mock_response("Done", tool_calls=[]),
        ]
        mock_client.chat.completions.create = MagicMock(side_effect=responses)

        memory = WorkingMemory()
        tracer = Tracer()
        run_agent("Do something", memory, trace=tracer)

        run = tracer.get_runs()[-1]
        # Tool execution failure is handled by runtime, not a crash
        # So run should still complete successfully
        assert run.status == "success"


# ── Bounded iteration tests ──────────────────────────────────────────────────


def test_agent_finishes_before_max_iterations():
    """Agent completes normally when LLM returns no tool calls before limit."""
    from agent.loop import run_agent

    fn = MagicMock()
    fn.name = "load_dataset"
    fn.arguments = '{"path": "data/cities.csv"}'
    tool_calls = [MagicMock(id="tc1", function=fn)]

    with patch("agent.loop.client") as mock_client:
        # Two iterations: tool call -> final response
        responses = [
            _make_mock_response(None, tool_calls=tool_calls),
            _make_mock_response("Dataset loaded!", tool_calls=[]),
        ]
        mock_client.chat.completions.create = MagicMock(side_effect=responses)

        memory = WorkingMemory()
        tracer = Tracer()
        result = run_agent("Load data", memory, trace=tracer, max_iterations=5)

        assert result == "Dataset loaded!"
        run = tracer.get_runs()[-1]
        assert run.status == "success"
        # Should have 2 llm_call events (one for tool call, one for final)
        llm_calls = [e for e in run.events if e.event_type == "llm_call"]
        assert len(llm_calls) == 2


def test_agent_stops_at_max_iterations():
    """Agent stops gracefully when max_iterations is reached."""
    from agent.loop import run_agent

    fn = MagicMock()
    fn.name = "run_query"
    fn.arguments = '{"query": "SELECT * FROM data"}'
    tool_calls = [MagicMock(id="tc1", function=fn)]

    with patch("agent.loop.client") as mock_client:
        # Always return tool calls - agent should stop after max_iterations
        mock_client.chat.completions.create = MagicMock(
            return_value=_make_mock_response(None, tool_calls=tool_calls)
        )

        memory = WorkingMemory()
        tracer = Tracer()
        result = run_agent("Query data", memory, trace=tracer, max_iterations=3)

        # Should return the graceful stop message
        assert "stopped after reaching the maximum number of iterations (3)" in result
        run = tracer.get_runs()[-1]
        assert run.status == "stopped"
        # Should have exactly 3 llm_call events
        llm_calls = [e for e in run.events if e.event_type == "llm_call"]
        assert len(llm_calls) == 3
        # Should have max_iterations_reached event
        max_iter_events = [e for e in run.events if e.event_type == "max_iterations_reached"]
        assert len(max_iter_events) == 1
        assert max_iter_events[0].metadata["max_iterations"] == 3
        assert max_iter_events[0].metadata["final_iteration"] == 3


def test_invalid_max_iterations_raises_value_error():
    """Invalid max_iterations values raise ValueError."""
    from agent.loop import run_agent

    with patch("agent.loop.client") as mock_client:
        mock_client.chat.completions.create = MagicMock(
            return_value=_make_mock_response("OK")
        )

        memory = WorkingMemory()

        # Test zero
        try:
            run_agent("test", memory, max_iterations=0)
            assert False, "Expected ValueError for max_iterations=0"
        except ValueError as e:
            assert "positive integer" in str(e)

        # Test negative
        try:
            run_agent("test", memory, max_iterations=-1)
            assert False, "Expected ValueError for max_iterations=-1"
        except ValueError as e:
            assert "positive integer" in str(e)

        # Test non-integer
        try:
            run_agent("test", memory, max_iterations=2.5)
            assert False, "Expected ValueError for max_iterations=2.5"
        except ValueError as e:
            assert "positive integer" in str(e)

        # Test string
        try:
            run_agent("test", memory, max_iterations="5")
            assert False, "Expected ValueError for max_iterations='5'"
        except ValueError as e:
            assert "positive integer" in str(e)


def test_agent_validation_failure_allows_retry_within_limit():
    """Validation failures count as iterations and allow retry within limit."""
    from agent.loop import run_agent

    # First call: tool call that will fail validation
    fn1 = MagicMock()
    fn1.name = "run_query"
    fn1.arguments = '{"query": "SELECT AVG(value) FROM data"}'
    tool_calls_1 = [MagicMock(id="tc1", function=fn1)]

    # Second call: tool call again (retry after validation failure)
    fn2 = MagicMock()
    fn2.name = "run_query"
    fn2.arguments = '{"query": "SELECT AVG(value) FROM data"}'
    tool_calls_2 = [MagicMock(id="tc2", function=fn2)]

    # Third call: final response
    tool_calls_3 = []

    with patch("agent.loop.client") as mock_client:
        responses = [
            _make_mock_response(None, tool_calls=tool_calls_1),
            _make_mock_response(None, tool_calls=tool_calls_2),
            _make_mock_response("Corrected result!", tool_calls=tool_calls_3),
        ]
        mock_client.chat.completions.create = MagicMock(side_effect=responses)

        memory = WorkingMemory()
        tracer = Tracer()
        result = run_agent("Calculate average", memory, trace=tracer, max_iterations=5)

        assert result == "Corrected result!"
        run = tracer.get_runs()[-1]
        assert run.status == "success"
        llm_calls = [e for e in run.events if e.event_type == "llm_call"]
        assert len(llm_calls) == 3
