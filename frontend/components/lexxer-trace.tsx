'use client'

import { ChevronDown, Clock3, Code2, RotateCcw } from 'lucide-react'
import { useState } from 'react'
import type { Run, TraceEvent } from '@/lib/lexxer-api'

export function LexxerTrace({ run, loading, error, onRetry }: { run?: Run | null; loading?: boolean; error?: string; onRetry?: () => void }) {
  const [open, setOpen] = useState<string | null>(null)
  const events = run?.events ?? []

  return (
    <section className="panel trace-panel">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">selected run</p>
          <h2 className="panel-title">Trace timeline</h2>
        </div>
        <div className="trace-meta"><span><Clock3 size={13} /> {run ? `${run.durationMs}ms` : '—'}</span><span className="status-dot" /> {run?.status ?? 'no run selected'}</div>
      </div>
      {loading ? <div className="empty-state">Loading trace...</div> : <>
        {error && <div className="trace-notice"><span>{error}</span><button onClick={onRetry} className="text-button"><RotateCcw size={14} /> Retry</button></div>}
        {events.length ? <div className="timeline">
          {events.map((event) => <TraceRow key={event.id} event={event} open={open === event.id} onToggle={() => setOpen(open === event.id ? null : event.id)} />)}
        </div> : <div className="empty-state">{run ? 'No trace events recorded for this run.' : 'Select a run to inspect its trace.'}</div>}
      </>}
    </section>
  )
}

function TraceRow({ event, open, onToggle }: { event: TraceEvent; open: boolean; onToggle: () => void }) {
  return <div className={`trace-row ${open ? 'is-open' : ''}`}>
    <button className="trace-row-button" onClick={onToggle} aria-expanded={open}>
      <span className="timeline-marker" />
      <span className="trace-label">{event.label}</span>
      {event.tool && <span className="tool-chip"><Code2 size={11} /> {event.tool}</span>}
      <span className="trace-time">{event.timestamp}</span>
      <span className="trace-duration">{event.durationMs}ms</span>
      <ChevronDown size={14} className={`chevron ${open ? 'rotate-180' : ''}`} />
    </button>
    {open && <div className="trace-detail"><p>{event.detail}</p>{event.metadata && <pre>{JSON.stringify(event.metadata, null, 2)}</pre>}</div>}
  </div>
}