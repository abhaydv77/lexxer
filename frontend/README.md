# Lexxer Frontend

The Lexxer observability dashboard — a Next.js (App Router) client for the
Lexxer Data Analyst Agent backend. It displays live agent runs, trace
timelines, dataset info, and a chat interface connected to the FastAPI API.

## Stack

- Next.js 16 (Turbopack) / React 19
- Tailwind CSS v4
- TypeScript

## Getting started

```bash
cd frontend
npm install
npm run dev
```

Open <http://localhost:3000>.

## Connecting to the backend

The frontend reads the backend URL from an environment variable, falling
back to `http://localhost:8000`:

| Env var | Notes |
|---------|-------|
| `NEXT_PUBLIC_API_URL` | Standard Next.js client-side env var. |
| `VITE_API_URL` | Also supported by the API client for non-Next.js setups. |

Create `frontend/.env.local` to override the default:

```
NEXT_PUBLIC_API_URL=http://localhost:8000
```

Backend start (from the repo root):

```bash
source .venv/bin/activate
uvicorn api.main:app --reload --port 8000
```

> Next.js only inlines `NEXT_PUBLIC_`-prefixed env vars into the browser
> bundle; `VITE_API_URL` will not be picked up unless it is prefixed with
> `NEXT_PUBLIC_`.

## API surface

The client in `lib/lexxer-api.ts` maps the backend DTOs to frontend types:

| Endpoint | Purpose | Frontend usage |
|----------|---------|----------------|
| `GET /api/health` | Liveness check | Health badge in dashboard |
| `POST /api/chat` | Send a user query through the agent | `LexxerChat` |
| `GET /api/runs` | Recent run history (newest first) | `Recent runs` panel |
| `GET /api/runs/{run_id}` | Full trace for a single run | `Trace timeline` panel |
| `GET /api/dataset` | Loaded dataset metadata | `Dataset` panel |

## Scripts

| Command | Description |
|---------|-------------|
| `npm run dev` | Start the dev server |
| `npm run build` | Production build |
| `npm run start` | Serve the production build |
| `npm run lint` | Run ESLint |

## Project structure

```text
frontend/
├── app/            # App Router pages and layout
├── components/     # Dashboard, chat, trace, and UI components
├── hooks/          # Shared React hooks
├── lib/
│   ├── lexxer-api.ts   # Backend API client + DTO mapping
│   └── utils.ts
├── styles/         # Global CSS
└── public/         # Static assets
```