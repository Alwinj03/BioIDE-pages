import React, { useCallback, useEffect, useMemo, useState } from 'react'
import ReactFlow, {
  addEdge, Background, Controls, Handle, MiniMap, Position, applyEdgeChanges, applyNodeChanges,
  type Connection, type Edge, type EdgeChange, type Node, type NodeChange,
} from 'reactflow'
import 'reactflow/dist/style.css'
import { api } from '../lib/api'
import { useAsync } from '../lib/useAsync'
import { Code, Empty, ErrorBox, ExecBadge, Icon, I, Section, Spinner, Tabs } from '../components/ui'

const EXEC_COLOUR: Record<string, string> = {
  native: '#34D399', local: '#38BDF8', local_db: '#FBBF24', external: '#94A3B8',
  input: '#475569', io: '#475569', script: '#A78BFA',
}

function StepNode({ data, selected }: any) {
  const c = EXEC_COLOUR[data.execution] ?? '#475569'
  const unfilled = Object.entries(data.params ?? {}).filter(([, v]) => typeof v === 'string' && /<.+>/.test(v))
  return (
    <div className={`w-[228px] rounded-lg border-2 bg-panel shadow-lg transition-all ${selected ? 'border-accent' : 'border-line'}`}>
      <Handle type="target" position={Position.Top} />
      <div className="h-1 rounded-t" style={{ background: c }} />
      <div className="p-2.5">
        <div className="flex items-start justify-between gap-1.5">
          <div className="text-[11.5px] font-semibold leading-snug text-ink">{data.label}</div>
          {data.status === 'not_run' && <span className="mt-0.5 shrink-0 text-[9px] text-muted">not run</span>}
        </div>
        {data.tool_name && <div className="mono mt-1 text-[10px] text-accent">{data.tool_name}</div>}
        <div className="mt-1.5"><ExecBadge kind={data.execution} /></div>
        <div className="mono mt-1.5 space-y-0.5 text-[9.5px] text-muted">
          {data.inputs?.length > 0 && <div>in: {data.inputs.join(', ')}</div>}
          {data.outputs?.length > 0 && <div>out: {data.outputs.join(', ')}</div>}
        </div>
        {unfilled.length > 0 && (
          <div className="mt-1.5 flex items-center gap-1 text-[9.5px] text-amber-300">
            <Icon d={I.warn} className="h-2.5 w-2.5" />{unfilled.length} parameter{unfilled.length > 1 ? 's' : ''} to fill
          </div>
        )}
      </div>
      <Handle type="source" position={Position.Bottom} />
    </div>
  )
}

const nodeTypes = { step: StepNode }

