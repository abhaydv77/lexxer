"""Tests for harness.context.ContextBuilder."""

from harness.context import ContextBuilder, BuiltContext
from memory.working import WorkingMemory

# Minimal tool definitions for tests
TEST_TOOLS = [
    {
        "name": "inspect_dataset",
        "description": "Inspect dataset structure and statistics.",
        "input_schema": {"properties": {}, "required": []},
    },
    {
        "name": "calculate_average",
        "description": "Calculate the average of a numeric column.",
        "input_schema": {
            "properties": {"column": {"type": "string"}},
            "required": ["column"],
        },
    },
]


def make_builder():
    return ContextBuilder(system_instructions="You are a data analyst agent.")


# ── 1. Empty memory ────────────────────────────────────────────────────

def test_empty_memory():
    """ContextBuilder should not crash with empty memory."""
    mem = WorkingMemory()
    ctx = make_builder().build(mem, tools=TEST_TOOLS)

    assert isinstance(ctx, BuiltContext)
    assert "SYSTEM INSTRUCTIONS:" in ctx.system_prompt
    assert "You are a data analyst agent." in ctx.system_prompt
    assert "RECENT TOOL RESULTS: None" in ctx.system_prompt
    assert ctx.messages == []


def test_empty_memory_no_tools():
    """Builder handles tools=None gracefully (defaults to real tools)."""
    mem = WorkingMemory()
    ctx = make_builder().build(mem)  # tools=None -> default TOOLS
    assert "AVAILABLE TOOLS:" in ctx.system_prompt
    assert ctx.messages == []


# ── 2. Current task ────────────────────────────────────────────────────

def test_current_task_in_context():
    mem = WorkingMemory()
    mem.set_task("Calculate the average of Average_income")
    ctx = make_builder().build(mem, tools=TEST_TOOLS)

    assert "CURRENT TASK:" in ctx.system_prompt
    assert "Calculate the average of Average_income" in ctx.system_prompt


# ── 3. Conversation order ──────────────────────────────────────────────

def test_conversation_order_preserved():
    mem = WorkingMemory()
    mem.add_message("user", "Show me the average")
    mem.add_message("assistant", "Which column?")
    mem.add_message("user", "Average_income")
    mem.add_assistant_message({"content": "Computing...", "tool_calls": []})
    mem.add_tool_message("tc1", '{"success": true}')

    ctx = make_builder().build(mem, tools=TEST_TOOLS)
    roles = [m["role"] for m in ctx.messages]

    assert roles == ["user", "assistant", "user", "assistant", "tool"]


def test_conversation_not_in_system_prompt():
    """Conversation belongs in messages, not the system prompt."""
    mem = WorkingMemory()
    mem.add_message("user", "hello there")
    ctx = make_builder().build(mem, tools=TEST_TOOLS)

    assert "hello there" not in ctx.system_prompt


# ── 4. Dataset ─────────────────────────────────────────────────────────

def test_dataset_in_context():
    mem = WorkingMemory()
    mem.set_dataset({
        "name": "cities.csv",
        "row_count": 10,
        "columns": [
            {"name": "Population", "dtype": "int64"},
            {"name": "Average_income", "dtype": "float64"},
        ],
    })
    ctx = make_builder().build(mem, tools=TEST_TOOLS)

    assert "DATASET INFORMATION:" in ctx.system_prompt
    assert "cities.csv" in ctx.system_prompt
    assert "10 rows" in ctx.system_prompt
    assert "SCHEMA:" in ctx.system_prompt
    assert "Population: int64" in ctx.system_prompt
    assert "Average_income: float64" in ctx.system_prompt


def test_no_dataset_no_fabrication():
    """When no dataset is present, no dataset section is fabricated."""
    mem = WorkingMemory()
    ctx = make_builder().build(mem, tools=TEST_TOOLS)

    assert "DATASET INFORMATION:" not in ctx.system_prompt


# ── 5. Tool results ────────────────────────────────────────────────────

