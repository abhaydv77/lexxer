from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from tools.dataset import TOOLS


@dataclass
class ToolResult:
    """A single tool execution result stored in working memory."""

    name: str
    arguments: dict[str, Any]
    result: dict[str, Any]
    duration_ms: float | None = None

    def summarize(self) -> str:
        """Return a concise text summary suitable for inclusion in an LLM prompt."""
        success = self.result.get("success", False)
        data = self.result.get("data", {})
        meta = self.result.get("meta", {})
        dur = meta.get("duration_ms")

        parts: list[str] = []
        parts.append(f"- {self.name}({self.arguments}) → success={success}")
        if dur is not None:
            parts[-1] += f" ({dur}ms)"

        if success:
            if "row_count" in data:
                parts.append(f"  rows: {data['row_count']}")
            if "columns" in data:
                cols = ", ".join(
                    f"{c['name']}({c['dtype']})" for c in data["columns"]
                )
                parts[-1] += f"\n  columns: {cols}"
            if "rows" in data and data["rows"]:
                n = data.get("row_count", 0)
                trunc = data.get("truncated", False)
                parts.append(f"  rows: {n}" + (" (truncated)" if trunc else ""))
                parts.append(f"  preview: {data['rows'][:3]}")
        else:
            err = self.result.get("error", "")
            parts[-1] += f"\n  error: {err}"

        return "\n".join(parts)


@dataclass
class WorkingMemory:
    """
    Short-term session state for a data-analysis agent run.

    Stores the conversation messages, current task, dataset metadata,
    tool results, and arbitrary analysis state — everything needed
    during a single agent session. State is lost on process restart.
    """

    messages: list[dict[str, Any]] = field(default_factory=list)
    current_task: str | None = None
    dataset: dict[str, Any] | None = None
    dataset_schema: list[dict[str, str]] | None = None
    tool_results: list[ToolResult] = field(default_factory=list)
    analysis_state: dict[str, Any] = field(default_factory=dict)

    # ── messages ──────────────────────────────────────────────────────

    def add_message(self, role: str, content: str) -> None:
        """Append a well-formed message to the conversation history."""
        if not isinstance(role, str) or not role.strip():
            raise ValueError("role must be a non-empty string")
        if not isinstance(content, str):
            raise ValueError("content must be a string")
        self.messages.append({"role": role, "content": content})

    def get_messages(self) -> list[dict[str, Any]]:
        """Return a shallow copy of the message list."""
        return list(self.messages)

    def add_assistant_message(self, msg: dict[str, Any]) -> None:
        """Record an assistant message dict (may contain tool_calls)."""
        if not isinstance(msg, dict):
            raise ValueError("assistant message must be a dict")
        dump = {
            "role": "assistant",
            "content": msg.get("content") or "",
            "tool_calls": msg.get("tool_calls") or [],
        }
        # keep top-level keys the OpenAI/Groq client expects
        if "tool_call_id" in msg:
            dump["tool_call_id"] = msg["tool_call_id"]
        self.messages.append(dump)

    def add_tool_message(self, tool_call_id: str, content: str) -> None:
        """Record a tool-role message for a previously emitted tool_call."""
        self.messages.append({
            "role": "tool",
            "tool_call_id": tool_call_id,
            "content": content,
        })

    # ── task ──────────────────────────────────────────────────────────

    def set_task(self, task: str) -> None:
        """Set the current user task/query."""
        self.current_task = task

    def get_task(self) -> str | None:
        """Return the current task string, or None."""
        return self.current_task

    # ── dataset ───────────────────────────────────────────────────────

    def set_dataset(self, dataset_info: dict[str, Any]) -> None:
        """Store dataset metadata returned by load_dataset."""
        self.dataset = dataset_info
        # cache the column schema separately for quick access
        self.dataset_schema = dataset_info.get("columns", [])

    def get_dataset(self) -> dict[str, Any] | None:
        """Return the stored dataset metadata, or None."""
        return self.dataset

    def get_dataset_schema(self) -> list[dict[str, str]] | None:
        """Return the cached column schema, or None."""
        return self.dataset_schema

    # ── tool results ──────────────────────────────────────────────────

    def add_tool_result(
        self,
        name: str,
        arguments: dict[str, Any],
        result: dict[str, Any],
    ) -> None:
        """Record the outcome of a single tool call."""
        meta = result.get("meta", {})
        self.tool_results.append(
            ToolResult(
                name=name,
                arguments=arguments,
                result=result,
                duration_ms=meta.get("duration_ms"),
            )
        )

    def get_tool_results(self) -> list[ToolResult]:
        """Return a copy of the tool-result list."""
        return list(self.tool_results)

    def get_tool_results_summary(self) -> str:
        """Return a text digest of all tool results for prompt context."""
        if not self.tool_results:
            return "No tool results yet."
        lines = [tr.summarize() for tr in self.tool_results]
        return "\n".join(lines)

    # ── analysis state ────────────────────────────────────────────────

    def set_analysis_state(self, **kwargs: Any) -> None:
        """Update one or more keys in the analysis-state dict."""
        self.analysis_state.update(kwargs)

    def get_analysis_state(self) -> dict[str, Any]:
        """Return the full analysis-state dict."""
        return dict(self.analysis_state)

    def get(self, key: str, default: Any = None) -> Any:
        """Shorthand for reading a key from analysis_state."""
        return self.analysis_state.get(key, default)

    # ── context building ───────────────────────────────────────────────

    def build_context(self) -> str:
        """
        Build a compact prompt context from current working-memory state.

        The format is human-readable text intended to be pasted into an
        LLM system or user message.  It includes:
          - The current task
          - Dataset summary (name, row count, columns)
          - Recent tool results (summary form)
          - Any analysis-state key/value pairs
        """
        parts: list[str] = []

        if self.current_task:
            parts.append(f"Current task: {self.current_task}")

        if self.dataset:
            ds = self.dataset
            parts.append(
                f"Dataset: {ds.get('name', 'unnamed')} "
                f"({ds.get('row_count', '?')} rows)"
            )
            if self.dataset_schema:
                cols = ", ".join(
                    f"{c['name']}({c['dtype']})" for c in self.dataset_schema
                )
                parts.append(f"Schema: {cols}")

        if self.tool_results:
            parts.append("\nTool results:\n" + self.get_tool_results_summary())

        if self.analysis_state:
            parts.append("\nAnalysis state:")
            for k, v in self.analysis_state.items():
                parts.append(f"  {k}: {v}")

        return "\n".join(parts)

    # ── lifecycle ─────────────────────────────────────────────────────

    def clear(self) -> None:
        """Reset *all* state to empty defaults."""
        self.messages = []
        self.current_task = None
        self.dataset = None
        self.dataset_schema = None
        self.tool_results = []
        self.analysis_state = {}

    def is_empty(self) -> bool:
        """Return True if no state has been populated."""
        return not (
            self.messages
            or self.current_task
            or self.dataset
            or self.tool_results
            or self.analysis_state
        )
