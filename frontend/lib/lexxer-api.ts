export type RunStatus = 'completed' | 'running' | 'failed'

export type TraceEvent = {
  id: string
  label: string
  timestamp: string
  status: 'completed' | 'running' | 'failed'
  durationMs?: number
  detail?: string
  tool?: string
  metadata?: Record<string, string | number | boolean>
}

export type Run = {
  id: string
  question: string
  status: RunStatus
  createdAt: string
  durationMs: number
  score?: number
  events: TraceEvent[]
}

export type Dataset = {
  name: string
  rows: number
  columns: number
  refreshedAt?: string
}

export type Health = {
  status: string
  service: string
}

// ── Backend DTOs (snake_case, mirrors api/schemas.py) ───────────────────────

type BackendTraceEvent = {
  event_type: string
  timestamp: string
  status: string | null
  duration_ms: number | null
  metadata: Record<string, unknown>
  message: string | null
}

type BackendRunSummary = {
  run_id: string
  status: string
  started_at: string
  ended_at: string | null
  duration_ms: number | null
  query: string | null
}

type BackendRunDetail = BackendRunSummary & {
  response: string | null
  events: BackendTraceEvent[]
}

type BackendRunList = { runs: BackendRunSummary[] }

type BackendDataset = {
  name: string
  rows: number
  columns: string[]
}

type BackendChatResponse = {
  run_id: string
  message: string
  status: string
}

// ── Mapping (backend → frontend) ─────────────────────────────────────────────

const EVENT_LABELS: Record<string, string> = {
  run_started: 'run started',
  context_built: 'context built',
  llm_call: 'llm call',
  tool_call: 'tool call',
  tool_completed: 'tool completed',
  validation: 'validation',
  response_generated: 'response generated',
  run_completed: 'run completed',
  error: 'error',
}

function toRunStatus(status: string | null | undefined): RunStatus {
  if (status === 'success' || status === 'passed') return 'completed'
  if (status === 'failed' || status === 'error') return 'failed'
  return 'running'
}

function formatTime(iso: string | null): string {
  if (!iso) return '—'
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return iso
  return date.toLocaleTimeString([], { hour12: false })
}

function toTraceEvent(event: BackendTraceEvent, index: number): TraceEvent {
  const metadata = event.metadata ?? {}
  const tool = typeof metadata.tool === 'string' ? metadata.tool : undefined
  return {
    id: `${event.event_type}-${index}`,
    label: EVENT_LABELS[event.event_type] ?? event.event_type.replace(/_/g, ' '),
    timestamp: formatTime(event.timestamp),
    status: toRunStatus(event.status),
    durationMs: event.duration_ms ?? undefined,
    detail: event.message ?? undefined,
    tool,
    metadata: metadata as Record<string, string | number | boolean>,
  }
}

function toRun(summary: BackendRunSummary, events: TraceEvent[] = []): Run {
  return {
    id: summary.run_id,
    question: summary.query ?? '',
    status: toRunStatus(summary.status),
    createdAt: formatTime(summary.started_at),
    durationMs: Math.round(summary.duration_ms ?? 0),
    events,
  }
}

// ── Client ───────────────────────────────────────────────────────────────────

const baseUrl = (
  process.env.NEXT_PUBLIC_API_URL ??
  process.env.VITE_API_URL ??
  'http://localhost:8000'
).replace(/\/$/, '')

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${baseUrl}/api${path}`, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...options?.headers },
  })
  if (!response.ok) throw new Error(`Request failed: ${response.status}`)
  return response.json()
}

export async function getRuns(): Promise<Run[]> {
  const data = await request<BackendRunList>('/runs')
  return data.runs.map((run) => toRun(run))
}

export async function getDataset(): Promise<Dataset> {
  const data = await request<BackendDataset>('/dataset')
  return { name: data.name, rows: data.rows, columns: data.columns.length }
}

export async function getRun(id: string): Promise<Run> {
  const data = await request<BackendRunDetail>(`/runs/${encodeURIComponent(id)}`)
  return toRun(data, data.events.map((event, index) => toTraceEvent(event, index)))
}

export async function sendMessage(message: string): Promise<{ message: string; run_id: string }> {
  return request<BackendChatResponse>('/chat', {
    method: 'POST',
    body: JSON.stringify({ message }),
  })
}

export async function getHealth(): Promise<Health> {
  return request<Health>('/health')
}
