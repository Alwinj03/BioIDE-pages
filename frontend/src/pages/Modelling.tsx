import React, { useEffect, useMemo, useState } from 'react'
import { api } from '../lib/api'
import { useAsync } from '../lib/useAsync'
import { Plot, PALETTE } from '../components/Plot'
import {
  Caveats, Code, Empty, ErrorBox, Icon, I, ProvenanceBadge, Section, Spinner, Stat, Table, Tabs,
} from '../components/ui'

type Bounds = Record<string, [number, number]>

const MEDIA: { id: string; label: string; bounds: Bounds; note: string }[] = [
  { id: 'aerobic', label: 'Aerobic glucose', bounds: {}, note: 'Model defaults: glucose uptake capped, oxygen open.' },
  { id: 'anaerobic', label: 'Anaerobic glucose', bounds: { EX_o2_e: [0, 1000] },
    note: 'Oxygen uptake blocked. Expect fermentation products and far lower growth.' },
  { id: 'glucose_limited', label: 'Glucose-limited (1 mmol)', bounds: { EX_glc__D_e: [-1, 1000] },
    note: 'Carbon-limited: growth should scale roughly linearly with uptake.' },
  { id: 'acetate', label: 'Acetate as sole carbon source', bounds: { EX_glc__D_e: [0, 1000], EX_ac_e: [-10, 1000] },
    note: 'Glucose blocked, acetate opened. Requires the glyoxylate shunt and gluconeogenesis.' },
]

