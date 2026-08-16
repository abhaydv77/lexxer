"""Tests for harness.validator.Validator."""

import math

import pandas as pd
import pytest

from harness.runtime import ToolResult, TOOL_NOT_FOUND, INVALID_ARGUMENTS, TOOL_EXECUTION_ERROR
from harness.validator import (
    Validator,
    ValidationResult,
    ValidationContext,
)


# ── Fake dataset ─────────────────────────────────────────────────────────

@pytest.fixture
def sample_df():
    return pd.DataFrame({
        "Average_income": [100, 200, 300],
        "Population": [1000, 2000, 3000],
    })


def make_ctx(df):
    return ValidationContext(dataset=df)


# ── Test 1: Correct average ──────────────────────────────────────────────

def test_correct_average(sample_df):
    """Tool returns the correct AVG → PASS."""
    df = sample_df
    actual_avg = df["Average_income"].mean()  # 200.0
    result = ToolResult(
        success=True,
        tool_name="run_query",
        output={"success": True, "data": {
            "query": "SELECT AVG(Average_income) FROM df",
            "rows": [{"AVG(Average_income)": actual_avg}],
            "row_count": 1,
        }},
    )
    validation = Validator().validate(result, context=make_ctx(df))
    assert validation.valid is True
    assert validation.validator_name == "run_query_validator"


# ── Test 2: Incorrect average ────────────────────────────────────────────

def test_incorrect_average(sample_df):
    """Tool returns wrong value → FAIL."""
    result = ToolResult(
        success=True,
        tool_name="run_query",
        output={"success": True, "data": {
            "query": "SELECT AVG(Average_income) FROM df",
            "rows": [{"AVG(Average_income)": 250}],
            "row_count": 1,
        }},
    )
    validation = Validator().validate(result, context=make_ctx(sample_df))
    assert validation.valid is False
    assert validation.expected == 200.0
    assert validation.actual == 250
    assert "did not match" in (validation.message or "")


# ── Test 3: Floating point tolerance ─────────────────────────────────────

def test_floating_point_tolerance(sample_df):
    """Tiny float difference → PASS."""
    expected = sample_df["Average_income"].mean()
    tiny_off = expected + 1e-9
    result = ToolResult(
        success=True,
        tool_name="run_query",
        output={"success": True, "data": {
            "query": "SELECT AVG(Average_income) FROM df",
            "rows": [{"AVG(Average_income)": tiny_off}],
        }},
    )
    validation = Validator().validate(result, context=make_ctx(sample_df))
    assert validation.valid is True


# ── Test 4: Missing column ───────────────────────────────────────────────

def test_missing_column(sample_df):
    """Query references a non-existent column → FAIL."""
    result = ToolResult(
        success=True,
        tool_name="run_query",
        output={"success": True, "data": {
            "query": "SELECT AVG(DoesNotExist) FROM df",
            "rows": [{"AVG(DoesNotExist)": 0}],
        }},
    )
    validation = Validator().validate(result, context=make_ctx(sample_df))
    assert validation.valid is False
    assert "does not exist" in (validation.error or "")


# ── Test 5: Invalid actual value ─────────────────────────────────────────

def test_invalid_actual_value(sample_df):
    """Tool returns non-numeric → FAIL."""
    result = ToolResult(
        success=True,
        tool_name="run_query",
        output={"success": True, "data": {
            "query": "SELECT AVG(Average_income) FROM df",
            "rows": [{"AVG(Average_income)": "unknown"}],
        }},
    )
    validation = Validator().validate(result, context=make_ctx(sample_df))
    assert validation.valid is False
    assert "not numeric" in (validation.message or "")


# ── Test 6: Tool failure → skip validation ───────────────────────────────

def test_tool_failure_skips_validation():
    """A failed ToolResult (not success) is skipped, not validated."""
    result = ToolResult(
        success=False,
        tool_name="run_query",
        output=None,
        error="Some error",
        error_type=TOOL_EXECUTION_ERROR,
    )
    validation = Validator().validate(result, context=make_ctx(None))
    assert validation.valid is False
    assert validation.validator_name == "skip_failed_tool"
    assert validation.error == "Some error"


# ── Additional: no dataset ───────────────────────────────────────────────

def test_no_dataset_fails():
    result = ToolResult(
        success=True,
        tool_name="run_query",
        output={"success": True, "data": {
            "query": "SELECT AVG(Average_income) FROM df",
            "rows": [{"AVG(Average_income)": 200}],
        }},
    )
    validation = Validator().validate(result, context=ValidationContext(dataset=None))
    assert validation.valid is False
    assert "Dataset unavailable" in (validation.message or "")


# ── Additional: no aggregate → passthrough ─────────────────────────────────

def test_no_aggregate_passthrough(sample_df):
    result = ToolResult(
        success=True,
        tool_name="run_query",
        output={"success": True, "data": {
            "query": "SELECT * FROM df WHERE Population > 1000",
            "rows": [{"a": 1}],
        }},
    )
    validation = Validator().validate(result, context=make_ctx(sample_df))
    assert validation.valid is True
    assert "not applicable" in (validation.message or "")


# ── Additional: unregistered tool → passthrough ────────────────────────────

def test_unregistered_tool_passthrough():
    result = ToolResult(
        success=True,
        tool_name="load_dataset",
        output={"success": True, "data": {"row_count": 10}, "meta": {}},
    )
    validation = Validator().validate(result, context=ValidationContext())
    assert validation.valid is True
    assert validation.validator_name == "passthrough"


# ── Additional: validator does not crash ─────────────────────────────────

def test_validator_exception_caught(sample_df):
    """If a registered handler raises, validation returns a safe failure."""
    v = Validator()
    def bad_handler(tool_result, context):
        raise RuntimeError("boom")
    v.register("run_query", bad_handler)

    result = ToolResult(
        success=True,
        tool_name="run_query",
        output={"success": True, "data": {"query": "SELECT 1", "rows": [{"x": 1}]}},
    )
    validation = v.validate(result, context=make_ctx(sample_df))
    assert validation.valid is False
    assert "crashed" in (validation.message or "")
    assert validation.error == "boom"


# ── Additional: register + unregister ────────────────────────────────────

def test_register_unregister():
    v = Validator()
    def custom_handler(tool_result, context):
        return ValidationResult(True, "custom", message="custom check")
    v.register("run_query", custom_handler)

    result = ToolResult(
        success=True,
        tool_name="run_query",
        output={"success": True, "data": {"query": "SELECT 1", "rows": []}},
    )
    assert v.validate(result, context=ValidationContext()).validator_name == "custom"

    v.unregister("run_query")
    # After unregister, the default handler is gone → passthrough
    assert v.validate(result, context=ValidationContext()).validator_name == "passthrough"
