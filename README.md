# BioIDE

**An AI-native development environment for computational biology.**
*From biological questions to computational solutions.*

BioIDE is a working MVP, not a mockup. Four things run for real inside it: constraint-based
metabolic modelling with COBRApy, sequence and structure analysis with Biopython, differential
expression with PyDESeq2, and workflow generation that exports to Snakemake and Nextflow.
Everything else is either a live API call or an explicit integration boundary that tells you what
to install and generates the command.

The organising constraint is this: **BioIDE never shows a number it did not compute.** That is
enforced architecturally, not by instructions in a prompt. See [Scientific reliability](#scientific-reliability).

---

## Quick start

```bash
# backend
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# frontend, development (proxies /api to the backend)
cd frontend
npm install
npm run dev                      # http://localhost:5173

# or build into the backend and serve one process
npm run build                    # writes backend/static/
cd ../backend && uvicorn app.main:app --port 8000     # http://localhost:8000
```

No API key is needed. Every analysis endpoint works without one; a key only enables the
conversational agent.

Then, in five minutes:

1. **Computational Modelling** → the E. coli core model loads and the quality report runs.
   Press **Run FBA**: growth is 0.8739 h⁻¹ on the default medium.
2. Switch the medium to **Anaerobic** and run again: 0.2117 h⁻¹, with formate, acetate and
   ethanol secreted. Save both runs and compare them.
3. **Variability (FVA)** → most core reactions turn out to be variable rather than fixed, which is
   why a single FBA flux should not be quoted as a prediction.
4. **Omics** → load the airway dataset, run QC and PCA, then PyDESeq2. 3,077 genes pass
   padj < 0.05 on the paired design.
5. **Workflows** → type an objective, export Snakemake or Nextflow, then **Tools → This machine**
   to see which of those tools exist here.

---

## What actually works

The `/api/capabilities` endpoint returns this at runtime, and the Home page renders it verbatim, so
this table cannot quietly drift from the code.

### Runs for real, with a provenance record

| Capability | Engine |
|---|---|
| FBA, pFBA, flux variability, gene and reaction deletion scans, production envelopes | COBRApy 0.32 |
| Model structural quality: mass/charge balance, orphans, dead ends, GPR coverage | COBRApy |
| User-specified reaction addition with mass and charge checking | COBRApy |
| FASTA/GenBank parsing, GC content and skew, six-frame ORF scan, codon usage | Biopython 1.88 |
| ORF scan scored against curated CDS annotation | Biopython |
| PDB/mmCIF parsing, chains, B-factors, radius of gyration, ProtParam properties | Biopython |
| Count-matrix QC, including rejection of non-integer input | pandas, numpy |
| Differential expression, Wald test, BH correction, LFC shrinkage | PyDESeq2 0.5.4 |
| PCA, hierarchical clustering, Fisher over-representation | numpy, scipy |
| Workflow generation, DAG validation, format-compatibility checking | BioIDE |
| Export to Snakemake, Nextflow, Bash, Python | BioIDE |
| Tool feasibility checks against this machine's RAM, PATH and libraries | psutil, shutil |
| Python execution with real library access and resource limits | subprocess |

### Needs configuration

| Capability | Requires | Fallback |
|---|---|---|
| Conversational BioAgent with tool calling | `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` | Deterministic keyword routing, which needs no key |
| Literature search (Europe PMC, OpenAlex, Crossref, PubMed) | Outbound HTTPS to those APIs | None. The error is shown; no records are substituted |
| NCBI sequence and RCSB structure fetching | Outbound HTTPS | Upload a file, or use the bundled records |

### Deliberately not implemented

| Capability | Why | What BioIDE does instead |
|---|---|---|
| Running Kraken2, HUMAnN, MetaPhlAn, Bakta, Salmon, STAR | Each needs the binary plus a multi-gigabyte reference database on the executing machine | Detects whether it is installed, generates the command and install plan, runs it only on explicit approval |
| AlphaFold, ESMFold, ProteinMPNN | GPU inference and large weight files | Links the hosted route, prepares inputs |
| Molecular dynamics, docking | GPU/CPU-hours and specialised setup | Catalogue entry with honest resource expectations |
| Proteomics/metabolomics raw-file processing | Vendor formats and large search databases | Accepts processed abundance matrices for QC, PCA, statistics |
| Authentication and multi-user support | Not built; this MVP is single-user | Nothing. Do not expose this backend on a public network |

---

## Scientific reliability

Stating a rule in a system prompt is not enforcement. These are structural.

**Numbers cannot come from the language model.** The LLM has no path to the display layer. It can
call the same 14 declared tools that back the REST API, and the UI renders the structured result
objects those tools return — not the model's prose. Every compute endpoint opens a provenance run
in SQLite *before* computing and closes it with the outcome, so a result that is not in the run
table was not produced by BioIDE.

**Every displayed result carries a provenance badge** naming the library, its version, the input
hash, and the run id. Click it to see the record.

**Predictions are labelled every time.** Modelling and statistics endpoints return a `caveats`
array that the UI renders next to the numbers: FBA fluxes are predictions under an assumed
objective and medium, in-silico essentiality disagrees with experimental screens for a meaningful
fraction of genes, ORF calls are hypotheses, a production envelope is a stoichiometric ceiling and
not an achievable titre.

**Failures are reported as failures.** Errors surface with the backend's message verbatim under a
"This did not run" heading. Failed runs stay in the provenance table and are counted in the project
report.

**Citations cannot be invented.** There is no local literature cache. Records come from Europe PMC,
OpenAlex, Crossref or PubMed, and when a provider is unreachable you get the error and an empty
result set.

**Commands do not run silently.** A command is statically reviewed, then issued an HMAC token bound
to that exact string and valid for ten minutes. Shell metacharacters, destructive patterns,
privilege escalation and credential paths are refused by rule. Install commands are off unless
explicitly enabled. Every attempt is logged, approved or not.

**Execution class is always visible.** Each tool is marked `runs here`, `your machine`,
`machine + database`, or `external service`. Workflow nodes carry the same badge, so a generated
pipeline never implies BioIDE will run it.

### What this does not protect you from

- A badly curated model. COBRApy will happily solve one. Run the quality check, and MEMOTE before publishing.
- A wrong design formula. PyDESeq2 fits what you specify; omitting a batch factor gives confident wrong answers.
- A wrong question. No amount of provenance makes an inappropriate method appropriate.
- An LLM misreading a correct result. The numbers are real; the prose around them deserves the same scepticism as a colleague's.

---

## The six sample projects

| # | Project | Runs here | Needs your machine |
|---|---|---|---|
| 01 | Bacterial genome analysis | Parsing, GC skew, ORF scan, scoring against curated CDS | Bakta, HMMER, Pyrodigal |
| 02 | Differential gene expression | QC, PCA, PyDESeq2, volcano, heatmap, enrichment | fastp, Salmon/STAR if starting from FASTQ |
| 03 | Metagenomic functional profiling | Workflow generation, validation, feasibility check, export | MetaPhlAn, HUMAnN, dbCAN (≈50 GB of databases) |
| 04 | Protein structure exploration | Parsing, B-factors, ProtParam, 3D view | DSSP, Foldseek, ESMFold |
| 05 | Constraint-based metabolic analysis | Everything: FBA, FVA, deletions, envelope, network | MEMOTE, a commercial solver for speed |
| 06 | Heterologous pathway analysis | Reaction validation, model comparison, yield analysis | cameo/straindesign, MILP solver |

**Bundled data** is public and cited:

- *Yersinia pestis* plasmid pPCP1 (NC_005816, 9,609 bp, 10 curated CDS) — NCBI RefSeq, via the Biopython test suite
- HIV-1 capsid C-terminal domain (1A8O, 1.7 Å) — RCSB PDB, via the Biopython test suite
- Airway smooth muscle RNA-seq (GSE52778, 38,694 genes × 8 samples) — Himes et al. (2014) *PLoS ONE* 9(6):e99625, counts as distributed with the Bioconductor `airway` package
- *E. coli* core and iJO1366 models — ship with COBRApy (Orth et al. 2010, 2011)

Project 03 bundles **no** dataset on purpose. A metagenome subsample small enough to ship cannot
produce a meaningful profile, so BioIDE plans the run rather than showing numbers that mean nothing.

---

## Architecture

```
backend/
  app/
    main.py              FastAPI routes; mounts the built frontend
    config.py            Environment-variable configuration
    store.py             SQLite projects, provenance runs, versioned artifacts
    samples.py           The six sample projects
    services/
      modelling.py       COBRApy: FBA, pFBA, FVA, deletions, envelopes, networks
      omics.py           PyDESeq2, QC, PCA, clustering, enrichment
      sequence.py        Biopython sequence analysis
      structure.py       Biopython structure parsing and ProtParam
      literature.py      Europe PMC, OpenAlex, Crossref, PubMed clients
      catalogue.py       ~50 tools with execution class and resource needs
      workflow.py        Templates, DAG validation, engine export
      local_agent.py     Environment probing, command review and gated execution
      notebook.py        Resource-limited Python execution
      agent.py           Routing, tool-calling orchestration, report assembly
  tests/test_compute.py  73 tests
frontend/
  src/pages/             One file per workspace
  src/components/        Shared UI, provenance badge, plots, structure viewer
```

**Stack.** FastAPI + Pydantic; React 18 + TypeScript + Tailwind + Vite; React Flow for the workflow
canvas, Monaco for the editor (bundled, not CDN, so it works offline), Plotly for charts, 3Dmol.js
for structures. SQLite for provenance. The heavy frontend chunks are lazy-loaded: the entry bundle
is ~38 kB.

---

## Configuration

Everything is an environment variable. See `backend/.env.example`.

| Variable | Default | Effect |
|---|---|---|
| `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` | unset | Enables the conversational agent |
| `BIOIDE_LLM_BASE_URL` | provider default | Point at a local model (Ollama, vLLM, LM Studio) |
| `BIOIDE_LLM_MODEL` | provider default | Model identifier |
| `BIOIDE_CONTACT_EMAIL` | unset | Sent to literature APIs for polite-pool rate limits |
| `NCBI_API_KEY` | unset | Raises NCBI E-utilities rate limits |
| `BIOIDE_ALLOW_CODE_EXEC` | `1` | Master switch for the sandbox and command execution |
| `BIOIDE_ALLOW_LOCAL_INSTALL` | `0` | Permits approved install commands to execute |
| `BIOIDE_EXEC_TIMEOUT` | `120` | Seconds before a cell or command is killed |
| `BIOIDE_EXEC_MEM_MB` | `2048` | Address-space limit per execution |
| `BIOIDE_MAX_UPLOAD_MB` | `50` | Upload size limit |
| `BIOIDE_DATA_DIR` | `~/.bioide` | Projects, provenance and sessions |

---

## Tests

```bash
cd backend
BIOIDE_DATA_DIR=/tmp/bioide_test pytest -q      # 73 passed
```

They assert against externally verifiable values — the published optimum of the core model, known
dexamethasone responders in the airway dataset, the documented content of the bundled records — and
against the honesty properties themselves: that provenance is recorded, that failures fail, that a
token issued for one command will not run another, that the volcano plot's counts agree with the
summary statistics above it.

---

## Before you expose this to anyone else

- **There is no authentication.** Add it, or keep the backend bound to localhost.
- **The notebook sandbox is resource-isolated, not security-isolated.** Code runs as the backend
  user. Appropriate on your own machine; put it in a container with a read-only root and no network
  before it accepts code from anyone but you.
- Set `BIOIDE_ALLOW_CODE_EXEC=0` and `BIOIDE_ALLOW_LOCAL_INSTALL=0` on any shared deployment.
- Loaded models and notebook sessions are per-process in-memory state. Run a single worker, or move
  that state to Postgres and object storage as the architecture intends.

---

## Known limitations

- The ORF scanner has no RBS model, does not resolve overlapping genes, and misses ORFs that wrap
  the origin of a circular replicon. It recovers 7 of pPCP1's 10 annotated CDS, which the UI shows
  you rather than hides. Use Pyrodigal or Bakta for real annotation.
- Secondary-structure fractions come from ProtParam sequence propensities, not DSSP on coordinates.
- Enrichment is Fisher over-representation on gene sets you supply. No GO or KEGG database ships
  with BioIDE, and it is not GSEA.
- FVA over all reactions is refused on genome-scale models rather than left to time out.
- The network view is a force-directed sketch; a curated Escher map is clearer for canonical pathways.
- Generated workflow files fill the parameters BioIDE can infer and leave explicit placeholders for
  the rest. They are a reviewed starting point, not validated pipelines.

---

## Roadmap

Phase 1–3 are done (UI, projects, LLM integration, literature, catalogue, intent classification,
React Flow editor, workflow export, real Biopython/COBRApy/PyDESeq2 execution, notebooks, sample
datasets, provenance, visualisation). What follows:

- **Phase 4 — Omics breadth.** Proteomics and metabolomics statistics, multi-omics integration,
  single-cell support via scanpy/anndata.
- **Phase 5 — Local execution.** Package the local agent as a separate signed binary rather than
  running in the backend process, with per-tool database management and resumable jobs.
- **Phase 6 — Community.** Public project templates, workflow sharing, GitHub integration.

The honest priority order is different from the feature list: authentication and container
isolation come before any of the above if more than one person is to use an instance.