export function Modelling({ projectId, pending }: { projectId: string | null; pending?: any }) {
  const [modelId, setModelId] = useState('e_coli_core')
  const [medium, setMedium] = useState('aerobic')
  const [customBounds, setCustomBounds] = useState<Bounds>({})
  const [knockouts, setKnockouts] = useState<string[]>([])
  const [geneKOs, setGeneKOs] = useState<string[]>([])
  const [objective, setObjective] = useState('')
  const [parsimonious, setParsimonious] = useState(false)
  const [tab, setTab] = useState('fba')
  const [saved, setSaved] = useState<{ label: string; fluxes: Record<string, number>; obj: number | null }[]>([])
  const [query, setQuery] = useState('')
  const [target, setTarget] = useState('EX_ac_e')
  const [fvaSubset, setFvaSubset] = useState('')

  const models = useAsync<any>(() => api.get('/api/model/list'), true)
  const inspect = useAsync<any>((id: string) => api.get(`/api/model/${id}/inspect?with_quality=true`))
  const fba = useAsync<any>((b: any) => api.post('/api/model/fba', b))
  const fva = useAsync<any>((b: any) => api.post('/api/model/fva', b))
  const del = useAsync<any>((b: any) => api.post('/api/model/deletions', b))
  const env = useAsync<any>((b: any) => api.post('/api/model/envelope', b))
  const net = useAsync<any>((b: any) => api.post('/api/model/network', b))
  const search = useAsync<any>((id: string, q: string, kind: string) =>
    api.get(`/api/model/${id}/search?q=${encodeURIComponent(q)}&kind=${kind}`))

  useEffect(() => { void inspect.run(modelId) }, [modelId])

  useEffect(() => {
    if (pending?.body?.model_id) setModelId(pending.body.model_id)
    if (pending?.body?.bounds) {
      const m = MEDIA.find(x => JSON.stringify(x.bounds) === JSON.stringify(pending.body.bounds))
      if (m) setMedium(m.id); else setCustomBounds(pending.body.bounds)
    }
    if (pending?.endpoint?.includes('/fva')) setTab('fva')
    if (pending?.endpoint?.includes('/envelope')) setTab('envelope')
    if (pending?.run || pending?.endpoint?.includes('/fba')) setTimeout(() => void runFBA(), 60)
  }, [pending])

  const bounds = useMemo(() => ({ ...(MEDIA.find(m => m.id === medium)?.bounds ?? {}), ...customBounds }), [medium, customBounds])
  const common = () => ({
    model_id: modelId, bounds: Object.keys(bounds).length ? bounds : null,
    knockouts: knockouts.length ? knockouts : null,
    gene_knockouts: geneKOs.length ? geneKOs : null,
    objective: objective || null, project_id: projectId,
  })

  const runFBA = async () => {
    const r = await fba.run({ ...common(), parsimonious })
    if (r?.all_fluxes) void net.run({ model_id: modelId, fluxes: r.all_fluxes, max_nodes: 120 })
  }
  const runFVA = () => fva.run({
    ...common(), fraction: 0.9,
    reactions: fvaSubset.trim() ? fvaSubset.split(/[,\s]+/).filter(Boolean) : null,
  })
  const runDel = () => del.run({ model_id: modelId, level: 'gene', bounds: common().bounds, objective: objective || null, project_id: projectId })
  const runEnv = () => env.run({ model_id: modelId, target, points: 20, bounds: common().bounds, project_id: projectId })

  const saveRun = () => {
    if (!fba.data?.all_fluxes) return
    const label = `${MEDIA.find(m => m.id === medium)?.label ?? 'custom'}${knockouts.length ? ` ΔR:${knockouts.join(',')}` : ''}${geneKOs.length ? ` Δg:${geneKOs.join(',')}` : ''}${parsimonious ? ' (pFBA)' : ''}`
    setSaved(s => [...s, { label, fluxes: fba.data.all_fluxes, obj: fba.data.objective_value }].slice(-4))
  }

  const comparison = useAsync<any>(() => api.post('/api/model/compare', {
    model_id: modelId, runs: saved.map(s => ({ label: s.label, fluxes: s.fluxes })),
  }))

  const big = (inspect.data?.counts?.reactions ?? 0) > 600

  return (
    <div className="flex h-full min-h-0">
      {/* left: model + constraints */}
      <div className="w-[320px] shrink-0 space-y-3 overflow-y-auto border-r border-line p-3">
        <div>
          <label className="label">Model</label>
          <select className="input mt-1" value={modelId} onChange={e => setModelId(e.target.value)}>
            {models.data?.models?.map((m: any) => (
              <option key={m.id} value={m.id}>{m.label}</option>
            ))}
          </select>
          {inspect.data && (
            <p className="mt-1.5 text-[10.5px] leading-relaxed text-muted">{inspect.data.source}</p>
          )}
        </div>

        <div>
          <label className="label">Growth medium</label>
          <div className="mt-1 space-y-1">
            {MEDIA.map(m => (
              <button key={m.id} onClick={() => setMedium(m.id)}
                      className={`w-full rounded-lg border px-2.5 py-1.5 text-left text-[11.5px] transition-colors ${
                        medium === m.id ? 'border-accent bg-accent/10 text-ink' : 'border-line bg-bg text-muted hover:text-ink'}`}>
                {m.label}
              </button>
            ))}
          </div>
          <p className="mt-1.5 text-[10.5px] leading-relaxed text-muted">{MEDIA.find(m => m.id === medium)?.note}</p>
        </div>

        <div>
          <label className="label">Reaction knockouts</label>
          <input className="input mt-1 mono" placeholder="PGI, ZWF, SUCDi"
                 value={knockouts.join(', ')}
                 onChange={e => setKnockouts(e.target.value.split(/[,\s]+/).filter(Boolean))} />
        </div>
        <div>
          <label className="label">Gene knockouts</label>
          <input className="input mt-1 mono" placeholder="b2926, b1136"
                 value={geneKOs.join(', ')}
                 onChange={e => setGeneKOs(e.target.value.split(/[,\s]+/).filter(Boolean))} />
        </div>
        <div>
          <label className="label">Objective override</label>
          <input className="input mt-1 mono" placeholder="(biomass by default)"
                 value={objective} onChange={e => setObjective(e.target.value)} />
        </div>
        <label className="flex items-center gap-2 text-[11.5px] text-muted">
          <input type="checkbox" checked={parsimonious} onChange={e => setParsimonious(e.target.checked)}
                 className="accent-accent" />
          Parsimonious FBA (unique minimal-flux solution)
        </label>

        <button className="btn-primary w-full justify-center" onClick={runFBA} disabled={fba.loading}>
          <Icon d={I.play} className="h-3.5 w-3.5" />{fba.loading ? 'Solving…' : 'Run FBA'}
        </button>

        <div className="border-t border-line pt-3">
          <label className="label">Find reactions, metabolites, genes</label>
          <div className="mt-1 flex gap-1">
            <input className="input mono" placeholder="pyruvate" value={query}
                   onChange={e => setQuery(e.target.value)}
                   onKeyDown={e => e.key === 'Enter' && query && search.run(modelId, query, 'reaction')} />
          </div>
          <div className="mt-1 flex gap-1">
            {['reaction', 'metabolite', 'gene'].map(k => (
              <button key={k} className="btn px-2 py-1 text-[10.5px]" disabled={!query}
                      onClick={() => search.run(modelId, query, k)}>{k}</button>
            ))}
          </div>
          {search.loading && <div className="mt-2"><Spinner /></div>}
          {search.data?.matches && (
            <div className="mt-2 max-h-56 space-y-1 overflow-y-auto">
              {search.data.matches.length === 0 && <div className="text-[11px] text-muted">No matches.</div>}
              {search.data.matches.map((m: any) => (
                <div key={m.id} className="panel-tight p-1.5">
                  <div className="mono text-[11px] text-accent">{m.id}</div>
                  <div className="text-[10.5px] leading-snug text-muted">{m.name}</div>
                  {m.reaction && <div className="mono mt-0.5 break-words text-[9.5px] text-muted/70">{m.reaction}</div>}
                  {m.formula && <div className="mono mt-0.5 text-[9.5px] text-muted/70">{m.formula} · charge {m.charge}</div>}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* right: results */}
      <div className="min-w-0 flex-1 overflow-y-auto">
        {inspect.loading && <div className="p-6"><Spinner label="Loading model…" /></div>}
        {inspect.error && <div className="p-6"><ErrorBox error={inspect.error} /></div>}

        {inspect.data && (
          <div className="space-y-4 p-4">
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-5">
              <Stat label="Reactions" value={inspect.data.counts.reactions} />
              <Stat label="Metabolites" value={inspect.data.counts.metabolites} />
              <Stat label="Genes" value={inspect.data.counts.genes} />
              <Stat label="Exchanges" value={inspect.data.counts.exchanges} />
              <Stat label="Default growth" value={inspect.data.objective_value_default_medium?.toFixed(4) ?? '—'}
                    unit="h⁻¹" tone="good" />
            </div>

            {inspect.data.quality && (
              <Section title="Model quality" subtitle="Structural checks run before you trust any simulation from it.">
                <div className="grid gap-2 sm:grid-cols-5">
                  {[
                    ['Mass/charge imbalanced', inspect.data.quality.mass_or_charge_imbalanced],
                    ['Unverifiable (no formula)', inspect.data.quality.reactions_unverifiable_no_formula],
                    ['Orphan metabolites', inspect.data.quality.orphan_metabolites],
                    ['Dead-end metabolites', inspect.data.quality.dead_end_metabolites],
                    ['Reactions without GPR', inspect.data.quality.reactions_without_gpr],
                  ].map(([label, v]: any) => (
                    <Stat key={label} label={label} value={v.count} tone={v.count === 0 ? 'good' : 'warn'} />
                  ))}
                </div>
                <p className="mt-2 text-[11px] leading-relaxed text-muted">{inspect.data.quality.note}</p>
                <p className="mt-1 text-[11px] leading-relaxed text-amber-200/70">
                  This is a small subset of what MEMOTE checks. Run MEMOTE before publishing a reconstruction.
                </p>
              </Section>
            )}

            <Tabs active={tab} onChange={setTab} tabs={[
              { id: 'fba', label: 'Flux distribution' },
              { id: 'fva', label: 'Variability (FVA)' },
              { id: 'deletions', label: 'Gene essentiality' },
              { id: 'envelope', label: 'Production envelope' },
              { id: 'network', label: 'Network' },
              { id: 'compare', label: 'Compare runs', badge: saved.length || undefined },
              { id: 'script', label: 'Script' },
            ]} />

            {tab === 'fba' && (
              <div className="space-y-3">
                {fba.loading && <Spinner label="Solving the LP…" />}
                {fba.error && <ErrorBox error={fba.error} />}
                {!fba.data && !fba.loading && !fba.error && (
                  <Empty title="No simulation has run yet" icon={I.atom}
                         body="Set a medium and any knockouts on the left, then run FBA. Every value shown afterwards comes from COBRApy."
                         action={<button className="btn-primary mt-2" onClick={runFBA}><Icon d={I.play} className="h-3.5 w-3.5" />Run FBA</button>} />
                )}
                {fba.data && (
                  <>
                    <div className="flex flex-wrap items-center gap-2">
                      <ProvenanceBadge p={fba.data.provenance} elapsed={fba.elapsed} />
                      <span className="chip">{fba.data.method}</span>
                      <span className={`chip ${fba.data.status === 'optimal' ? 'border-accent2/40 text-accent2' : 'border-rose-500/40 text-rose-300'}`}>
                        {fba.data.status}
                      </span>
                      <span className="chip">{fba.data.solve_seconds} s solve</span>
                      <button className="btn ml-auto px-2 py-1 text-[11px]" onClick={saveRun}>
                        <Icon d={I.copy} className="h-3 w-3" />Save for comparison
                      </button>
                    </div>

                    {fba.data.modifications?.length > 0 && (
                      <div className="panel-tight p-2">
                        <div className="label">Applied to a copy of the model</div>
                        <ul className="mono mt-1 space-y-0.5 text-[10.5px] text-muted">
                          {fba.data.modifications.map((m: string, i: number) => <li key={i}>· {m}</li>)}
                        </ul>
                      </div>
                    )}

                    <div className="grid gap-2 sm:grid-cols-3">
                      <Stat label="Objective value" value={fba.data.objective_value?.toFixed(5) ?? '—'}
                            tone={fba.data.status === 'optimal' ? 'good' : 'bad'} />
                      <Stat label="Active reactions" value={fba.data.active_reaction_count} />
                      <Stat label="Exchange fluxes" value={fba.data.exchange_fluxes?.length ?? 0} />
                    </div>

                    {fba.data.interpretation && <ErrorBox error={fba.data.interpretation} />}

                    {fba.data.exchange_fluxes?.length > 0 && (
                      <Section title="Exchange fluxes" subtitle="What the cell takes up and secretes at this optimum.">
                        <Plot height={260}
                              data={[{
                                type: 'bar', orientation: 'h',
                                y: fba.data.exchange_fluxes.slice(0, 14).map((e: any) => e.id).reverse(),
                                x: fba.data.exchange_fluxes.slice(0, 14).map((e: any) => e.flux).reverse(),
                                marker: { color: fba.data.exchange_fluxes.slice(0, 14).map((e: any) => e.flux < 0 ? PALETTE[0] : PALETTE[1]).reverse() },
                                hovertemplate: '%{y}<br>%{x:.4f} mmol gDW⁻¹ h⁻¹<extra></extra>',
                              }]}
                              layout={{ xaxis: { title: 'flux (negative = uptake)' }, margin: { l: 110, r: 20, t: 10, b: 40 } }} />
                      </Section>
                    )}

                    <Section title="Active fluxes" subtitle="Reactions carrying non-zero flux, largest in magnitude first."
                             right={<span className="text-[10.5px] text-muted">showing {Math.min(fba.data.active_reactions.length, 80)} of {fba.data.active_reaction_count}</span>}>
                      <Table rows={fba.data.active_reactions}
                             cols={[
                               { key: 'id', label: 'Reaction', className: 'mono text-accent' },
                               { key: 'name', label: 'Name', className: 'text-muted' },
                               { key: 'equation', label: 'Equation', className: 'mono text-[10.5px] text-muted/80' },
                               { key: 'flux', label: 'Flux', align: 'right',
                                 render: (r: any) => <span className="mono">{r.flux.toFixed(4)}</span> },
                             ]} />
                    </Section>

                    <Caveats items={fba.data.caveats} />
                  </>
                )}
              </div>
            )}

            {tab === 'fva' && (
              <div className="space-y-3">
                <div className="panel-tight flex flex-wrap items-end gap-2 p-3">
                  <div className="min-w-[260px] flex-1">
                    <label className="label">Reactions (leave blank for all)</label>
                    <input className="input mt-1 mono" placeholder="PGI, PFK, PYK" value={fvaSubset}
                           onChange={e => setFvaSubset(e.target.value)} />
                  </div>
                  <button className="btn-primary" onClick={runFVA} disabled={fva.loading}>
                    <Icon d={I.play} className="h-3.5 w-3.5" />Run FVA at 90% of optimum
                  </button>
                </div>
                {big && !fvaSubset.trim() && (
                  <Caveats title="This model is large"
                           items={[`${inspect.data.counts.reactions} reactions: the backend refuses a full FVA here and will ask for an explicit reaction list. That refusal is deliberate, not a bug.`]} />
                )}
                {fva.loading && <Spinner label="Solving two LPs per reaction…" />}
                {fva.error && <ErrorBox error={fva.error} />}
                {fva.data && (
                  <>
                    <div className="flex flex-wrap items-center gap-2">
                      <ProvenanceBadge p={fva.data.provenance} elapsed={fva.elapsed} />
                      <span className="chip">{fva.data.n_reactions} reactions · {fva.data.solve_seconds} s</span>
                    </div>
                    <div className="grid gap-2 sm:grid-cols-4">
                      <Stat label="Blocked" value={fva.data.summary_counts.blocked} />
                      <Stat label="Fully determined" value={fva.data.summary_counts.fixed} tone="good" />
                      <Stat label="Variable" value={fva.data.summary_counts.variable} tone="warn" />
                      <Stat label="Variable + reversible" value={fva.data.summary_counts.variable_reversible} tone="warn" />
                    </div>
                    <Section title="Flux ranges" subtitle="Widest intervals first. A wide interval means the model does not determine that flux.">
                      <Plot height={320}
                            data={[{
                              type: 'bar', orientation: 'h',
                              y: fva.data.ranges.slice(0, 18).map((r: any) => r.id).reverse(),
                              x: fva.data.ranges.slice(0, 18).map((r: any) => r.span).reverse(),
                              base: fva.data.ranges.slice(0, 18).map((r: any) => r.minimum).reverse(),
                              marker: { color: PALETTE[2] },
                              hovertemplate: '%{y}<br>range %{base:.3f} → %{customdata:.3f}<extra></extra>',
                              customdata: fva.data.ranges.slice(0, 18).map((r: any) => r.maximum).reverse(),
                            }]}
                            layout={{ xaxis: { title: 'feasible flux interval' }, margin: { l: 110, r: 20, t: 10, b: 40 } }} />
                      <div className="mt-3">
                        <Table rows={fva.data.ranges}
                               cols={[
                                 { key: 'id', label: 'Reaction', className: 'mono text-accent' },
                                 { key: 'name', label: 'Name', className: 'text-muted' },
                                 { key: 'minimum', label: 'Min', align: 'right', render: (r: any) => <span className="mono">{r.minimum.toFixed(3)}</span> },
                                 { key: 'maximum', label: 'Max', align: 'right', render: (r: any) => <span className="mono">{r.maximum.toFixed(3)}</span> },
                                 { key: 'span', label: 'Span', align: 'right', render: (r: any) => <span className="mono">{r.span.toFixed(3)}</span> },
                                 { key: 'classification', label: 'Class',
                                   render: (r: any) => <span className="chip">{r.classification}</span> },
                               ]} />
                      </div>
                    </Section>
                    <Caveats items={fva.data.caveats} />
                  </>
                )}
              </div>
            )}

            {tab === 'deletions' && (
              <div className="space-y-3">
                <button className="btn-primary" onClick={runDel} disabled={del.loading}>
                  <Icon d={I.play} className="h-3.5 w-3.5" />Run single gene deletion scan
                </button>
                {del.loading && <Spinner label="Solving one LP per gene…" />}
                {del.error && <ErrorBox error={del.error} />}
                {del.data && (
                  <>
                    <div className="flex flex-wrap items-center gap-2">
                      <ProvenanceBadge p={del.data.provenance} elapsed={del.elapsed} />
                      <span className="chip">wild type {del.data.wildtype_objective?.toFixed(4)} h⁻¹</span>
                      <span className="chip">{del.data.solve_seconds} s</span>
                    </div>
                    <div className="grid gap-2 sm:grid-cols-5">
                      <Stat label="Lethal" value={del.data.counts.lethal} tone="bad" />
                      <Stat label="Severe" value={del.data.counts.severe} tone="warn" />
                      <Stat label="Mild" value={del.data.counts.mild} />
                      <Stat label="Neutral" value={del.data.counts.neutral} tone="good" />
                      <Stat label="Unsolved" value={del.data.counts.unsolved} />
                    </div>
                    <Section title="Deletion phenotypes" subtitle="Growth relative to wild type, under the simulated medium.">
                      <Plot height={300}
                            data={[{
                              type: 'bar',
                              x: del.data.results.slice(0, 40).map((r: any) => r.label ?? r.id),
                              y: del.data.results.slice(0, 40).map((r: any) => r.ratio_to_wildtype ?? 0),
                              marker: { color: del.data.results.slice(0, 40).map((r: any) =>
                                r.phenotype === 'lethal' ? '#F87171' : r.phenotype === 'severe' ? '#FBBF24'
                                  : r.phenotype === 'mild' ? '#38BDF8' : '#34D399') },
                              hovertemplate: '%{x}<br>growth ratio %{y:.3f}<extra></extra>',
                            }]}
                            layout={{ yaxis: { title: 'growth / wild-type' }, xaxis: { tickangle: -60 }, margin: { b: 90 } }} />
                      <div className="mt-3">
                        <Table rows={del.data.results}
                               cols={[
                                 { key: 'label', label: 'Gene', className: 'mono text-accent',
                                   render: (r: any) => r.label ?? r.id },
                                 { key: 'growth', label: 'Growth', align: 'right',
                                   render: (r: any) => <span className="mono">{r.growth?.toFixed(5) ?? '—'}</span> },
                                 { key: 'ratio_to_wildtype', label: 'Ratio', align: 'right',
                                   render: (r: any) => <span className="mono">{r.ratio_to_wildtype?.toFixed(3) ?? '—'}</span> },
                                 { key: 'phenotype', label: 'Phenotype', render: (r: any) => <span className="chip">{r.phenotype}</span> },
                                 { key: 'status', label: 'LP status', className: 'text-muted' },
                               ]} />
                      </div>
                    </Section>
                    <Caveats items={del.data.caveats} />
                  </>
                )}
              </div>
            )}

            {tab === 'envelope' && (
              <div className="space-y-3">
                <div className="panel-tight flex flex-wrap items-end gap-2 p-3">
                  <div className="min-w-[220px] flex-1">
                    <label className="label">Target exchange reaction</label>
                    <input className="input mt-1 mono" value={target} onChange={e => setTarget(e.target.value)} />
                  </div>
                  <button className="btn-primary" onClick={runEnv} disabled={env.loading}>
                    <Icon d={I.play} className="h-3.5 w-3.5" />Compute envelope
                  </button>
                </div>
                {env.loading && <Spinner />}
                {env.error && <ErrorBox error={env.error} />}
                {env.data && (
                  <>
                    <ProvenanceBadge p={env.data.provenance} elapsed={env.elapsed} />
                    <Section title={`Growth versus ${env.data.target}`}
                             subtitle="The stoichiometric ceiling: the boundary of what mass and redox balance permit.">
                      <Plot height={320}
                            data={[
                              { type: 'scatter', mode: 'lines+markers', name: 'maximum growth',
                                x: env.data.points.map((p: any) => p[env.data.target]),
                                y: env.data.points.map((p: any) => p.flux_maximum),
                                line: { color: PALETTE[0], width: 2 } },
                              { type: 'scatter', mode: 'lines', name: 'minimum growth',
                                x: env.data.points.map((p: any) => p[env.data.target]),
                                y: env.data.points.map((p: any) => p.flux_minimum),
                                line: { color: PALETTE[3], width: 1.5, dash: 'dot' } },
                            ]}
                            layout={{ xaxis: { title: `${env.data.target} flux` }, yaxis: { title: 'growth rate (h⁻¹)' } }} />
                    </Section>
                    <Caveats items={env.data.caveats} />
                  </>
                )}
              </div>
            )}

            {tab === 'network' && (
              <div className="space-y-3">
                {!fba.data && <Empty title="Run FBA first" body="The network is coloured by the flux distribution from the last solve." icon={I.flow} />}
                {net.loading && <Spinner label="Building the graph…" />}
                {net.error && <ErrorBox error={net.error} />}
                {net.data && <NetworkView graph={net.data} />}
              </div>
            )}

            {tab === 'compare' && (
              <div className="space-y-3">
                {saved.length < 2 ? (
                  <Empty title="Save at least two runs" icon={I.chart}
                         body="Run FBA under one condition, press 'Save for comparison', change the medium or knockouts, run again, then compare." />
                ) : (
                  <>
                    <div className="flex flex-wrap gap-2">
                      {saved.map((s, i) => (
                        <span key={i} className="chip border-accent/40 text-accent">
                          {s.label} · {s.obj?.toFixed(4)}
                        </span>
                      ))}
                      <button className="btn ml-auto px-2 py-1 text-[11px]" onClick={() => comparison.run()}>
                        <Icon d={I.chart} className="h-3 w-3" />Compare
                      </button>
                      <button className="btn px-2 py-1 text-[11px]" onClick={() => setSaved([])}>
                        <Icon d={I.trash} className="h-3 w-3" />Clear
                      </button>
                    </div>
                    {comparison.loading && <Spinner />}
                    {comparison.error && <ErrorBox error={comparison.error} />}
                    {comparison.data && (
                      <Section title="Fluxes that differ between runs"
                               subtitle={`${comparison.data.n_differing} reactions differ by more than 1e-6.`}>
                        <Table rows={comparison.data.differences}
                               cols={[
                                 { key: 'id', label: 'Reaction', className: 'mono text-accent' },
                                 { key: 'name', label: 'Name', className: 'text-muted' },
                                 ...comparison.data.labels.map((l: string, i: number) => ({
                                   key: `v${i}`, label: l, align: 'right' as const,
                                   render: (r: any) => <span className="mono">{r.values[i]?.toFixed(4)}</span>,
                                 })),
                                 { key: 'spread', label: 'Spread', align: 'right',
                                   render: (r: any) => <span className="mono text-amber-300">{r.spread.toFixed(4)}</span> },
                               ]} />
                      </Section>
                    )}
                  </>
                )}
              </div>
            )}

            {tab === 'script' && (
              <Section title="Reproduce this in COBRApy"
                       subtitle="The same calls the backend just made. Run it anywhere COBRApy is installed.">
                <Code filename="bioide_fba.py" language="python" code={scriptFor(modelId, bounds, knockouts, geneKOs, objective, parsimonious, target)} />
              </Section>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

function NetworkView({ graph }: { graph: any }) {
  const nodes = graph.nodes ?? []
  const edges = graph.edges ?? []
  const pos = useMemo(() => layout(nodes, edges), [graph])
  const maxFlux = Math.max(...nodes.filter((n: any) => n.type === 'reaction').map((n: any) => Math.abs(n.flux ?? 0)), 1e-9)

  return (
    <Section title="Metabolic network, coloured by flux"
             subtitle={graph.note}>
      <svg viewBox="0 0 1000 620" className="w-full rounded-lg border border-line bg-bg">
        {edges.map((e: any, i: number) => {
          const a = pos[e.source], b = pos[e.target]
          if (!a || !b) return null
          const w = 0.5 + 2.6 * Math.sqrt((e.flux ?? 0) / maxFlux)
          return <line key={i} x1={a.x} y1={a.y} x2={b.x} y2={b.y}
                       stroke={e.flux > 1e-9 ? '#38BDF8' : '#263449'}
                       strokeOpacity={e.flux > 1e-9 ? 0.55 : 0.3} strokeWidth={w} />
        })}
        {nodes.map((n: any) => {
          const p = pos[n.id]
          if (!p) return null
          const isR = n.type === 'reaction'
          const mag = Math.abs(n.flux ?? 0)
          const active = isR && mag > 1e-9
          return (
            <g key={n.id}>
              {isR ? (
                <rect x={p.x - 5} y={p.y - 5} width="10" height="10" rx="2"
                      fill={active ? '#38BDF8' : '#263449'}
                      fillOpacity={active ? Math.max(0.35, Math.sqrt(mag / maxFlux)) : 0.7}
                      stroke={active ? '#7DD3FC' : '#334155'} strokeWidth="0.8" />
              ) : (
                <circle cx={p.x} cy={p.y} r="3.2" fill="#34D399" fillOpacity="0.75" />
              )}
              <title>{isR ? `${n.id} — ${n.name}\nflux ${n.flux}` : `${n.id} — ${n.label} ${n.formula ?? ''}`}</title>
              {(active && mag / maxFlux > 0.1) && (
                <text x={p.x + 8} y={p.y + 3} fontSize="8.5" fill="#94A3B8" className="mono">{n.label}</text>
              )}
            </g>
          )
        })}
      </svg>
      <div className="mt-2 flex flex-wrap gap-3 text-[10.5px] text-muted">
        <span className="flex items-center gap-1.5"><span className="inline-block h-2.5 w-2.5 rounded-sm bg-accent" />reaction (opacity ∝ |flux|)</span>
        <span className="flex items-center gap-1.5"><span className="inline-block h-2.5 w-2.5 rounded-full bg-accent2" />metabolite</span>
        <span>{graph.omitted_hub_metabolites?.length ?? 0} cofactor hubs omitted</span>
      </div>
    </Section>
  )
}

/** Small deterministic force-directed layout. Good enough to show flux structure;
 *  a curated Escher map is clearer for canonical pathways. */
function layout(nodes: any[], edges: any[]) {
  const W = 1000, H = 620
  const pos: Record<string, { x: number; y: number; vx: number; vy: number }> = {}
  nodes.forEach((n, i) => {
    const a = (i / Math.max(nodes.length, 1)) * Math.PI * 2
    const r = 150 + 110 * ((i * 2654435761 % 100) / 100)
    pos[n.id] = { x: W / 2 + Math.cos(a) * r, y: H / 2 + Math.sin(a) * r, vx: 0, vy: 0 }
  })
  const list = Object.keys(pos)
  for (let step = 0; step < 220; step++) {
    const k = 1 - step / 240
    for (let i = 0; i < list.length; i++) {
      for (let j = i + 1; j < list.length; j++) {
        const a = pos[list[i]], b = pos[list[j]]
        let dx = a.x - b.x, dy = a.y - b.y
        let d2 = dx * dx + dy * dy
        if (d2 < 1) { dx = (i - j) || 1; dy = 1; d2 = 2 }
        if (d2 > 60000) continue
        const f = 900 / d2
        a.vx += dx * f; a.vy += dy * f
        b.vx -= dx * f; b.vy -= dy * f
      }
    }
    for (const e of edges) {
      const a = pos[e.source], b = pos[e.target]
      if (!a || !b) continue
      const dx = b.x - a.x, dy = b.y - a.y
      const d = Math.sqrt(dx * dx + dy * dy) || 1
      const f = (d - 52) * 0.016
      a.vx += dx / d * f * 10; a.vy += dy / d * f * 10
      b.vx -= dx / d * f * 10; b.vy -= dy / d * f * 10
    }
    for (const id of list) {
      const p = pos[id]
      p.vx += (W / 2 - p.x) * 0.0022
      p.vy += (H / 2 - p.y) * 0.0022
      p.x += Math.max(-14, Math.min(14, p.vx * k * 0.4))
      p.y += Math.max(-14, Math.min(14, p.vy * k * 0.4))
      p.vx *= 0.82; p.vy *= 0.82
      p.x = Math.max(24, Math.min(W - 24, p.x))
      p.y = Math.max(20, Math.min(H - 20, p.y))
    }
  }
  return pos
}

function scriptFor(modelId: string, bounds: Bounds, kos: string[], gkos: string[],
                   objective: string, pfba: boolean, target: string) {
  const loader = ['e_coli_core', 'iJO1366', 'salmonella'].includes(modelId)
    ? `load_model(${JSON.stringify(modelId === 'e_coli_core' ? 'textbook' : modelId)})`
    : `read_sbml_model("your_model.xml")`
  const lines = [
    '"""Generated by BioIDE. Reproduces the analysis configured in the Modelling workspace."""',
    'import cobra',
    'from cobra.io import load_model, read_sbml_model',
    'from cobra.flux_analysis import flux_variability_analysis, pfba, single_gene_deletion, production_envelope',
    '',
    `model = ${loader}`,
    'print(f"cobrapy {cobra.__version__}: {len(model.reactions)} reactions, {len(model.genes)} genes")',
    '',
    '# Modifications are applied inside a context manager, so the base model is not mutated.',
    'with model:',
  ]
  for (const [rid, [lb, ub]] of Object.entries(bounds)) lines.push(`    model.reactions.${rid}.bounds = (${lb}, ${ub})`)
  for (const r of kos) lines.push(`    model.reactions.get_by_id(${JSON.stringify(r)}).knock_out()`)
  for (const g of gkos) lines.push(`    model.genes.get_by_id(${JSON.stringify(g)}).knock_out()`)
  if (objective) lines.push(`    model.objective = ${JSON.stringify(objective)}`)
  lines.push(
    `    solution = ${pfba ? 'pfba(model)' : 'model.optimize()'}`,
    '    print("status:", solution.status, "objective:", solution.objective_value)',
    '',
    '    # Bound the answer before quoting any single flux.',
    '    fva = flux_variability_analysis(model, fraction_of_optimum=0.9)',
    '    print(fva.assign(span=fva.maximum - fva.minimum).sort_values("span", ascending=False).head(15))',
    '',
    '    # In-silico essentiality under this medium.',
    '    deletions = single_gene_deletion(model)',
    '    wt = solution.objective_value',
    '    print(deletions.assign(ratio=deletions.growth / wt).sort_values("ratio").head(15))',
    '',
    `    # Growth versus product trade-off.`,
    `    envelope = production_envelope(model, reactions=[${JSON.stringify(target)}], points=20)`,
    '    print(envelope.head())',
    '',
    '# Reminder: these are predictions under an assumed objective and medium, not measurements.',
  )
  return lines.join('\n')
}