export function Workflows({ projectId, pending }: { projectId: string | null; pending?: any }) {
  const [objective, setObjective] = useState('Perform metagenomic functional profiling and identify carbohydrate-active enzymes')
  const [template, setTemplate] = useState<string>('')
  const [nodes, setNodes] = useState<Node[]>([])
  const [edges, setEdges] = useState<Edge[]>([])
  const [wf, setWf] = useState<any>(null)
  const [selected, setSelected] = useState<string | null>(null)
  const [tab, setTab] = useState('validation')
  const [target, setTarget] = useState('snakemake')

  const templates = useAsync<any>(() => api.get('/api/workflow/templates'), true)
  const gen = useAsync<any>((o: string, t?: string) => api.post('/api/workflow/generate', { objective: o, template: t || null }))
  const validate = useAsync<any>((w: any) => api.post('/api/workflow/validate', { wf: w }))
  const exportWf = useAsync<any>((w: any, t: string) => api.post('/api/workflow/export', { wf: w, target: t }))
  const samples = useAsync<any>((id: string) => api.get(`/api/samples/${id}`))

  const place = (w: any) => {
    const order: string[] = w.validation?.order ?? w.nodes.map((n: any) => n.id)
    const depth: Record<string, number> = {}
    for (const id of order) {
      const parents = w.edges.filter((e: any) => e.target === id).map((e: any) => e.source)
      depth[id] = parents.length ? Math.max(...parents.map((p: string) => (depth[p] ?? 0) + 1)) : 0
    }
    const byDepth: Record<number, string[]> = {}
    for (const [id, d] of Object.entries(depth)) (byDepth[d] ??= []).push(id)
    setNodes(w.nodes.map((n: any) => {
      const d = depth[n.id] ?? 0
      const row = byDepth[d]
      const i = row.indexOf(n.id)
      return {
        id: n.id, type: 'step', data: n,
        position: { x: 60 + i * 268 - (row.length - 1) * 134 + 420, y: 40 + d * 168 },
      }
    }))
    setEdges(w.edges.map((e: any, i: number) => ({
      id: `e${i}`, source: e.source, target: e.target, animated: false,
      style: { stroke: '#38587a', strokeWidth: 1.6 },
      markerEnd: { type: 'arrowclosed' as any, color: '#38587a' },
    })))
    setWf(w)
  }

  const generate = async (o?: string, t?: string) => {
    const w = await gen.run(o ?? objective, t ?? template)
    if (w) place(w)
  }

  useEffect(() => {
    if (pending?.sample) {
      samples.run(pending.sample).then((s: any) => {
        if (s?.workflow) { setObjective(s.objective); setTemplate(s.workflow_template); place(s.workflow) }
      })
    } else if (pending?.body?.objective) {
      setObjective(pending.body.objective)
      void generate(pending.body.objective, pending.body.template)
    } else if (!wf) {
      void generate()
    }
  }, [pending])

  const current = useMemo(() => {
    if (!wf) return null
    return { ...wf, nodes: nodes.map(n => n.data), edges: edges.map(e => ({ source: e.source, target: e.target })) }
  }, [wf, nodes, edges])

  const onNodesChange = useCallback((c: NodeChange[]) => setNodes(n => applyNodeChanges(c, n)), [])
  const onEdgesChange = useCallback((c: EdgeChange[]) => setEdges(e => applyEdgeChanges(c, e)), [])
  const onConnect = useCallback((c: Connection) => setEdges(e => addEdge({
    ...c, style: { stroke: '#38587a', strokeWidth: 1.6 }, markerEnd: { type: 'arrowclosed' as any, color: '#38587a' },
  }, e)), [])

  const addStep = () => {
    const id = `step_${Date.now().toString(36).slice(-4)}`
    setNodes(n => [...n, {
      id, type: 'step',
      data: { id, label: 'New step', kind: 'script', execution: 'script', inputs: [], outputs: [], params: {}, status: 'not_run' },
      position: { x: 560, y: 40 + n.length * 40 },
    }])
    setSelected(id)
  }
  const deleteSelected = () => {
    if (!selected) return
    setNodes(n => n.filter(x => x.id !== selected))
    setEdges(e => e.filter(x => x.source !== selected && x.target !== selected))
    setSelected(null)
  }
  const updateNode = (id: string, patch: any) =>
    setNodes(n => n.map(x => x.id === id ? { ...x, data: { ...x.data, ...patch } } : x))

  const sel = nodes.find(n => n.id === selected)?.data
  const v = validate.data ?? wf?.validation

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex flex-wrap items-end gap-2 border-b border-line p-3">
        <div className="min-w-[320px] flex-1">
          <label className="label">Objective</label>
          <input className="input mt-1" value={objective} onChange={e => setObjective(e.target.value)}
                 onKeyDown={e => e.key === 'Enter' && generate()} />
        </div>
        <div>
          <label className="label">Template</label>
          <select className="input mt-1 !w-56" value={template} onChange={e => setTemplate(e.target.value)}>
            <option value="">auto-classify</option>
            {templates.data?.templates?.map((t: any) => (
              <option key={t.id} value={t.id}>{t.title}</option>
            ))}
          </select>
        </div>
        <button className="btn-primary" onClick={() => generate()} disabled={gen.loading}>
          <Icon d={I.flow} className="h-3.5 w-3.5" />{gen.loading ? 'Generating…' : 'Generate'}
        </button>
        <div className="ml-auto flex gap-1">
          <button className="btn" onClick={addStep}><Icon d={I.up} className="h-3.5 w-3.5" />Add step</button>
          <button className="btn" onClick={deleteSelected} disabled={!selected}>
            <Icon d={I.trash} className="h-3.5 w-3.5" />Delete
          </button>
          <button className="btn" onClick={() => current && validate.run(current)} disabled={!current}>
            <Icon d={I.check} className="h-3.5 w-3.5" />Validate
          </button>
        </div>
      </div>

      {gen.error && <div className="p-4"><ErrorBox error={gen.error} /></div>}

      <div className="flex min-h-0 flex-1">
        <div className="min-w-0 flex-1">
          {nodes.length === 0 && !gen.loading ? (
            <div className="p-6"><Empty title="No workflow yet" icon={I.flow}
                                       body="Describe an objective above. BioIDE matches it against workflow templates with explicit keyword rules, then builds a DAG you can edit." /></div>
          ) : (
            <ReactFlow
              nodes={nodes} edges={edges} nodeTypes={nodeTypes}
              onNodesChange={onNodesChange} onEdgesChange={onEdgesChange} onConnect={onConnect}
              onNodeClick={(_, n) => setSelected(n.id)}
              onPaneClick={() => setSelected(null)}
              fitView proOptions={{ hideAttribution: true }}
              defaultEdgeOptions={{ type: 'smoothstep' }}>
              <Background color="#1c2941" gap={22} size={1} />
              <Controls showInteractive={false} />
              <MiniMap pannable zoomable
                       style={{ background: '#111827', border: '1px solid #263449' }}
                       nodeColor={(n: any) => EXEC_COLOUR[n.data?.execution] ?? '#475569'}
                       maskColor="rgba(11,16,32,0.75)" />
            </ReactFlow>
          )}
        </div>

        <div className="w-[400px] shrink-0 overflow-y-auto border-l border-line">
          <Tabs active={tab} onChange={setTab} tabs={[
            { id: 'validation', label: 'Validation', badge: v?.warnings?.length || undefined },
            { id: 'step', label: 'Step' },
            { id: 'export', label: 'Export' },
            { id: 'notes', label: 'Notes' },
          ]} />

          <div className="space-y-3 p-3">
            {tab === 'validation' && (
              <>
                {validate.loading && <Spinner />}
                {!v && <Empty title="Generate a workflow first" icon={I.check} />}
                {v && (
                  <>
                    <div className={`rounded-lg border p-3 ${v.ok ? 'border-accent2/40 bg-accent2/[0.07]' : 'border-rose-500/40 bg-rose-500/[0.07]'}`}>
                      <div className="flex items-center gap-2 text-xs font-semibold">
                        <Icon d={v.ok ? I.check : I.x} className={`h-4 w-4 ${v.ok ? 'text-accent2' : 'text-rose-400'}`} />
                        {v.ok ? 'Structurally valid DAG' : 'Structural errors'}
                      </div>
                      {v.errors?.length > 0 && (
                        <ul className="mt-1.5 space-y-1 pl-5">
                          {v.errors.map((e: string, i: number) => (
                            <li key={i} className="list-disc text-[11.5px] text-rose-200/90">{e}</li>
                          ))}
                        </ul>
                      )}
                    </div>

                    <div className="grid grid-cols-3 gap-2">
                      {[
                        ['Runs here', v.executable_here?.length ?? 0, 'text-accent2'],
                        ['Your machine', v.needs_local_agent?.length ?? 0, 'text-accent'],
                        ['External', v.needs_external?.length ?? 0, 'text-muted'],
                      ].map(([l, n, c]: any) => (
                        <div key={l} className="panel-tight px-2 py-1.5">
                          <div className="text-[9.5px] font-semibold uppercase tracking-wider text-muted">{l}</div>
                          <div className={`mono text-base ${c}`}>{n}</div>
                        </div>
                      ))}
                    </div>

                    {v.warnings?.length > 0 && (
                      <div className="rounded-lg border border-amber-500/25 bg-amber-500/[0.05] p-3">
                        <div className="flex items-center gap-2 text-xs font-semibold text-amber-200">
                          <Icon d={I.warn} className="h-3.5 w-3.5" />{v.warnings.length} things to resolve
                        </div>
                        <ul className="mt-1.5 space-y-1.5 pl-5">
                          {v.warnings.map((w: string, i: number) => (
                            <li key={i} className="list-disc text-[11px] leading-relaxed text-amber-100/80">{w}</li>
                          ))}
                        </ul>
                      </div>
                    )}

                    {v.order?.length > 0 && (
                      <div className="panel-tight p-2">
                        <div className="label">Topological execution order</div>
                        <ol className="mono mt-1 space-y-0.5 text-[10.5px] text-muted">
                          {v.order.map((id: string, i: number) => {
                            const n = nodes.find(x => x.id === id)?.data
                            return <li key={id}>{i + 1}. {id} <span className="text-muted/60">— {n?.label}</span></li>
                          })}
                        </ol>
                      </div>
                    )}
                  </>
                )}
              </>
            )}

            {tab === 'step' && (
              !sel ? <Empty title="Select a step" body="Click a node on the canvas to edit it." icon={I.flow} /> : (
                <div className="space-y-3">
                  <div>
                    <label className="label">Label</label>
                    <input className="input mt-1" value={sel.label}
                           onChange={e => updateNode(sel.id, { label: e.target.value })} />
                  </div>
                  <div>
                    <label className="label">Execution class</label>
                    <select className="input mt-1" value={sel.execution}
                            onChange={e => updateNode(sel.id, { execution: e.target.value })}>
                      {['native', 'local', 'local_db', 'external', 'script', 'input'].map(k => <option key={k}>{k}</option>)}
                    </select>
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <label className="label">Inputs</label>
                      <input className="input mt-1 mono" value={(sel.inputs ?? []).join(', ')}
                             onChange={e => updateNode(sel.id, { inputs: e.target.value.split(/,\s*/).filter(Boolean) })} />
                    </div>
                    <div>
                      <label className="label">Outputs</label>
                      <input className="input mt-1 mono" value={(sel.outputs ?? []).join(', ')}
                             onChange={e => updateNode(sel.id, { outputs: e.target.value.split(/,\s*/).filter(Boolean) })} />
                    </div>
                  </div>
                  {sel.tool && (
                    <div className="panel-tight p-2">
                      <div className="label">Tool</div>
                      <div className="mono mt-0.5 text-[11px] text-accent">{sel.tool_name}</div>
                      <p className="mt-1 text-[11px] leading-relaxed text-muted">{sel.tool_description}</p>
                      {sel.resources && <p className="mt-1 text-[10.5px] text-amber-200/70">{sel.resources}</p>}
                      {sel.docs && <a href={sel.docs} target="_blank" rel="noreferrer" className="link mt-1 inline-flex items-center gap-1 text-[10.5px]">
                        <Icon d={I.link} className="h-3 w-3" />documentation</a>}
                      {sel.alternatives?.length > 0 && (
                        <div className="mt-1.5 flex flex-wrap gap-1">
                          {sel.alternatives.map((a: string) => <span key={a} className="chip">{a}</span>)}
                        </div>
                      )}
                    </div>
                  )}
                  <div>
                    <label className="label">Parameters</label>
                    <div className="mt-1 space-y-1">
                      {Object.entries(sel.params ?? {}).map(([k, val]) => (
                        <div key={k} className="flex items-center gap-1.5">
                          <span className="mono w-32 shrink-0 truncate text-[10.5px] text-muted" title={k}>{k}</span>
                          <input className="input !py-1 mono text-[11px]" value={String(val)}
                                 onChange={e => updateNode(sel.id, { params: { ...sel.params, [k]: e.target.value } })} />
                        </div>
                      ))}
                      {Object.keys(sel.params ?? {}).length === 0 && (
                        <div className="text-[11px] text-muted">No parameters declared for this step.</div>
                      )}
                    </div>
                  </div>
                  {Object.entries(sel.install ?? {}).length > 0 && (
                    <div className="panel-tight p-2">
                      <div className="label">Install</div>
                      {Object.entries(sel.install).map(([mgr, cmd]: any) => (
                        <div key={mgr} className="mono mt-1 break-words text-[10px] text-muted">
                          <span className="text-accent">{mgr}</span> · {cmd}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )
            )}

            {tab === 'export' && (
              <div className="space-y-3">
                <div className="flex flex-wrap gap-1">
                  {['snakemake', 'nextflow', 'bash', 'python', 'json'].map(t => (
                    <button key={t} onClick={() => { setTarget(t); current && exportWf.run(current, t) }}
                            className={`btn px-2 py-1 text-[11px] ${target === t ? 'border-accent text-accent' : ''}`}>
                      {t}
                    </button>
                  ))}
                </div>
                {exportWf.loading && <Spinner />}
                {exportWf.error && <ErrorBox error={exportWf.error} />}
                {!exportWf.data && !exportWf.loading && (
                  <Empty title="Pick an export target" icon={I.code}
                         body="BioIDE writes real engine files. It defines no workflow language of its own." />
                )}
                {exportWf.data && (
                  <>
                    <div className="rounded-lg border border-amber-500/25 bg-amber-500/[0.05] p-2 text-[11px] leading-relaxed text-amber-100/80">
                      {exportWf.data.disclaimer} Placeholders in angle brackets and braces are yours to fill.
                    </div>
                    <Code code={exportWf.data.code} filename={exportWf.data.filename}
                          language={exportWf.data.language} maxH="max-h-[520px]" />
                  </>
                )}
              </div>
            )}

            {tab === 'notes' && (
              <div className="space-y-2">
                {wf?.notes?.map((n: string, i: number) => (
                  <div key={i} className="panel-tight p-2 text-[11.5px] leading-relaxed text-muted">{n}</div>
                ))}
                {wf?.classification && (
                  <div className="panel-tight p-2">
                    <div className="label">How this template was chosen</div>
                    <div className="mono mt-1 text-[10.5px] text-muted">{wf.classification.method}</div>
                    {wf.classification.candidates?.map((c: any) => (
                      <div key={c.template} className="mt-1 text-[10.5px] text-muted">
                        <span className={c.template === wf.template ? 'text-accent' : ''}>{c.template}</span>
                        {' '}· score {c.score} · matched {c.matched_terms.join(', ')}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
