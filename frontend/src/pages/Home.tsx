import React, { useEffect, useState } from 'react'
import { api } from '../lib/api'
import { useAsync } from '../lib/useAsync'
import { Code, ErrorBox, ExecBadge, Icon, I, Section, Spinner, useRotating } from '../components/ui'

const EXAMPLES = [
  'Analyse RNA-seq data and identify differentially expressed genes',
  'Reconstruct a genome-scale metabolic model using COBRApy',
  'Identify carbohydrate-active enzymes from a bacterial genome',
  'Perform metagenomic functional profiling',
  'Compare protein structures',
  'Which genes are essential in E. coli on glucose?',
  'Design a computational workflow for genome annotation',
  'Which tools can I use for metagenomics on an 8 GB RAM laptop?',
]

export function Home({ onNavigate, onAsk }: { onNavigate: (w: string, p?: any) => void; onAsk: (q: string) => void }) {
  const [q, setQ] = useState('')
  const rotating = useRotating(EXAMPLES)
  const samples = useAsync<any>(() => api.get('/api/samples'), true)
  const caps = useAsync<any>(() => api.get('/api/capabilities'), true)
  const route = useAsync<any>((text: string) => api.post('/api/agent/route', { q: text }))

  const submit = () => { if (q.trim()) void route.run(q.trim()) }

  return (
    <div className="mx-auto max-w-6xl space-y-8 p-6 pb-16">
      <div className="pt-6 text-center">
        <h1 className="text-[34px] font-bold leading-tight tracking-tight text-ink">
          Your biological research, one intelligent workspace.
        </h1>
        <p className="mx-auto mt-3 max-w-2xl text-[13.5px] leading-relaxed text-muted">
          Discover literature, design computational workflows, execute bioinformatics tools and explore
          biological systems with AI.
        </p>
      </div>

      <div className="mx-auto max-w-3xl">
        <div className="panel p-2 shadow-[0_0_40px_-12px_rgba(56,189,248,0.25)]">
          <div className="flex items-start gap-2">
            <Icon d={I.search} className="ml-2 mt-3 h-4 w-4 shrink-0 text-muted" />
            <textarea
              value={q}
              onChange={e => setQ(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); submit() } }}
              rows={2}
              placeholder="Describe your biological research problem or computational objective…"
              className="min-h-[52px] flex-1 resize-none bg-transparent py-2 text-[13.5px] text-ink outline-none placeholder:text-muted/60" />
            <button className="btn-primary mt-1 shrink-0" onClick={submit} disabled={!q.trim() || route.loading}>
              <Icon d={I.play} className="h-3.5 w-3.5" />Classify
            </button>
          </div>
          <div className="flex flex-wrap items-center gap-2 border-t border-line px-2 py-2">
            <button className="btn-ghost" onClick={() => setQ(rotating)}>
              <Icon d={I.refresh} className="h-3 w-3" />
              <span className="max-w-[340px] truncate italic">{rotating}</span>
            </button>
            <div className="ml-auto flex gap-1">
              <button className="btn-ghost" onClick={() => onNavigate('bioinformatics')}>
                <Icon d={I.dna} className="h-3 w-3" />upload sequence
              </button>
              <button className="btn-ghost" onClick={() => onNavigate('omics')}>
                <Icon d={I.layers} className="h-3 w-3" />upload counts
              </button>
              <button className="btn-ghost" onClick={() => q.trim() && onAsk(q.trim())}>
                <Icon d={I.spark} className="h-3 w-3" />ask BioAgent
              </button>
            </div>
          </div>
        </div>

        {route.loading && <div className="mt-3"><Spinner label="Classifying…" /></div>}
        {route.error && <div className="mt-3"><ErrorBox error={route.error} /></div>}
        {route.data && (
          <div className="panel mt-3 animate-fade p-4">
            <div className="flex flex-wrap items-center gap-2">
              <span className="chip border-accent/40 text-accent">intent · {route.data.intent}</span>
              <span className="chip">workspace · {route.data.workspace}</span>
              {route.data.workflow_match?.best && (
                <span className="chip border-accent2/40 text-accent2">
                  workflow · {route.data.workflow_match.best}
                </span>
              )}
              <span className="ml-auto text-[10.5px] text-muted">{route.data.method}</span>
            </div>
            {route.data.suggested_actions?.length > 0 && (
              <div className="mt-3 space-y-1">
                {route.data.suggested_actions.map((a: any, i: number) => (
                  <button key={i} onClick={() => onNavigate(route.data.workspace, a)}
                          className="flex w-full items-center gap-2 rounded-lg border border-line bg-bg px-3 py-2 text-left text-xs hover:border-accent/50">
                    <Icon d={I.play} className="h-3 w-3 shrink-0 text-accent" />
                    <span className="min-w-0 flex-1 truncate">{a.label}</span>
                    <span className="mono shrink-0 text-[10px] text-muted">{a.endpoint}</span>
                  </button>
                ))}
              </div>
            )}
            {route.data.intent === 'unclear' && (
              <p className="mt-3 text-[11.5px] text-muted">
                No rule matched this text with confidence. Open a workspace directly, or ask BioAgent, which can
                decompose the question when an LLM key is configured.
              </p>
            )}
          </div>
        )}
      </div>

      <Section title="Explore BioIDE with sample projects"
               subtitle="Real computational biology use cases. No prior configuration required.">
        {samples.loading && <Spinner />}
        {samples.error && <ErrorBox error={samples.error} />}
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {samples.data?.samples?.map((s: any) => (
            <article key={s.id} className="panel-tight card-hover flex flex-col p-3">
              <div className="flex items-start justify-between gap-2">
                <span className="mono text-accent">PROJECT {s.number}</span>
                <span className="chip">{s.runs_here?.length ?? 0} live steps</span>
              </div>
              <h4 className="mt-1.5 text-[13.5px] font-semibold leading-snug text-ink">{s.title}</h4>
              <p className="mt-0.5 text-[10.5px] text-muted">{s.organism}</p>
              <p className="mt-2 flex-1 text-[11.5px] leading-relaxed text-muted">{s.summary}</p>
              <div className="mt-2 flex flex-wrap gap-1">
                {s.needs_local_tools?.length > 0 && <ExecBadge kind="local_db" />}
                <ExecBadge kind="native" />
              </div>
              <div className="mt-3 flex flex-wrap gap-1.5 border-t border-line pt-2.5">
                <button className="btn px-2 py-1 text-[11px]" onClick={() => onNavigate('projects', { openSample: s.id })}>
                  Open project
                </button>
                <button className="btn px-2 py-1 text-[11px]" onClick={() => onNavigate('workflows', { sample: s.id })}>
                  View workflow
                </button>
                <button className="btn px-2 py-1 text-[11px]" onClick={() => onNavigate('projects', { openSample: s.id, tab: 'data' })}>
                  Explore dataset
                </button>
                <button className="btn-primary px-2 py-1 text-[11px]"
                        onClick={() => onNavigate(s.entry_points?.[0] ? workspaceFor(s.id) : 'projects', { sample: s.id, run: true })}>
                  <Icon d={I.play} className="h-3 w-3" />Run demo
                </button>
              </div>
            </article>
          ))}
        </div>
      </Section>

      <Section title="What works, and what does not"
               subtitle="Read from /api/capabilities at load time, so this page cannot drift from the backend.">
        {caps.loading && <Spinner />}
        {caps.error && <ErrorBox error={caps.error} />}
        {caps.data && (
          <div className="grid gap-4 lg:grid-cols-3">
            <div>
              <div className="mb-2 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider text-accent2">
                <Icon d={I.check} className="h-3.5 w-3.5" />Working now
              </div>
              <ul className="space-y-1.5">
                {caps.data.working_now.map((f: any, i: number) => (
                  <li key={i} className="panel-tight p-2">
                    <div className="text-[11.5px] leading-snug text-ink">{f.feature}</div>
                    <div className="mono mt-0.5 text-[10px] text-muted">{f.engine} · {f.status}</div>
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <div className="mb-2 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider text-amber-300">
                <Icon d={I.gear} className="h-3.5 w-3.5" />Needs configuration
              </div>
              <ul className="space-y-1.5">
                {caps.data.needs_configuration.map((f: any, i: number) => (
                  <li key={i} className="panel-tight p-2">
                    <div className="flex items-start justify-between gap-2">
                      <div className="text-[11.5px] leading-snug text-ink">{f.feature}</div>
                      {f.configured !== null && (
                        <span className={`chip shrink-0 ${f.configured ? 'border-accent2/40 text-accent2' : 'border-amber-500/40 text-amber-300'}`}>
                          {f.configured ? 'set' : 'not set'}
                        </span>
                      )}
                    </div>
                    <div className="mt-0.5 text-[10.5px] leading-relaxed text-muted">requires {f.requires}</div>
                    <div className="mt-0.5 text-[10.5px] leading-relaxed text-muted/80">fallback: {f.fallback}</div>
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <div className="mb-2 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider text-muted">
                <Icon d={I.x} className="h-3.5 w-3.5" />Not implemented here
              </div>
              <ul className="space-y-1.5">
                {caps.data.not_implemented_here.map((f: any, i: number) => (
                  <li key={i} className="panel-tight p-2">
                    <div className="text-[11.5px] leading-snug text-ink">{f.feature}</div>
                    <div className="mt-0.5 text-[10.5px] leading-relaxed text-muted">why: {f.why}</div>
                    <div className="mt-0.5 text-[10.5px] leading-relaxed text-accent/80">instead: {f.what_bioide_does}</div>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        )}
      </Section>
    </div>
  )
}

export function workspaceFor(sampleId: string): string {
  return ({
    genome_annotation: 'bioinformatics',
    rnaseq_de: 'omics',
    metagenomics: 'workflows',
    protein_structure: 'bioinformatics',
    metabolic_modelling: 'modelling',
    pathway_engineering: 'modelling',
  } as Record<string, string>)[sampleId] ?? 'projects'
}
