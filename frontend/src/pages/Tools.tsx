import React, { useMemo, useState } from 'react'
import { api } from '../lib/api'
import { useAsync } from '../lib/useAsync'
import { Code, Empty, ErrorBox, ExecBadge, Icon, I, Section, Spinner, Stat, Table, Tabs } from '../components/ui'

export function Tools({ projectId, pending }: { projectId: string | null; pending?: any }) {
  const [tab, setTab] = useState('catalogue')
  return (
    <div className="h-full min-h-0 overflow-y-auto">
      <div className="border-b border-line px-4">
        <Tabs active={tab} onChange={setTab} tabs={[
          { id: 'catalogue', label: 'Tool catalogue' },
          { id: 'recommend', label: 'Recommend for my objective' },
          { id: 'environment', label: 'This machine' },
          { id: 'terminal', label: 'Approved execution' },
        ]} />
      </div>
      {tab === 'catalogue' && <Catalogue />}
      {tab === 'recommend' && <Recommend pending={pending} />}
      {tab === 'environment' && <Environment />}
      {tab === 'terminal' && <Terminal projectId={projectId} />}
    </div>
  )
}

function Catalogue() {
  const [q, setQ] = useState('')
  const [cat, setCat] = useState('')
  const [exec, setExec] = useState('')
  const [sel, setSel] = useState<string | null>(null)

  const list = useAsync<any>(() => api.get(`/api/tools?${new URLSearchParams({
    ...(q ? { q } : {}), ...(cat ? { category: cat } : {}), ...(exec ? { execution: exec } : {}),
  })}`), false, [q, cat, exec])
  const detail = useAsync<any>((id: string) => api.get(`/api/tools/${id}`))
  const feas = useAsync<any>((id: string) => api.get(`/api/tools/${id}/feasibility`))

  React.useEffect(() => { void list.run() }, [q, cat, exec])
  const open = (id: string) => { setSel(id); void detail.run(id); void feas.run(id) }

  return (
    <div className="flex min-h-0">
      <div className="w-[380px] shrink-0 overflow-y-auto border-r border-line p-3">
        <input className="input" placeholder="Search tools, applications, alternatives…"
               value={q} onChange={e => setQ(e.target.value)} />
        <div className="mt-2 grid grid-cols-2 gap-2">
          <select className="input text-[11px]" value={cat} onChange={e => setCat(e.target.value)}>
            <option value="">all categories</option>
            {Object.keys(list.data?.categories ?? {}).map(c => <option key={c} value={c}>{c}</option>)}
          </select>
          <select className="input text-[11px]" value={exec} onChange={e => setExec(e.target.value)}>
            <option value="">all execution types</option>
            {['native', 'local', 'local_db', 'external'].map(c => <option key={c} value={c}>{c}</option>)}
          </select>
        </div>
        <div className="mt-2 text-[10.5px] text-muted">
          {list.data?.count ?? 0} tools · {list.data?.native_tools?.length ?? 0} run inside BioIDE
        </div>

        {list.loading && <div className="mt-3"><Spinner /></div>}
        {list.error && <div className="mt-3"><ErrorBox error={list.error} /></div>}
        <div className="mt-2 space-y-1.5">
          {list.data?.tools?.map((t: any) => (
            <button key={t.id} onClick={() => open(t.id)}
                    className={`w-full rounded-lg border p-2 text-left transition-colors ${
                      sel === t.id ? 'border-accent bg-accent/[0.07]' : 'border-line bg-bg hover:border-accent/50'}`}>
              <div className="flex items-start justify-between gap-2">
                <span className="text-[12px] font-medium text-ink">{t.name}</span>
                <ExecBadge kind={t.execution} />
              </div>
              <div className="mt-0.5 text-[10px] text-muted">{t.category}</div>
              <p className="mt-1 line-clamp-2 text-[10.5px] leading-snug text-muted">{t.description}</p>
            </button>
          ))}
        </div>
      </div>

      <div className="min-w-0 flex-1 overflow-y-auto p-4">
        {!sel ? (
          <Empty title="Select a tool" icon={I.gear}
                 body="Each entry says where the tool can run, what it needs on disk and in memory, and what the alternatives are." />
        ) : (
          <div className="space-y-4">
            {detail.loading && <Spinner />}
            {detail.error && <ErrorBox error={detail.error} />}
            {detail.data && (
              <>
                <div>
                  <div className="flex flex-wrap items-center gap-2">
                    <h2 className="text-lg font-semibold">{detail.data.name}</h2>
                    <ExecBadge kind={detail.data.execution} />
                    <span className="chip">{detail.data.category}</span>
                    {detail.data.languages?.map((l: string) => <span key={l} className="chip">{l}</span>)}
                  </div>
                  <p className="mt-1.5 text-[12.5px] leading-relaxed text-muted">{detail.data.description}</p>
                  <p className="mt-1 text-[11.5px] leading-relaxed text-accent/80">{detail.data.execution_meaning}</p>
                </div>

                <Section title="Biological application">
                  <p className="text-[12px] leading-relaxed text-muted">{detail.data.biological_application}</p>
                </Section>

                {feas.data && (
                  <Section title="Can it run here?"
                           subtitle={`Checked against the machine the BioIDE backend is on (${feas.data.machine.ram_total_gb} GB RAM, ${feas.data.machine.cpu_logical} logical CPUs, ${feas.data.machine.disk_free_gb} GB free).`}>
                    <div className="flex flex-wrap items-center gap-2">
                      <span className={`chip ${feas.data.installed ? 'border-accent2/40 text-accent2' : 'border-amber-500/40 text-amber-300'}`}>
                        {feas.data.installed ? 'detected' : 'not detected'}
                      </span>
                      <span className={`chip ${feas.data.can_run_now ? 'border-accent2/40 text-accent2' : 'border-line'}`}>
                        {feas.data.can_run_now ? 'can run now' : 'cannot run now'}
                      </span>
                      <span className="mono text-[10.5px] text-muted">{feas.data.detection}</span>
                    </div>
                    {feas.data.blockers?.length > 0 && (
                      <ul className="mt-2 space-y-1 pl-5">
                        {feas.data.blockers.map((b: string, i: number) => (
                          <li key={i} className="list-disc text-[11.5px] leading-relaxed text-amber-100/80">{b}</li>
                        ))}
                      </ul>
                    )}
                  </Section>
                )}

                <div className="grid gap-4 lg:grid-cols-2">
                  <Section title="Formats">
                    <div className="space-y-2">
                      <div>
                        <div className="label">Inputs</div>
                        <div className="mt-1 flex flex-wrap gap-1">
                          {detail.data.inputs.map((f: string) => <span key={f} className="chip mono">{f}</span>)}
                        </div>
                      </div>
                      <div>
                        <div className="label">Outputs</div>
                        <div className="mt-1 flex flex-wrap gap-1">
                          {detail.data.outputs.map((f: string) => <span key={f} className="chip mono">{f}</span>)}
                        </div>
                      </div>
                    </div>
                  </Section>
                  <Section title="Resources">
                    <p className="text-[11.5px] leading-relaxed text-muted">
                      {detail.data.resources || 'No specific resource constraints recorded.'}
                    </p>
                    {detail.data.notes && (
                      <p className="mt-2 border-t border-line pt-2 text-[11.5px] leading-relaxed text-amber-100/70">
                        {detail.data.notes}
                      </p>
                    )}
                  </Section>
                </div>

                <Section title="Installation"
                         subtitle="Commands only. BioIDE does not install software unless you explicitly enable and approve it.">
                  {Object.entries(detail.data.install ?? {}).length === 0 ? (
                    <p className="text-[11.5px] text-muted">No package-manager route; see the documentation.</p>
                  ) : (
                    <div className="space-y-2">
                      {Object.entries(detail.data.install).map(([mgr, cmd]: any) => (
                        <div key={mgr}>
                          <div className="label">{mgr}</div>
                          <Code code={cmd} maxH="max-h-20" />
                        </div>
                      ))}
                    </div>
                  )}
                  <a className="link mt-2 inline-flex items-center gap-1 text-[11.5px]"
                     href={detail.data.docs} target="_blank" rel="noreferrer">
                    <Icon d={I.link} className="h-3 w-3" />official documentation
                  </a>
                </Section>

                {detail.data.alternatives?.length > 0 && (
                  <Section title="Alternatives"
                           subtitle="Worth considering before committing; often one of these fits the constraint better.">
                    <div className="flex flex-wrap gap-1.5">
                      {detail.data.alternatives.map((a: string) => <span key={a} className="chip">{a}</span>)}
                    </div>
                    {detail.data.alternatives_in_catalogue?.length > 0 && (
                      <div className="mt-2 flex flex-wrap gap-1.5">
                        {detail.data.alternatives_in_catalogue.map((a: any) => (
                          <button key={a.id} className="btn px-2 py-1 text-[11px]" onClick={() => open(a.id)}>
                            {a.name} <ExecBadge kind={a.execution} />
                          </button>
                        ))}
                      </div>
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

function Recommend({ pending }: { pending?: any }) {
  const [objective, setObjective] = useState('metagenomic functional profiling')
  const [ram, setRam] = useState(8)
  const [gpu, setGpu] = useState(false)
  const rec = useAsync<any>((body: any) => api.post('/api/tools/recommend', body))

  React.useEffect(() => {
    if (pending?.body?.objective) { setObjective(pending.body.objective); }
    void rec.run({ objective: pending?.body?.objective ?? objective, ram_gb: pending?.body?.ram_gb ?? ram, has_gpu: gpu })
  }, [pending])

  return (
    <div className="space-y-4 p-4">
      <Section title="What are you trying to do?"
               subtitle="The ranking is a deterministic keyword match over the catalogue, re-ranked by what your hardware can actually run. Each result says why it matched.">
        <div className="flex flex-wrap items-end gap-3">
          <div className="min-w-[300px] flex-1">
            <label className="label">Objective</label>
            <input className="input mt-1" value={objective} onChange={e => setObjective(e.target.value)}
                   onKeyDown={e => e.key === 'Enter' && rec.run({ objective, ram_gb: ram, has_gpu: gpu })} />
          </div>
          <div>
            <label className="label">RAM (GB)</label>
            <input type="number" min="2" max="1024" className="input mt-1 !w-24 mono" value={ram}
                   onChange={e => setRam(parseInt(e.target.value) || 8)} />
          </div>
          <label className="flex items-center gap-2 pb-2 text-[11.5px] text-muted">
            <input type="checkbox" checked={gpu} onChange={e => setGpu(e.target.checked)} className="accent-accent" />
            GPU available
          </label>
          <button className="btn-primary" onClick={() => rec.run({ objective, ram_gb: ram, has_gpu: gpu })}>
            <Icon d={I.search} className="h-3.5 w-3.5" />Recommend
          </button>
        </div>
      </Section>

      {rec.loading && <Spinner />}
      {rec.error && <ErrorBox error={rec.error} />}
      {rec.data && (
        <>
          <div className="flex flex-wrap items-center gap-2">
            <span className="chip">matched categories: {rec.data.matched_categories.join(', ')}</span>
            <span className="text-[10.5px] text-muted">{rec.data.method}</span>
          </div>
          <div className="grid gap-2 md:grid-cols-2">
            {rec.data.recommendations.map((r: any) => (
              <div key={r.id} className="panel-tight p-3">
                <div className="flex items-start justify-between gap-2">
                  <span className="text-[12.5px] font-medium text-ink">{r.name}</span>
                  <ExecBadge kind={r.execution} />
                </div>
                <p className="mt-1 text-[11.5px] leading-relaxed text-muted">{r.description}</p>
                <div className="mono mt-1.5 text-[10px] text-muted/70">{r.why}</div>
                {r.warnings?.length > 0 && (
                  <ul className="mt-1.5 space-y-1 pl-4">
                    {r.warnings.map((w: string, i: number) => (
                      <li key={i} className="list-disc text-[10.5px] leading-relaxed text-amber-200/80">{w}</li>
                    ))}
                  </ul>
                )}
              </div>
            ))}
          </div>
          <div className="rounded-lg border border-line bg-bg2 p-3 text-[11.5px] leading-relaxed text-muted">
            {rec.data.caveat}
          </div>
        </>
      )}
    </div>
  )
}

function Environment() {
  const [deep, setDeep] = useState(false)
  const env = useAsync<any>((d: boolean) => api.get(`/api/environment?deep=${!!d}`))

  React.useEffect(() => { void env.run(deep) }, [deep])

  return (
    <div className="space-y-4 p-4">
      {env.loading && <Spinner label="Probing the environment…" />}
      {env.error && <ErrorBox error={env.error} />}
      {env.data && (
        <>
          <div className="rounded-lg border border-accent/30 bg-accent/[0.06] p-3 text-[11.5px] leading-relaxed text-accent/90">
            {env.data.where_this_runs}
          </div>

          <div className="grid gap-2 sm:grid-cols-6">
            <Stat label="Logical CPUs" value={env.data.resources.cpu_logical} />
            <Stat label="Physical cores" value={env.data.resources.cpu_physical ?? '—'} />
            <Stat label="RAM total" value={env.data.resources.ram_total_gb} unit="GB" />
            <Stat label="RAM available" value={env.data.resources.ram_available_gb} unit="GB" />
            <Stat label="Disk free" value={env.data.resources.disk_free_gb} unit="GB" />
            <Stat label="Python" value={env.data.backend_host.python} />
          </div>

          <div className="flex items-center gap-2">
            <label className="flex items-center gap-2 text-[11.5px] text-muted">
              <input type="checkbox" checked={deep} onChange={e => setDeep(e.target.checked)} className="accent-accent" />
              Deep probe (checks every tool in the catalogue; slower)
            </label>
            <button className="btn ml-auto px-2 py-1 text-[11px]" onClick={() => env.run(deep)}>
              <Icon d={I.refresh} className="h-3 w-3" />re-probe
            </button>
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            <Section title={`Detected tools (${Object.keys(env.data.tools_found).length})`}>
              <Table maxH="max-h-72"
                     rows={Object.entries(env.data.tools_found).map(([k, v]: any) => ({ name: k, ...v }))}
                     cols={[
                       { key: 'name', label: 'Tool', className: 'mono text-accent2' },
                       { key: 'version', label: 'Version', className: 'mono' },
                       { key: 'path', label: 'Path', className: 'mono text-[10px] text-muted' },
                     ]} />
            </Section>
            <Section title={`Not on PATH (${env.data.tools_missing.length})`}
                     subtitle="Absence here is a fact about this machine, not a judgement about the tool.">
              <div className="flex max-h-72 flex-wrap gap-1 overflow-y-auto">
                {env.data.tools_missing.map((t: string) => <span key={t} className="chip mono">{t}</span>)}
              </div>
            </Section>
          </div>

          <Section title="Python libraries">
            <div className="flex flex-wrap gap-1.5">
              {Object.entries(env.data.python_libraries).map(([k, v]: any) => (
                <span key={k} className={`chip mono ${v ? 'border-accent2/40 text-accent2' : 'border-line text-muted/60'}`}>
                  {k} {v ?? '—'}
                </span>
              ))}
            </div>
          </Section>

          {env.data.conda_environments?.length > 0 && (
            <Section title="Conda environments">
              <div className="mono space-y-0.5 text-[10.5px] text-muted">
                {env.data.conda_environments.map((e: string) => <div key={e}>{e}</div>)}
              </div>
            </Section>
          )}

          <Section title="Execution permissions">
            <div className="flex flex-wrap gap-2">
              <span className={`chip ${env.data.permissions.code_execution_enabled ? 'border-accent2/40 text-accent2' : 'border-rose-500/40 text-rose-300'}`}>
                code execution {env.data.permissions.code_execution_enabled ? 'enabled' : 'disabled'}
              </span>
              <span className={`chip ${env.data.permissions.install_execution_enabled ? 'border-amber-500/40 text-amber-300' : 'border-line'}`}>
                installs {env.data.permissions.install_execution_enabled ? 'enabled' : 'disabled'}
              </span>
            </div>
            <p className="mt-2 text-[11.5px] leading-relaxed text-muted">{env.data.permissions.note}</p>
          </Section>
        </>
      )}
    </div>
  )
}

function Terminal({ projectId }: { projectId: string | null }) {
  const [cmd, setCmd] = useState('samtools --version')
  const review = useAsync<any>((c: string) => api.post('/api/execute/review', { command: c, project_id: projectId }))
  const run = useAsync<any>((c: string, token: string) =>
    api.post('/api/execute/run', { command: c, approval_token: token, project_id: projectId }))
  const log = useAsync<any>(() => api.get('/api/execute/log'), true)

  const doRun = async () => {
    if (!review.data?.approval_token) return
    await run.run(cmd, review.data.approval_token)
    void log.run()
  }

  return (
    <div className="space-y-4 p-4">
      <Section title="Approved command execution"
               subtitle="Two steps, always. BioIDE reviews a command statically and issues a token bound to that exact string; nothing runs until you submit the token.">
        <div className="flex gap-2">
          <input className="input mono" value={cmd} onChange={e => { setCmd(e.target.value); review.reset(); run.reset() }}
                 onKeyDown={e => e.key === 'Enter' && review.run(cmd)} />
          <button className="btn shrink-0" onClick={() => review.run(cmd)} disabled={!cmd.trim() || review.loading}>
            <Icon d={I.check} className="h-3.5 w-3.5" />Review
          </button>
        </div>
        <ul className="mt-2 space-y-1 pl-5 text-[10.5px] leading-relaxed text-muted">
          <li className="list-disc">Shell metacharacters are refused outright; commands are tokenised and run without a shell.</li>
          <li className="list-disc">Destructive patterns, privilege escalation and credential paths are refused by rule.</li>
          <li className="list-disc">Install commands are refused unless the instance is configured to allow them.</li>
          <li className="list-disc">Every attempt is written to the command log below, approved or not.</li>
        </ul>

        {review.loading && <div className="mt-3"><Spinner /></div>}
        {review.error && <div className="mt-3"><ErrorBox error={review.error} /></div>}
        {review.data && (
          <div className={`mt-3 rounded-lg border p-3 ${review.data.may_execute ? 'border-accent2/40 bg-accent2/[0.06]' : 'border-rose-500/40 bg-rose-500/[0.07]'}`}>
            <div className="flex items-center gap-2 text-xs font-semibold">
              <Icon d={review.data.may_execute ? I.check : I.x}
                    className={`h-4 w-4 ${review.data.may_execute ? 'text-accent2' : 'text-rose-400'}`} />
              {review.data.may_execute ? 'Approved for execution' : 'Refused'}
            </div>
            {review.data.resolved_binary && (
              <div className="mono mt-1 text-[10.5px] text-muted">resolves to {review.data.resolved_binary}</div>
            )}
            {review.data.reasons?.length > 0 && (
              <ul className="mt-1.5 space-y-1 pl-5">
                {review.data.reasons.map((r: string, i: number) => (
                  <li key={i} className="list-disc text-[11.5px] leading-relaxed text-rose-200/90">{r}</li>
                ))}
              </ul>
            )}
            <div className="mt-2 text-[10.5px] text-muted">{review.data.note}</div>
            {review.data.may_execute && (
              <button className="btn-primary mt-2" onClick={doRun} disabled={run.loading}>
                <Icon d={I.terminal} className="h-3.5 w-3.5" />{run.loading ? 'Running…' : 'Execute with this token'}
              </button>
            )}
          </div>
        )}

        {run.error && <div className="mt-3"><ErrorBox error={run.error} /></div>}
        {run.data && (
          <div className="mt-3 space-y-2">
            <div className="flex flex-wrap items-center gap-2">
              <span className={`chip ${run.data.status === 'succeeded' ? 'border-accent2/40 text-accent2' : 'border-rose-500/40 text-rose-300'}`}>
                {run.data.status}
              </span>
              <span className="chip mono">exit {String(run.data.returncode)}</span>
              <span className="chip">{run.data.duration_s} s</span>
              <span className="mono text-[10px] text-muted">cwd {run.data.cwd}</span>
            </div>
            {run.data.stdout && <Code code={run.data.stdout} language="stdout" maxH="max-h-64" />}
            {run.data.stderr && <Code code={run.data.stderr} language="stderr" maxH="max-h-48" />}
          </div>
        )}
      </Section>

      <Section title="Command log" subtitle="Every review and execution, in order."
               right={<button className="btn-ghost" onClick={() => log.run()}><Icon d={I.refresh} className="h-3 w-3" />refresh</button>}>
        <Table maxH="max-h-80" rows={log.data?.commands ?? []} empty="No commands have been submitted."
               cols={[
                 { key: 'created', label: 'When', render: (r: any) => (
                   <span className="mono text-[10px] text-muted">{new Date(r.created * 1000).toLocaleTimeString()}</span>) },
                 { key: 'command', label: 'Command', className: 'mono text-[10.5px]' },
                 { key: 'approved', label: 'Approved', render: (r: any) => (
                   <span className={`chip ${r.approved ? 'border-accent/40 text-accent' : 'border-line'}`}>
                     {r.approved ? 'yes' : 'no'}</span>) },
                 { key: 'status', label: 'Status', render: (r: any) => (
                   <span className={`chip ${r.status === 'succeeded' ? 'border-accent2/40 text-accent2'
                     : r.status.startsWith('ref') || r.status.startsWith('rej') ? 'border-rose-500/40 text-rose-300' : 'border-line'}`}>
                     {r.status}</span>) },
                 { key: 'returncode', label: 'Exit', align: 'right',
                   render: (r: any) => <span className="mono">{r.returncode ?? '—'}</span> },
               ]} />
      </Section>
    </div>
  )
}
