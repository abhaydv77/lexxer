# Memory

Short-term state management for the Data Analyst Agent harness.

## Structure

- **`working.py`** — `WorkingMemory` class and `ToolResult` dataclass for session-scoped state.

## WorkingMemory

A `@dataclass` that holds everything the agent needs during a single session:

| Field | Type | Description |
|-------|------|-------------|
| `messages` | `list[dict]` | OpenAI-format conversation messages |
| `current_task` | `str \| None` | Latest user query |
| `dataset` | `dict \| None` | Dataset metadata from `load_dataset` |
| `dataset_schema` | `list[dict] \| None` | Column schema cache |
| `tool_results` | `list[ToolResult]` | Recorded tool call outcomes |
| `analysis_state` | `dict` | Arbitrary intermediate analysis state |

### Key Methods

```python
from memory.working import WorkingMemory

mem = WorkingMemory()

# Messages
mem.add_message("user", "Load data.csv")
mem.get_messages()          # → copy of message list

# Task
mem.set_task("Find average income")
mem.get_task()              # → "Find average income"

# Dataset
mem.set_dataset({"name": "data.csv", "row_count": 10})
mem.get_dataset()           # → dict
mem.get_dataset_schema()    # → column list

# Tool results
mem.add_tool_result("run_query", {"query": "SELECT..."}, {"success": True, ...})
mem.get_tool_results()      # → list[ToolResult]
mem.get_tool_results_summary()  # → text digest for prompts

# Analysis state
mem.set_analysis_state(last_column="income", threshold=50000)
mem.get_analysis_state()    # → dict
mem.get("last_column")      # → "income"

# Context building
mem.build_context()         # → compact text for LLM prompting

# Lifecycle
mem.clear()                 # reset all state
mem.is_empty()              # → bool
```

## Design Notes

- **No global state** — `WorkingMemory` instances are created per-session
- **Mutable defaults safe** — uses `field(default_factory=list)` etc.
- **Defensive** — validates message roles/content, returns copies from getters
- **Intentionally simple** — no long-term/semantic/vector memory yet

## Future Plans

This module is designed to grow incrementally:

```
Working Memory   ← current (this file)
Semantic Memory  ← planned
Episodic Memory  ← planned
Procedural Memory ← planned
```
