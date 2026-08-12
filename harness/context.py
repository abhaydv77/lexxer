from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from tools.dataset import TOOLS

DEFAULT_SYSTEM_INSTRUCTIONS = (
    "You are a data analyst agent.\n"
    "Use the provided dataset for numerical claims.\n"
    "Do not invent numerical results.\n"
    "Use tools when calculation is required."
)


@dataclass
class BuiltContext:
    """The final, LLM-ready context assembled by the ContextBuilder."""

    system_prompt: str
    messages: list[dict[str, Any]] = field(default_factory=list)

    def to_messages(self) -> list[dict[str, Any]]:
        """Return messages in OpenAI/Groq format, system prompt first."""
        return [{"role": "system", "content": self.system_prompt}] + self.messages


class ContextBuilder:
    """
    Transform WorkingMemory state into the structured context the LLM needs.

    Working Memory answers:   "What information do I currently have?"
    Context Builder answers:  "What information does the LLM need right now?"

    The builder composes a system prompt from the current task, dataset
    information, available tools, and recent tool results, then pairs it
    with the ordered conversation history. It never mutates memory.
    """

    def __init__(self, system_instructions: str | None = None):
        self.system_instructions = system_instructions or DEFAULT_SYSTEM_INSTRUCTIONS

    def build(
        self,
        memory,
        tools: list[dict[str, Any]] | None = None,
    ) -> BuiltContext:
        """
        Construct LLM-ready context from a WorkingMemory instance.

        Parameters
        ----------
        memory : WorkingMemory
            The session state store.
        tools : list[dict], optional
            Tool schemas (Anthropic-style, from tools.dataset.TOOLS).
            Defaults to the dataset toolkit tools.

        Returns
        -------
        BuiltContext
            A system prompt plus the ordered conversation messages.
        """
        tools = tools or TOOLS

        system_prompt = self._build_system_prompt(memory, tools)
        conversation = [
            m for m in memory.get_messages() if m.get("role") != "system"
        ]
        return BuiltContext(system_prompt=system_prompt, messages=conversation)

    # ── system prompt construction ─────────────────────────────────────

    def _build_system_prompt(self, memory, tools: list[dict[str, Any]]) -> str:
        parts: list[str] = []

        parts.append("SYSTEM INSTRUCTIONS:")
        parts.append(self.system_instructions)

        task = memory.get_task()
        if task:
            parts.append("\nCURRENT TASK:")
            parts.append(task)

        dataset = memory.get_dataset()
        if dataset:
            parts.append("\nDATASET INFORMATION:")
            parts.append(self._format_dataset(dataset))
            schema = memory.get_dataset_schema()
            if schema:
                parts.append("SCHEMA:")
                for col in schema:
                    parts.append(f"  {col.get('name')}: {col.get('dtype')}")

        parts.append("\nAVAILABLE TOOLS:")
        parts.append(self._format_tools(tools))

        tool_results = memory.get_tool_results()
        if tool_results:
            parts.append("\nRECENT TOOL RESULTS:")
            for tr in tool_results[-5:]:
                parts.append(self._format_tool_result(tr))
        else:
            parts.append("\nRECENT TOOL RESULTS: None")

        return "\n".join(parts)

    # ── formatters ─────────────────────────────────────────────────────

    @staticmethod
    def _format_dataset(dataset: dict[str, Any]) -> str:
        name = dataset.get("name") or dataset.get("sources") or "unknown"
        row_count = dataset.get("row_count")
        if row_count is not None:
            return f"Dataset: {name} ({row_count} rows)"
        return f"Dataset: {name}"

    @staticmethod
    def _format_tools(tools: list[dict[str, Any]]) -> str:
        if not tools:
            return "  No tools available."
        lines = []
        for i, t in enumerate(tools, 1):
            name = t.get("name", "?")
            desc = t.get("description", "")
            lines.append(f"  {i}. {name}")
            if desc:
                lines.append(f"     Description: {desc}")
        return "\n".join(lines)

    @staticmethod
    def _format_tool_result(tr) -> str:
        result = tr.result
        status = "OK" if result.get("success") else "ERROR"
        line = f"  - {tr.name} -> {status}"
        if not result.get("success"):
            error = result.get("error", "unknown error")
            line += f" ({error})"
        else:
            data = result.get("data", {})
            if "row_count" in data:
                line += f" | rows: {data['row_count']}"
            elif data:
                summary = str(data)[:120]
                line += f" | {summary}"
        return line
