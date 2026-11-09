import React, { useEffect, useState } from 'react'
import { api } from '../lib/api'
import { useAsync } from '../lib/useAsync'
import { Code, Empty, ErrorBox, ExecBadge, Icon, I, Section, Spinner, Stat, Table, Tabs } from '../components/ui'

export function Projects({ projectId, setProjectId, pending, onNavigate }: {
  projectId: string | null
  setProjectId: (id: string | null) => void
  pending?: any
  onNavigate: (w: string, p?: any) => void
}) {
  const [tab, setTab] = useState('overview')
  const [newName, setNewName] = useState('')
  const [newObjective, setNewObjective] = useState('')

  const list = useAsync<any>(() => api.get('/api/projects'), true)
  const detail = useAsync<any>((id: string) => api.get(`/api/projects/${id}`))
  const samples = useAsync<any>(() => api.get('/api/samples'), true)
  const sample = useAsync<any>((id: string) => api.get(`/api/samples/${id}`))
  const openSample = useAsync<any>((id: string) => api.post(`/api/samples/${id}/open`))
  const create = useAsync<any>((body: any) => api.post('/api/projects', body))
  const report = useAsync<string>((id: string) => api.get(`/api/projects/${id}/report`))

  const refresh = async () => { await list.run(); if (projectId) void detail.run(projectId) }
  useEffect(() => { if (projectId) void detail.run(projectId) }, [projectId])

  useEffect(() => {
    if (pending?.openSample || pending?.sample) {
      const sid = pending.openSample ?? pending.sample
      void sample.run(sid)
      openSample.run(sid).then(async (r: any) => {
        if (r?.project?.id) { setProjectId(r.project.id); await refresh() }
      })
      if (pending.tab) setTab(pending.tab)
    }
  }, [pending])

  const doCreate = async () => {
    if (!newName.trim()) return
    const p = await create.run({ name: newName, objective: newObjective })
    if (p?.id) { setProjectId(p.id); setNewName(''); setNewObjective(''); await refresh() }
  }

  const remove = async (id: string) => {
    await api.del(`/api/projects/${id}`)
    if (projectId === id) setProjectId(null)
    await refresh()
  }

  const d = detail.data
  const s = sample.data

  return (
    <div className="flex h-full min-h-0">
      <div className="w-[300px] shrink-0 space-y-3 overflow-y-auto border-r border-line p-3">
        <Section title="Projects" className="!p-3"
                 right={<button className="btn-ghost" onClick={refresh}><Icon d={I.refresh} className="h-3 w-3" /></button>}>
          {list.loading && <Spinner />}
          {list.error && <ErrorBox error={list.error} />}
          <div className="space-y-1">
            {list.data?.projects?.length === 0 && (
              <p className="text-[11px] text-muted">No projects yet. Open a sample below or create one.</p>
            )}
            {list.data?.projects?.map((p: any) => (
              <div key={p.id} className={`group rounded-lg border px-2 py-1.5 transition-colors ${
                projectId === p.id ? 'border-accent bg-accent/[0.07]' : 'border-line bg-bg hover:border-accent/50'}`}>
                <button className="w-full text-left" onClick={() => { setProjectId(p.id); if (p.sample_id) void sample.run(p.sample_id) }}>
                  <div className="text-[11.5px] font-medium text-ink">{p.name}</div>
                  <div className="mono mt-0.5 text-[9.5px] text-muted">
                    {p.id} · {new Date(p.updated * 1000).toLocaleDateString()}
                  </div>
                </button>
                <button className="btn-ghost mt-1 opacity-0 transition-opacity group-hover:opacity-100"
                        onClick={() => remove(p.id)}>
                  <Icon d={I.trash} className="h-3 w-3" />delete
                </button>
              </div>
            ))}
          </div>

          <div className="mt-3 space-y-1.5 border-t border-line pt-3">
            <label className="label">New project</label>
            <input className="input" placeholder="Project name" value={newName} onChange={e => setNewName(e.target.value)} />
            <input className="input" placeholder="Research objective (optional)" value={newObjective}
                   onChange={e => setNewObjective(e.target.value)} />
            <button className="btn w-full justify-center" onClick={doCreate} disabled={!newName.trim() || create.loading}>
              <Icon d={I.folder} className="h-3.5 w-3.5" />Create
            </button>
          </div>
        </Section>

        <Section title="Sample projects" className="!p-3">
          <div className="space-y-1">
            {samples.data?.samples?.map((sp: any) => (
              <button key={sp.id}
                      onClick={() => { void sample.run(sp.id); openSample.run(sp.id).then(async (r: any) => { if (r?.project?.id) { setProjectId(r.project.id); await refresh() } }) }}
                      className="w-full rounded-lg border border-line bg-bg px-2 py-1.5 text-left hover:border-accent/50">
                <div className="mono text-[9.5px] text-accent">PROJECT {sp.number}</div>
                <div className="text-[11.5px] font-medium text-ink">{sp.title}</div>
              </button>
            ))}
          </div>
        </Section>
      </div>

      <div className="min-w-0 flex-1 overflow-y-auto">
        {!projectId ? (
          <div className="p-6">
            <Empty title="No project selected" icon={I.folder}
                   body="A project collects your runs, artifacts, literature and reports, so the work stays reproducible. Open a sample project or create one." />
          </div>
        ) : (
          <div className="space-y-4 p-4">
            {detail.loading && <Spinner />}
            {detail.error && <ErrorBox error={detail.error} />}
            {d && (
              <>
                <div>
                  <h2 className="text-lg font-semibold">{d.name}</h2>
                  {d.objective && <p className="mt-1 text-[12.5px] leading-relaxed text-muted">{d.objective}</p>}
                  <div className="mono mt-1 text-[10px] text-muted">
                    {d.id} · created {new Date(d.created * 1000).toLocaleString()}
                  </div>
                </div>

                <div className="grid gap-2 sm:grid-cols-4">
                  <Stat label="Recorded runs" value={d.runs?.length ?? 0} />
                  <Stat label="Succeeded" value={d.runs?.filter((r: any) => r.status === 'succeeded').length ?? 0} tone="good" />
                  <Stat label="Failed" value={d.runs?.filter((r: any) => r.status === 'failed').length ?? 0}
                        tone={(d.runs?.filter((r: any) => r.status === 'failed').length ?? 0) > 0 ? 'bad' : 'default'} />
                  <Stat label="Papers saved" value={d.papers?.length ?? 0} />
                </div>

                <Tabs active={tab} onChange={setTab} tabs={[
                  { id: 'overview', label: 'Sample guide' },
                  { id: 'runs', label: 'Provenance', badge: d.runs?.length },
                  { id: 'data', label: 'Data' },
                  { id: 'literature', label: 'Literature', badge: d.papers?.length },
                  { id: 'report', label: 'Report' },
                ]} />

                {tab === 'overview' && (
                  s ? (
                    <div className="space-y-4">
                      <div className="rounded-lg border border-accent/30 bg-accent/[0.06] p-3 text-[11.5px] leading-relaxed text-accent/90">
                        {s.honesty_note}
                      </div>
                      <Section title="Objective"><p className="text-[12.5px] leading-relaxed text-muted">{s.objective}</p></Section>
                      <Section title="Learning objectives">
                        <ul className="space-y-1 pl-5">
                          {s.learning_objectives?.map((l: string, i: number) => (
                            <li key={i} className="list-disc text-[12px] leading-relaxed text-muted">{l}</li>
                          ))}
                        </ul>
                      </Section>
                      <div className="grid gap-4 lg:grid-cols-2">
                        <Section title="Runs here, for real"
                                 right={<ExecBadge kind="native" />}>
                          <ul className="space-y-1 pl-5">
                            {s.runs_here?.map((r: string, i: number) => (
                              <li key={i} className="list-disc text-[11.5px] leading-relaxed text-accent2/90">{r}</li>
                            ))}
                          </ul>
                        </Section>
                        <Section title="Needs your own machine"
                                 right={<ExecBadge kind="local_db" />}>
                          <ul className="space-y-1 pl-5">
                            {s.needs_local_tools?.map((r: string, i: number) => (
                              <li key={i} className="list-disc text-[11.5px] leading-relaxed text-amber-100/80">{r}</li>
                            ))}
                          </ul>
                        </Section>
                      </div>
                      <Section title="The biology">
                        <p className="text-[12.5px] leading-relaxed text-muted">{s.biology}</p>
                      </Section>
                      <Section title="Expected outputs">
                        <div className="flex flex-wrap gap-1.5">
                          {s.expected_outputs?.map((o: string) => <span key={o} className="chip">{o}</span>)}
                        </div>
                      </Section>
                      <Section title="Start here">
                        <div className="space-y-1.5">
                          {s.entry_points?.map((e: any, i: number) => (
                            <div key={i} className="flex items-center gap-2 rounded-lg border border-line bg-bg px-3 py-2">
                              <Icon d={I.play} className="h-3 w-3 shrink-0 text-accent" />
                              <div className="min-w-0 flex-1">
                                <div className="text-[11.5px] text-ink">{e.label}</div>
                                <div className="mono text-[9.5px] text-muted">{e.method} {e.endpoint}</div>
                                {e.note && <div className="text-[10px] text-amber-200/70">{e.note}</div>}
                              </div>
                              <button className="btn shrink-0 px-2 py-1 text-[11px]"
                                      onClick={() => onNavigate(workspaceOf(s.id), { ...e, run: true, sample: s.id })}>
                                open
                              </button>
                            </div>
                          ))}
                        </div>
                      </Section>
                    </div>
                  ) : (
                    <Empty title="This is a project of your own" icon={I.folder}
                           body="Runs you perform in any workspace with this project selected are recorded here with full provenance." />
                  )
                )}

                {tab === 'runs' && (
                  <Section title="Every recorded execution"
                           subtitle="Written at the moment each library call ran. A result that is not here was not produced by BioIDE."
                           right={<button className="btn-ghost" onClick={() => detail.run(projectId)}>
                             <Icon d={I.refresh} className="h-3 w-3" />refresh</button>}>
                    <Table maxH="max-h-[560px]" rows={d.runs ?? []} empty="No runs recorded for this project yet."
                           cols={[
                             { key: 'started', label: 'When',
                               render: (r: any) => <span className="mono text-[10px] text-muted">{new Date(r.started * 1000).toLocaleTimeString()}</span> },
                             { key: 'kind', label: 'Analysis', className: 'mono text-accent' },
                             { key: 'tool', label: 'Tool',
                               render: (r: any) => <span className="mono">{r.tool} <span className="text-muted">{r.tool_version}</span></span> },
                             { key: 'status', label: 'Status',
                               render: (r: any) => <span className={`chip ${r.status === 'succeeded' ? 'border-accent2/40 text-accent2'
                                 : r.status === 'failed' ? 'border-rose-500/40 text-rose-300' : 'border-line'}`}>{r.status}</span> },
                             { key: 'duration_s', label: 'Seconds', align: 'right',
                               render: (r: any) => <span className="mono">{r.duration_s ?? '—'}</span> },
                             { key: 'summary', label: 'Summary / error',
                               render: (r: any) => (
                                 <span className="mono text-[10px] text-muted">
                                   {r.error ? <span className="text-rose-300">{r.error.slice(0, 90)}</span>
                                     : JSON.stringify(r.summary)?.slice(0, 90)}
                                 </span>) },
                           ]} />
                  </Section>
                )}

                {tab === 'data' && (
                  s?.data ? (
                    <Section title="Datasets in this sample"
                             subtitle="Public, cited sources only, with a note on why each one was chosen.">
                      <div className="space-y-2">
                        {s.data.map((dd: any, i: number) => (
                          <div key={i} className="panel-tight p-3">
                            <div className="flex flex-wrap items-center gap-2">
                              <span className="text-[12.5px] font-medium text-ink">{dd.name}</span>
                              {dd.accession && <span className="chip mono">{dd.accession}</span>}
                              <span className="chip">{dd.size}</span>
                              {dd.file && (
                                <a className="btn ml-auto px-2 py-1 text-[11px]"
                                   href={`/api/samples/${s.id}/data/${dd.file}`} target="_blank" rel="noreferrer">
                                  <Icon d={I.down} className="h-3 w-3" />download
                                </a>
                              )}
                            </div>
                            <div className="mt-1 text-[11px] leading-relaxed text-muted">source: {dd.source}</div>
                            <div className="mt-1 text-[11px] leading-relaxed text-accent/80">why this one: {dd.why}</div>
                          </div>
                        ))}
                      </div>
                    </Section>
                  ) : (
                    <Empty title="No bundled data" icon={I.layers}
                           body="Upload data in any workspace with this project selected, and the run will be recorded here." />
                  )
                )}

                {tab === 'literature' && (
                  <Section title="Literature collection"
                           subtitle="Papers saved from the Research workspace, with the identifiers the provider returned.">
                    {d.papers?.length === 0 ? (
                      <Empty title="No papers saved" icon={I.book}
                             action={<button className="btn mt-2" onClick={() => onNavigate('research')}>
                               <Icon d={I.search} className="h-3.5 w-3.5" />Open Research</button>} />
                    ) : (
                      <div className="space-y-2">
                        {d.papers.map((p: any, i: number) => (
                          <div key={i} className="panel-tight p-2.5">
                            <div className="text-[12px] font-medium leading-snug text-ink">{p.title}</div>
                            <div className="mt-0.5 text-[10.5px] text-muted">
                              {(p.authors ?? []).slice(0, 3).join(', ')} · {p.year} · {p.journal}
                            </div>
                            {p.doi && <a className="link mono text-[10px]" href={`https://doi.org/${p.doi}`}
                                         target="_blank" rel="noreferrer">{p.doi}</a>}
                          </div>
                        ))}
                      </div>
                    )}
                  </Section>
                )}

                {tab === 'report' && (
                  <Section title="Project report"
                           subtitle="Assembled from the recorded runs by the backend, with no language model involved, so nothing in it can be fabricated."
                           right={<div className="flex gap-1">
                             <button className="btn px-2 py-1 text-[11px]" onClick={() => report.run(projectId)}>
                               <Icon d={I.docs} className="h-3 w-3" />Generate
                             </button>
                             <a className="btn px-2 py-1 text-[11px]" href={`/api/projects/${projectId}/export`}
                                target="_blank" rel="noreferrer">
                               <Icon d={I.down} className="h-3 w-3" />Export JSON
                             </a>
                           </div>}>
                    {report.loading && <Spinner />}
                    {report.error && <ErrorBox error={report.error} />}
                    {report.data ? (
                      <Code code={report.data} filename={`${d.name.replace(/\W+/g, '_')}_report.md`}
                            language="markdown" maxH="max-h-[560px]" />
                    ) : (
                      <Empty title="No report generated yet" icon={I.docs}
                             body="The report lists every run with its tool, version, status and duration, plus the interpretation limits that apply to each method." />
                    )}
                  </Section>
                )}
              </>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

function workspaceOf(sampleId: string): string {
  return ({
    genome_annotation: 'bioinformatics', rnaseq_de: 'omics', metagenomics: 'workflows',
    protein_structure: 'bioinformatics', metabolic_modelling: 'modelling', pathway_engineering: 'modelling',
  } as Record<string, string>)[sampleId] ?? 'projects'
}
