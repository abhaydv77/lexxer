# Agent

The agent layer for the Data Analyst Agent harness.

## Structure

- **`loop.py`** — The agent loop that connects Groq's Chat Completions API to dataset tools.

## Agent Loop

The `run_agent()` function orchestrates the LLM ↔ tools interaction:

```
User message
    ↓
WorkingMemory (messages, task, dataset, tool results)
    ↓
LLM (Groq API with tool definitions)
    ↓
Tool call → execution → result
    ↓
Result stored in WorkingMemory
    ↓
LLM continues (loop until no tool_calls)
    ↓
Final text response returned
```

### Key Components

| Component | Description |
|-----------|-------------|
| `MODEL` | `"openai/gpt-oss-20b"` — the LLM model used |
| `client` | Groq client initialized from `GROQ_API_KEY` |
| `FUNCTIONS` | Dict mapping tool names → Python function callables |
| `TOOLS_OPENAI` | Tool schema list formatted for Groq/OpenAI API |
| `SYSTEM_PROMPT` | Static system message guiding agent behavior |

### Usage

```python
from agent.loop import run_agent
from memory.working import WorkingMemory

memory = WorkingMemory()

# Each call continues the conversation with full context
response = run_agent("Load data/cities.csv", memory)
response = run_agent("What's the average income?", memory)

# Or standalone (no memory persistence)
response = run_agent("Hello")
```

### REPL

The module runs as a standalone REPL when executed directly:

```bash
python -m agent.loop
```

Each turn's conversation state is tracked in a session-scoped `WorkingMemory`.

## Design Notes

- `run_agent` accepts an optional `WorkingMemory` instance — if `None`, creates an ephemeral one
- The system prompt is only added once per memory session
- All messages, tool calls, and results are recorded in WorkingMemory
- Dataset metadata from `load_dataset` is extracted and stored automatically
- No classes needed — the loop is a pure function driven by explicit memory state
