# Harness

The harness layer of **Lexxer** — the runtime infrastructure that sits between the agent loop and the rest of the system.

The harness answers *"how do tools actually get executed, and what context does the LLM see?"* It is intentionally independent of the LLM provider, Working Memory internals, and any dashboard/frontend.

## Structure

| File | Purpose |
|------|---------|
| `context.py` | `ContextBuilder` + `BuiltContext` — transforms Working Memory state into LLM-ready context |
| `runtime.py` | `ToolRuntime` + `ToolResult` — the execution boundary that runs tools requested by the agent |

Empty placeholder files (future phases, not yet implemented):
- `guardrails.py`
- `validator.py`

---

## Context Builder (`context.py`)

The **state → context transformation layer**. It sits between Working Memory and the LLM.

```text
Working Memory   →  Context Builder  →  LLM
  (state store)      (transformation)   (consumes)
```

### The core distinction

- **Working Memory** answers: *"What information do I currently have?"*
- **Context Builder** answers: *"What information does the LLM need right now?"*

The builder reads Working Memory, composes a structured system prompt, and pairs it with the ordered conversation history. It **never mutates memory**.

### Usage

```python
from harness.context import ContextBuilder
from memory.working import WorkingMemory

builder = ContextBuilder(system_instructions="You are a data analyst agent.")
memory = WorkingMemory()

# ... populate memory (task, dataset, tool results, messages) ...

context = builder.build(memory, tools=tool_schemas)
messages = context.to_messages()   # OpenAI/Groq-format: [system, ...conversation]
```

### `BuiltContext`

A small dataclass returned by `build()`:

| Field | Type | Description |
|-------|------|-------------|
| `system_prompt` | `str` | The assembled system prompt with structured sections |
| `messages` | `list[dict]` | Ordered conversation (system messages filtered out) |

- `to_messages()` → returns `[{"role": "system", "content": system_prompt}] + messages`, ready to pass directly to a chat-completions API call.

### System prompt sections

The generated system prompt is a text block with clearly separated sections:

```text
SYSTEM INSTRUCTIONS:      the base agent instructions (never mixed into history)
CURRENT TASK:             the latest user task from Working Memory
DATASET INFORMATION:      dataset name, row count
SCHEMA:                   column name → dtype lines
AVAILABLE TOOLS:          numbered list of tool names + descriptions
RECENT TOOL RESULTS:      last 5 tool results as compact "Tool -> OK/ERROR" lines
```

Design rules followed:
- No dataset present → the dataset/schema section is simply **omitted** (never fabricated).
- Conversation is preserved in its original order and passed as `messages`, not dumped into the system prompt.
- Tool results are rendered compactly; raw huge outputs are not exposed.
- No token counting / summarization yet — that belongs to a future phase.

---

## Tool Runtime (`runtime.py`)

The **execution boundary** between the Agent Loop and individual tools.

```text
Agent Loop  →  ToolRuntime.execute()  →  Tool  →  ToolResult  →  Working Memory
```

### Separation of responsibilities

| Layer | Decides |
|-------|---------|
| **Agent** | *"I want to call this tool with these arguments."* |
| **Tool Runtime** | *"How should it execute, and what result is returned?"* |

The runtime:
1. Finds the registered tool by name
2. Validates arguments against the tool schema
3. Executes the Python function
4. Catches exceptions (never crashes the agent loop)
5. Measures execution duration
6. Returns a structured `ToolResult`

It is **stateless** with respect to conversation state — it receives `tool_name + arguments` and returns a `ToolResult`. It knows nothing about the LLM, Working Memory, or Context Builder.

### Usage

```python
from harness.runtime import ToolRuntime

runtime = ToolRuntime()
runtime.register("calculate_average", calculate_average, schema=TOOLS[0])
# or: runtime.register_all(FUNCTIONS, TOOLS)

result = runtime.execute(
    tool_name="calculate_average",
    arguments={"column": "Average_income"},
)
```

### `ToolResult`

A typed result of one tool execution:

| Field | Type | Description |
|-------|------|-------------|
| `success` | `bool` | Whether execution succeeded |
| `tool_name` | `str` | The tool that ran |
| `output` | `Any` | Return value of the tool |
| `error` | `str \| None` | Human-readable error message |
| `error_type` | `str \| None` | Categorized error (`ToolNotFound`, `InvalidArguments`, `ToolExecutionError`) |
| `duration_ms` | `float \| None` | Execution time in milliseconds (for future Tracing) |

- `as_dict()` → returns a plain dict envelope `{"success", "data", "error", "meta"}` compatible with Working Memory. If the tool already returned an envelope dict, it is passed through unchanged (duration filled in when missing).

### Error categories

| `error_type` | Trigger |
|--------------|---------|
| `ToolNotFound` | Tool name not registered |
| `InvalidArguments` | Missing required args, or arg type mismatch |
| `ToolExecutionError` | The tool function raised an exception |

The runtime **never raises** — all failures are returned as structured `ToolResult`s so the agent can decide what to do next.

### Argument validation

- If a schema is attached, `required` list and per-property `type` hints (`string`, `integer`, `number`, `boolean`) are checked.
- If no schema is attached, it falls back to the function's Python signature (required = params without defaults).
- Schemas use the Anthropic-style format from `tools/dataset.py`'s `TOOLS` list.

### Agent Loop integration

The Agent Loop owns LLM calls, tool-call detection, loop continuation, and final-answer generation. It calls the runtime for execution:

```python
exec_result = tool_runtime.execute(fn_name, args)
result = exec_result.as_dict()
memory.add_tool_result(fn_name, args, result)
```

A clear boundary for future safety mechanisms (permission/guardrail → sandbox → tool).

---

## Current architecture

```text
                    ┌──────────────────┐
                    │      User        │
                    └────────┬─────────┘
                             ↓
                    ┌──────────────────┐
                    │  Working Memory  │
                    └────────┬─────────┘
                             ↓
                    ┌──────────────────┐
                    │ Context Builder  │
                    └────────┬─────────┘
                             ↓
                    ┌──────────────────┐
                    │   Agent Loop     │
                    └────────┬─────────┘
                             ↓
                       Tool Call
                             ↓
                    ┌──────────────────┐
                    │   Tool Runtime   │
                    └────────┬─────────┘
                             ↓
                    ┌──────────────────┐
                    │      Tool        │
                    └────────┬─────────┘
                             ↓
                       ToolResult
                             ↓
                    ┌──────────────────┐
                    │  Working Memory  │
                    └──────────────────┘
```

## Design principles

- Small, typed, predictable, easy to test
- Independent from the LLM provider
- Independent from Working Memory
- Independent from any dashboard/frontend
- The Tool Runtime is usable without knowing anything about the LLM

## Future phases (not yet implemented)

The harness is designed to grow incrementally. Future layers will slot around the existing pieces:

```text
Agent
 ↓
Tool Runtime
 ↓
Permission / Guardrail   ← future
 ↓
Sandbox                  ← future
 ↓
Tool
```

Plus Tracing, Validation, and Evaluation systems — each will consume the execution metadata (`duration_ms`) the runtime already exposes.
