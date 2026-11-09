import React, { useRef, useState } from 'react'
import MonacoEditor, { loader } from '@monaco-editor/react'
import * as monaco from 'monaco-editor'

// Use the bundled Monaco rather than the CDN, so the editor works offline and on
// networks that block jsdelivr. Workers are wired up explicitly for the same reason.
import editorWorker from 'monaco-editor/esm/vs/editor/editor.worker?worker'
import jsonWorker from 'monaco-editor/esm/vs/language/json/json.worker?worker'

;(self as any).MonacoEnvironment = {
  getWorker(_: string, label: string) {
    return label === 'json' ? new jsonWorker() : new editorWorker()
  },
}
loader.config({ monaco })
import { api, base } from '../lib/api'
import { useAsync } from '../lib/useAsync'
import { Code, Empty, ErrorBox, Icon, I, Section, Spinner, Table } from '../components/ui'

type Cell = { id: string; code: string; out?: any; running?: boolean; error?: string }

const SNIPPETS: { label: string; language: string; code: string }[] = [
  {
    label: 'COBRApy: FBA and FVA',
    language: 'python',
    code: `import cobra
from cobra.io import load_model
from cobra.flux_analysis import flux_variability_analysis

model = load_model("textbook")
print(f"cobrapy {cobra.__version__}: {len(model.reactions)} reactions")

solution = model.optimize()
print("growth:", round(solution.objective_value, 5), "h^-1")

# Bound the answer before quoting any single flux.
fva = flux_variability_analysis(model, fraction_of_optimum=0.9)
fva["span"] = fva.maximum - fva.minimum
print(fva.sort_values("span", ascending=False).head(10))
`,
  },
  {
    label: 'COBRApy: anaerobic shift',
    language: 'python',
    code: `from cobra.io import load_model

model = load_model("textbook")
aerobic = model.slim_optimize()

with model:                                  # changes revert on exit
    model.reactions.EX_o2_e.bounds = (0, 1000)
    anaerobic = model.optimize()

print(f"aerobic   {aerobic:.4f} h^-1")
print(f"anaerobic {anaerobic.objective_value:.4f} h^-1")

secreted = {r.id: round(anaerobic.fluxes[r.id], 3)
            for r in model.exchanges if anaerobic.fluxes[r.id] > 1e-6}
print("fermentation products:", secreted)
`,
  },
  {
    label: 'Biopython: GC and ORFs',
    language: 'python',
    code: `from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqUtils import gc_fraction

# The bundled records ship with the backend; this resolves wherever it is installed.
from app.config import SAMPLES_DIR
record = SeqIO.read(SAMPLES_DIR / "Ypestis_pPCP1_NC_005816.gb", "genbank")
seq = str(record.seq).upper()
print(record.id, len(seq), "bp, GC", round(gc_fraction(seq) * 100, 2), "%")

cds = [f for f in record.features if f.type == "CDS"]
for f in cds[:5]:
    print(f.qualifiers.get("locus_tag", ["?"])[0],
          int(f.location.start) + 1, int(f.location.end),
          f.qualifiers.get("product", [""])[0][:50])
`,
  },
  {
    label: 'PyDESeq2: differential expression',
    language: 'python',
    code: `import pandas as pd
from pydeseq2.dds import DeseqDataSet
from pydeseq2.ds import DeseqStats

from app.config import SAMPLES_DIR
counts = pd.read_csv(SAMPLES_DIR / "airway_counts.csv.gz", index_col=0)
meta = pd.read_csv(SAMPLES_DIR / "airway_metadata.csv", index_col=0)

keep = counts.sum(axis=1) >= 10
dds = DeseqDataSet(counts=counts.loc[keep].T.astype(int), metadata=meta,
                   design="~ celltype + dex", quiet=True)
dds.deseq2()

stats = DeseqStats(dds, contrast=["dex", "treated", "control"], quiet=True)
stats.summary()
res = stats.results_df
print("significant:", int((res.padj < 0.05).sum()))
print(res.sort_values("padj").head(10))
`,
  },
  {
    label: 'Bash: check what is installed',
    language: 'shell',
    code: `# Run this in your own terminal. BioIDE will not execute a shell pipeline for you.
for tool in samtools bcftools fastp salmon kraken2 metaphlan bakta nextflow snakemake; do
  if command -v "$tool" >/dev/null 2>&1; then
    printf '%-12s %s\\n' "$tool" "$($tool --version 2>&1 | head -1)"
  else
    printf '%-12s %s\\n' "$tool" "not installed"
  fi
done
`,
  },
]

