<div align="center">

# BioIDE

**The AI-native development environment for biological engineering**

*From biological questions to computational solutions.*

[![tests](https://img.shields.io/badge/tests-73%20passing-34D399?style=flat-square)](#tests)
[![python](https://img.shields.io/badge/python-3.12%2B-38BDF8?style=flat-square)](#)
[![license](https://img.shields.io/badge/license-MIT-94A3B8?style=flat-square)](LICENSE)
[![status](https://img.shields.io/badge/status-working%20MVP-FBBF24?style=flat-square)](#what-actually-works)

</div>

---

BioIDE is a computational biology IDE where the analyses actually run. Metabolic
modelling, differential expression, sequence and structure analysis execute against real
scientific libraries; workflow generation exports to real engines. What it cannot run, it
says so and gives you the command instead.

The organising constraint: **BioIDE never displays a number it did not compute.** That is
enforced architecturally, not by instructions in a prompt — see
[Scientific reliability](#scientific-reliability).

```
┌─ Research ──┬─ Workflows ─┬─ Bioinformatics ─┬─ Omics ─┬─ Modelling ─┐
│ Europe PMC  │ 7 templates │ Biopython        │PyDESeq2 │ COBRApy     │
│ OpenAlex    │ DAG valid.  │ GC · ORF · PDB   │QC · PCA │ FBA · FVA   │
│ Crossref    │ Snakemake   │ ProtParam · 3D   │DE · heat│ KO · envelope│
│ PubMed      │ Nextflow    │                  │enrich.  │ networks    │
└─────────────┴─────────────┴──────────────────┴─────────┴─────────────┘
         every result carries tool · version · run id · input hash
```

---

## Table of contents

- [Quick start](#quick-start)
- [Deployment](#deployment) — **including why Vercel hosts the frontend only**
- [What actually works](#what-actually-works)
- [Scientific reliability](#scientific-reliability)
- [The six sample projects](#the-six-sample-projects)
- [Architecture](#architecture)
- [Configuration](#configuration)
- [Tests](#tests)
- [Known limitations](#known-limitations)
- [Roadmap](#roadmap)

---

## Quick start

```bash
git clone https://github.com/<you>/bioide.git && cd bioide

# backend
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# frontend (second terminal) — proxies /api to the backend
cd frontend
npm install
npm run dev                      # http://localhost:5173
```

Or one process, with the backend serving the built frontend:

```bash
cd frontend && npm run build     # writes backend/static/
cd ../backend && uvicorn app.main:app --port 8000     # http://localhost:8000
```

With Docker:

```bash
docker compose up --build        # backend on :8000
```

**No API key is required.** Every analysis endpoint works without one; a key only enables
the conversational agent.

### Five minutes, end to end

| Step | Where | What you should see |
|---|---|---|
| 1 | Modelling → **Run FBA** | 0.8739 h⁻¹ on the default medium |
| 2 | Switch to **Anaerobic**, run again | 0.2117 h⁻¹, secreting formate, acetate, ethanol |
| 3 | **Variability (FVA)** | Most core reactions are *variable*, not fixed — which is why a lone FBA flux is not a prediction |
| 4 | Omics → airway dataset → **Run PyDESeq2** | 3,077 genes at padj < 0.05 on the paired design |
| 5 | Workflows → export Nextflow → Tools → **This machine** | Which of those tools exist on your box, and what each still needs |

---

## Deployment

> **Vercel hosts the frontend. It cannot host this backend.** Not a configuration
> problem — three hard limits, measured rather than assumed.

| Blocker | Measured | Vercel limit |
|---|---|---|
| Dependency size | **274 MB** (scipy 107, pandas 50, sklearn 46, numpy 41, Biopython 15 …) | 250 MB unzipped per function |
| Execution time | Gene-deletion scan ≈ 11 s · PyDESeq2 fit ≈ 60 s | 10 s (Hobby) / 60 s (Pro) |
| State | SQLite provenance, in-memory model cache, notebook sessions, `subprocess` sandbox | Stateless, read-only FS, no subprocesses |

So the architecture is a split: **static frontend on Vercel, containerised backend on a
host that can run one.**

```
  ┌──────────────────┐   HTTPS/CORS   ┌───────────────────────┐
  │  Vercel (static) │ ─────────────► │  Render / Fly / Railway│
  │  React bundle    │                │  FastAPI + COBRApy     │
  │  VITE_API_BASE ──┼───────────────►│  + PyDESeq2 + Biopython│
  └──────────────────┘                │  volume → /data        │
                                      └───────────────────────┘
```

### 1 · Backend first

<details open>
<summary><b>Render</b> — <code>render.yaml</code> is in the repo</summary>

Point Render at the repo; it reads `render.yaml` and builds `backend/Dockerfile`.
Then set, in the dashboard:

```
BIOIDE_CORS_ORIGINS = https://your-app.vercel.app
BIOIDE_CONTACT_EMAIL = you@university.edu        # optional, literature rate limits
ANTHROPIC_API_KEY    = sk-ant-...                # optional, enables the agent
```

The free tier gives 512 MB RAM and sleeps after inactivity. That is enough for the core
model but **not** for iJO1366 FVA or a PyDESeq2 fit — use at least 2 GB.
</details>

<details>
<summary><b>Fly.io</b> — <code>fly.toml</code> is in the repo</summary>

```bash
fly launch --no-deploy          # reads fly.toml
fly volumes create bioide_data --size 1
fly secrets set BIOIDE_CORS_ORIGINS=https://your-app.vercel.app
fly deploy
```
Defaults to 2 GB in `sin` (Singapore). Machines suspend when idle and wake on request.
</details>

<details>
<summary><b>Railway · Hugging Face Spaces · any VPS</b></summary>

All read `backend/Dockerfile` directly. On a VPS:

```bash
docker build -t bioide-api ./backend
docker run -d -p 8000:8000 -v bioide-data:/data \
  -e BIOIDE_CORS_ORIGINS=https://your-app.vercel.app \
  bioide-api
```
</details>

### 2 · Frontend on Vercel

```bash
npm i -g vercel
vercel --prod
```

`vercel.json` already sets the build command, output directory and SPA rewrites. Add one
environment variable in the Vercel dashboard, then redeploy:

```
VITE_API_BASE = https://bioide-api.onrender.com      # no trailing slash
```

It is baked in at build time, so a change needs a rebuild.

### 3 · Check the two halves agree

```bash
curl https://bioide-api.onrender.com/api/health
curl -I -X OPTIONS https://bioide-api.onrender.com/api/model/fba \
     -H "Origin: https://your-app.vercel.app" \
     -H "Access-Control-Request-Method: POST"      # expect access-control-allow-origin
```

If the UI shows *"The backend is not reachable"*, it is almost always `VITE_API_BASE`
unset at build time, or `BIOIDE_CORS_ORIGINS` not listing the Vercel domain.

### What a hosted instance turns off

`backend/Dockerfile` ships `BIOIDE_ALLOW_CODE_EXEC=0`. The Code Editor's sandbox is
resource-isolated, **not** security-isolated: cells run as the backend user. Appropriate
on your own machine, not on a public URL where anyone can submit code. The UI reports it
as *disabled by configuration* rather than failing opaquely. There is also **no
authentication** — anyone with the URL can create projects and run analyses. Add auth
before sharing a link widely.

---

## What actually works

`GET /api/capabilities` returns this at runtime and the Home page renders it verbatim, so
this table cannot quietly drift from the code.

### Runs for real, with a provenance record

| Capability | Engine |
|---|---|
| FBA, pFBA, flux variability, gene/reaction deletion scans, production envelopes | COBRApy 0.32 |
| Model quality: mass/charge balance, orphans, dead ends, GPR coverage | COBRApy |
| User-specified reaction addition, mass- and charge-checked | COBRApy |
| Flux-weighted network views, run-to-run flux comparison | COBRApy |
| FASTA/GenBank parsing, GC content and cumulative skew, six-frame ORF scan, codon usage | Biopython 1.88 |
| ORF scan scored against curated CDS annotation | Biopython |
| PDB/mmCIF parsing, chains, B-factors, radius of gyration, ProtParam | Biopython |
| Count-matrix QC, including rejection of non-integer input | pandas, numpy |
| Differential expression: Wald test, BH correction, LFC shrinkage | PyDESeq2 0.5.4 |
| PCA, hierarchical clustering, Fisher over-representation | numpy, scipy |
| Workflow generation, DAG validation, format-compatibility checking | BioIDE |
| Export to Snakemake, Nextflow, Bash, Python | BioIDE |
| Tool feasibility against this machine's RAM, PATH and libraries | psutil |
| Python execution with real library access and resource limits | subprocess |

### Needs configuration

| Capability | Requires | Fallback |
|---|---|---|
| Conversational BioAgent (14 declared tools) | `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` | Deterministic keyword routing, needs no key |
| Literature search | Outbound HTTPS to Europe PMC / OpenAlex / Crossref / PubMed | None — the error is shown, no records substituted |
| NCBI and RCSB fetching | Outbound HTTPS | Upload a file, or use the bundled records |

### Deliberately not implemented

| Capability | Why | What BioIDE does instead |
|---|---|---|
| Running Kraken2, HUMAnN, MetaPhlAn, Bakta, Salmon, STAR | Binary + multi-GB reference database on the executing machine | Detects installation, generates the command and install plan, runs only on explicit approval |
| AlphaFold, ESMFold, ProteinMPNN | GPU inference, large weight files | Links the hosted route, prepares inputs |
| Molecular dynamics, docking | GPU/CPU-hours, specialised setup | Catalogue entry with honest resource expectations |
| Proteomics/metabolomics raw files | Vendor formats, large search databases | Accepts processed abundance matrices |
| Authentication, multi-user | Not built; this MVP is single-user | Nothing — see [Deployment](#deployment) |

---

## Scientific reliability

Stating a rule in a system prompt is not enforcement. These are structural.

**Numbers cannot come from the language model.** The LLM has no path to the display layer.
It calls the same 14 declared tools that back the REST API, and the UI renders the
structured result objects those tools return — never the model's prose. Every compute
endpoint opens a provenance run in SQLite *before* computing and closes it with the
outcome, so a result absent from the run table was not produced by BioIDE.

**Every displayed result carries a provenance badge** — library, version, input hash,
run id, timestamp. Click it to see the record.

**Predictions are labelled, every time.** Modelling and statistics endpoints return a
`caveats` array rendered next to the numbers: FBA fluxes are predictions under an assumed
objective and medium; in-silico essentiality disagrees with experimental screens for a
meaningful fraction of genes; a production envelope is a stoichiometric ceiling, not an
achievable titre.

**Failures are reported as failures.** Errors surface with the backend message verbatim
under a *"This did not run"* heading. Failed runs stay in the provenance table and are
counted in the project report.

**Citations cannot be invented.** No local literature cache exists. Records come from
Europe PMC, OpenAlex, Crossref or PubMed; when a provider is unreachable you get the
error and an empty result set.

**Commands do not run silently.** A command is statically reviewed, then issued an HMAC
token bound to that exact string, valid ten minutes. Shell metacharacters, destructive
patterns, privilege escalation and credential paths are refused by rule. Install commands
are off unless explicitly enabled. Every attempt is logged, approved or not.

**Execution class is always visible.** Each tool is badged `runs here`, `your machine`,
`machine + database`, or `external service`. Workflow nodes carry the same badge, so a
generated pipeline never implies BioIDE will run it.

<details>
<summary><b>What this does <i>not</i> protect you from</b></summary>

- A badly curated model. COBRApy will happily solve one. Run the quality check, and MEMOTE before publishing.
- A wrong design formula. PyDESeq2 fits what you specify; omitting a batch factor gives confident, wrong answers.
- A wrong question. No amount of provenance makes an inappropriate method appropriate.
- An LLM misreading a correct result. The numbers are real; the prose around them deserves the same scepticism as a colleague's.
</details>

---

## The six sample projects

| # | Project | Runs here | Needs your machine |
|---|---|---|---|
| 01 | Bacterial genome analysis | Parsing, GC skew, ORF scan, CDS scoring | Bakta, HMMER, Pyrodigal |
| 02 | Differential gene expression | QC, PCA, PyDESeq2, volcano, heatmap, enrichment | fastp, Salmon/STAR if starting from FASTQ |
| 03 | Metagenomic functional profiling | Generation, validation, feasibility, export | MetaPhlAn, HUMAnN, dbCAN (≈50 GB of databases) |
| 04 | Protein structure exploration | Parsing, B-factors, ProtParam, 3D view | DSSP, Foldseek, ESMFold |
| 05 | Constraint-based metabolic analysis | Everything: FBA, FVA, deletions, envelope, network | MEMOTE, a commercial solver for speed |
| 06 | Heterologous pathway analysis | Reaction validation, model comparison, yields | cameo/straindesign, MILP solver |

**Bundled data** is public and cited:

- *Yersinia pestis* plasmid pPCP1 — NC_005816, 9,609 bp, 10 curated CDS (NCBI RefSeq, via the Biopython test suite)
- HIV-1 capsid C-terminal domain — 1A8O, 1.7 Å (RCSB PDB, via the Biopython test suite)
- Airway smooth muscle RNA-seq — GSE52778, 38,694 genes × 8 samples; Himes et al. (2014) *PLoS ONE* 9(6):e99625, counts as distributed with the Bioconductor `airway` package
- *E. coli* core and iJO1366 — ship with COBRApy (Orth et al. 2010, 2011)

Project 03 bundles **no** dataset, on purpose. A metagenome subsample small enough to ship
cannot produce a meaningful profile, so BioIDE plans the run rather than showing numbers
that mean nothing.

---

## Architecture

```
backend/
  Dockerfile             Container image; code execution off by default
  app/
    main.py              FastAPI routes; mounts the built frontend if present
    config.py            Environment-variable configuration, CORS origins
    store.py             SQLite projects, provenance runs, versioned artifacts
    samples.py           The six sample projects
    services/
      modelling.py       COBRApy: FBA, pFBA, FVA, deletions, envelopes, networks
      omics.py           PyDESeq2, QC, PCA, clustering, enrichment
      sequence.py        Biopython sequence analysis
      structure.py       Biopython structure parsing and ProtParam
      literature.py      Europe PMC, OpenAlex, Crossref, PubMed clients
      catalogue.py       54 tools with execution class and resource needs
      workflow.py        7 templates, DAG validation, engine export
      local_agent.py     Environment probing, command review, gated execution
      notebook.py        Resource-limited Python execution
      agent.py           Routing, tool-calling orchestration, report assembly
  tests/test_compute.py  73 tests
frontend/
  src/pages/             One file per workspace
  src/components/        Shared UI, provenance badge, plots, structure viewer
  src/lib/api.ts         VITE_API_BASE-aware client
vercel.json              Frontend build + SPA rewrites
render.yaml · fly.toml · docker-compose.yml
```

**Stack.** FastAPI + Pydantic · React 18 + TypeScript + Tailwind + Vite · React Flow
(workflow canvas) · Monaco (bundled, not CDN, so the editor works offline) · Plotly ·
3Dmol.js · SQLite. Heavy chunks are lazy-loaded: the entry bundle is **38 kB**.

---

## Configuration

Everything is an environment variable — `backend/.env.example`, `frontend/.env.example`.

| Variable | Default | Effect |
|---|---|---|
| `VITE_API_BASE` | *(empty)* | **Frontend, build time.** Backend origin for split deployment |
| `BIOIDE_CORS_ORIGINS` | `*` | Comma-separated browser origins allowed to call the API |
| `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` | unset | Enables the conversational agent |
| `BIOIDE_LLM_BASE_URL` | provider default | Point at a local model (Ollama, vLLM, LM Studio) |
| `BIOIDE_LLM_MODEL` | provider default | Model identifier |
| `BIOIDE_CONTACT_EMAIL` | unset | Sent to literature APIs for polite-pool rate limits |
| `NCBI_API_KEY` | unset | Raises NCBI E-utilities rate limits |
| `BIOIDE_ALLOW_CODE_EXEC` | `1` local, `0` in Docker | Notebook sandbox and command execution |
| `BIOIDE_ALLOW_LOCAL_INSTALL` | `0` | Permits approved install commands to execute |
| `BIOIDE_EXEC_TIMEOUT` | `120` | Seconds before a cell or command is killed |
| `BIOIDE_EXEC_MEM_MB` | `2048` | Address-space limit per execution |
| `BIOIDE_MAX_UPLOAD_MB` | `50` | Upload size limit |
| `BIOIDE_DATA_DIR` | `~/.bioide` | Projects, provenance, sessions |

---

## Tests

```bash
cd backend
BIOIDE_DATA_DIR=/tmp/bioide_test pytest -q      # 73 passed
```

They assert against externally verifiable values — the published optimum of the core
model, known dexamethasone responders in GSE52778, the documented content of the bundled
records — and against the honesty properties themselves: that provenance is recorded,
that failures fail, that a token issued for one command will not run another, that the
volcano plot's counts agree with the summary statistics above it.

---

## Known limitations

- The ORF scanner has no RBS model, does not resolve overlapping genes, and misses ORFs
  wrapping the origin of a circular replicon. It recovers **7 of pPCP1's 10** annotated
  CDS — which the UI shows you rather than hides. Use Pyrodigal or Bakta for real annotation.
- Secondary-structure fractions come from ProtParam sequence propensities, not DSSP on coordinates.
- Enrichment is Fisher over-representation on gene sets *you* supply. No GO or KEGG
  database ships with BioIDE, and it is not GSEA.
- FVA over all reactions is refused on genome-scale models rather than left to time out.
- The network view is a force-directed sketch; a curated Escher map is clearer for canonical pathways.
- Generated workflow files fill the parameters BioIDE can infer and leave explicit
  placeholders for the rest. A reviewed starting point, not a validated pipeline.
- **The literature clients are untested against the live APIs** — they were unreachable
  from the build environment. The error path is verified; the response parsing is not.
- Loaded models and notebook sessions are per-process in-memory state. Run one worker, or
  move that state to Postgres and object storage as the architecture intends.

---

## Roadmap

Phases 1–3 are done: UI, projects, LLM integration, literature, catalogue, intent
classification, React Flow editor, workflow export, real Biopython/COBRApy/PyDESeq2
execution, notebooks, sample datasets, provenance, visualisation.

- **Phase 4 — Omics breadth.** Proteomics and metabolomics statistics, multi-omics
  integration, single-cell via scanpy/anndata.
- **Phase 5 — Local execution.** Package the local agent as a separate signed binary
  rather than running in the backend process, with per-tool database management and
  resumable jobs.
- **Phase 6 — Community.** Public project templates, workflow sharing, GitHub integration.

The honest priority order differs from that list: **authentication and container
isolation come before any of it** if more than one person is to use an instance.

---

## Contributing

The most useful contributions right now, in order:

1. **Verify the literature clients** against the live Europe PMC / OpenAlex / Crossref / PubMed APIs.
2. **Authentication**, so an instance can be shared.
3. **New workflow templates** — `backend/app/services/workflow.py`, one declarative dict each.
4. **Catalogue entries** — `backend/app/services/catalogue.py`; be honest about the `execution` class and database sizes.

Run `pytest -q` and `npx tsc --noEmit` before opening a PR.

## License

MIT — see [LICENSE](LICENSE).

## Citing the bundled data

If you publish anything derived from the sample projects, cite the original sources
listed under [The six sample projects](#the-six-sample-projects), not BioIDE.
