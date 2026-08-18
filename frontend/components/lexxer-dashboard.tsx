'use client'

import { Activity, BarChart3, Database, Gauge, Layers3, RefreshCw, ShieldCheck, Timer, WandSparkles } from 'lucide-react'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { getDataset, getHealth, getRun, getRuns, type Dataset, type Run } from '@/lib/lexxer-api'
import { LexxerArchitecture } from '@/components/lexxer-architecture'
import { LexxerChat } from '@/components/lexxer-chat'
import { LexxerTrace } from '@/components/lexxer-trace'

type HealthState = 'checking' | 'ok' | 'error'

export function LexxerDashboard() {
  const [runs, setRuns] = useState<Run[]>([])
  const [selected, setSelected] = useState<Run | null>(null)
  const [dataset, setDataset] = useState<Dataset | null>(null)
  const [health, setHealth] = useState<HealthState>('checking')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const loadDashboard = useCallback(async () => {
    setLoading(true)
    setError('')
    const [runsResult, datasetResult, healthResult] = await Promise.allSettled([getRuns(), getDataset(), getHealth()])
    if (runsResult.status === 'fulfilled') {
      const nextRuns = runsResult.value
      setRuns(nextRuns)
      setSelected((current) => (current && nextRuns.some((run) => run.id === current.id) ? current : nextRuns[0] ?? null))
    } else {
      setError('Unable to load run history. Is the backend running?')
    }
    if (datasetResult.status === 'fulfilled') setDataset(datasetResult.value)
    setHealth(healthResult.status === 'fulfilled' ? 'ok' : 'error')
    setLoading(false)
  }, [])

  useEffect(() => { loadDashboard() }, [loadDashboard])

  async function selectRun(run: Run) {
    setSelected(run)
    setError('')
    try {
      setSelected(await getRun(run.id))
    } catch {
      setError(`Could not load details for run ${run.id}.`)
    }
  }

  const successRate = useMemo(() => `${Math.round((runs.filter((run) => run.status === 'completed').length / Math.max(runs.length, 1)) * 100)}%`, [runs])
  const avgLatency = useMemo(() => {
    if (!runs.length) return '—'
    const total = runs.reduce((sum, run) => sum + run.durationMs, 0)
    return `${(total / runs.length / 1000).toFixed(2)}s`
  }, [runs])
  const healthLabel = health === 'ok' ? 'backend connected' : health === 'error' ? 'backend unavailable' : 'checking backend…'

  return <main className="app-shell">
    <header className="topbar"><div className="wordmark"><span className="wordmark-symbol">⌁</span><span>lexxer</span><span className="wordmark-beta">beta</span></div><div className="workspace-label"><span className="workspace-dot" /> revenue analyst <span className="slash">/</span> production</div><div className="top-actions"><button className="top-action" onClick={loadDashboard}><RefreshCw size={14} className={loading ? 'spin' : ''} /> sync</button><div className="avatar">AD</div></div></header>
    <div className="app-content">
      <div className="dashboard-column">
        <div className="page-intro"><div><p className="eyebrow">observability workspace</p><h1>See what your agents <em>actually</em> did.</h1><p className="intro-copy">Trace every decision, tool call, and validation step across your production harness.</p></div><div className="health-badge"><span className="status-dot" /> {healthLabel}</div></div>
        <div className="stats-grid"><Stat icon={Activity} label="recent runs" value={String(runs.length)} /><Stat icon={Gauge} label="success rate" value={successRate} /><Stat icon={Timer} label="avg latency" value={avgLatency} /><Stat icon={ShieldCheck} label="rows" value={dataset ? dataset.rows.toLocaleString() : '—'} /></div>
        <div className="workspace-grid"><section className="panel runs-panel"><div className="panel-heading"><div><p className="eyebrow">activity</p><h2 className="panel-title">Recent runs</h2></div><button className="filter-button">all runs <span>⌄</span></button></div>{runs.length ? <div className="run-list">{runs.map((run) => <button key={run.id} className={`run-item ${selected?.id === run.id ? 'selected' : ''}`} onClick={() => selectRun(run)}><span className={`run-status ${run.status === 'failed' ? 'failed' : ''}`} /><span className="run-question">{run.question}<small>{run.id}</small></span><span className="run-score">{run.score ? `${Math.round(run.score * 100)}%` : '—'}</span><span className="run-time">{run.createdAt}</span></button>)}</div> : <div className="empty-state">{loading ? 'Loading runs...' : 'No runs yet. Ask the analyst a question.'}</div>}</section><section className="panel dataset-panel"><div className="panel-heading"><div><p className="eyebrow">connected source</p><h2 className="panel-title">Dataset</h2></div><Database size={16} className="muted-icon" /></div>{dataset ? <><div className="dataset-name"><span className="dataset-icon"><Layers3 size={15} /></span><div><strong>{dataset.name}</strong><p>production warehouse</p></div></div><div className="dataset-stats"><div><strong>{dataset.rows.toLocaleString()}</strong><span>rows</span></div><div><strong>{dataset.columns}</strong><span>columns</span></div><div><strong>—</strong><span>freshness</span></div></div><div className="dataset-bar"><span /></div></> : <div className="empty-state">{loading ? 'Loading dataset...' : 'No dataset loaded.'}</div>}</section></div>
        <LexxerTrace run={selected} loading={loading} error={error} onRetry={loadDashboard} /><LexxerArchitecture />
      </div>
      <LexxerChat onRunCreated={loadDashboard} />
    </div>
    <footer className="footer"><span><WandSparkles size={13} /> built for agentic systems</span><span>lexxer / v0.4.2</span></footer>
  </main>
}

function Stat({ icon: Icon, label, value }: { icon: typeof Activity; label: string; value: string }) { return <div className="stat-card"><Icon size={16} className="stat-icon" /><p>{label}</p><strong>{value}</strong></div> }