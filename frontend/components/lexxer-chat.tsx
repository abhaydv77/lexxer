'use client'

import { ArrowUp, Bot, Copy, Loader2, Sparkles, UserRound } from 'lucide-react'
import { FormEvent, useState } from 'react'
import { sendMessage } from '@/lib/lexxer-api'

type Message = { id: string; role: 'user' | 'assistant'; content: string }

export function LexxerChat({ onRunCreated }: { onRunCreated: () => void }) {
  const [messages, setMessages] = useState<Message[]>([
    { id: 'welcome', role: 'assistant', content: 'I can help you investigate runs, compare traces, and explain what the harness observed.' },
  ])
  const [value, setValue] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (!value.trim() || loading) return
    const content = value.trim()
    setValue(''); setError(''); setLoading(true)
    setMessages((current) => [...current, { id: crypto.randomUUID(), role: 'user', content }])
    try {
      const response = await sendMessage(content)
      setMessages((current) => [...current, { id: crypto.randomUUID(), role: 'assistant', content: response.message }])
      onRunCreated()
    } catch { setError('The analyst endpoint is unavailable. Your message is still visible here.') }
    finally { setLoading(false) }
  }

  return <section className="chat-shell">
    <div className="chat-header"><div className="brand-mark"><Sparkles size={15} /></div><div><p className="chat-title">lexxer analyst</p><p className="chat-subtitle"><span className="status-dot" /> online · grounded in traces</p></div><button className="icon-button" aria-label="Copy conversation"><Copy size={15} /></button></div>
    <div className="chat-messages">{messages.map((message) => <div key={message.id} className={`message ${message.role}`}><div className="message-avatar">{message.role === 'assistant' ? <Bot size={14} /> : <UserRound size={14} />}</div><div><p className="message-role">{message.role === 'assistant' ? 'lexxer' : 'you'}</p><p className="message-copy">{message.content}</p></div></div>)}{loading && <div className="message assistant"><div className="message-avatar"><Bot size={14} /></div><div><p className="message-role">lexxer</p><p className="message-copy loading-copy"><Loader2 size={14} className="spin" /> analyzing recent traces...</p></div></div>}{error && <p className="chat-error">{error}</p>}</div>
    <form className="chat-form" onSubmit={submit}><input value={value} onChange={(event) => setValue(event.target.value)} placeholder="Ask about this workspace..." aria-label="Ask Lexxer" /><button type="submit" disabled={!value.trim() || loading} aria-label="Send message"><ArrowUp size={16} /></button></form>
  </section>
}
