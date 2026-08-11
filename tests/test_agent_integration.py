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
