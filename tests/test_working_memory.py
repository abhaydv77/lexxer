"""Focused tests for memory.working.WorkingMemory."""

from memory.working import WorkingMemory, ToolResult


# ── 1. Empty memory ────────────────────────────────────────────────────

def test_empty_memory():
    """A fresh WorkingMemory has no state."""
    mem = WorkingMemory()
    assert mem.is_empty() is True
    assert mem.get_messages() == []
    assert mem.get_task() is None
    assert mem.get_tool_results() == []
    assert mem.get_dataset() is None
    assert mem.get_dataset_schema() is None
    assert mem.get_analysis_state() == {}


# ── 2. Messages ────────────────────────────────────────────────────────

def test_add_and_get_messages():
    """Messages are stored and retrievable in order."""
    mem = WorkingMemory()
    mem.add_message("user", "hello")
    mem.add_message("assistant", "hi there")

    msgs = mem.get_messages()
    assert len(msgs) == 2
    assert msgs[0]["role"] == "user"
    assert msgs[0]["content"] == "hello"
    assert msgs[1]["role"] == "assistant"
    assert msgs[1]["content"] == "hi there"


def test_get_messages_returns_copy():
    """get_messages should return a copy, not the internal list."""
    mem = WorkingMemory()
    mem.add_message("user", "hi")

    msgs = mem.get_messages()
    msgs.append({"role": "user", "content": "tampered"})

    assert len(mem.get_messages()) == 1


def test_add_assistant_message_with_tool_calls():
    """Assistant messages with tool_calls are recorded correctly."""
    mem = WorkingMemory()
    mem.add_assistant_message({
        "content": None,
        "tool_calls": [{"id": "tc1", "function": {"name": "load_dataset", "arguments": '{"path": "x.csv"'}}],
    })
    msgs = mem.get_messages()
    assert len(msgs) == 1
    assert msgs[0]["role"] == "assistant"
    assert len(msgs[0]["tool_calls"]) == 1


def test_add_tool_message():
    """Tool-role messages are stored with their tool_call_id."""
    mem = WorkingMemory()
    mem.add_tool_message("tc1", '{"success": true}')
    msgs = mem.get_messages()
    assert len(msgs) == 1
    assert msgs[0]["role"] == "tool"
    assert msgs[0]["tool_call_id"] == "tc1"


def test_add_message_validates():
    """Invalid messages raise ValueError."""
    mem = WorkingMemory()
    try:
        mem.add_message("", "content")
        assert False, "should have raised"
    except ValueError:
        pass

    try:
        mem.add_message("user", 123)
        assert False, "should have raised"
    except ValueError:
        pass


# ── 3. Task ───────────────────────────────────────────────────────────

def test_set_and_get_task():
    mem = WorkingMemory()
    assert mem.get_task() is None

    mem.set_task("Find the average income")
    assert mem.get_task() == "Find the average income"


# ── 4. Dataset ────────────────────────────────────────────────────────

def test_set_and_get_dataset():
    mem = WorkingMemory()
    ds_info = {
        "name": "cities.csv",
        "row_count": 10,
        "columns": [{"name": "City", "dtype": "str"}, {"name": "Population", "dtype": "int64"}],
    }
    mem.set_dataset(ds_info)

    assert mem.get_dataset()["name"] == "cities.csv"
    assert mem.get_dataset_schema() == ds_info["columns"]


# ── 5. Tool results ───────────────────────────────────────────────────

def test_add_and_get_tool_result():
    mem = WorkingMemory()
    result = {"success": True, "data": {"row_count": 5}, "meta": {"duration_ms": 12.3}}
    mem.add_tool_result("run_query", {"query": "SELECT * FROM df"}, result)

    tool_results = mem.get_tool_results()
    assert len(tool_results) == 1
    assert tool_results[0].name == "run_query"
    assert tool_results[0].arguments == {"query": "SELECT * FROM df"}
    assert tool_results[0].result["success"] is True
    assert tool_results[0].duration_ms == 12.3


def test_get_tool_results_returns_copy():
    mem = WorkingMemory()
    mem.add_tool_result("run_query", {"query": "x"}, {"success": True, "data": {}, "meta": {}})

    results = mem.get_tool_results()
    results.clear()
    assert len(mem.get_tool_results()) == 1