export function Editor({ projectId }: { projectId: string | null }) {
  const [cells, setCells] = useState<Cell[]>([{ id: 'c1', code: SNIPPETS[0].code }])
  const [session, setSession] = useState<string | null>(null)
  const [language, setLanguage] = useState('python')
  const files = useAsync<any>((s: string) => api.get(`/api/notebook/${s}/files`))

  const runCell = async (id: string) => {
    const cell = cells.find(c => c.id === id)
    if (!cell) return
    setCells(cs => cs.map(c => c.id === id ? { ...c, running: true, error: undefined } : c))
    try {
      const r = await api.post('/api/notebook/run', { code: cell.code, session, project_id: projectId })
      setSession(r.session)
      setCells(cs => cs.map(c => c.id === id ? { ...c, out: r, running: false } : c))
      void files.run(r.session)
    } catch (e: any) {
      setCells(cs => cs.map(c => c.id === id ? { ...c, error: e?.detail ?? String(e), running: false } : c))
    }
  }

  const addCell = (code = '') =>
    setCells(cs => [...cs, { id: `c${Date.now().toString(36)}`, code }])

  return (
    <div className="flex h-full min-h-0">
      <div className="w-[260px] shrink-0 space-y-3 overflow-y-auto border-r border-line p-3">
        <Section title="Snippets" className="!p-3"
                 subtitle="Starting points that use the libraries actually installed in the backend.">
          <div className="space-y-1">
            {SNIPPETS.map(s => (
              <button key={s.label} onClick={() => { addCell(s.code); setLanguage(s.language) }}
                      className="w-full rounded border border-line bg-bg px-2 py-1.5 text-left text-[11px] text-muted hover:border-accent/50 hover:text-ink">
                {s.label}
                <span className="mono ml-1 text-[9.5px] text-muted/60">{s.language}</span>
              </button>
            ))}
          </div>
        </Section>

        <Section title="Session" className="!p-3">
          {session ? (
            <>
              <div className="mono text-[10.5px] text-accent">{session}</div>
              <p className="mt-1 text-[10px] leading-relaxed text-muted">
                JSON-serialisable variables carry between cells. Objects such as a loaded model do not —
                rebuild those in the cell that uses them.
              </p>
              <button className="btn mt-2 w-full justify-center" onClick={() => files.run(session)}>
                <Icon d={I.refresh} className="h-3 w-3" />List session files
              </button>
              {files.data?.files?.length > 0 && (
                <div className="mt-2 space-y-1">
                  {files.data.files.map((f: any) => (
                    <a key={f.name} href={`${base}/api/notebook/${session}/file/${encodeURIComponent(f.name)}`}
                       target="_blank" rel="noreferrer"
                       className="block rounded border border-line bg-bg px-2 py-1 text-[10.5px] hover:border-accent/50">
                      <span className="mono text-accent">{f.name}</span>
                      <span className="ml-1 text-muted">{(f.size_bytes / 1024).toFixed(1)} KB</span>
                    </a>
                  ))}
                </div>
              )}
            </>
          ) : (
            <p className="text-[11px] text-muted">A session starts when you run the first cell.</p>
          )}
        </Section>

        <div className="rounded-lg border border-amber-500/30 bg-amber-500/[0.05] p-2.5">
          <div className="flex items-center gap-1.5 text-[11px] font-semibold text-amber-200">
            <Icon d={I.warn} className="h-3.5 w-3.5" />About this sandbox
          </div>
          <p className="mt-1 text-[10.5px] leading-relaxed text-amber-100/80">
            Cells run in a separate process with memory, CPU, process-count and file-size limits. That is
            resource isolation, not a security boundary: code runs as the backend user. Appropriate on your own
            machine; put it behind a container before exposing it to anyone else.
          </p>
        </div>
      </div>

      <div className="min-w-0 flex-1 overflow-y-auto p-4">
        <div className="space-y-4">
          {cells.map((cell, i) => (
            <div key={cell.id} className="panel overflow-hidden">
              <div className="flex items-center gap-2 border-b border-line bg-bg2 px-3 py-1.5">
                <span className="mono text-[10.5px] text-muted">[{i + 1}]</span>
                <select className="input !w-auto !border-none !bg-transparent !py-0.5 text-[10.5px]"
                        value={language} onChange={e => setLanguage(e.target.value)}>
                  {['python', 'r', 'shell', 'json', 'yaml', 'groovy'].map(l => <option key={l} value={l}>{l}</option>)}
                </select>
                <div className="ml-auto flex gap-1">
                  <button className="btn-ghost" onClick={() => runCell(cell.id)} disabled={cell.running || language !== 'python'}
                          title={language !== 'python' ? 'Only Python executes in the sandbox. Other languages are for editing and export.' : ''}>
                    <Icon d={I.play} className="h-3 w-3" />{cell.running ? 'running' : 'run'}
                  </button>
                  <button className="btn-ghost" onClick={() => setCells(cs => cs.filter(c => c.id !== cell.id))}>
                    <Icon d={I.trash} className="h-3 w-3" />
                  </button>
                </div>
              </div>
              <MonacoEditor
                height={Math.min(460, Math.max(140, cell.code.split('\n').length * 19 + 24))}
                language={language === 'shell' ? 'shell' : language}
                theme="vs-dark"
                value={cell.code}
                onChange={v => setCells(cs => cs.map(c => c.id === cell.id ? { ...c, code: v ?? '' } : c))}
                options={{
                  minimap: { enabled: false }, fontSize: 12.5, fontFamily: 'JetBrains Mono, monospace',
                  lineNumbers: 'on', scrollBeyondLastLine: false, padding: { top: 10, bottom: 10 },
                  renderLineHighlight: 'none', automaticLayout: true, tabSize: 4,
                }} />
              {language !== 'python' && (
                <div className="border-t border-line bg-bg2 px-3 py-1.5 text-[10.5px] text-muted">
                  Only Python executes here. R, shell and workflow languages are edited and exported, because
                  BioIDE does not ship an R or Nextflow runtime.
                </div>
              )}
              {cell.error && <div className="p-3"><ErrorBox error={cell.error} /></div>}
              {cell.out && (
                <div className="border-t border-line">
                  <div className="flex flex-wrap items-center gap-2 bg-bg2 px-3 py-1.5">
                    <span className={`chip ${cell.out.status === 'succeeded' ? 'border-accent2/40 text-accent2' : 'border-rose-500/40 text-rose-300'}`}>
                      {cell.out.status}
                    </span>
                    <span className="chip mono">exit {String(cell.out.returncode)}</span>
                    <span className="chip">{cell.out.duration_s} s</span>
                    <span className="mono text-[10px] text-muted">run {cell.out.run_id}</span>
                    {cell.out.new_files?.length > 0 && (
                      <span className="chip border-accent/40 text-accent">
                        {cell.out.new_files.length} new file{cell.out.new_files.length > 1 ? 's' : ''}
                      </span>
                    )}
                  </div>
                  {cell.out.stdout && (
                    <pre className="max-h-80 overflow-auto bg-bg px-3 py-2 mono leading-relaxed text-ink/90">{cell.out.stdout}</pre>
                  )}
                  {cell.out.stderr && (
                    <pre className="max-h-64 overflow-auto border-t border-line bg-rose-500/[0.04] px-3 py-2 mono leading-relaxed text-rose-200/90">{cell.out.stderr}</pre>
                  )}
                  {cell.out.new_files?.filter((f: string) => /\.(png|jpg|svg)$/i.test(f)).map((f: string) => (
                    <div key={f} className="border-t border-line p-3">
                      <img src={`${base}/api/notebook/${cell.out.session}/file/${encodeURIComponent(f)}`}
                           alt={f} className="hidden" />
                      <a className="link text-[11px]" href={`${base}/api/notebook/${cell.out.session}/file/${encodeURIComponent(f)}`}
                         target="_blank" rel="noreferrer">
                        <Icon d={I.chart} className="inline h-3 w-3" /> open {f}
                      </a>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
          <button className="btn w-full justify-center" onClick={() => addCell()}>
            <Icon d={I.code} className="h-3.5 w-3.5" />Add cell
          </button>
        </div>
      </div>
    </div>
  )
}