def test_tool_results_in_context():
    mem = WorkingMemory()
    mem.add_tool_result(
        "run_query",
        {"query": "SELECT AVG(Average_income) FROM df"},
        {"success": True, "data": {"row_count": 1}, "meta": {"duration_ms": 5.0}},
    )
    ctx = make_builder().build(mem, tools=TEST_TOOLS)

    assert "RECENT TOOL RESULTS:" in ctx.system_prompt
    assert "run_query" in ctx.system_prompt
    assert "rows: 1" in ctx.system_prompt


def test_tool_result_error_shown():
    mem = WorkingMemory()
    mem.add_tool_result(
        "run_query",
        {"query": "SELECT bad FROM df"},
        {"success": False, "error": "catalog error", "meta": {}},
    )
    ctx = make_builder().build(mem, tools=TEST_TOOLS)

    assert "ERROR" in ctx.system_prompt
    assert "catalog error" in ctx.system_prompt


# ── 6. Complete context ────────────────────────────────────────────────

def test_complete_context():
    mem = WorkingMemory()
    mem.set_task("Show me the average of Average_income")
    mem.add_message("user", "Show me the average of Average_income")
    mem.set_dataset({
        "name": "cities.csv",
        "row_count": 10,
        "columns": [{"name": "Average_income", "dtype": "float64"}],
    })
    mem.add_tool_result(
        "run_query",
        {"query": "SELECT AVG(Average_income) FROM df"},
        {"success": True, "data": {"row_count": 1}, "meta": {}},
    )

    ctx = make_builder().build(mem, tools=TEST_TOOLS)

    for section in [
        "SYSTEM INSTRUCTIONS:",
        "CURRENT TASK:",
        "DATASET INFORMATION:",
        "AVAILABLE TOOLS:",
        "RECENT TOOL RESULTS:",
    ]:
        assert section in ctx.system_prompt

    assert "inspect_dataset" in ctx.system_prompt
    assert "calculate_average" in ctx.system_prompt


# ── 7. No duplication ──────────────────────────────────────────────────

def test_no_duplicate_messages():
    mem = WorkingMemory()
    mem.add_message("user", "hi")
    ctx = make_builder().build(mem, tools=TEST_TOOLS)

    user_msgs = [m for m in ctx.messages if m["role"] == "user"]
    assert len(user_msgs) == 1


def test_no_duplicate_between_calls():
    """Building twice from the same memory yields the same conversation."""
    mem = WorkingMemory()
    mem.add_message("user", "hi")
    mem.add_message("assistant", "hello")

    builder = make_builder()
    ctx1 = builder.build(mem, tools=TEST_TOOLS)
    ctx2 = builder.build(mem, tools=TEST_TOOLS)

    assert len(ctx1.messages) == len(ctx2.messages) == 2


def test_system_message_not_duplicated():
    """System message appears exactly once in to_messages()."""
    mem = WorkingMemory()
    mem.add_message("user", "hi")
    ctx = make_builder().build(mem, tools=TEST_TOOLS)

    msgs = ctx.to_messages()
    system_msgs = [m for m in msgs if m["role"] == "system"]
    assert len(system_msgs) == 1


# ── to_messages ────────────────────────────────────────────────────────

def test_to_messages_format():
    mem = WorkingMemory()
    mem.add_message("user", "hi")
    ctx = make_builder().build(mem, tools=TEST_TOOLS)

    msgs = ctx.to_messages()
    assert msgs[0]["role"] == "system"
    assert msgs[1]["role"] == "user"
    assert msgs[1]["content"] == "hi"


def test_build_context_does_not_mutate_memory():
    """Building context must not modify the underlying WorkingMemory."""
    mem = WorkingMemory()
    mem.set_task("task")
    mem.add_message("user", "hello")

    before_msgs = mem.get_messages()
    before_task = mem.get_task()

    make_builder().build(mem, tools=TEST_TOOLS)

    assert mem.get_messages() == before_msgs
    assert mem.get_task() == before_task
