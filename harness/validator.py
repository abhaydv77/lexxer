"""Validator: verifies tool results independently before trusting them."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Any, Callable

import pandas as pd


@dataclass
class ValidationResult:
    """Outcome of validating a single ToolResult."""

    valid: bool
    validator_name: str
    message: str | None = None
    expected: Any = None
    actual: Any = None
    error: str | None = None


@dataclass
class ValidationContext:
    """
    Lightweight context provided by the caller (agent loop) to the
    validator.  The validator needs the source dataset to independently
    recompute expected results.
    """

    dataset: pd.DataFrame | None = None


# Maps aggregate SQL function names → pandas method names.
_AGGREGATE_MAP: dict[str, str] = {
    "AVG": "mean",
    "SUM": "sum",
    "MIN": "min",
    "MAX": "max",
    "COUNT": "count",
}

# Regex to extract  AGG(column)  or  AGG( column )
_AGG_RE = re.compile(
    r"\b(" + "|".join(_AGGREGATE_MAP) + r")\s*\(\s*\"?([A-Za-z_][A-Za-z0-9_]*)\"?\s*\)",
    re.IGNORECASE,
)


class Validator:
    """
    Verifies tool results by independently recomputing expected values.

    The validator is **stateless** — it holds no agent session data.
    It answers: *"Can I verify that this result is correct?"*

    Tool-specific validation is supported via `register(tool_name, fn)`.
    A built-in handler for `run_query` detects SQL aggregate calls
    (AVG / SUM / MIN / MAX / COUNT) and recomputes them with pandas
    against the dataset in the validation context.
    """

    def __init__(self) -> None:
        self._handlers: dict[str, Callable] = {}
        self._register_defaults()

    # ── registration ───────────────────────────────────────────────────

    def register(self, tool_name: str, handler: Callable) -> None:
        """Register a validation handler for a tool name."""
        self._handlers[tool_name] = handler

    def unregister(self, tool_name: str) -> None:
        """Remove a registered handler (restores default if any)."""
        self._handlers.pop(tool_name, None)

    # ── public API ───────────────────────────────────────────────────────

    def validate(
        self,
        tool_result: Any,
        context: ValidationContext | None = None,
    ) -> ValidationResult:
        """
        Validate a ToolResult from the Tool Runtime.

        Parameters
        ----------
        tool_result : ToolResult
            The structured result from ``ToolRuntime.execute``.
        context : ValidationContext, optional
            Provides the source dataset for recomputation.

        Returns
        -------
        ValidationResult
        """
        context = context or ValidationContext()

        # ── Test 6: failed tool execution → skip validation ──
        if not tool_result.success:
            return ValidationResult(
                valid=False,
                validator_name="skip_failed_tool",
                message="Tool execution failed; validation skipped.",
                error=tool_result.error,
            )

        # ── Dispatch to a registered or default handler ──
        handler = self._handlers.get(tool_result.tool_name)
        if handler is None:
            # No validator for this tool → treat as verified (passthrough)
            return ValidationResult(
                valid=True,
                validator_name="passthrough",
                message="No validator registered for this tool.",
            )

        try:
            return handler(tool_result, context)
        except Exception as exc:
            # Validation itself must not crash the agent.
            return ValidationResult(
                valid=False,
                validator_name="exception",
                message=f"Validator crashed: {exc}",
                error=str(exc),
            )

    # ── default handlers ─────────────────────────────────────────────────

    def _register_defaults(self) -> None:
        self.register("run_query", self._validate_run_query)

    def _validate_run_query(
        self,
        tool_result: Any,
        context: ValidationContext,
    ) -> ValidationResult:
        """
        Validate a run_query tool result by recomputing aggregates.

        Detects SQL aggregates (AVG/SUM/MIN/MAX/COUNT) in the query,
        recomputes the same value via pandas, and compares.
        """
        output = tool_result.output
        if not isinstance(output, dict):
            return ValidationResult(
                valid=False,
                validator_name="run_query_validator",
                message="Unexpected tool result format.",
                error="Tool result is not a dict.",
            )

        data = output.get("data", {})
        query: str = data.get("query", "")
        rows: list = data.get("rows", [])

        match = _AGG_RE.search(query)
        if not match:
            # No aggregate detected → cannot deterministically verify.
            return ValidationResult(
                valid=True,
                validator_name="run_query_validator",
                message="No aggregate detected; verification not applicable.",
            )

        agg_func = match.group(1).upper()
        column = match.group(2)

        df = context.dataset
        if df is None:
            return ValidationResult(
                valid=False,
                validator_name="run_query_validator",
                message="Dataset unavailable for validation.",
                error=f"Cannot verify {agg_func}({column}) without a dataset.",
            )

        if column not in df.columns:
            return ValidationResult(
                valid=False,
                validator_name="run_query_validator",
                message=f"Column '{column}' does not exist in the dataset.",
                error=f"Column '{column}' does not exist.",
            )

        pandas_method = _AGGREGATE_MAP[agg_func]
        series = pd.to_numeric(df[column], errors="coerce").dropna()
        expected = getattr(series, pandas_method)()

        # Extract the actual numeric value from the query result row(s).
        actual = _extract_actual(rows)

        if actual is None:
            return ValidationResult(
                valid=False,
                validator_name="run_query_validator",
                message="Could not extract any value from query results.",
                error="No result found in tool output.",
            )

        if not isinstance(actual, (int, float)) or isinstance(actual, bool):
            return ValidationResult(
                valid=False,
                validator_name="run_query_validator",
                message="Tool result is not numeric.",
                error=f"Expected numeric result, got '{actual}' ({type(actual).__name__}).",
            )

        if math.isclose(float(actual), float(expected), rel_tol=1e-6, abs_tol=1e-6):
            return ValidationResult(
                valid=True,
                validator_name="run_query_validator",
                message=f"{agg_func}({column}) verified.",
                expected=expected,
                actual=actual,
            )

        return ValidationResult(
            valid=False,
            validator_name="run_query_validator",
            message=f"{agg_func}({column}) did not match independently computed value.",
            expected=expected,
            actual=actual,
            error=f"Expected {expected}, got {actual}.",
        )


def _extract_actual(rows: list) -> Any:
    """Pull the first scalar value from a list of result-row dicts."""
    for row in rows:
        if isinstance(row, dict):
            for val in row.values():
                if val is not None:
                    return val
        elif row is not None:
            return row
    return None
