# Lexxer API

REST API that exposes the Lexxer Data Analyst Agent harness to a separate frontend.

The API is a thin layer above the existing agent architecture:

```text
Frontend
   ↓
FastAPI   (this API)
   ↓
AgentService
   ↓
Lexxer Harness
   ├── Working Memory
   ├── Context Builder
   ├── Agent Loop
   ├── Tool Runtime
   ├── Validator
   └── Tracer
```

No agent logic lives in the route handlers — the API only orchestrates the existing harness.

## Base URL

```text
http://localhost:8000
```

## Conventions

- All JSON fields are `snake_case`.
- Response fields are always present (nullable where the value may legitimately be absent) so the frontend never has to guess field names.
- Timestamps are ISO 8601 UTC strings.
- Errors use the standard FastAPI shape: `{"detail": "..."}` with an appropriate HTTP status code.

---

## GET /api/health

**Purpose:** Liveness check for the backend.

**Response — 200:**

```json
{
  "status": "ok",
  "service": "lexxer"
}
```

---

## POST /api/chat

**Purpose:** Send a user query through the Data Analyst Agent. The agent may call tools (via the Tool Runtime), tool results are validated, and everything is recorded in the trace. Returns the final response plus a `run_id` that links to the run's trace.

**Request body:**

```json
{
  "message": "Show me the average of Average_income"
}
```

**Response — 200 (success):**

```json
{
  "run_id": "9f1b3a4e-5c2d-4e1f-8a9b-0c1d2e3f4a5b",
  "message": "The average Average_income is 38,200.",
  "status": "success"
}
```

**Response — 200 (agent failed):** the request was handled but the agent run failed. Details stay server-side in the trace; the client only sees a generic message.

```json
{
  "run_id": "9f1b3a4e-5c2d-4e1f-8a9b-0c1d2e3f4a5b",
  "status": "failed",
  "message": "Agent execution failed."
}
```

| Field | Type | Notes |
|-------|------|-------|
| `run_id` | string (uuid) | Identifies the run; query `GET /api/runs/{run_id}` for its trace. |
| `message` | string | The agent's final answer, or a generic failure message. |
| `status` | string | `"success"` or `"failed"`. |

**Validation:** `message` must be a non-empty string (422 otherwise).

---

## GET /api/runs

**Purpose:** List recent agent runs, newest first.

**Query parameters:**

| Param | Default | Notes |
|-------|---------|-------|
| `limit` | `20` | Max runs to return (`1`–`100`). |

**Response — 200:**

```json
{
  "runs": [
    {
      "run_id": "9f1b3a4e-5c2d-4e1f-8a9b-0c1d2e3f4a5b",
      "status": "success",
      "started_at": "2026-08-17T12:34:56.789Z",
      "ended_at": "2026-08-17T12:34:58.629Z",
      "duration_ms": 1840.0,
      "query": "Show me the average of Average_income"
    }
  ]
}
```

| Field | Type | Notes |
|-------|------|-------|
| `run_id` | string | Unique run identifier. |
| `status` | string | `"success"`, `"failed"`, or `"running"`. |
| `started_at` | string | ISO 8601 UTC. |
| `ended_at` | string \| null | ISO 8601 UTC; null while running. |
| `duration_ms` | number \| null | Total run duration; null while running. |
| `query` | string \| null | The original user query. |

---

## GET /api/runs/{run_id}

**Purpose:** Full details and trace for a single run. The trace is a structured, in-memory history of events emitted by the harness (context building, LLM calls, tool calls, validation, response generation).

**Path parameters:**

| Param | Type | Notes |
|-------|------|-------|
| `run_id` | string | Run id returned by `POST /api/chat`. |

**Response — 200:**