def test_get_tool_results_summary():
    mem = WorkingMemory()
    mem.add_tool_result(
        "load_dataset",
        {"path": "data/cities.csv"},
        {"success": True, "data": {"row_count": 10, "columns": [{"name": "City", "dtype": "str"}]}, "meta": {"duration_ms": 5.0}},
    )
    summary = mem.get_tool_results_summary()
    assert "load_dataset" in summary
    assert "success=True" in summary
    assert "City(str)" in summary


# ── 6. Analysis state ─────────────────────────────────────────────────

def test_set_and_get_analysis_state():
    mem = WorkingMemory()
    mem.set_analysis_state(last_column="Population", threshold=1000)
    state = mem.get_analysis_state()
    assert state["last_column"] == "Population"
    assert state["threshold"] == 1000

    # get() shorthand
    assert mem.get("last_column") == "Population"
    assert mem.get("nonexistent", "default") == "default"


def test_analysis_state_accumulates():
    """Multiple set_analysis_state calls accumulate, not overwrite."""
    mem = WorkingMemory()
    mem.set_analysis_state(a=1)
    mem.set_analysis_state(b=2)
    state = mem.get_analysis_state()
    assert state == {"a": 1, "b": 2}


# ── 7. Clear ─────────────────────────────────────────────────────────

def test_clear_resets_all_state():
    """clear() wipes everything back to empty defaults."""
    mem = WorkingMemory()
    mem.add_message("user", "hello")
    mem.set_task("do something")
    mem.set_dataset({"name": "test.csv"})
    mem.add_tool_result("load_dataset", {"path": "test.csv"}, {"success": True, "data": {}, "meta": {}})
    mem.set_analysis_state(key="value")

    assert not mem.is_empty()

    mem.clear()

    assert mem.is_empty()
    assert mem.get_messages() == []
    assert mem.get_task() is None
    assert mem.get_dataset() is None
    assert mem.get_dataset_schema() is None
    assert mem.get_tool_results() == []
    assert mem.get_analysis_state() == {}


# ── 8. Build context ──────────────────────────────────────────────────

def test_build_context_empty():
    mem = WorkingMemory()
    ctx = mem.build_context()
    assert ctx == ""


def test_build_context_with_state():
    mem = WorkingMemory()
    mem.set_task("Find average income")
    mem.set_dataset({"name": "cities.csv", "row_count": 10})
    mem.set_dataset({"columns": [{"name": "Average_income", "dtype": "float"}]})
    # Note: set_dataset overwrites, so set again with full info
    mem.set_dataset({
        "name": "cities.csv",
        "row_count": 10,
        "columns": [{"name": "Average_income", "dtype": "float"}],
    })

    ctx = mem.build_context()
    assert "Current task: Find average income" in ctx
    assert "Dataset: cities.csv (10 rows)" in ctx
    assert "Average_income(float)" in ctx


# ── 9. No mutable defaults ────────────────────────────────────────────

def test_no_mutable_default_sharing():
    """Two WorkingMemory instances should not share state."""
    mem1 = WorkingMemory()
    mem2 = WorkingMemory()

    mem1.add_message("user", "hello")
    mem1.set_task("task1")

    assert len(mem2.get_messages()) == 0
    assert mem2.get_task() is None


# ── 10. ToolResult dataclass ───────────────────────────────────────────

def test_tool_result_summarize_success():
    tr = ToolResult(
        name="run_query",
        arguments={"query": "SELECT * FROM df"},
        result={"success": True, "data": {"row_count": 100, "truncated": True, "rows": [{"a": 1}]}, "meta": {"duration_ms": 12.5}},
    )
    s = tr.summarize()
    assert "run_query" in s
    assert "success=True" in s
    assert "12.5ms" in s


def test_tool_result_summarize_failure():
    tr = ToolResult(
        name="run_query",
        arguments={"query": "SELECT * FROM nonexistent"},
        result={"success": False, "error": "table not found", "meta": {"duration_ms": 5.0}},
    )
    s = tr.summarize()
    assert "success=False" in s
    assert "table not found" in s
