import React, { useMemo, useRef, useState } from 'react'
import { api } from '../lib/api'
import { useAsync } from '../lib/useAsync'
import { Plot, PALETTE } from '../components/Plot'
import {
  Caveats, Code, Empty, ErrorBox, Icon, I, ProvenanceBadge, Section, Spinner, Stat, Table, Tabs,
} from '../components/ui'

type Loaded = { counts_csv: string | null; metadata_csv: string | null; dataset: string | null; label: string }

export function Omics({ projectId, pending }: { projectId: string | null; pending?: any }) {
  const [src, setSrc] = useState<Loaded | null>(null)
  const [design, setDesign] = useState('')
  const [contrast, setContrast] = useState<[string, string, string]>(['', '', ''])
  const [alpha, setAlpha] = useState(0.05)
  const [minCount, setMinCount] = useState(10)
  const [shrink, setShrink] = useState(true)
  const [tab, setTab] = useState('qc')
  const [lfcCut, setLfcCut] = useState(1)
  const fileRef = useRef<HTMLInputElement>(null)
  const metaRef = useRef<HTMLInputElement>(null)

  const datasets = useAsync<any>(() => api.get('/api/omics/datasets'), true)
  const dsInfo = useAsync<any>((k: string) => api.get(`/api/omics/dataset/${k}`))
  const upload = useAsync<any>((c: File, m?: File) =>
    api.upload('/api/omics/upload', m ? { counts: c, metadata: m } : { counts: c }))
  const qc = useAsync<any>((b: any) => api.post('/api/omics/qc', b))
  const pca = useAsync<any>((b: any) => api.post('/api/omics/pca', b))
  const de = useAsync<any>((b: any) => api.post('/api/omics/de', b))
  const heat = useAsync<any>((b: any) => api.post('/api/omics/heatmap', b))

  const payload = (extra: any = {}) => ({
    dataset: src?.dataset ?? null, counts_csv: src?.counts_csv ?? null,
    metadata_csv: src?.metadata_csv ?? null, project_id: projectId, ...extra,
  })

  const loadSample = async (key: string) => {
    const info = await dsInfo.run(key)
    if (!info) return
    setSrc({ dataset: key, counts_csv: null, metadata_csv: null, label: info.label })
    setDesign(info.design ?? '')
    setContrast((info.contrast ?? ['', '', '']) as [string, string, string])
    qc.reset(); pca.reset(); de.reset(); heat.reset()
    void qc.run({ dataset: key, project_id: projectId })
    void pca.run({ dataset: key, project_id: projectId })
  }

  const doUpload = async () => {
    const c = fileRef.current?.files?.[0]
    if (!c) return
    const m = metaRef.current?.files?.[0]
    const r = await upload.run(c, m)
    if (!r) return
    setSrc({ dataset: null, counts_csv: r.counts_csv, metadata_csv: r.metadata_csv, label: c.name })
    setDesign(''); setContrast(['', '', ''])
    qc.reset(); pca.reset(); de.reset(); heat.reset()
    void qc.run({ counts_csv: r.counts_csv, metadata_csv: r.metadata_csv, project_id: projectId })
    void pca.run({ counts_csv: r.counts_csv, metadata_csv: r.metadata_csv, project_id: projectId })
  }

  const runDE = async () => {
    const r = await de.run(payload({
      design, contrast: contrast.filter(Boolean).length === 3 ? contrast : null,
      alpha, min_count_sum: minCount, lfc_shrink: shrink,
    }))
    if (r?.most_significant?.length) {
      void heat.run(payload({ genes: r.most_significant.slice(0, 25).map((g: any) => g.gene) }))
    }
    setTab('de')
  }

  React.useEffect(() => { if (pending?.run || pending?.sample === 'rnaseq_de') void loadSample('airway') }, [pending])

  const volcano = useMemo(() => {
    const v = de.data?.volcano
    if (!v) return null
    const colours: Record<string, string> = {
      'not significant': '#475569', 'significant, small effect': '#94A3B8', up: '#F472B6', down: '#38BDF8',
    }
    const idx: Record<string, number[]> = { 'not significant': [], 'significant, small effect': [], up: [], down: [] }
    for (let i = 0; i < v.gene.length; i++) {
      const g = !v.significant[i] ? 'not significant'
        : Math.abs(v.log2fc[i]) < lfcCut ? 'significant, small effect'
        : v.log2fc[i] > 0 ? 'up' : 'down'
      idx[g].push(i)
    }
    return ['not significant', 'significant, small effect', 'down', 'up'].map(g => ({
      type: 'scattergl' as const, mode: 'markers' as const, name: `${g} (${idx[g].length.toLocaleString()})`,
      x: idx[g].map(i => v.log2fc[i]),
      y: idx[g].map(i => v.neglog10_padj[i]),
      text: idx[g].map(i => v.gene[i] + (v.at_precision_floor[i] ? ' (padj below double precision)' : '')),
      marker: { color: colours[g], size: g === 'up' || g === 'down' ? 5 : 3.2, opacity: 0.75 },
      hovertemplate: '%{text}<br>log2FC %{x:.3f}<br>-log10 padj %{y:.2f}<extra></extra>',
    }))
  }, [de.data, lfcCut])

  const metaCols = useMemo(() => {
    if (!de.data?.metadata?.length) {
      if (!dsInfo.data?.metadata?.length) return []
      return Object.keys(dsInfo.data.metadata[0]).filter(k => k !== 'index')
    }
    return Object.keys(de.data.metadata[0]).filter(k => k !== 'index')
  }, [de.data, dsInfo.data])

  return (
    <div className="flex h-full min-h-0">
      <div className="w-[330px] shrink-0 space-y-3 overflow-y-auto border-r border-line p-3">
        <Section title="Data source" className="!p-3">
          <div className="space-y-1.5">
            {datasets.data?.datasets?.map((d: any) => (
              <button key={d.id} onClick={() => loadSample(d.id)}
                      className={`w-full rounded-lg border px-2.5 py-2 text-left transition-colors ${
                        src?.dataset === d.id ? 'border-accent bg-accent/10' : 'border-line bg-bg hover:border-accent/50'}`}>
                <div className="text-[11.5px] font-medium text-ink">{d.label}</div>
                <div className="mt-0.5 text-[10px] leading-relaxed text-muted">{d.citation}</div>
              </button>
            ))}
          </div>
          <div className="mt-3 border-t border-line pt-3">
            <label className="label">Or upload your own</label>
            <div className="mt-1 space-y-1.5">
              <div>
                <div className="text-[10px] text-muted">raw count matrix (genes × samples)</div>
                <input ref={fileRef} type="file" accept=".csv,.tsv,.txt,.gz"
                       className="mt-0.5 w-full text-[10.5px] text-muted file:mr-2 file:rounded file:border-0 file:bg-line file:px-2 file:py-1 file:text-[10.5px] file:text-ink" />
              </div>
              <div>
                <div className="text-[10px] text-muted">sample metadata (optional, for DE)</div>
                <input ref={metaRef} type="file" accept=".csv,.tsv,.txt"
                       className="mt-0.5 w-full text-[10.5px] text-muted file:mr-2 file:rounded file:border-0 file:bg-line file:px-2 file:py-1 file:text-[10.5px] file:text-ink" />
              </div>
              <button className="btn w-full justify-center" onClick={doUpload} disabled={upload.loading}>
                <Icon d={I.up} className="h-3.5 w-3.5" />{upload.loading ? 'Uploading…' : 'Load matrix'}
              </button>
            </div>
            <p className="mt-1.5 text-[10px] leading-relaxed text-amber-200/70">
              Raw integer counts only. TPM, FPKM or already-normalised values break the negative-binomial model, and
              the QC step will tell you so rather than running anyway.
            </p>
          </div>
          {upload.error && <div className="mt-2"><ErrorBox error={upload.error} /></div>}
        </Section>

        {src && (
          <Section title="Differential expression" className="!p-3">
            <div className="space-y-2">
              <div>
                <label className="label">Design formula</label>
                <input className="input mt-1 mono" placeholder="~ condition" value={design}
                       onChange={e => setDesign(e.target.value)} />
                {metaCols.length > 0 && (
                  <div className="mt-1 flex flex-wrap gap-1">
                    {metaCols.map(c => (
                      <button key={c} className="chip hover:border-accent/60"
                              onClick={() => setDesign(d => d.includes(c) ? d : (d.trim() ? `${d} + ${c}` : `~ ${c}`))}>
                        + {c}
                      </button>
                    ))}
                  </div>
                )}
              </div>
              <div>
                <label className="label">Contrast</label>
                <div className="mt-1 grid grid-cols-3 gap-1">
                  {(['factor', 'test', 'reference'] as const).map((ph, i) => (
                    <input key={ph} className="input mono !px-2 !py-1.5 text-[11px]" placeholder={ph}
                           value={contrast[i]}
                           onChange={e => setContrast(c => { const n = [...c] as [string, string, string]; n[i] = e.target.value; return n })} />
                  ))}
                </div>
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="label">alpha</label>
                  <input type="number" step="0.01" min="0.001" max="0.5" className="input mt-1 mono"
                         value={alpha} onChange={e => setAlpha(parseFloat(e.target.value) || 0.05)} />
                </div>
                <div>
                  <label className="label">min count sum</label>
                  <input type="number" min="0" className="input mt-1 mono"
                         value={minCount} onChange={e => setMinCount(parseInt(e.target.value) || 0)} />
                </div>
              </div>
              <label className="flex items-center gap-2 text-[11px] text-muted">
                <input type="checkbox" checked={shrink} onChange={e => setShrink(e.target.checked)} className="accent-accent" />
                Apply log fold-change shrinkage
              </label>
              <button className="btn-primary w-full justify-center" onClick={runDE} disabled={de.loading || !design}>
                <Icon d={I.play} className="h-3.5 w-3.5" />{de.loading ? 'Fitting…' : 'Run PyDESeq2'}
              </button>
            </div>
          </Section>
        )}

        {dsInfo.data?.note && (
          <Caveats title="About this dataset" items={[dsInfo.data.note, dsInfo.data.licence]} />
        )}
      </div>

      <div className="min-w-0 flex-1 overflow-y-auto">
        {!src ? (
          <div className="p-6">
            <Empty title="Choose a dataset" icon={I.layers}
                   body="Load the bundled airway dataset (a real published experiment) or upload your own count matrix. Every statistic afterwards comes from PyDESeq2, numpy or scipy." />
          </div>
        ) : (
          <div className="space-y-4 p-4">
            <div className="flex flex-wrap items-center gap-2">
              <span className="chip border-accent/40 text-accent">{src.label}</span>
              {qc.data && <span className="chip">{qc.data.shape.genes.toLocaleString()} genes × {qc.data.shape.samples} samples</span>}
            </div>

            <Tabs active={tab} onChange={setTab} tabs={[
              { id: 'qc', label: 'Quality control' },
              { id: 'pca', label: 'PCA' },
              { id: 'de', label: 'Differential expression', badge: de.data?.n_significant },
              { id: 'heatmap', label: 'Heatmap' },
              { id: 'script', label: 'Script' },
            ]} />

            {tab === 'qc' && (
              <div className="space-y-3">
                {qc.loading && <Spinner />}
                {qc.error && <ErrorBox error={qc.error} />}
                {qc.data && (
                  <>
                    <div className="flex items-center gap-2">
                      <ProvenanceBadge p={qc.data.provenance} elapsed={qc.elapsed} />
                    </div>
                    {qc.data.problems?.length > 0 && (
                      <div className="rounded-lg border border-rose-500/40 bg-rose-500/[0.07] p-3">
                        <div className="flex items-center gap-2 text-xs font-semibold text-rose-300">
                          <Icon d={I.warn} className="h-3.5 w-3.5" />This matrix has problems
                        </div>
                        <ul className="mt-1.5 space-y-1 pl-5">
                          {qc.data.problems.map((p: string, i: number) => (
                            <li key={i} className="list-disc text-[11.5px] text-rose-200/90">{p}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                    <div className="grid gap-2 sm:grid-cols-4">
                      <Stat label="Genes" value={qc.data.shape.genes.toLocaleString()} />
                      <Stat label="All-zero genes" value={qc.data.genes_all_zero.toLocaleString()} />
                      <Stat label="Detected in every sample" value={qc.data.genes_detected_in_all_samples.toLocaleString()} />
                      <Stat label="Library size max/min" value={qc.data.library_size_ratio_max_min ?? '—'}
                            tone={(qc.data.library_size_ratio_max_min ?? 0) > 5 ? 'warn' : 'good'} />
                    </div>

                    <Section title="Library size and detection">
                      <Plot height={280}
                            data={[
                              { type: 'bar', name: 'library size',
                                x: qc.data.samples.map((s: any) => s.sample),
                                y: qc.data.samples.map((s: any) => s.library_size),
                                marker: { color: PALETTE[0] } },
                              { type: 'scatter', mode: 'lines+markers', name: 'detection rate', yaxis: 'y2',
                                x: qc.data.samples.map((s: any) => s.sample),
                                y: qc.data.samples.map((s: any) => s.detection_rate),
                                line: { color: PALETTE[1] } },
                            ]}
                            layout={{
                              yaxis: { title: 'total counts' },
                              yaxis2: { overlaying: 'y', side: 'right', title: 'detection rate', range: [0, 1], gridcolor: 'transparent' },
                              xaxis: { tickangle: -35 }, margin: { r: 56, b: 70 },
                            }} />
                    </Section>

                    <Section title="log2 CPM distribution per sample"
                             subtitle="A sample whose box sits well away from the others usually indicates a technical problem.">
                      <Plot height={280}
                            data={Object.entries(qc.data.log2cpm_boxplot).map(([s, v]: any, i) => ({
                              type: 'box', name: s, q1: [v.q1], median: [v.median], q3: [v.q3],
                              lowerfence: [v.min], upperfence: [v.max],
                              marker: { color: PALETTE[i % PALETTE.length] },
                            }))}
                            layout={{ yaxis: { title: 'log2 CPM' }, xaxis: { tickangle: -35 }, showlegend: false, margin: { b: 70 } }} />
                    </Section>

                    {qc.data.spearman_sample_correlation && (
                      <Section title="Sample–sample Spearman correlation"
                               subtitle="Replicates should correlate more tightly with each other than across groups.">
                        <Plot height={330}
                              data={[{
                                type: 'heatmap', z: qc.data.spearman_sample_correlation.matrix,
                                x: qc.data.spearman_sample_correlation.samples,
                                y: qc.data.spearman_sample_correlation.samples,
                                colorscale: [[0, '#0B1020'], [0.5, '#1E3A5F'], [1, '#38BDF8']],
                                hovertemplate: '%{y} vs %{x}<br>ρ = %{z:.4f}<extra></extra>',
                                colorbar: { thickness: 10, len: 0.8 },
                              }]}
                              layout={{ xaxis: { tickangle: -45 }, margin: { l: 90, b: 90 } }} />
                      </Section>
                    )}

                    <Section title="Most highly expressed genes"
                             subtitle="A handful of genes dominating the library can skew normalisation.">
                      <Table maxH="max-h-60" rows={qc.data.top_expressed_genes}
                             cols={[
                               { key: 'gene', label: 'Gene', className: 'mono text-accent' },
                               { key: 'total_counts', label: 'Total counts', align: 'right',
                                 render: (r: any) => <span className="mono">{r.total_counts.toLocaleString()}</span> },
                             ]} />
                    </Section>
                  </>
                )}
              </div>
            )}

            {tab === 'pca' && (
              <div className="space-y-3">
                {pca.loading && <Spinner />}
                {pca.error && <ErrorBox error={pca.error} />}
                {pca.data && (
                  <>
                    <div className="flex flex-wrap items-center gap-2">
                      <ProvenanceBadge p={pca.data.provenance} elapsed={pca.elapsed} />
                      <span className="chip">{pca.data.n_features_used} most variable features</span>
                      <span className="chip">{pca.data.transform}</span>
                    </div>
                    <Section title="Principal components"
                             subtitle={`PC1 ${(pca.data.explained_variance_ratio[0] * 100).toFixed(1)}% · PC2 ${(pca.data.explained_variance_ratio[1] * 100).toFixed(1)}% of variance`}>
                      <Plot height={400}
                            data={groupBy(pca.data.samples, metaCols[0]).map(([g, rows]: any, i) => ({
                              type: 'scatter', mode: 'markers+text', name: String(g),
                              x: rows.map((r: any) => r.PC1), y: rows.map((r: any) => r.PC2),
                              text: rows.map((r: any) => r.sample), textposition: 'top center',
                              textfont: { size: 9, color: '#94A3B8' },
                              marker: { size: 12, color: PALETTE[i % PALETTE.length], line: { width: 1, color: '#0B1020' } },
                            }))}
                            layout={{
                              xaxis: { title: `PC1 (${(pca.data.explained_variance_ratio[0] * 100).toFixed(1)}%)` },
                              yaxis: { title: `PC2 (${(pca.data.explained_variance_ratio[1] * 100).toFixed(1)}%)` },
                            }} />
                      <p className="mt-2 text-[11px] leading-relaxed text-muted">
                        If the samples separate by donor or batch rather than by treatment, that factor belongs in the
                        design formula.
                      </p>
                    </Section>
                    <Section title="Variance explained">
                      <Plot height={200}
                            data={[{ type: 'bar', x: pca.data.explained_variance_ratio.map((_: any, i: number) => `PC${i + 1}`),
                                     y: pca.data.explained_variance_ratio, marker: { color: PALETTE[0] } }]}
                            layout={{ yaxis: { title: 'fraction', tickformat: '.0%' } }} />
                    </Section>
                  </>
                )}
              </div>
            )}

            {tab === 'de' && (
              <div className="space-y-3">
                {de.loading && <Spinner label="Estimating dispersions and fitting…" />}
                {de.error && <ErrorBox error={de.error} hint="No results are shown because the fit did not complete." />}
                {!de.data && !de.loading && !de.error && (
                  <Empty title="No test has run" icon={I.chart}
                         body="Set a design formula and contrast on the left, then run PyDESeq2." />
                )}
                {de.data && (
                  <>
                    <div className="flex flex-wrap items-center gap-2">
                      <ProvenanceBadge p={de.data.provenance} elapsed={de.elapsed} />
                      <span className="chip">{de.data.method}</span>
                      <span className="chip mono">{de.data.design}</span>
                      <span className="chip mono">
                        {de.data.contrast.factor}: {de.data.contrast.test} vs {de.data.contrast.reference}
                      </span>
                      {!de.data.lfc_shrinkage_applied && <span className="chip border-amber-500/40 text-amber-300">no shrinkage</span>}
                    </div>
                    <div className="grid gap-2 sm:grid-cols-5">
                      <Stat label="Tested" value={de.data.genes_after_filter.toLocaleString()} />
                      <Stat label={`padj < ${de.data.alpha}`} value={de.data.n_significant.toLocaleString()} tone="good" />
                      <Stat label="Up" value={de.data.n_up.toLocaleString()} />
                      <Stat label="Down" value={de.data.n_down.toLocaleString()} />
                      <Stat label="padj = NA" value={de.data.n_padj_na.toLocaleString()} tone="warn" />
                    </div>

                    <Section title="Volcano plot"
                             right={
                               <label className="flex items-center gap-2 text-[11px] text-muted">
                                 |log2FC| ≥
                                 <input type="number" step="0.5" min="0" value={lfcCut}
                                        onChange={e => setLfcCut(parseFloat(e.target.value) || 0)}
                                        className="input !w-16 !px-1.5 !py-0.5 mono text-[11px]" />
                               </label>
                             }
                             subtitle={`All ${de.data.volcano.n_plotted.toLocaleString()} tested genes with a computed padj are plotted, so these counts match the totals above. ${de.data.volcano.n_excluded_padj_na.toLocaleString()} genes with padj = NA are absent rather than drawn at zero.${de.data.volcano.n_at_precision_floor > 0 ? ` ${de.data.volcano.n_at_precision_floor.toLocaleString()} p-values underflow double precision and sit on the capped line at the top.` : ''}`}>
                      {volcano && <Plot height={430} data={volcano}
                                        layout={{ xaxis: { title: 'log2 fold change' },
                                                  yaxis: { title: '−log10 adjusted p' },
                                                  shapes: [
                                                    { type: 'line', x0: lfcCut, x1: lfcCut, y0: 0, y1: 1, yref: 'paper', line: { color: '#263449', dash: 'dot', width: 1 } },
                                                    { type: 'line', x0: -lfcCut, x1: -lfcCut, y0: 0, y1: 1, yref: 'paper', line: { color: '#263449', dash: 'dot', width: 1 } },
                                                  ] }} />}
                    </Section>

                    <Section title="Dispersion estimates"
                             subtitle="Gene-wise dispersion against the fitted trend. A cloud far from the trend line means the fit is unreliable.">
                      <Plot height={300}
                            data={[
                              { type: 'scattergl', mode: 'markers', name: 'gene-wise',
                                x: de.data.dispersion_plot.base_mean, y: de.data.dispersion_plot.dispersion,
                                marker: { color: '#475569', size: 3, opacity: 0.5 } },
                              { type: 'scattergl', mode: 'markers', name: 'fitted trend',
                                x: de.data.dispersion_plot.base_mean, y: de.data.dispersion_plot.fitted,
                                marker: { color: PALETTE[3], size: 3, opacity: 0.8 } },
                            ]}
                            layout={{ xaxis: { title: 'mean of normalised counts', type: 'log' },
                                      yaxis: { title: 'dispersion', type: 'log' } }} />
                    </Section>

                    <Section title="Most significant genes"
                             right={<button className="btn px-2 py-1 text-[11px]" onClick={() => downloadCsv(de.data.results)}>
                               <Icon d={I.down} className="h-3 w-3" />CSV
                             </button>}>
                      <Table rows={de.data.most_significant}
                             cols={[
                               { key: 'gene', label: 'Gene', className: 'mono text-accent' },
                               { key: 'baseMean', label: 'Base mean', align: 'right',
                                 render: (r: any) => <span className="mono">{r.baseMean?.toFixed(1)}</span> },
                               { key: 'log2FoldChange', label: 'log2FC', align: 'right',
                                 render: (r: any) => <span className={`mono ${r.log2FoldChange > 0 ? 'text-pink-300' : 'text-accent'}`}>
                                   {r.log2FoldChange?.toFixed(3)}</span> },
                               { key: 'lfcSE', label: 'SE', align: 'right',
                                 render: (r: any) => <span className="mono text-muted">{r.lfcSE?.toFixed(3)}</span> },
                               { key: 'padj', label: 'padj', align: 'right',
                                 render: (r: any) => <span className="mono">{r.padj === null ? 'NA' : r.padj.toExponential(2)}</span> },
                             ]} />
                    </Section>

                    <Caveats items={de.data.caveats} />
                  </>
                )}
              </div>
            )}

            {tab === 'heatmap' && (
              <div className="space-y-3">
                {heat.loading && <Spinner />}
                {heat.error && <ErrorBox error={heat.error} />}
                {!heat.data && !heat.loading && <Empty title="Run differential expression first"
                                                       body="The heatmap shows the top genes from the last test." icon={I.layers} />}
                {heat.data && (
                  <Section title="Top differential genes, clustered"
                           subtitle={heat.data.note + ' Rows and columns ordered by hierarchical clustering.'}>
                    <Plot height={Math.max(360, heat.data.features.length * 16 + 120)}
                          data={[{
                            type: 'heatmap', z: heat.data.values, x: heat.data.samples, y: heat.data.features,
                            colorscale: [[0, '#38BDF8'], [0.5, '#0B1020'], [1, '#F472B6']], zmid: 0,
                            hovertemplate: '%{y} · %{x}<br>z = %{z:.2f}<extra></extra>',
                            colorbar: { thickness: 10, len: 0.7, title: 'z' },
                          }]}
                          layout={{ xaxis: { tickangle: -45 }, margin: { l: 140, b: 90 } }} />
                  </Section>
                )}
              </div>
            )}

            {tab === 'script' && (
              <Section title="Reproduce this in PyDESeq2"
                       subtitle="The same calls the backend made, as a standalone script.">
                <Code filename="bioide_de.py" language="python"
                      code={deScript(src, design, contrast, alpha, minCount, shrink)} />
              </Section>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

function groupBy(rows: any[], key?: string): [string, any[]][] {
  if (!key) return [['samples', rows]]
  const m = new Map<string, any[]>()
  for (const r of rows) {
    const g = String(r.metadata?.[key] ?? 'n/a')
    m.set(g, [...(m.get(g) ?? []), r])
  }
  return [...m.entries()]
}

function downloadCsv(rows: any[]) {
  const header = 'gene,baseMean,log2FoldChange,lfcSE,stat,pvalue,padj'
  const body = rows.map(r => [r.gene, r.baseMean, r.log2FoldChange, r.lfcSE, r.stat, r.pvalue, r.padj]
    .map(v => v === null || v === undefined ? 'NA' : v).join(',')).join('\n')
  const url = URL.createObjectURL(new Blob([header + '\n' + body], { type: 'text/csv' }))
  const a = document.createElement('a')
  a.href = url; a.download = 'bioide_de_results.csv'; a.click()
  URL.revokeObjectURL(url)
}

function deScript(src: Loaded | null, design: string, contrast: string[], alpha: number,
                  minCount: number, shrink: boolean) {
  const load = src?.dataset === 'airway'
    ? `# Counts as distributed with the Bioconductor 'airway' package (GEO: GSE52778)\ncounts = pd.read_csv("airway_counts.csv.gz", index_col=0)\nmetadata = pd.read_csv("airway_metadata.csv", index_col=0)`
    : `counts = pd.read_csv("counts.csv", index_col=0)      # genes x samples, RAW integer counts\nmetadata = pd.read_csv("metadata.csv", index_col=0)   # rows must match the count columns`
  return `"""Generated by BioIDE. Differential expression with PyDESeq2."""
import pandas as pd
import pydeseq2
from pydeseq2.dds import DeseqDataSet
from pydeseq2.ds import DeseqStats

${load}

# Keep only genes with enough evidence to test at all.
keep = counts.sum(axis=1) >= ${minCount}
print(f"testing {int(keep.sum())} of {len(counts)} genes")

dds = DeseqDataSet(
    counts=counts.loc[keep].T.astype(int),   # PyDESeq2 wants samples x genes
    metadata=metadata,
    design=${JSON.stringify(design || '~ condition')},
    refit_cooks=True,
)
dds.deseq2()

stats = DeseqStats(dds, contrast=${JSON.stringify(contrast.filter(Boolean).length === 3 ? contrast : ['condition', 'treated', 'control'])}, alpha=${alpha})
stats.summary()
${shrink ? `stats.lfc_shrink(coeff="${(contrast[0] || 'condition')}[T.${(contrast[1] || 'treated')}]")` : '# log fold-change shrinkage not applied'}

res = stats.results_df
print(res.sort_values("padj").head(20))
res.to_csv("de_results.csv")

# padj is NA where independent filtering or Cook's-distance outlier detection
# excluded the gene. NA is not the same as non-significant.
print("not tested:", int(res["padj"].isna().sum()))
`
}