```json
{
  "run_id": "9f1b3a4e-5c2d-4e1f-8a9b-0c1d2e3f4a5b",
  "status": "success",
  "query": "Show me the average of Average_income",
  "response": "The average income is 38,200.",
  "started_at": "2026-08-17T12:34:56.789Z",
  "ended_at": "2026-08-17T12:34:58.629Z",
  "duration_ms": 1840.0,
  "events": [
    {
      "event_type": "run_started",
      "timestamp": "2026-08-17T12:34:56.789Z",
      "status": "running",
      "duration_ms": null,
      "metadata": { "run_id": "9f1b3a4e-..." },
      "message": null
    },
    {
      "event_type": "context_built",
      "timestamp": "2026-08-17T12:34:56.812Z",
      "status": null,
      "duration_ms": null,
      "metadata": { "message_count": 4, "tool_count": 3, "dataset_available": true },
      "message": null
    },
    {
      "event_type": "llm_call",
      "timestamp": "2026-08-17T12:34:56.900Z",
      "status": "success",
      "duration_ms": 890.0,
      "metadata": { "provider": "groq", "model": "openai/gpt-oss-20b" },
      "message": null
    },
    {
      "event_type": "tool_call",
      "timestamp": "2026-08-17T12:34:57.010Z",
      "status": null,
      "duration_ms": null,
      "metadata": { "tool": "run_query", "arguments": { "query": "SELECT AVG(Average_income) FROM df" } },
      "message": null
    },
    {
      "event_type": "tool_completed",
      "timestamp": "2026-08-17T12:34:57.130Z",
      "status": "success",
      "duration_ms": 120.0,
      "metadata": { "tool": "run_query", "success": true, "error_type": null },
      "message": null
    },
    {
      "event_type": "validation",
      "timestamp": "2026-08-17T12:34:57.140Z",
      "status": "passed",
      "duration_ms": null,
      "metadata": { "validator": "run_query_validator", "valid": true, "expected": 38200.0, "actual": 38200.0 },
      "message": null
    },
    {
      "event_type": "response_generated",
      "timestamp": "2026-08-17T12:34:58.600Z",
      "status": null,
      "duration_ms": null,
      "metadata": { "length": 29 },
      "message": null
    },
    {
      "event_type": "run_completed",
      "timestamp": "2026-08-17T12:34:58.629Z",
      "status": "success",
      "duration_ms": 1840.0,
      "metadata": { "run_id": "9f1b3a4e-...", "status": "success" },
      "message": null
    }
  ]
}
```

**Event types** (in order of a typical successful run):

| `event_type` | Meaning | Typical `metadata` |
|--------------|---------|--------------------|
| `run_started` | Run began | `run_id` |
| `context_built` | ContextBuilder finished | `message_count`, `tool_count`, `dataset_available` |
| `llm_call` | LLM request emitted | `provider`, `model` |
| `tool_call` | Tool invoked by agent | `tool`, `arguments` |
| `tool_completed` | Tool finished | `tool`, `success`, `error_type` |
| `validation` | Validator ran on tool result | `validator`, `valid`, `expected`, `actual` |
| `response_generated` | Final answer produced | `length` |
| `run_completed` | Run finalized | `run_id`, `status` |
| `error` | Exception caught (failed runs) | `error_type`, `message` |

**Response — 404 (unknown run):**

```json
{
  "detail": "Run not found"
}
```

---

## GET /api/dataset

**Purpose:** Basic metadata about the dataset currently loaded into the agent. Only names, row count, and column names — the full dataset is intentionally not exposed.

**Response — 200:**

```json
{
  "name": "cities.csv",
  "rows": 10,
  "columns": [
    "City",
    "Country",
    "Population",
    "Area_km2",
    "Urban_density",
    "Tourism_index",
    "Average_income",
    "Cost_of_living_index",
    "Weather_zone"
  ]
}
```

**Response — 404 (no dataset loaded):**

```json
{
  "detail": "No dataset loaded"
}
```

---

## CORS

CORS is configured to allow local frontend origins during development
(`http://localhost:3000`, `http://localhost:5173` and their `127.0.0.1`
variants). To change the allow-list, edit `api/config.py` or set the
`LEXXER_CORS_ORIGINS` environment variable (comma-separated):

```bash
export LEXXER_CORS_ORIGINS=http://localhost:5173,http://localhost:3000
```

## Configuration

| Env var | Default | Purpose |
|---------|---------|---------|
| `LEXXER_CORS_ORIGINS` | localhost dev origins | Comma-separated CORS allow-list. |
| `LEXXER_DATASET` | `data/cities.csv` | Dataset pre-loaded into the agent at startup. |