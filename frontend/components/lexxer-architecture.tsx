'use client'

import { ArrowDown, BrainCircuit, CheckCircle2, CircleDot, Database, GitBranch, Search, Wrench } from 'lucide-react'

const nodes = [
  { label: 'user input', icon: Search, tone: 'cyan' },
  { label: 'working memory', icon: Database, tone: 'blue' },
  { label: 'context builder', icon: GitBranch, tone: 'blue' },
  { label: 'llm reasoning', icon: BrainCircuit, tone: 'violet' },
  { label: 'tool runtime', icon: Wrench, tone: 'orange' },
  { label: 'validator', icon: CheckCircle2, tone: 'green' },
]

export function LexxerArchitecture() {
  return (
    <section className="panel min-w-0 overflow-hidden">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">system map</p>
          <h2 className="panel-title">Harness architecture</h2>
        </div>
        <span className="live-pill"><span /> observing</span>
      </div>
      <div className="architecture-grid">
        <div className="architecture-flow">
          {nodes.map((node, index) => {
            const Icon = node.icon
            return (
              <div key={node.label} className="architecture-step">
                <div className={`architecture-node ${node.tone}`}>
                  <Icon size={15} />
                  <span>{node.label}</span>
                </div>
                {index < nodes.length - 1 && <ArrowDown className="architecture-arrow" size={16} />}
              </div>
            )
          })}
        </div>
        <div className="observer-card">
          <CircleDot size={15} />
          <div>
            <p className="observer-title">tracer</p>
            <p className="observer-copy">events, tokens, latency</p>
          </div>
          <div className="observer-line" />
        </div>
      </div>
    </section>
  )
}
