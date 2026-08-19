# Lexxer 🚧

### A Data Analyst Agent built as an Agent Harness Engineering project.

Lexxer is an experimental AI data analyst designed to explore **harness engineering** building the systems around an LLM that make an agent more reliable, observable, and capable of working through multi-step tasks.

Instead of focusing only on the model, Lexxer focuses on the environment the model operates inside: **memory, context management, tool execution, validation, tracing, evaluation, and observability.**

> **The goal isn't to build the smartest agent. It's to build a better environment for an agent to work in.**

---
## SCREENSHOT
<img width="1440" height="900" alt="Screenshot 2026-08-18 at 3 40 13 PM" src="https://github.com/user-attachments/assets/5d35ce08-2df6-4394-88c2-e4097b3f5915" />



## Why Lexxer?

A basic AI data analyst can look like:

```text
User → LLM → Answer
```

Lexxer explores what happens when we build an actual harness around that agent:

<img width="803" height="570" alt="Screenshot 2026-08-19 at 1 47 32 PM" src="https://github.com/user-attachments/assets/1326f578-a430-4b2e-adfa-19e694a8abf2" />


The architecture is intentionally being built incrementally.

---

## Current Progress

* [x] Agent loop
* [x] Dataset analysis tools
* [x] Working Memory
* [x] Context Builder
* [x] Tool Runtime
* [ ] Guardrails
* [x] Output Validation
* [x] Tracing
* [ ] Semantic Memory
* [ ] Episodic Memory
* [ ] Retrieval Gate
* [ ] Memory Consolidation
* [ ] Evaluation System
* [x] Frontend API (FastAPI layer)

---

## Core Concepts

### Agent Loop

The core execution loop allows the agent to decide when it needs a tool and continue working with the returned result.

```text
User
 ↓
LLM
 ↓
Tool Call
 ↓
Tool Execution
 ↓
Tool Result
 ↓
LLM
 ↓
Final Answer
```

---

### Working Memory

Maintains the state of the current agent session.

It can contain:

* Current task
* Conversation history
* Dataset information
* Tool results
* Intermediate analysis state

Working Memory answers:

> **"What information do I currently have?"**

---

### Context Builder

Transforms the current state into the relevant context that should be provided to the LLM.

```text
Working Memory
       ↓
Context Builder
       ↓
Relevant Context
       ↓
LLM
```

Context Builder answers:

> **"What does the agent need to know right now?"**

This separation allows the system to keep application state and LLM context management independent.

---

### Tool Runtime

The Tool Runtime acts as the execution layer between the agent and its tools.

Instead of allowing the agent to directly execute arbitrary functionality:

```text
Agent
 ↓
Tool Runtime
 ↓
Tool
 ↓
Structured Result
```

The runtime will eventually provide consistent execution, error handling, and observability for tools.

---

### Validator

The Validator independently verifies tool outputs by recomputing results from the source dataset.

For example:

```text
Agent:
Average income = $42,500

Validator:
Actual dataset value = $38,200

❌ Invalid
```

On failure, the validator surfaces a correction message back to the agent so it can retry. This reduces incorrect analytical conclusions and provides a deterministic mechanism for retrying or correcting failed operations.

See [`harness/validator.py`](harness/validator.py) for implementation details.

---

### Tracing

Tracing records what happens during an agent run — a structured history of events that the dashboard will eventually visualize.

```text
Agent Run
 ├── run_started
 ├── context_built
 ├── llm_call
 ├── tool_call → tool_completed
 ├── validation
 ├── llm_call
 ├── response_generated
 └── run_completed
```

Each event captures timestamps, durations (reused from ToolResult and Validator — no duplicate timers), and structured metadata (tool name, validator name, expected/actual values, LLM provider/model).

See the [tracing README](tracing/README.md) for details.

---

### Memory

Lexxer will eventually experiment with multiple types of memory:

```text
Memory
├── Working
├── Semantic
├── Episodic
└── Procedural
```

These will be introduced incrementally rather than all at once.

---

### Retrieval Gate

The Retrieval Gate will decide whether long-term memory is actually relevant to the current task.

```text
User Query
     ↓
Retrieval Gate
     ↓
 ┌───┴───┐
YES      NO
 ↓        ↓
Retrieve  Continue
Memory
```

This avoids blindly injecting large amounts of historical information into every agent context.

---

## Architecture Philosophy

Lexxer is heavily inspired by the idea that **agent quality is not only determined by the model.**

The surrounding system matters:

```text
Agent
  +
Tools
  +
Memory
  +
Context
  +
Runtime
  +
Validation
  +
Observability
  +
Evaluation
  =
Reliable Agent System
```

The project therefore treats the LLM as one component inside a larger engineered environment.

---

## Roadmap

### Phase 1 — Agent Core

* Agent loop
* Tool calling
* Dataset analysis

### Phase 2 — Harness Foundation

