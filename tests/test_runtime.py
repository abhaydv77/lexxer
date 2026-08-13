"""Tests for harness.runtime.ToolRuntime."""

import pytest

from harness.runtime import (
    ToolRuntime,
    ToolResult,
    TOOL_NOT_FOUND,
    INVALID_ARGUMENTS,
    TOOL_EXECUTION_ERROR,
)


def _avg(column: str) -> float:
    """Fake tool used for tests."""
    data = {"Average_income": 38200.0, "Population": 5500000.0}
    if column not in data:
        raise ValueError(f"Column '{column}' does not exist.")
    return data[column]


AVG_SCHEMA = {
    "name": "calculate_average",
    "description": "Calculate the average of a numeric column.",
    "input_schema": {
        "type": "object",
        "properties": {"column": {"type": "string"}},
        "required": ["column"],
    },
}


def make_runtime() -> ToolRuntime:
    runtime = ToolRuntime()
    runtime.register("calculate_average", _avg, schema=AVG_SCHEMA)
    return runtime


def test_empty_runtime():
    runtime = ToolRuntime()
    assert runtime.tool_names() == []
    assert not runtime.has_tool("anything")


# ── Test 1: Register tool ──────────────────────────────────────────────

def test_register_tool():
    runtime = make_runtime()
    assert runtime.has_tool("calculate_average")
    assert "calculate_average" in runtime.tool_names()


def test_register_requires_callable():
    runtime = ToolRuntime()
    with pytest.raises(TypeError):
        runtime.register("bad", 42)


# ── Test 2: Successful execution ───────────────────────────────────────

def test_successful_execution():
    runtime = make_runtime()
    result = runtime.execute(
        "calculate_average",
        {"column": "Average_income"},
    )
    assert isinstance(result, ToolResult)
    assert result.success is True
    assert result.tool_name == "calculate_average"
    assert result.output == 38200.0
    assert result.error is None
    assert result.error_type is None


# ── Test 3: Unknown tool ───────────────────────────────────────────────

def test_unknown_tool():
    runtime = make_runtime()
    result = runtime.execute("unknown_tool", {})
    assert result.success is False
    assert result.error_type == TOOL_NOT_FOUND
    assert result.output is None
    assert "unknown_tool" in result.error


# ── Test 4: Invalid arguments ──────────────────────────────────────────

def test_missing_required_argument():
    runtime = make_runtime()
    result = runtime.execute("calculate_average", {})
    assert result.success is False
    assert result.error_type == INVALID_ARGUMENTS
    assert "column" in result.error


def test_wrong_argument_type():
    runtime = make_runtime()
    result = runtime.execute("calculate_average", {"column": 123})
    assert result.success is False
    assert result.error_type == INVALID_ARGUMENTS


def test_arguments_must_be_dict():
    runtime = make_runtime()
    result = runtime.execute("calculate_average", None)
    # None args -> treated as empty dict -> missing required arg
    assert result.success is False
    assert result.error_type == INVALID_ARGUMENTS


# ── Test 5: Tool exception ─────────────────────────────────────────────

def test_tool_exception_captured():
    runtime = make_runtime()
    result = runtime.execute("calculate_average", {"column": "Revenue"})
    assert result.success is False
    assert result.error_type == TOOL_EXECUTION_ERROR
    assert result.output is None
    assert "Revenue" in result.error


# ── Test 6: Execution timing ───────────────────────────────────────────

def test_success_duration_non_negative():
    runtime = make_runtime()
    result = runtime.execute("calculate_average", {"column": "Average_income"})
    assert result.duration_ms is not None
    assert result.duration_ms >= 0


def test_failure_also_has_duration():
    runtime = make_runtime()
    result = runtime.execute("unknown_tool", {})
    assert result.duration_ms is not None
    assert result.duration_ms >= 0


# ── as_dict envelope ───────────────────────────────────────────────────

def test_as_dict_normal_output():
    runtime = make_runtime()
    result = runtime.execute("calculate_average", {"column": "Average_income"})
    d = result.as_dict()
    assert d["success"] is True
    assert d["data"] == 38200.0
    assert "duration_ms" in d["meta"]


def test_as_dict_passes_through_envelope():
    """A tool that already returns an envelope is passed through unchanged."""
    def envelope_tool(x: int) -> dict:
        return {"success": True, "data": {"x": x}, "error": None, "meta": {"duration_ms": 9.9}}

    runtime = ToolRuntime()
    runtime.register(
        "envelope_tool",
        envelope_tool,
        schema={"name": "envelope_tool", "input_schema": {"properties": {"x": {"type": "integer"}}, "required": ["x"]}},
    )
    r = runtime.execute("envelope_tool", {"x": 3})
    d = r.as_dict()
    assert d["success"] is True
    assert d["data"] == {"x": 3}
    # duration preserved from the tool's own envelope
    assert d["meta"]["duration_ms"] == 9.9


def test_as_dict_failure():
    runtime = make_runtime()
    result = runtime.execute("unknown_tool", {})
    d = result.as_dict()
    assert d["success"] is False
    assert d["error"] is not None


# ── register_all ───────────────────────────────────────────────────────

def test_register_all():
    def foo(a: int) -> int:
        return a

    def bar() -> str:
        return "bar"

    schemas = [
        {"name": "foo", "input_schema": {"properties": {"a": {"type": "integer"}}, "required": ["a"]}},
        {"name": "bar", "input_schema": {"properties": {}, "required": []}},
    ]
    runtime = ToolRuntime()
    runtime.register_all({"foo": foo, "bar": bar}, schemas=schemas)
    assert set(runtime.tool_names()) == {"foo", "bar"}


def test_register_all_validation():
    def foo(a: int) -> int:
        return a

    schemas = [
        {"name": "foo", "input_schema": {"properties": {"a": {"type": "integer"}}, "required": ["a"]}},
    ]
    runtime = ToolRuntime()
    runtime.register_all({"foo": foo}, schemas=schemas)

    ok = runtime.execute("foo", {"a": 5})
    assert ok.success is True and ok.output == 5

    bad = runtime.execute("foo", {})
    assert bad.success is False and bad.error_type == INVALID_ARGUMENTS


# ── Runtime is stateless & independent ─────────────────────────────────

def test_runtime_is_stateless():
    """Two calls with same args return equivalent results; no state leaks."""
    runtime = make_runtime()
    r1 = runtime.execute("calculate_average", {"column": "Average_income"})
    r2 = runtime.execute("calculate_average", {"column": "Average_income"})
    assert r1.output == r2.output