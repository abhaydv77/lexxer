# Lexxer 🚧

### A Data Analyst Agent built as an Agent Harness Engineering project.

Lexxer is an experimental AI data analyst designed to explore **harness engineering** building the systems around an LLM that make an agent more reliable, observable, and capable of working through multi-step tasks.

Instead of focusing only on the model, Lexxer focuses on the environment the model operates inside: **memory, context management, tool execution, validation, tracing, evaluation, and observability.**

> **The goal isn't to build the smartest agent. It's to build a better environment for an agent to work in.**

---

## Why Lexxer?

A basic AI data analyst can look like:

```text
User → LLM → Answer
```

Lexxer explores what happens when we build an actual harness around that agent:

```text
                      ┌──────────────────┐
                      │      User        │
                      └────────┬─────────┘
                              │
                              ▼
                      ┌──────────────────┐
                      │  Working Memory  │
                      └────────┬─────────┘
                              │
                              ▼
                      ┌──────────────────┐
                      │ Context Builder  │
                      └────────┬─────────┘
                              │
                              ▼
                      ┌──────────────────┐
                      │      Agent       │
                      └────────┬─────────┘
                              │
                              ▼
                      ┌──────────────────┐
                      │   Tool Runtime   │
                      └────────┬─────────┘
                              │
                    ┌─────────────┼─────────────┐
                    ▼             ▼             ▼
                 Dataset       Python        Charts
                   Tool          Tool          Tool
                     │             │             │
                     └─────────────┼─────────────┘
                              │
                              ▼
                      ┌──────────────────┐
                      │    Validator     │
                      └────────┬─────────┘
                              │
                              ▼
                          Response
```

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
* [ ] Tracing
* [ ] Semantic Memory
* [ ] Episodic Memory
* [ ] Retrieval Gate
* [ ] Memory Consolidation
* [ ] Evaluation System
* [ ] Overview Dashboard

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

Tracing will record the agent's execution lifecycle:

```text
Run
 ├── Context created
 ├── LLM call
 ├── Tool call
 ├── Tool result
 ├── Validation
 └── Final response
```

This will eventually power the Lexxer overview dashboard and make agent behavior easier to inspect and debug.

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
├── agent/
│   ├── loop.py
│   └── models.py
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

## Inspiration

The architecture and ideas explored in this project are influenced by modern agent-harness approaches, including the concepts demonstrated by **Waku**.

Lexxer is an independent implementation focused on learning and experimentation rather than being a clone of Waku.