* Working Memory
* Context Builder
* Tool Runtime
* Structured tool results

### Phase 3 — Reliability

* Error handling
* Guardrails
* Output validation
* Retry mechanisms

### Phase 4 — Observability

* Execution tracing
* Agent run history
* Tool metrics
* Failure inspection

### Phase 5 — Memory

* Semantic memory
* Episodic memory
* Procedural memory
* Retrieval Gate
* Memory consolidation

### Phase 6 — Evaluation

* Analytical test cases
* Agent accuracy
* Tool-use evaluation
* Memory evaluation
* Regression testing

### Phase 7 — Dashboard

A dedicated overview dashboard for inspecting:

* Agent runs
* Tool calls
* Execution traces
* Memory
* Validation results
* Evaluation results
* Errors and failures

---

## Project Structure

```text
lexxer/
│
├── api/
│   ├── main.py        # FastAPI app + CORS
│   ├── service.py     # AgentService (orchestrates the harness)
│   ├── schemas.py     # Pydantic request/response models
│   └── routes/        # health, chat, runs, dataset endpoints
│
├── agent/
│   ├── loop.py
│   └── models.py
│
├── tracing/
│   └── tracer.py
│
├── tools/
│   ├── dataset.py
│   └── ...
│
├── memory/
│   ├── working.py
│   └── ...
│
├── harness/
│   ├── context.py
│   ├── runtime.py
│   └── validator.py
│
├── tracing/
│   └── ...
│
├── evals/
│   └── ...
│
├── dashboard/
│   └── ...
│
├── docs/
│   └── API.md
│
├── data/
│   └── sample/
│
└── README.md
```

The structure will evolve as new harness capabilities are implemented.

---

## Learning Goal

Lexxer is also a learning project.

The objective is to understand how modern agent systems are engineered beyond simply calling an LLM API.

Areas being explored include:

* Agent loops
* Tool use
* Context engineering
* Working memory
* Long-term memory
* Retrieval
* Tool execution
* Guardrails
* Verification
* Observability
* Evaluation
* Agent reliability

---

## Status

🚧 **Active development**

Lexxer is being built incrementally. New components are intentionally added one at a time so that each part of the harness can be understood, tested, and evaluated independently.

---

## Backend MVP — Complete

The core harness backend is now complete. The following components are implemented and tested:

| Component | File | Tests |
|-----------|------|-------|
| Agent Loop | `agent/loop.py` | 6 |
| Working Memory | `memory/working.py` | 19 |
| Context Builder | `harness/context.py` | 11 |
| Tool Runtime | `harness/runtime.py` | 17 |
| Validator | `harness/validator.py` | 11 |
| Tracer | `tracing/tracer.py` | 14 |

```text
                         USER
                           │
                           ▼
                  ┌─────────────────┐
                  │ Working Memory  │
                  └────────┬────────┘
                           │
                           ▼
                  ┌─────────────────┐
                  │ Context Builder │
                  └────────┬────────┘
                           │
                           ▼
                  ┌─────────────────┐
                  │   Agent Loop    │
                  └────────┬────────┘
                           │
                           ▼
                  ┌─────────────────┐
                  │  Tool Runtime   │
                  └────────┬────────┘
                           │
                           ▼
                         TOOLS
                           │
                           ▼
                     Tool Result
                           │
                           ▼
                  ┌─────────────────┐
                  │    Validator    │
                  └────────┬────────┘
                           │
                           ▼
                    Final Response

                 ┌───────────────────┐
                 │      TRACER       │
                 │  Observing the    │
                 │  entire lifecycle │
                 └───────────────────┘
```

**What's next:** Frontend dashboard to visualize runs, traces, and agent behavior using the trace data.

---

## Frontend API

Lexxer exposes a small REST API (FastAPI) so a separate frontend can consume the backend. The API sits **above** the harness — it only orchestrates the existing agent, it does not reimplement it:

```text
Frontend
   ↓
FastAPI
   ↓
AgentService
   ↓
Lexxer Harness (Working Memory → Context Builder → Agent Loop → Tool Runtime → Validator → Tracer)
```

### Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/api/health` | Liveness check |
| `POST` | `/api/chat` | Send a user query through the agent |
| `GET` | `/api/runs` | Recent run history (newest first) |
| `GET` | `/api/runs/{run_id}` | Full trace for a single run |
| `GET` | `/api/dataset` | Basic info about the loaded dataset |

See [docs/API.md](docs/API.md) for request/response schemas and examples.

### Starting the backend

```bash
source .venv/bin/activate
pip install -r requirements.txt
uvicorn api.main:app --reload --port 8000
```

The API is then available at <http://localhost:8000> (interactive docs at <http://localhost:8000/docs>).

---

## Inspiration

The architecture and ideas explored in this project are influenced by modern agent-harness approaches, including the concepts demonstrated by **Waku**.

Lexxer is an independent implementation focused on learning and experimentation rather than being a clone of Waku.
