"""Tool Runtime: the execution boundary between the Agent Loop and tools."""

from __future__ import annotations

import inspect
import time
from dataclasses import dataclass, field
from typing import Any, Callable

# Structured error categories returned by the runtime.
TOOL_NOT_FOUND = "ToolNotFound"
INVALID_ARGUMENTS = "InvalidArguments"
TOOL_EXECUTION_ERROR = "ToolExecutionError"


@dataclass
class ToolResult:
    """A typed result of one tool execution requested by the agent."""

    success: bool
    tool_name: str
    output: Any = None
    error: str | None = None
    error_type: str | None = None
    duration_ms: float | None = None

    def as_dict(self) -> dict[str, Any]:
        """Return a plain dict envelope compatible with Working Memory."""
        if isinstance(self.output, dict) and "success" in self.output:
            # The tool already returned an envelope (e.g. dataset tools);
            # pass it through, only filling in duration when absent.
            envelope = dict(self.output)
            meta = dict(envelope.setdefault("meta", {}))
            if meta.get("duration_ms") is None and self.duration_ms is not None:
                meta["duration_ms"] = self.duration_ms
            envelope["meta"] = meta
            return envelope
        return {
            "success": self.success,
            "data": self.output,
            "error": self.error,
            "meta": {"duration_ms": self.duration_ms},
        }


@dataclass
class RegisteredTool:
    """Internal registry entry pairing a callable with its schema."""

    function: Callable[..., Any]
    schema: dict[str, Any] | None = None


class ToolRuntime:
    """
    Executes tools requested by the agent.

    Responsibilities:
      - find a registered tool by name
      - validate its arguments against the tool schema
      - execute the tool function
      - catch exceptions and return structured failures
      - measure execution time

    The runtime is intentionally stateless with respect to agent
    conversation state: it receives a tool name + arguments and returns
    a structured ``ToolResult``. It knows nothing about the LLM, Working
    Memory, or the Context Builder.
    """

    def __init__(self) -> None:
        self._tools: dict[str, RegisteredTool] = {}

    # ── registration ───────────────────────────────────────────────────

    def register(
        self,
        name: str,
        function: Callable[..., Any],
        schema: dict[str, Any] | None = None,
    ) -> None:
        """Register a callable tool under *name*, optionally with a schema."""
        if not isinstance(name, str) or not name.strip():
            raise ValueError("tool name must be a non-empty string")
        if not callable(function):
            raise TypeError(f"tool '{name}' must be callable")
        self._tools[name] = RegisteredTool(function=function, schema=schema)

    def register_all(
        self,
        functions: dict[str, Callable[..., Any]],
        schemas: list[dict[str, Any]] | None = None,
    ) -> None:
        """Register several tools at once.

        *functions* maps tool name -> callable. If *schemas* is given,
        each entry's ``name`` is matched against *functions* to attach
        its tool schema for argument validation.
        """
        schema_by_name = {s.get("name"): s for s in (schemas or [])}
        for name, func in functions.items():
            self.register(name, func, schema=schema_by_name.get(name))

    def unregister(self, name: str) -> None:
        """Remove a tool from the registry."""
        self._tools.pop(name, None)

    def has_tool(self, name: str) -> bool:
        """Return True if a tool is registered."""
        return name in self._tools

    def tool_names(self) -> list[str]:
        """Return the names of all registered tools."""
        return sorted(self._tools.keys())

    # ── execution ──────────────────────────────────────────────────────

    def execute(
        self,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
    ) -> ToolResult:
        """
        Execute a registered tool and return a structured ToolResult.

        Never raises: lookup failures, invalid arguments, and tool
        exceptions are all captured and returned as failures.
        """
        start = time.perf_counter()
        args = arguments if isinstance(arguments, dict) else {}

        # 1. lookup
        registered = self._tools.get(tool_name)
        if registered is None:
            return self._fail(
                tool_name,
                TOOL_NOT_FOUND,
                f"Tool '{tool_name}' is not registered.",
                start,
            )

        # 2. Argument validation against the schema
        invalid = self._validate_arguments(registered, args)
        if invalid:
            return self._fail(
                tool_name,
                INVALID_ARGUMENTS,
                f"Invalid arguments for '{tool_name}': {invalid}",
                start,
            )

        # 3. Execute the tool
        try:
            output = registered.function(**args)
            duration_ms = self._elapsed(start)
            return ToolResult(
                success=True,
                tool_name=tool_name,
                output=output,
                duration_ms=duration_ms,
            )
        except Exception as exc:
            duration_ms = self._elapsed(start)
            return ToolResult(
                success=False,
                tool_name=tool_name,
                output=None,
                error=str(exc),
                error_type=TOOL_EXECUTION_ERROR,
                duration_ms=duration_ms,
            )

    # ── internals ──────────────────────────────────────────────────────

    @staticmethod
    def _elapsed(start: float) -> float:
        return round((time.perf_counter() - start) * 1000, 2)

    @staticmethod
    def _fail(
        tool_name: str,
        error_type: str,
        error: str,
        start: float,
    ) -> ToolResult:
        return ToolResult(
            success=False,
            tool_name=tool_name,
            output=None,
            error=error,
            error_type=error_type,
            duration_ms=ToolRuntime._elapsed(start),
        )

    def _validate_arguments(
        self,
        registered: RegisteredTool,
        args: dict[str, Any],
    ) -> list[str]:
        """Return a list of validation problems (empty = valid)."""
        problems: list[str] = []

        schema = registered.schema
        if schema is None:
            # No schema: fall back to the function's parameter names.
            try:
                sig = inspect.signature(registered.function)
                params = sig.parameters
                if not params:
                    return problems
                if any(p.kind != inspect.Parameter.POSITIONAL_OR_KEYWORD for p in params.values()):
                    return problems
                required = [
                    name
                    for name, p in params.items()
                    if p.default is inspect.Parameter.empty
                ]
                return self._check_required(required, args)
            except (ValueError, TypeError):
                return problems

        required = schema.get("input_schema", {}).get("required", [])
        problems += self._check_required(required, args)

        properties = schema.get("input_schema", {}).get("properties", {})
        for name, arg in args.items():
            spec = properties.get(name)
            if spec is None:
                continue
            expected = spec.get("type")
            if expected == "string" and not isinstance(arg, str):
                problems.append(f"'{name}' must be a string")
            elif expected == "integer" and not isinstance(arg, int):
                problems.append(f"'{name}' must be an integer")
            elif expected == "number" and not isinstance(arg, (int, float)):
                problems.append(f"'{name}' must be a number")
            elif expected == "boolean" and not isinstance(arg, bool):
                problems.append(f"'{name}' must be a boolean")

        return problems

    @staticmethod
    def _check_required(
        required: list[str],
        args: dict[str, Any],
    ) -> list[str]:
        missing = [name for name in required if name not in args]
        return [f"missing required argument '{name}'" for name in missing]