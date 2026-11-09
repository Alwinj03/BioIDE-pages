import React, { useEffect, useRef, useState } from 'react'
import { api } from '../lib/api'
import { Code, ErrorBox, Icon, I, Spinner, Table } from './ui'

type Msg = { role: 'user' | 'assistant'; content: string }
type ToolResult = { tool: string; input: any; result: any }

/** The assistant panel. When no LLM key is configured it does not pretend to be a
 *  chatbot: it runs deterministic routing and offers the real endpoints instead. */
export function Assistant({ open, onClose, projectId, onNavigate, seed }: {
  open: boolean
  onClose: () => void
  projectId: string | null
  onNavigate: (workspace: string, payload?: any) => void
  seed?: string | null
}) {
  const [msgs, setMsgs] = useState<Msg[]>([])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [routing, setRouting] = useState<any>(null)
  const [tools, setTools] = useState<ToolResult[]>([])
  const [llmEnabled, setLlmEnabled] = useState<boolean | null>(null)
  const scroller = useRef<HTMLDivElement>(null)

  useEffect(() => {
    api.get('/api/health').then(h => setLlmEnabled(!!h?.config?.llm_enabled)).catch(() => setLlmEnabled(false))
  }, [])

  useEffect(() => { if (seed) setInput(seed) }, [seed])
  useEffect(() => { scroller.current?.scrollTo({ top: 1e9, behavior: 'smooth' }) }, [msgs, tools, routing])

  const send = async (text?: string) => {
    const q = (text ?? input).trim()
    if (!q || busy) return
    setInput('')
    setError(null)
    setBusy(true)
    const next: Msg[] = [...msgs, { role: 'user', content: q }]
    setMsgs(next)
    try {
      const r = await api.post('/api/agent/chat', { messages: next, project_id: projectId })
      if (r.error) setError(r.error)
      if (r.reply) setMsgs([...next, { role: 'assistant', content: r.reply }])
      if (r.tool_results?.length) setTools(t => [...t, ...r.tool_results])
      if (r.llm === false) {
        setRouting(r.routing)
        setMsgs([...next, { role: 'assistant', content: r.message }])
      }
    } catch (e: any) {
      setError(e?.detail ?? String(e))
      setMsgs(next)
    } finally {
      setBusy(false)
    }
  }

  if (!open) return null

  return (
    <aside className="flex w-[420px] shrink-0 flex-col border-l border-line bg-bg2">
      <header className="flex items-center gap-2 border-b border-line px-4 py-3">
        <Icon d={I.spark} className="h-4 w-4 text-accent" />
        <div className="min-w-0 flex-1">
          <div className="text-sm font-semibold">BioAgent</div>
          <div className="text-[10.5px] text-muted">
            {llmEnabled === null ? 'checking provider…'
              : llmEnabled ? 'tool-calling enabled · results come from real runs'
              : 'no LLM key · deterministic routing only'}
          </div>
        </div>
        <button className="btn-ghost" onClick={onClose}><Icon d={I.x} className="h-4 w-4" /></button>
      </header>

      <div ref={scroller} className="flex-1 space-y-3 overflow-y-auto p-4">
        {msgs.length === 0 && (
          <div className="space-y-3">
            <div className="panel-tight p-3">
              <div className="text-[11px] font-semibold uppercase tracking-wider text-muted">What BioAgent may do</div>
              <ul className="mt-2 space-y-1 text-[11.5px] leading-relaxed text-muted">
                <li className="list-disc list-inside">Configure and run real analyses through {' '}
                  <span className="text-ink">14 declared tools</span> (COBRApy, PyDESeq2, Biopython, the catalogue, the sandbox).</li>
                <li className="list-disc list-inside">Search live literature APIs and cite only what came back.</li>
                <li className="list-disc list-inside">Generate and export workflows, and check what your machine can run.</li>
              </ul>
              <div className="mt-2 border-t border-line pt-2 text-[11px] text-rose-300/90">
                It may not state a number, a p-value or a citation that no tool returned. If it has not run
                something, it says so.
              </div>
            </div>
            <div className="space-y-1.5">
              {[
                'Run FBA on the E. coli core model and tell me what changes without oxygen',
                'Which tools can I use for metagenomic analysis on an 8 GB RAM laptop?',
                'Generate a Nextflow pipeline for genome annotation',
                'Find literature on synthetic methylotrophy in E. coli',
                'Which genes are essential in the core model on glucose?',
              ].map(s => (
                <button key={s} onClick={() => send(s)}
                        className="w-full rounded-lg border border-line bg-bg px-3 py-2 text-left text-[11.5px] text-muted transition-colors hover:border-accent/50 hover:text-ink">
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {msgs.map((m, i) => (
          <div key={i} className={`animate-fade rounded-lg px-3 py-2 text-[12.5px] leading-relaxed ${
            m.role === 'user' ? 'ml-6 bg-accent/10 text-ink' : 'mr-2 bg-panel text-ink/90'}`}>
            <div className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-muted">
              {m.role === 'user' ? 'you' : 'bioagent'}
            </div>
            <div className="whitespace-pre-wrap">{m.content}</div>
          </div>
        ))}

        {busy && <Spinner label="BioAgent is working…" />}
        {error && <ErrorBox error={error} hint="Nothing was executed for this turn." />}

        {routing && (
          <div className="panel-tight animate-fade p-3">
            <div className="text-[11px] font-semibold uppercase tracking-wider text-muted">
              Routed deterministically → {routing.intent}
            </div>
            <div className="mt-2 space-y-1">
              {routing.suggested_actions?.map((a: any, i: number) => (
                <button key={i} onClick={() => onNavigate(routing.workspace, a)}
                        className="flex w-full items-center gap-2 rounded border border-line bg-bg px-2 py-1.5 text-left text-[11.5px] hover:border-accent/50">
                  <Icon d={I.play} className="h-3 w-3 shrink-0 text-accent" />
                  <span className="min-w-0 flex-1 truncate">{a.label}</span>
                  <span className="mono shrink-0 text-[10px] text-muted">{a.method}</span>
                </button>
              ))}
            </div>
            {routing.tool_suggestions?.length > 0 && (
              <div className="mt-3 border-t border-line pt-2">
                <div className="text-[10px] font-semibold uppercase tracking-wider text-muted">Tools that match</div>
                <div className="mt-1 flex flex-wrap gap-1">
                  {routing.tool_suggestions.map((t: any) => (
                    <span key={t.id} title={t.why} className="chip">{t.name}</span>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {tools.map((t, i) => (
          <details key={i} className="panel-tight animate-fade p-2">
            <summary className="cursor-pointer text-[11.5px]">
              <span className="mono text-accent">{t.tool}</span>
              <span className={`ml-2 text-[10px] ${t.result?.error ? 'text-rose-400' : 'text-accent2'}`}>
                {t.result?.error ? 'failed' : 'returned data'}
              </span>
            </summary>
            <div className="mt-2">
              <Code code={JSON.stringify(t.result, null, 2)} maxH="max-h-64" language="tool result" />
            </div>
          </details>
        ))}
      </div>

      <div className="border-t border-line p-3">
        <textarea
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); void send() } }}
          rows={2}
          placeholder="Ask BioAgent, or describe an analysis…"
          className="input resize-none" />
        <div className="mt-2 flex items-center justify-between">
          <span className="text-[10px] text-muted">Enter to send · Shift+Enter for a new line</span>
          <button className="btn-primary px-3 py-1.5" disabled={busy || !input.trim()} onClick={() => void send()}>
            <Icon d={I.spark} className="h-3.5 w-3.5" />Send
          </button>
        </div>
      </div>
    </aside>
  )
}
