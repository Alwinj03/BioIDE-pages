import React, { useState } from 'react'
import { api, base } from '../lib/api'
import { useAsync } from '../lib/useAsync'
import { Code, ErrorBox, Icon, I, Section, Spinner, Table, Tabs } from '../components/ui'

export function Docs() {
  const [tab, setTab] = useState('start')
  const caps = useAsync<any>(() => api.get('/api/capabilities'), true)
  const tools = useAsync<any>(() => api.get('/api/agent/tools'), true)
  const health = useAsync<any>(() => api.get('/api/health'), true)

  return (
    <div className="h-full min-h-0 overflow-y-auto">
      <div className="border-b border-line px-4">
        <Tabs active={tab} onChange={setTab} tabs={[
          { id: 'start', label: 'Getting started' },
          { id: 'honesty', label: 'Scientific reliability' },
          { id: 'agent', label: 'Agent tools', badge: tools.data?.count },
          { id: 'api', label: 'API' },
          { id: 'deploy', label: 'Deployment' },
          { id: 'limits', label: 'Known limitations' },
        ]} />
      </div>

      <div className="mx-auto max-w-4xl space-y-4 p-6">
        {tab === 'start' && (
          <>
            <Section title="What BioIDE is">
              <p className="text-[12.5px] leading-relaxed text-muted">
                An integrated environment for computational biology. Four things run for real inside it today:
                constraint-based metabolic modelling with COBRApy, sequence and structure analysis with Biopython,
                differential expression with PyDESeq2, and workflow generation that exports to Snakemake and Nextflow.
                Everything else it does is either a live API call (literature, NCBI, RCSB) or an honest
                integration boundary: it tells you what to install and generates the command.
              </p>
            </Section>
            <Section title="Five minutes, end to end">
              <ol className="space-y-2 pl-5">
                {[
                  'Open Computational Modelling. The E. coli core model loads and the quality report runs. Press Run FBA: growth should be about 0.874 h⁻¹ on the default medium.',
                  'Switch the medium to anaerobic and run again. Growth falls to roughly 0.21 h⁻¹ and the model starts secreting formate, acetate and ethanol. Save both runs and compare them.',
                  'Open the FVA tab. Most core reactions turn out to be variable rather than fixed, which is why a single FBA flux should not be quoted as a prediction.',
                  'Open Omics, load the airway dataset, run QC and PCA, then run PyDESeq2. About 3,000 genes pass padj < 0.05 on a paired design.',
                  'Open Workflows, type an objective, and export Snakemake or Nextflow. Then open Bioinformatics → This machine to see which of the tools in that workflow actually exist here.',
                ].map((s, i) => <li key={i} className="list-decimal text-[12.5px] leading-relaxed text-muted">{s}</li>)}
              </ol>
            </Section>
            <Section title="Installed versions">
              {health.data && (
                <div className="flex flex-wrap gap-1.5">
                  {Object.entries(health.data.versions).map(([k, v]: any) => (
                    <span key={k} className="chip mono">{k} {v}</span>
                  ))}
                </div>
              )}
            </Section>
          </>
        )}

        {tab === 'honesty' && (
          <>
            <Section title="The rules, and how they are enforced"
                     subtitle="Stating a rule in a prompt is not enforcement. These are structural.">
              <div className="space-y-3">
                {[
                  ['No fabricated computational results',
                   'Numbers reach the UI only through endpoints that call COBRApy, PyDESeq2, Biopython, numpy or scipy. Each call opens a provenance run in SQLite before computing and closes it with the outcome. The language model has no path to the display layer: it can call the same endpoints as tools, and the UI renders the structured result, not its prose.'],
                  ['No fabricated citations',
                   'Literature records are returned by Europe PMC, OpenAlex, Crossref or PubMed. There is no local literature cache, so when a provider is unreachable you get the error and an empty result set.'],
                  ['Predictions are labelled as predictions',
                   'Every modelling and statistics endpoint returns a caveats array that the UI renders next to the numbers. FBA fluxes, in-silico essentiality, ORF calls and docking scores are described as computational hypotheses every time.'],
                  ['Failures are reported as failures',
                   'Errors surface with the backend message verbatim under a "This did not run" heading. Failed runs stay in the provenance table and are counted in the project report.'],
                  ['No silent command execution',
                   'A command is statically reviewed, then issued an HMAC token bound to that exact string, valid for ten minutes. Shell metacharacters, destructive patterns, privilege escalation and credential paths are refused. Install commands are off unless explicitly enabled. Every attempt is logged.'],
                  ['Execution class is always visible',
                   'Each tool is marked as running here, needing your machine, needing your machine plus a large database, or being an external service. Workflow nodes carry the same badge, so a generated pipeline never implies BioIDE will run it.'],
                ].map(([t, b]) => (
                  <div key={t as string} className="panel-tight p-3">
                    <div className="flex items-start gap-2">
                      <Icon d={I.check} className="mt-0.5 h-4 w-4 shrink-0 text-accent2" />
                      <div>
                        <div className="text-[12.5px] font-semibold text-ink">{t}</div>
                        <p className="mt-1 text-[11.5px] leading-relaxed text-muted">{b}</p>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </Section>
            <Section title="What this does not protect you from">
              <ul className="space-y-1.5 pl-5">
                {[
                  'A wrong model. COBRApy will happily solve a badly curated reconstruction. Run the quality check, and MEMOTE before publishing.',
                  'A wrong design formula. PyDESeq2 fits what you specify. Omitting a batch or donor factor produces confident, wrong answers.',
                  'A wrong question. No amount of provenance makes an inappropriate method appropriate.',
                  'An LLM that misreads a correct result. The numbers are real; the prose around them is a model\'s interpretation and deserves the same scepticism as any colleague\'s.',
                ].map((s, i) => <li key={i} className="list-disc text-[12px] leading-relaxed text-amber-100/80">{s}</li>)}
              </ul>
            </Section>
          </>
        )}

        {tab === 'agent' && (
          <>
            <Section title="How the agent is constrained"
                     subtitle="The model may only act through these declared tools. Each one calls the same verified service the REST API uses.">
              {tools.data && <Code code={tools.data.rules} language="system prompt" maxH="max-h-80" />}
            </Section>
            {tools.loading && <Spinner />}
            {tools.error && <ErrorBox error={tools.error} />}
            {tools.data && (
              <Section title={`Declared tools (${tools.data.count})`}>
                <div className="space-y-2">
                  {tools.data.tools.map((t: any) => (
                    <details key={t.name} className="panel-tight p-2.5">
                      <summary className="cursor-pointer">
                        <span className="mono text-[12px] text-accent">{t.name}</span>
                        <span className="ml-2 text-[11px] text-muted">
                          ({Object.keys(t.schema.properties ?? {}).length} parameters)
                        </span>
                      </summary>
                      <p className="mt-1.5 text-[11.5px] leading-relaxed text-muted">{t.description}</p>
                      <div className="mt-2">
                        <Code code={JSON.stringify(t.schema, null, 2)} maxH="max-h-56" language="json schema" />
                      </div>
                    </details>
                  ))}
                </div>
              </Section>
            )}
          </>
        )}

        {tab === 'api' && (
          <>
            <Section title="REST API"
                     subtitle="Every workspace in this UI is a thin client over these endpoints. The interactive OpenAPI docs are at /docs.">
              <a className="link inline-flex items-center gap-1 text-[12px]" href={`${base}/docs`} target="_blank" rel="noreferrer">
                <Icon d={I.link} className="h-3 w-3" />open the interactive API documentation
              </a>
            </Section>
            <Section title="The endpoints that actually compute">
              <Table maxH="max-h-[520px]" rows={ENDPOINTS}
                     cols={[
                       { key: 'method', label: 'Method', className: 'mono text-accent' },
                       { key: 'path', label: 'Path', className: 'mono text-[10.5px]' },
                       { key: 'engine', label: 'Engine', className: 'mono text-[10.5px] text-accent2' },
                       { key: 'what', label: 'What it does', className: 'text-muted' },
                     ]} />
            </Section>
            <Section title="Example: FBA from curl">
              <Code language="shell" code={`curl -s -X POST http://127.0.0.1:8000/api/model/fba \\
  -H 'content-type: application/json' \\
  -d '{"model_id": "e_coli_core", "bounds": {"EX_o2_e": [0, 1000]}}' | jq '{
    status, objective_value,
    secreted: [.exchange_fluxes[] | select(.direction == "secretion") | .id],
    provenance
  }'`} />
            </Section>
          </>
        )}

        {tab === 'deploy' && (
          <>
            <Section title="Run it locally">
              <Code language="shell" code={`# backend
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# frontend (development, with API proxy)
cd frontend
npm install
npm run dev          # http://localhost:5173

# or build the frontend into the backend and serve one process
npm run build        # writes backend/static/
uvicorn app.main:app --port 8000   # http://localhost:8000`} />
            </Section>
            <Section title="Configuration" subtitle="Everything is an environment variable; nothing is hard-coded.">
              <Table rows={ENV_VARS}
                     cols={[
                       { key: 'name', label: 'Variable', className: 'mono text-accent' },
                       { key: 'default', label: 'Default', className: 'mono text-[10.5px] text-muted' },
                       { key: 'what', label: 'Effect', className: 'text-muted' },
                     ]} />
            </Section>
            <Section title="Before exposing this to anyone else">
              <ul className="space-y-1.5 pl-5">
                {[
                  'There is no authentication. Add it, or keep the backend bound to localhost.',
                  'The notebook sandbox is resource-isolated, not security-isolated. Put it in a container with a read-only root and no network before it accepts code from anyone but you.',
                  'Set BIOIDE_ALLOW_CODE_EXEC=0 and BIOIDE_ALLOW_LOCAL_INSTALL=0 on any shared deployment.',
                  'Models and notebook sessions live in process memory and on local disk. Multiple workers will not share them; run a single worker, or move state to Postgres and object storage as the architecture intends.',
                ].map((s, i) => <li key={i} className="list-disc text-[12px] leading-relaxed text-rose-200/80">{s}</li>)}
              </ul>
            </Section>
          </>
        )}

        {tab === 'limits' && (
          <>
            {caps.data && (
              <Section title="Not implemented, and why">
                <div className="space-y-2">
                  {caps.data.not_implemented_here.map((f: any, i: number) => (
                    <div key={i} className="panel-tight p-3">
                      <div className="text-[12.5px] font-medium text-ink">{f.feature}</div>
                      <div className="mt-1 text-[11.5px] leading-relaxed text-muted">why: {f.why}</div>
                      <div className="mt-1 text-[11.5px] leading-relaxed text-accent/80">what BioIDE does instead: {f.what_bioide_does}</div>
                    </div>
                  ))}
                </div>
              </Section>
            )}
            <Section title="Specific shortcomings of what is implemented">
              <ul className="space-y-1.5 pl-5">
                {[
                  'The ORF scanner is a six-frame stop-to-stop scan. It has no RBS model, does not resolve overlapping genes, and misses ORFs that wrap the origin of a circular replicon. Use Pyrodigal or Bakta for real annotation.',
                  'Secondary-structure fractions on the structure page come from ProtParam sequence propensities, not DSSP on the coordinates.',
                  'Enrichment is a Fisher over-representation test on gene sets you supply. BioIDE ships no GO or KEGG database, and it is not GSEA.',
                  'FVA over all reactions is refused on genome-scale models rather than left to time out. Pass a reaction list.',
                  'Loaded models and notebook sessions are per-process in-memory state. A restart clears them, and they are not shared across workers.',
                  'The workflow network layout is a simple force-directed sketch. For canonical pathways an Escher map is far clearer.',
                  'Proteomics and metabolomics accept processed abundance matrices only. No vendor raw-file reading, no spectral search.',
                  'Command export fills parameters it can infer and leaves explicit placeholders for the rest. The generated files are a starting point for review, not validated pipelines.',
                ].map((s, i) => <li key={i} className="list-disc text-[12px] leading-relaxed text-muted">{s}</li>)}
              </ul>
            </Section>
          </>
        )}
      </div>
    </div>
  )
}

const ENDPOINTS = [
  { method: 'GET', path: '/api/capabilities', engine: '—', what: 'What works, needs configuration, or is not implemented' },
  { method: 'GET', path: '/api/model/{id}/inspect?with_quality=true', engine: 'cobrapy', what: 'Model summary plus structural quality checks' },
  { method: 'POST', path: '/api/model/fba', engine: 'cobrapy', what: 'FBA or pFBA with bounds, knockouts, added reactions' },
  { method: 'POST', path: '/api/model/fva', engine: 'cobrapy', what: 'Flux variability, optionally loopless' },
  { method: 'POST', path: '/api/model/deletions', engine: 'cobrapy', what: 'Single gene or reaction deletion scan' },
  { method: 'POST', path: '/api/model/envelope', engine: 'cobrapy', what: 'Growth versus product trade-off' },
  { method: 'POST', path: '/api/model/add_reaction', engine: 'cobrapy', what: 'Validate a reaction spec, with mass and charge balance' },
  { method: 'POST', path: '/api/omics/qc', engine: 'pandas, numpy', what: 'Count-matrix QC, including raw-count validation' },
  { method: 'POST', path: '/api/omics/de', engine: 'pydeseq2', what: 'Negative-binomial DE with BH correction and LFC shrinkage' },
  { method: 'POST', path: '/api/omics/pca', engine: 'numpy', what: 'PCA by SVD on the most variable features' },
  { method: 'POST', path: '/api/omics/enrichment', engine: 'scipy', what: "Fisher over-representation on gene sets you supply" },
  { method: 'POST', path: '/api/sequence/analyze', engine: 'biopython', what: 'Parse, GC profile, six-frame ORF scan, codon usage' },
  { method: 'GET', path: '/api/structure/fetch/{pdb_id}', engine: 'biopython + RCSB', what: 'Fetch and parse a structure' },
  { method: 'POST', path: '/api/literature/search', engine: 'live REST APIs', what: 'Europe PMC, OpenAlex, Crossref, PubMed, merged' },
  { method: 'POST', path: '/api/workflow/generate', engine: 'BioIDE', what: 'Template-matched DAG with validation' },
  { method: 'POST', path: '/api/workflow/export', engine: 'BioIDE', what: 'Snakemake, Nextflow, Bash, Python or JSON' },
  { method: 'GET', path: '/api/tools/{id}/feasibility', engine: 'local probe', what: 'Whether that tool can run on this machine' },
  { method: 'POST', path: '/api/execute/review', engine: '—', what: 'Static review; issues a token bound to the command' },
  { method: 'POST', path: '/api/notebook/run', engine: 'subprocess', what: 'Python with resource limits, real stdout' },
  { method: 'GET', path: '/api/projects/{id}/report', engine: 'BioIDE', what: 'Markdown report assembled from recorded runs' },
]

const ENV_VARS = [
  { name: 'ANTHROPIC_API_KEY', default: '(unset)', what: 'Enables the conversational agent with Anthropic tool calling' },
  { name: 'OPENAI_API_KEY', default: '(unset)', what: 'Enables the agent against an OpenAI-compatible endpoint' },
  { name: 'BIOIDE_LLM_BASE_URL', default: '(provider default)', what: 'Point at a local model server (Ollama, vLLM, LM Studio)' },
  { name: 'BIOIDE_LLM_MODEL', default: 'provider default', what: 'Model identifier to use' },
  { name: 'BIOIDE_CONTACT_EMAIL', default: '(unset)', what: 'Sent to literature APIs for polite-pool rate limits' },
  { name: 'NCBI_API_KEY', default: '(unset)', what: 'Raises NCBI E-utilities rate limits' },
  { name: 'BIOIDE_ALLOW_CODE_EXEC', default: '1', what: 'Master switch for the notebook sandbox and command execution' },
  { name: 'BIOIDE_ALLOW_LOCAL_INSTALL', default: '0', what: 'Permits approved install commands to execute' },
  { name: 'BIOIDE_EXEC_TIMEOUT', default: '120', what: 'Seconds before a cell or command is killed' },
  { name: 'BIOIDE_EXEC_MEM_MB', default: '2048', what: 'Address-space limit per execution' },
  { name: 'BIOIDE_MAX_UPLOAD_MB', default: '50', what: 'Upload size limit' },
  { name: 'BIOIDE_DATA_DIR', default: '~/.bioide', what: 'Where projects, provenance and sessions are stored' },
]
