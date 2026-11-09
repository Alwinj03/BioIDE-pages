import React, { useEffect, useRef, useState } from 'react'
import { api } from '../lib/api'
import { useAsync } from '../lib/useAsync'
import { Plot, PALETTE } from '../components/Plot'
import {
  Caveats, Empty, ErrorBox, Icon, I, ProvenanceBadge, Section, Spinner, Stat, Table, Tabs,
} from '../components/ui'
import { StructureViewer } from '../components/StructureViewer'

export function Bioinformatics({ projectId, pending }: { projectId: string | null; pending?: any }) {
  const [mode, setMode] = useState<'sequence' | 'structure'>('sequence')
  return (
    <div className="h-full min-h-0 overflow-y-auto">
      <div className="border-b border-line px-4">
        <Tabs active={mode} onChange={m => setMode(m as any)} tabs={[
          { id: 'sequence', label: 'Sequence analysis' },
          { id: 'structure', label: 'Protein structure' },
        ]} />
      </div>
      {mode === 'sequence' ? <SequencePane projectId={projectId} pending={pending} />
                           : <StructurePane projectId={projectId} pending={pending} />}
    </div>
  )
}

function SequencePane({ projectId, pending }: { projectId: string | null; pending?: any }) {
  const [text, setText] = useState('')
  const [minAa, setMinAa] = useState(100)
  const [altStarts, setAltStarts] = useState(false)
  const [accession, setAccession] = useState('NC_000913.3')
  const [recIdx, setRecIdx] = useState(0)
  const fileRef = useRef<HTMLInputElement>(null)

  const analyze = useAsync<any>((body: any) => api.post('/api/sequence/analyze', body))
  const sample = useAsync<any>(() => api.get(`/api/sequence/sample/pPCP1?min_aa=${minAa}&project_id=${projectId ?? ''}`))
  const fetchNcbi = useAsync<any>((acc: string) => api.get(`/api/sequence/fetch/${encodeURIComponent(acc)}?min_aa=${minAa}`))
  const upload = useAsync<any>((f: File) =>
    api.upload(`/api/sequence/upload?min_aa=${minAa}&alt_starts=${altStarts}`, { file: f }))

  const result = analyze.data ?? sample.data ?? fetchNcbi.data ?? upload.data
  const err = analyze.error ?? sample.error ?? fetchNcbi.error ?? upload.error
  const busy = analyze.loading || sample.loading || fetchNcbi.loading || upload.loading
  const prov = result?.provenance
  const rec = result?.records?.[recIdx]

  useEffect(() => { if (pending?.run || pending?.sample === 'genome_annotation') void sample.run() }, [pending])

  return (
    <div className="flex min-h-0">
      <div className="w-[330px] shrink-0 space-y-3 overflow-y-auto border-r border-line p-3">
        <Section title="Input" className="!p-3">
          <button className="btn w-full justify-center" onClick={() => sample.run()} disabled={busy}>
            <Icon d={I.dna} className="h-3.5 w-3.5" />Load bundled pPCP1 (GenBank)
          </button>
          <p className="mt-1 text-[10px] leading-relaxed text-muted">
            Yersinia pestis plasmid NC_005816, 9,609 bp with 10 curated CDS — so the ORF scan can be scored.
          </p>

          <div className="mt-3 border-t border-line pt-3">
            <label className="label">Fetch from NCBI</label>
            <div className="mt-1 flex gap-1">
              <input className="input mono" value={accession} onChange={e => setAccession(e.target.value)} />
              <button className="btn shrink-0" onClick={() => fetchNcbi.run(accession)} disabled={busy}>
                <Icon d={I.down} className="h-3.5 w-3.5" />
              </button>
            </div>
            <p className="mt-1 text-[10px] leading-relaxed text-muted">
              Needs outbound access to eutils.ncbi.nlm.nih.gov. If it is blocked you will see the error, not a
              substitute record.
            </p>
          </div>

          <div className="mt-3 border-t border-line pt-3">
            <label className="label">Upload FASTA or GenBank</label>
            <input ref={fileRef} type="file" accept=".fa,.fasta,.fna,.gb,.gbk,.genbank,.txt"
                   onChange={e => e.target.files?.[0] && upload.run(e.target.files[0])}
                   className="mt-1 w-full text-[10.5px] text-muted file:mr-2 file:rounded file:border-0 file:bg-line file:px-2 file:py-1 file:text-[10.5px] file:text-ink" />
          </div>

          <div className="mt-3 border-t border-line pt-3">
            <label className="label">Or paste</label>
            <textarea className="input mt-1 mono h-24 resize-none" placeholder=">my_sequence&#10;ATGC…"
                      value={text} onChange={e => setText(e.target.value)} />
            <button className="btn mt-1 w-full justify-center" disabled={!text.trim() || busy}
                    onClick={() => analyze.run({ content: text, min_aa: minAa, alt_starts: altStarts, project_id: projectId })}>
              <Icon d={I.play} className="h-3.5 w-3.5" />Analyse
            </button>
          </div>
        </Section>

        <Section title="ORF scan parameters" className="!p-3">
          <label className="label">Minimum ORF length (aa)</label>
          <input type="range" min="20" max="300" step="10" value={minAa}
                 onChange={e => setMinAa(parseInt(e.target.value))} className="mt-1 w-full accent-accent" />
          <div className="mono text-[11px] text-accent">{minAa} aa</div>
          <label className="mt-2 flex items-center gap-2 text-[11px] text-muted">
            <input type="checkbox" checked={altStarts} onChange={e => setAltStarts(e.target.checked)} className="accent-accent" />
            Allow GTG and TTG start codons
          </label>
          <p className="mt-2 text-[10.5px] leading-relaxed text-muted">
            Translation table 11 (bacterial). ORFs crossing the origin of a circular record are not detected —
            a real limitation of this scan, not of the sequence.
          </p>
        </Section>
      </div>

      <div className="min-w-0 flex-1 overflow-y-auto">
        {busy && <div className="p-6"><Spinner label="Parsing and scanning…" /></div>}
        {err && <div className="p-6"><ErrorBox error={err} /></div>}
        {!result && !busy && !err && (
          <div className="p-6">
            <Empty title="No sequence loaded" icon={I.dna}
                   body="Load the bundled record, fetch an accession, upload a file or paste a sequence. All statistics come from Biopython." />
          </div>
        )}

        {rec && (
          <div className="space-y-4 p-4">
            <div className="flex flex-wrap items-center gap-2">
              <ProvenanceBadge p={prov} />
              <span className="chip">{result.format}</span>
              {result.records.length > 1 && (
                <select className="input !w-auto !py-1 text-[11px]" value={recIdx}
                        onChange={e => setRecIdx(parseInt(e.target.value))}>
                  {result.records.map((r: any, i: number) => (
                    <option key={r.id} value={i}>{r.id} ({r.length.toLocaleString()} bp)</option>
                  ))}
                </select>
              )}
            </div>

            <div>
              <h3 className="text-sm font-semibold">{rec.id}</h3>
              <p className="text-[11.5px] text-muted">{rec.description}</p>
            </div>

            <div className="grid grid-cols-2 gap-2 sm:grid-cols-5">
              <Stat label="Length" value={rec.length.toLocaleString()} unit="bp" />
              <Stat label="GC content" value={rec.gc_percent.toFixed(2)} unit="%" />
              <Stat label="ORFs found" value={rec.orf_count} />
              <Stat label="ORF coding fraction" value={(rec.orf_coding_fraction * 100).toFixed(1)} unit="%" />
              <Stat label="Ambiguous bases" value={rec.ambiguous_bases}
                    tone={rec.ambiguous_bases > 0 ? 'warn' : 'good'} />
            </div>

            <Section title="GC content and cumulative skew"
                     subtitle={`Sliding window of ${rec.window_size.toLocaleString()} bp. In most bacterial chromosomes the cumulative skew extremes mark the replication origin and terminus.`}>
              <Plot height={320}
                    data={[
                      { type: 'scattergl', mode: 'lines', name: 'GC %',
                        x: rec.windows.position, y: rec.windows.gc_percent,
                        line: { color: PALETTE[0], width: 1.4 } },
                      { type: 'scattergl', mode: 'lines', name: 'cumulative GC skew', yaxis: 'y2',
                        x: rec.windows.position, y: rec.windows.cumulative_skew,
                        line: { color: PALETTE[1], width: 1.4 } },
                    ]}
                    layout={{
                      xaxis: { title: 'position (bp)' }, yaxis: { title: 'GC %' },
                      yaxis2: { overlaying: 'y', side: 'right', title: 'cumulative skew', gridcolor: 'transparent' },
                      margin: { r: 60 },
                    }} />
            </Section>

            <div className="grid gap-4 lg:grid-cols-2">
              <Section title="Base composition">
                <Plot height={240}
                      data={[{ type: 'bar', x: Object.keys(rec.composition), y: Object.values(rec.composition),
                               marker: { color: PALETTE[0] },
                               text: Object.values(rec.composition).map((v: any) => ((v / rec.length) * 100).toFixed(1) + '%'),
                               textposition: 'outside' as const }]}
                      layout={{ yaxis: { title: 'count' } }} />
              </Section>
              <Section title="Codon usage in predicted ORFs"
                       subtitle="Counted across predicted ORFs, so it inherits the scan's biases.">
                <Plot height={240}
                      data={[{ type: 'bar',
                               x: rec.codon_usage_top.slice(0, 24).map((c: any) => c[0]),
                               y: rec.codon_usage_top.slice(0, 24).map((c: any) => c[1]),
                               marker: { color: PALETTE[2] } }]}
                      layout={{ xaxis: { tickangle: -60 }, yaxis: { title: 'count' }, margin: { b: 70 } }} />
              </Section>
            </div>

            {rec.annotation_comparison && (
              <Section title="ORF scan against curated annotation"
                       subtitle={rec.annotation_comparison.note}>
                <div className="grid gap-2 sm:grid-cols-3">
                  <Stat label="Annotated CDS" value={rec.annotation_comparison.annotated_cds} />
                  <Stat label="Recovered by the scan" value={rec.annotation_comparison.recovered} tone="good" />
                  <Stat label="Missed" value={rec.annotation_comparison.annotated_cds - rec.annotation_comparison.recovered}
                        tone="warn" />
                </div>
                <div className="mt-3">
                  <Table rows={rec.annotation_comparison.features}
                         cols={[
                           { key: 'locus_tag', label: 'Locus tag', className: 'mono text-accent' },
                           { key: 'product', label: 'Product', className: 'text-muted' },
                           { key: 'start', label: 'Start', align: 'right', render: (r: any) => <span className="mono">{r.start.toLocaleString()}</span> },
                           { key: 'end', label: 'End', align: 'right', render: (r: any) => <span className="mono">{r.end.toLocaleString()}</span> },
                           { key: 'strand', label: 'Strand', align: 'right', render: (r: any) => <span className="mono">{r.strand > 0 ? '+' : '−'}</span> },
                           { key: 'length_aa', label: 'aa', align: 'right', render: (r: any) => <span className="mono">{r.length_aa}</span> },
                           { key: 'recovered_by_orf_scan', label: 'Recovered',
                             render: (r: any) => r.recovered_by_orf_scan
                               ? <span className="chip border-accent2/40 text-accent2">yes</span>
                               : <span className="chip border-amber-500/40 text-amber-300">no</span> },
                         ]} />
                </div>
              </Section>
            )}

            <Section title="Predicted open reading frames"
                     right={<span className="text-[10.5px] text-muted">
                       {rec.orfs_truncated ? `showing first 500 of ${rec.orf_count}` : `${rec.orf_count} total`}
                     </span>}>
              <Plot height={200}
                    data={[1, -1].map((strand, i) => ({
                      type: 'scatter' as const, mode: 'markers' as const, name: strand > 0 ? 'forward' : 'reverse',
                      x: rec.orfs.filter((o: any) => o.strand === strand).map((o: any) => o.start),
                      y: rec.orfs.filter((o: any) => o.strand === strand).map((o: any) => o.length_aa),
                      marker: { color: PALETTE[i], size: 7, symbol: strand > 0 ? 'triangle-right' : 'triangle-left' },
                      text: rec.orfs.filter((o: any) => o.strand === strand).map((o: any) => o.protein),
                      hovertemplate: 'start %{x}<br>%{y} aa<br>%{text}<extra></extra>',
                    }))}
                    layout={{ xaxis: { title: 'start position (bp)' }, yaxis: { title: 'length (aa)' } }} />
              <div className="mt-3">
                <Table rows={rec.orfs}
                       cols={[
                         { key: 'start', label: 'Start', align: 'right', render: (r: any) => <span className="mono">{r.start.toLocaleString()}</span> },
                         { key: 'end', label: 'End', align: 'right', render: (r: any) => <span className="mono">{r.end.toLocaleString()}</span> },
                         { key: 'strand', label: 'Strand', align: 'right', render: (r: any) => <span className="mono">{r.strand > 0 ? '+' : '−'}</span> },
                         { key: 'length_aa', label: 'aa', align: 'right', render: (r: any) => <span className="mono">{r.length_aa}</span> },
                         { key: 'start_codon', label: 'Start codon', className: 'mono' },
                         { key: 'protein', label: 'Translation (N-terminus)', className: 'mono text-[10px] text-muted' },
                       ]} />
              </div>
            </Section>

            <Caveats items={result.interpretation_notes} />
          </div>
        )}
      </div>
    </div>
  )
}

