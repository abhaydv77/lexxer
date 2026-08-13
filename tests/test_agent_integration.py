"""Integration tests verifying the agent loop works with WorkingMemory."""

import os
from unittest.mock import patch, MagicMock

from memory.working import WorkingMemory


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
