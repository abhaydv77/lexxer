# Lexxer API

FastAPI layer that exposes the Lexxer Data Analyst Agent harness to the
frontend. It is a thin orchestration layer — **no agent logic lives in the
route handlers**:

```text
Frontend → FastAPI → AgentService → Lexxer Harness
  (Working Memory → Context Builder → Agent Loop → Tool Runtime → Validator → Tracer)
```

## Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/api/health` | Liveness check |
| `POST` | `/api/chat` | Send a user query through the agent |
| `GET` | `/api/runs` | Recent run history (newest first) |
| `GET` | `/api/runs/{run_id}` | Full trace for a single run |
| `GET` | `/api/dataset` | Basic info about the loaded dataset |

Interactive docs are available at <http://localhost:8000/docs> once the
server is running.

## Getting started

From the repo root:

```bash
source .venv/bin/activate
pip install -r requirements.txt
uvicorn api.main:app --reload --port 8000
```

The API is then available at <http://localhost:8000>.

## Running tests

```bash
source .venv/bin/activate
python -m pytest tests/test_api.py
```

The Groq client is mocked in the tests; the rest of the harness runs for real.

## Environment variables

| Env var | Default | Purpose |
|---------|---------|---------|
| `GROQ_API_KEY` | — (required) | API key for the agent's LLM provider (loaded from the root `.env`). |
| `LEXXER_CORS_ORIGINS` | `localhost:3000`, `localhost:5173` (+ `127.0.0.1` variants) | Comma-separated CORS allow-list. |
| `LEXXER_DATASET` | `data/cities.csv` | Dataset pre-loaded into the agent at startup. |

## CORS

CORS is configured in `config.py` and defaults to common local development
origins (`http://localhost:3000`, `http://localhost:5173` and their
`127.0.0.1` variants). Override at runtime with `LEXXER_CORS_ORIGINS`:

```bash
export LEXXER_CORS_ORIGINS=http://localhost:5173,http://localhost:3000
```

## Project structure

```text
api/
├── main.py        # FastAPI app + CORS + lifespan (shared AgentService)
├── config.py      # CORS origins / settings
├── schemas.py     # Pydantic request/response models (snake_case)
├── service.py     # AgentService: orchestrates the harness, keeps run history
└── routes/        # health, chat, runs, dataset handlers
```

## Conventions

- All JSON fields are `snake_case`; response fields are always present
  (nullable where the value may legitimately be absent).
- Timestamps are ISO 8601 UTC strings.
- Errors use the standard FastAPI shape: `{"detail": "..."}` with an
  appropriate HTTP status code.

See [docs/API.md](../docs/API.md) for full request/response schemas and
examples.