function StructurePane({ projectId, pending }: { projectId: string | null; pending?: any }) {
  const [pdbId, setPdbId] = useState('1UBQ')
  const [chainIdx, setChainIdx] = useState(0)
  const [style, setStyle] = useState<'cartoon' | 'stick' | 'sphere'>('cartoon')
  const [colour, setColour] = useState<'spectrum' | 'bfactor' | 'chain'>('spectrum')

  const sample = useAsync<any>(() => api.get(`/api/structure/sample?project_id=${projectId ?? ''}`))
  const fetchPdb = useAsync<any>((id: string) => api.get(`/api/structure/fetch/${encodeURIComponent(id)}`))
  const upload = useAsync<any>((f: File) => api.upload('/api/structure/analyze', { file: f }))

  const result = sample.data ?? fetchPdb.data ?? upload.data
  const err = sample.error ?? fetchPdb.error ?? upload.error
  const busy = sample.loading || fetchPdb.loading || upload.loading
  const chain = result?.chains?.[chainIdx]

  useEffect(() => { if (pending?.run || pending?.sample === 'protein_structure') void sample.run() }, [pending])

  return (
    <div className="flex min-h-0">
      <div className="w-[320px] shrink-0 space-y-3 overflow-y-auto border-r border-line p-3">
        <Section title="Structure source" className="!p-3">
          <button className="btn w-full justify-center" onClick={() => sample.run()} disabled={busy}>
            <Icon d={I.atom} className="h-3.5 w-3.5" />Load bundled 1A8O
          </button>
          <p className="mt-1 text-[10px] leading-relaxed text-muted">
            HIV-1 capsid C-terminal domain, X-ray at 1.7 Å.
          </p>
          <div className="mt-3 border-t border-line pt-3">
            <label className="label">Fetch from RCSB PDB</label>
            <div className="mt-1 flex gap-1">
              <input className="input mono" maxLength={4} value={pdbId}
                     onChange={e => setPdbId(e.target.value.toUpperCase())} />
              <button className="btn shrink-0" onClick={() => fetchPdb.run(pdbId)} disabled={busy}>
                <Icon d={I.down} className="h-3.5 w-3.5" />
              </button>
            </div>
          </div>
          <div className="mt-3 border-t border-line pt-3">
            <label className="label">Upload PDB or mmCIF</label>
            <input type="file" accept=".pdb,.cif,.ent,.mmcif"
                   onChange={e => e.target.files?.[0] && upload.run(e.target.files[0])}
                   className="mt-1 w-full text-[10.5px] text-muted file:mr-2 file:rounded file:border-0 file:bg-line file:px-2 file:py-1 file:text-[10.5px] file:text-ink" />
          </div>
        </Section>

        {result?.coordinates && (
          <Section title="Display" className="!p-3">
            <label className="label">Representation</label>
            <div className="mt-1 flex gap-1">
              {(['cartoon', 'stick', 'sphere'] as const).map(s => (
                <button key={s} onClick={() => setStyle(s)}
                        className={`btn flex-1 justify-center px-1 py-1 text-[10.5px] ${style === s ? 'border-accent text-accent' : ''}`}>{s}</button>
              ))}
            </div>
            <label className="label mt-2">Colour by</label>
            <div className="mt-1 flex gap-1">
              {(['spectrum', 'bfactor', 'chain'] as const).map(s => (
                <button key={s} onClick={() => setColour(s)}
                        className={`btn flex-1 justify-center px-1 py-1 text-[10.5px] ${colour === s ? 'border-accent text-accent' : ''}`}>{s}</button>
              ))}
            </div>
          </Section>
        )}
      </div>

      <div className="min-w-0 flex-1 overflow-y-auto">
        {busy && <div className="p-6"><Spinner label="Parsing coordinates…" /></div>}
        {err && <div className="p-6"><ErrorBox error={err} /></div>}
        {!result && !busy && !err && (
          <div className="p-6">
            <Empty title="No structure loaded" icon={I.atom}
                   body="Load the bundled structure, fetch a PDB ID or upload coordinates. Parsing uses Biopython's Bio.PDB." />
          </div>
        )}
        {result && (
          <div className="space-y-4 p-4">
            <div className="flex flex-wrap items-center gap-2">
              <ProvenanceBadge p={result.provenance} />
              <span className="chip">{result.format}</span>
              <span className="chip">{result.n_models} model{result.n_models > 1 ? 's' : ''}</span>
              {result.header?.resolution && <span className="chip">{result.header.resolution} Å</span>}
              {result.header?.structure_method && <span className="chip">{result.header.structure_method}</span>}
            </div>
            <div>
              <h3 className="text-sm font-semibold">{result.id} — {result.header?.name ?? 'structure'}</h3>
              <p className="text-[11.5px] text-muted">{result.header?.head} · deposited {result.header?.deposition_date ?? 'n/a'}</p>
            </div>

            {result.coordinates && (
              <Section title="3D view" subtitle="Rendered client-side with 3Dmol.js. Drag to rotate, scroll to zoom.">
                <StructureViewer pdb={result.coordinates} style={style} colour={colour} height={420} />
              </Section>
            )}

            <div className="grid gap-2 sm:grid-cols-4">
              <Stat label="Chains" value={result.chains.length} />
              <Stat label="Residues" value={result.chains.reduce((s: number, c: any) => s + c.n_residues, 0)} />
              <Stat label="Atoms" value={result.chains.reduce((s: number, c: any) => s + c.n_atoms, 0)} />
              <Stat label="Radius of gyration (CA)" value={result.radius_of_gyration_ca_A ?? '—'} unit="Å" />
            </div>

            <Section title="Chains"
                     right={result.chains.length > 1 ? (
                       <select className="input !w-auto !py-1 text-[11px]" value={chainIdx}
                               onChange={e => setChainIdx(parseInt(e.target.value))}>
                         {result.chains.map((c: any, i: number) => (
                           <option key={c.chain_id} value={i}>chain {c.chain_id} ({c.n_residues} res)</option>
                         ))}
                       </select>
                     ) : undefined}>
              <Table maxH="max-h-48" rows={result.chains}
                     cols={[
                       { key: 'chain_id', label: 'Chain', className: 'mono text-accent' },
                       { key: 'n_residues', label: 'Residues', align: 'right' },
                       { key: 'n_atoms', label: 'Atoms', align: 'right' },
                       { key: 'range', label: 'Numbering', render: (c: any) => <span className="mono">{c.first_residue}–{c.last_residue}</span> },
                       { key: 'hetero_groups', label: 'Hetero groups',
                         render: (c: any) => c.hetero_groups.length
                           ? <span className="mono text-[10.5px]">{c.hetero_groups.join(', ')}</span>
                           : <span className="text-muted">none</span> },
                     ]} />
            </Section>

            {chain?.bfactors?.length > 0 && (
              <Section title={`B-factor profile — chain ${chain.chain_id}`}
                       subtitle="Mean per residue. For a crystal structure this mixes positional uncertainty with genuine mobility; in a predicted model this column holds pLDDT instead, where high means confident.">
                <Plot height={240}
                      data={[{ type: 'scattergl', mode: 'lines', x: chain.residue_numbers, y: chain.bfactors,
                               line: { color: PALETTE[3], width: 1.4 }, name: 'B-factor' }]}
                      layout={{ xaxis: { title: 'residue number' }, yaxis: { title: 'B-factor (Å²)' } }} />
              </Section>
            )}

            {chain?.properties?.length && (
              <div className="grid gap-4 lg:grid-cols-2">
                <Section title={`Physicochemical properties — chain ${chain.chain_id}`}
                         subtitle="Computed from the sequence with Biopython's ProtParam.">
                  <dl className="space-y-1">
                    {[
                      ['Length', `${chain.properties.length} aa`],
                      ['Molecular weight', `${chain.properties.molecular_weight_da.toLocaleString()} Da`],
                      ['Isoelectric point', chain.properties.isoelectric_point],
                      ['GRAVY (hydropathy)', chain.properties.gravy],
                      ['Instability index', `${chain.properties.instability_index} ${chain.properties.instability_index > 40 ? '(predicted unstable)' : '(predicted stable)'}`],
                      ['Aromaticity', chain.properties.aromaticity],
                      ['ε₂₈₀ (reduced)', `${chain.properties.extinction_coeff_reduced.toLocaleString()} M⁻¹cm⁻¹`],
                    ].map(([k, v]) => (
                      <div key={k as string} className="flex items-baseline justify-between gap-2 border-b border-line/50 py-1">
                        <dt className="text-[11.5px] text-muted">{k}</dt>
                        <dd className="mono text-[11.5px] text-ink">{v}</dd>
                      </div>
                    ))}
                  </dl>
                </Section>
                <Section title="Amino acid composition">
                  <Plot height={280}
                        data={[{ type: 'bar', x: Object.keys(chain.properties.aa_percent),
                                 y: Object.values(chain.properties.aa_percent), marker: { color: PALETTE[0] } }]}
                        layout={{ yaxis: { title: '%' } }} />
                </Section>
              </div>
            )}

            {chain?.sequence && (
              <Section title={`Sequence — chain ${chain.chain_id}`}
                       subtitle="Built from the coordinate records, so gaps in the model appear as missing residues.">
                <div className="mono max-h-40 overflow-y-auto break-all rounded-lg border border-line bg-bg p-3 leading-relaxed text-ink/90">
                  {chain.sequence}
                </div>
              </Section>
            )}

            <Caveats items={result.notes} />
          </div>
        )}
      </div>
    </div>
  )
}
