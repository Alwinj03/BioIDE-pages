"""BioIDE REST API."""
from __future__ import annotations

import io
import json
import time
from pathlib import Path
from typing import Any

import pandas as pd
from fastapi import Body, FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .config import SAMPLES_DIR, settings
from .samples import SAMPLE_PROJECTS, sample_detail
from .services import agent, catalogue, literature, local_agent, modelling, notebook, omics, sequence, structure, workflow
from .store import store

app = FastAPI(title="BioIDE API", version="0.1.0",
              description="Computational biology IDE backend. Every numerical result is produced by a named "
                          "library call and recorded as a provenance run.")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=False,          # no cookie auth exists; keep it off
    allow_methods=["*"],
    allow_headers=["*"],
)

MAX_BYTES = settings.max_upload_mb * 1024 * 1024


def _err(exc: Exception, code: int = 400) -> HTTPException:
    return HTTPException(status_code=code, detail=f"{type(exc).__name__}: {exc}")


async def _read(f: UploadFile) -> bytes:
    data = await f.read()
    if len(data) > MAX_BYTES:
        raise HTTPException(413, f"File exceeds the {settings.max_upload_mb} MB upload limit.")
    return data


# ===================================================================== meta

@app.get("/api/health")
def health() -> dict:
    import cobra, Bio, pydeseq2, numpy, scipy, sys
    return {"status": "ok", "time": time.time(), "python": sys.version.split()[0],
            "versions": {"cobrapy": cobra.__version__, "biopython": Bio.__version__,
                         "pydeseq2": pydeseq2.__version__, "numpy": numpy.__version__,
                         "scipy": scipy.__version__, "pandas": pd.__version__},
            "config": settings.public()}


@app.get("/api/capabilities")
def capabilities() -> dict:
    """What actually works in this deployment, and what does not. The UI renders this verbatim."""
    env = local_agent.inspect_environment(deep=False)
    return {
        "working_now": [
            {"feature": "Metabolic modelling (FBA, pFBA, FVA, deletions, production envelope)",
             "engine": "COBRApy", "status": "live"},
            {"feature": "Sequence analysis (FASTA/GenBank parsing, GC profile, ORF scan, codon usage)",
             "engine": "Biopython", "status": "live"},
            {"feature": "Protein structure parsing and sequence-derived properties",
             "engine": "Biopython Bio.PDB + ProtParam", "status": "live"},
            {"feature": "RNA-seq differential expression, QC, PCA, heatmap, enrichment",
             "engine": "PyDESeq2, numpy, scipy", "status": "live"},
            {"feature": "Workflow generation, validation and export to Snakemake/Nextflow/Bash/Python",
             "engine": "BioIDE workflow module", "status": "live (files are generated, not executed)"},
            {"feature": "Tool catalogue, feasibility checks and install-command generation",
             "engine": "BioIDE catalogue + local agent", "status": "live"},
            {"feature": "Python execution with real library access", "engine": "subprocess with resource limits",
             "status": "live" if settings.allow_code_exec else "disabled by configuration"},
        ],
        "needs_configuration": [
            {"feature": "Conversational BioAgent with tool calling",
             "requires": "ANTHROPIC_API_KEY or OPENAI_API_KEY (BIOIDE_LLM_BASE_URL for a local model)",
             "configured": settings.llm_enabled,
             "fallback": "Deterministic keyword routing, which needs no key"},
            {"feature": "Literature search (Europe PMC, OpenAlex, Crossref, PubMed)",
             "requires": "outbound HTTPS to those APIs; BIOIDE_CONTACT_EMAIL and NCBI_API_KEY are optional",
             "configured": None,
             "fallback": "None. If the APIs are unreachable the error is reported; no records are substituted."},
            {"feature": "NCBI sequence and RCSB structure fetching",
             "requires": "outbound HTTPS to eutils.ncbi.nlm.nih.gov and files.rcsb.org",
             "configured": None, "fallback": "Upload the file, or use the bundled sample records"},
        ],
        "not_implemented_here": [
            {"feature": "Running Kraken2, HUMAnN, MetaPhlAn, Bakta, Salmon, STAR and other command-line tools",
             "why": "Each needs the binary and a multi-gigabyte reference database on the executing machine",
             "what_bioide_does": "Detects whether it is installed, generates the command and install plan, and runs it only on explicit approval"},
            {"feature": "AlphaFold, ESMFold, ProteinMPNN, RFdiffusion",
             "why": "GPU inference and large weight files", "what_bioide_does": "Links the hosted route and prepares inputs"},
            {"feature": "Molecular dynamics and docking", "why": "GPU/CPU-hours and specialised setup",
             "what_bioide_does": "Catalogue entry with resource expectations"},
            {"feature": "Proteomics and metabolomics raw-file processing",
             "why": "Vendor raw formats and large search databases",
             "what_bioide_does": "Accepts processed abundance matrices for QC, PCA and statistics"},
            {"feature": "Multi-user authentication and authorisation",
             "why": "Not built; this MVP is single-user by design",
             "what_bioide_does": "Nothing. Do not expose this backend on a public network."},
        ],
        "host": {"ram_gb": env["resources"]["ram_total_gb"], "cpu": env["resources"]["cpu_logical"],
                 "note": env["where_this_runs"]},
    }


# ===================================================================== agent / search

class ChatIn(BaseModel):
    messages: list[dict] = Field(..., description="[{role: 'user'|'assistant', content: str}]")
    project_id: str | None = None


@app.post("/api/agent/route")
def agent_route(q: str = Body(..., embed=True)) -> dict:
    return agent.route(q)


@app.post("/api/agent/chat")
async def agent_chat(body: ChatIn) -> dict:
    ctx = None
    if body.project_id:
        p = store.get_project(body.project_id)
        if p:
            runs = store.list_runs(body.project_id, limit=15)
            ctx = (f"Project: {p['name']}\nObjective: {p.get('objective') or '(none)'}\n"
                   f"Recorded runs: " + ", ".join(f"{r['kind']}({r['status']})" for r in runs))
    try:
        return await agent.chat(body.messages, project_context=ctx)
    except Exception as exc:
        raise _err(exc, 500)


@app.get("/api/agent/tools")
def agent_tools() -> dict:
    return {"count": len(agent.TOOLS),
            "tools": [{"name": k, "description": v["description"], "schema": v["schema"]} for k, v in agent.TOOLS.items()],
            "rules": agent.SYSTEM_PROMPT}


# ===================================================================== literature

class LitIn(BaseModel):
    query: str
    providers: list[str] | None = None
    limit: int = 20
    year_min: int | None = None
    year_max: int | None = None
    open_access: bool = False
    article_type: str | None = None
    project_id: str | None = None


@app.get("/api/literature/providers")
def lit_providers() -> dict:
    return {"providers": literature.PROVIDERS, "article_types": literature.ARTICLE_TYPES,
            "note": "BioIDE queries these APIs live. It holds no local copy of any literature database, "
                    "so a provider outage is reported as an error rather than filled in from elsewhere."}


@app.post("/api/literature/search")
async def lit_search(body: LitIn) -> dict:
    try:
        return await literature.search(body.query, body.providers, body.limit, body.year_min,
                                       body.year_max, body.open_access, body.article_type, body.project_id)
    except Exception as exc:
        raise _err(exc, 502)


@app.get("/api/literature/fulltext/{pmcid}")
async def lit_fulltext(pmcid: str) -> dict:
    try:
        return await literature.fetch_open_access_text(pmcid)
    except Exception as exc:
        raise _err(exc, 502)


@app.post("/api/literature/bibtex")
def lit_bibtex(papers: list[dict] = Body(...)) -> PlainTextResponse:
    return PlainTextResponse(literature.collection_to_bibtex(papers), media_type="text/plain")


@app.post("/api/projects/{pid}/literature")
def lit_save(pid: str, record: dict = Body(...)) -> dict:
    if not store.get_project(pid):
        raise HTTPException(404, "No such project")
    store.save_paper(pid, record)
    return {"saved": True, "count": len(store.list_papers(pid))}


@app.get("/api/projects/{pid}/literature")
def lit_list(pid: str) -> dict:
    return {"papers": store.list_papers(pid)}


@app.delete("/api/projects/{pid}/literature/{key}")
def lit_remove(pid: str, key: str) -> dict:
    store.remove_paper(pid, key)
    return {"removed": True}


# ===================================================================== sequence

class SeqIn(BaseModel):
    content: str
    min_aa: int = 100
    alt_starts: bool = False
    window: int | None = None
    project_id: str | None = None


@app.post("/api/sequence/analyze")
def seq_analyze(body: SeqIn) -> dict:
    try:
        return sequence.analyze(body.content, body.min_aa, body.alt_starts, body.window, body.project_id, "paste")
    except Exception as exc:
        raise _err(exc)


@app.post("/api/sequence/upload")
async def seq_upload(file: UploadFile = File(...), min_aa: int = Query(100), alt_starts: bool = Query(False),
                     project_id: str | None = Query(None)) -> dict:
    data = await _read(file)
    try:
        return sequence.analyze(data.decode("utf-8", "replace"), min_aa, alt_starts, None, project_id, file.filename or "upload")
    except Exception as exc:
        raise _err(exc)


@app.get("/api/sequence/sample/{name}")
def seq_sample(name: str, min_aa: int = Query(100), project_id: str | None = Query(None)) -> dict:
    try:
        text = sequence.load_sample(name)
        return sequence.analyze(text, min_aa, False, None, project_id, f"bundled sample: {name}")
    except Exception as exc:
        raise _err(exc)


@app.get("/api/sequence/fetch/{accession}")
async def seq_fetch(accession: str, min_aa: int = Query(100), project_id: str | None = Query(None)) -> dict:
    try:
        text = await sequence.fetch_ncbi(accession)
    except Exception as exc:
        raise _err(exc, 502)
    try:
        return sequence.analyze(text, min_aa, False, None, project_id, f"NCBI {accession}")
    except Exception as exc:
        raise _err(exc)


# ===================================================================== structure

@app.post("/api/structure/analyze")
async def struct_upload(file: UploadFile = File(...), project_id: str | None = Query(None)) -> dict:
    data = await _read(file)
    try:
        return structure.analyze_structure(data.decode("utf-8", "replace"), None,
                                           Path(file.filename or "structure").stem, project_id)
    except Exception as exc:
        raise _err(exc)


@app.get("/api/structure/sample")
def struct_sample(project_id: str | None = Query(None)) -> dict:
    text, sid = structure.load_sample()
    out = structure.analyze_structure(text, "pdb", sid, project_id)
    out["coordinates"] = text
    return out


@app.get("/api/structure/fetch/{pdb_id}")
async def struct_fetch(pdb_id: str, project_id: str | None = Query(None)) -> dict:
    try:
        text = await structure.fetch_rcsb(pdb_id)
    except Exception as exc:
        raise _err(exc, 502)
    out = structure.analyze_structure(text, None, pdb_id.upper(), project_id)
    out["coordinates"] = text
    return out


@app.post("/api/structure/properties")
def struct_props(seq: str = Body(..., embed=True)) -> dict:
    p = structure.protein_properties(seq)
    if not p:
        raise HTTPException(400, "Sequence too short or contains no standard amino acids.")
    return p


# ===================================================================== models

@app.get("/api/model/list")
def model_list() -> dict:
    return {"models": modelling.list_models(),
            "note": "Bundled models ship with COBRApy. Upload your own SBML for anything else."}


@app.get("/api/model/{model_id}/inspect")
def model_inspect(model_id: str, with_quality: bool = Query(False)) -> dict:
    try:
        return modelling.inspect(model_id, with_quality)
    except Exception as exc:
        raise _err(exc, 404)


@app.get("/api/model/{model_id}/search")
def model_search(model_id: str, q: str, kind: str = Query("reaction")) -> dict:
    try:
        return {"matches": modelling.search_entities(model_id, q, kind)}
    except Exception as exc:
        raise _err(exc)


@app.get("/api/model/{model_id}/reaction/{rid}")
def model_reaction(model_id: str, rid: str) -> dict:
    try:
        return modelling.reaction_detail(model_id, rid)
    except Exception as exc:
        raise _err(exc, 404)


@app.post("/api/model/upload")
async def model_upload(file: UploadFile = File(...)) -> dict:
    data = await _read(file)
    try:
        mid = modelling.import_model(file.filename or "model.xml", data)
        return modelling.inspect(mid, with_quality=True)
    except Exception as exc:
        raise _err(exc)


class FBAIn(BaseModel):
    model_id: str = "e_coli_core"
    bounds: dict[str, list[float]] | None = None
    knockouts: list[str] | None = None
    gene_knockouts: list[str] | None = None
    objective: str | None = None
    added_reactions: list[dict] | None = None
    parsimonious: bool = False
    project_id: str | None = None


@app.post("/api/model/fba")
def model_fba(body: FBAIn) -> dict:
    try:
        return modelling.run_fba(body.model_id, body.bounds, body.knockouts, body.gene_knockouts,
                                 body.objective, body.added_reactions, body.parsimonious, 80, body.project_id)
    except Exception as exc:
        raise _err(exc)


class FVAIn(FBAIn):
    reactions: list[str] | None = None
    fraction: float = 0.9
    loopless: bool = False


@app.post("/api/model/fva")
def model_fva(body: FVAIn) -> dict:
    try:
        return modelling.run_fva(body.model_id, body.reactions, body.fraction, body.loopless, body.bounds,
                                 body.knockouts, body.gene_knockouts, body.objective, body.added_reactions,
                                 body.project_id)
    except Exception as exc:
        raise _err(exc)


class DelIn(BaseModel):
    model_id: str = "e_coli_core"
    level: str = "gene"
    ids: list[str] | None = None
    method: str = "fba"
    bounds: dict[str, list[float]] | None = None
    objective: str | None = None
    project_id: str | None = None


@app.post("/api/model/deletions")
def model_deletions(body: DelIn) -> dict:
    try:
        return modelling.run_deletions(body.model_id, body.level, body.ids, body.method,
                                       body.bounds, body.objective, body.project_id)
    except Exception as exc:
        raise _err(exc)


class EnvIn(BaseModel):
    model_id: str = "e_coli_core"
    target: str
    carbon_source: str | None = None
    points: int = 20
    bounds: dict[str, list[float]] | None = None
    project_id: str | None = None


@app.post("/api/model/envelope")
def model_envelope(body: EnvIn) -> dict:
    try:
        return modelling.run_envelope(body.model_id, body.target, body.carbon_source, body.points,
                                      body.bounds, body.project_id)
    except Exception as exc:
        raise _err(exc)


class NetIn(BaseModel):
    model_id: str = "e_coli_core"
    fluxes: dict[str, float] | None = None
    subsystem: str | None = None
    seed_reactions: list[str] | None = None
    max_nodes: int = 160
    hub_degree: int = 12


@app.post("/api/model/network")
def model_network(body: NetIn) -> dict:
    try:
        return modelling.network_graph(body.model_id, body.fluxes, body.subsystem,
                                       body.seed_reactions, body.max_nodes, body.hub_degree)
    except Exception as exc:
        raise _err(exc)


@app.post("/api/model/compare")
def model_compare(model_id: str = Body(...), runs: list[dict] = Body(...)) -> dict:
    try:
        return modelling.compare_runs(model_id, runs)
    except Exception as exc:
        raise _err(exc)


@app.post("/api/model/add_reaction")
def model_add_reaction(model_id: str = Body(...), spec: dict = Body(...)) -> dict:
    """Validate a reaction specification against a model without mutating the stored model."""
    try:
        m = modelling.get_model(model_id).copy()
        msg = modelling.add_reaction(m, spec)
        r = m.reactions.get_by_id(spec["id"])
        return {"message": msg, "reaction": r.build_reaction_string(True),
                "mass_balance": {k: float(v) for k, v in (r.check_mass_balance() or {}).items()},
                "note": "Validated on a copy. Pass this spec as 'added_reactions' to an FBA or FVA call to use it."}
    except Exception as exc:
        raise _err(exc)


# ===================================================================== omics

class OmicsIn(BaseModel):
    counts_csv: str | None = None
    metadata_csv: str | None = None
    dataset: str | None = None
    design: str | None = None
    contrast: list[str] | None = None
    min_count_sum: int = 10
    alpha: float = 0.05
    lfc_shrink: bool = True
    project_id: str | None = None


def _load_omics(body: OmicsIn) -> tuple[pd.DataFrame, pd.DataFrame | None, dict | None]:
    if body.dataset:
        c, m, spec = omics.load_sample_dataset(body.dataset)
        return c, m, spec
    if not body.counts_csv:
        raise HTTPException(400, "Provide either 'dataset' (a bundled sample) or 'counts_csv'.")
    c = omics.read_table(body.counts_csv)
    m = omics.read_table(body.metadata_csv) if body.metadata_csv else None
    return c, m, None


@app.get("/api/omics/datasets")
def omics_datasets() -> dict:
    return {"datasets": [{"id": k, **{x: v[x] for x in ("label", "citation", "licence", "design", "contrast", "note")}}
                         for k, v in omics.SAMPLE_DATASETS.items()]}


@app.get("/api/omics/dataset/{key}")
def omics_dataset(key: str, preview_rows: int = Query(10)) -> dict:
    try:
        c, m, spec = omics.load_sample_dataset(key)
    except Exception as exc:
        raise _err(exc, 404)
    return {"id": key, **{x: spec[x] for x in ("label", "citation", "licence", "design", "contrast", "note")},
            "shape": {"genes": int(c.shape[0]), "samples": int(c.shape[1])},
            "samples": list(c.columns), "metadata": m.reset_index().to_dict("records"),
            "preview": c.head(preview_rows).reset_index().to_dict("records")}


@app.post("/api/omics/qc")
def omics_qc(body: OmicsIn) -> dict:
    c, m, _ = _load_omics(body)
    try:
        return omics.qc(c, m, body.project_id)
    except Exception as exc:
        raise _err(exc)


@app.post("/api/omics/de")
def omics_de(body: OmicsIn) -> dict:
    c, m, spec = _load_omics(body)
    design = body.design or (spec or {}).get("design")
    contrast = body.contrast or (spec or {}).get("contrast")
    if m is None:
        raise HTTPException(400, "Differential expression needs sample metadata (metadata_csv).")
    if not design or not contrast:
        raise HTTPException(400, "Provide 'design' (e.g. '~ condition') and 'contrast' "
                                 "(e.g. ['condition','treated','control']).")
    try:
        return omics.differential_expression(c, m, design, contrast, body.min_count_sum,
                                             body.alpha, body.lfc_shrink, body.project_id)
    except Exception as exc:
        raise _err(exc)


@app.post("/api/omics/sample/{key}/de")
def omics_sample_de(key: str, project_id: str | None = Query(None)) -> dict:
    return omics_de(OmicsIn(dataset=key, project_id=project_id))


class PCAIn(OmicsIn):
    n_top: int = 500
    transform: str = "log2cpm"


@app.post("/api/omics/pca")
def omics_pca(body: PCAIn) -> dict:
    c, m, _ = _load_omics(body)
    try:
        return omics.pca(c, m, body.n_top, body.transform, body.project_id)
    except Exception as exc:
        raise _err(exc)


class HeatIn(OmicsIn):
    genes: list[str]
    scale: str = "zscore"
    cluster: bool = True


@app.post("/api/omics/heatmap")
def omics_heatmap(body: HeatIn) -> dict:
    c, m, _ = _load_omics(body)
    try:
        return omics.heatmap(c, body.genes, m, body.scale, body.cluster, body.project_id)
    except Exception as exc:
        raise _err(exc)


class EnrichIn(BaseModel):
    selected: list[str]
    background: list[str]
    gene_sets: dict[str, list[str]]
    min_set_size: int = 5
    project_id: str | None = None


@app.post("/api/omics/enrichment")
def omics_enrichment(body: EnrichIn) -> dict:
    try:
        return omics.enrichment(body.selected, body.background, body.gene_sets, body.min_set_size, body.project_id)
    except Exception as exc:
        raise _err(exc)


@app.post("/api/omics/upload")
async def omics_upload(counts: UploadFile = File(...), metadata: UploadFile | None = File(None)) -> dict:
    cdata = await _read(counts)
    try:
        c = omics.read_table(cdata, counts.filename or "counts.csv")
        m = None
        if metadata is not None:
            m = omics.read_table(await _read(metadata), metadata.filename or "meta.csv")
        return {"counts_shape": {"genes": int(c.shape[0]), "samples": int(c.shape[1])},
                "samples": list(c.columns), "preview": c.head(8).reset_index().to_dict("records"),
                "metadata": m.reset_index().to_dict("records") if m is not None else None,
                "metadata_columns": list(m.columns) if m is not None else None,
                "counts_csv": c.to_csv(), "metadata_csv": m.to_csv() if m is not None else None,
                "qc": omics.qc(c, m)}
    except Exception as exc:
        raise _err(exc)


# ===================================================================== catalogue / environment

@app.get("/api/tools")
def tools_list(category: str | None = None, execution: str | None = None, q: str | None = None) -> dict:
    return catalogue.listing(category, execution, q)


@app.get("/api/tools/{tool_id}")
def tools_get(tool_id: str) -> dict:
    try:
        return catalogue.get(tool_id)
    except Exception as exc:
        raise _err(exc, 404)


@app.get("/api/tools/{tool_id}/feasibility")
def tools_feasibility(tool_id: str) -> dict:
    try:
        return local_agent.feasibility(tool_id)
    except Exception as exc:
        raise _err(exc, 404)


@app.get("/api/tools/{tool_id}/install")
def tools_install(tool_id: str) -> dict:
    try:
        return local_agent.install_plan(tool_id)
    except Exception as exc:
        raise _err(exc, 404)


@app.post("/api/tools/recommend")
def tools_recommend(objective: str = Body(...), ram_gb: float | None = Body(None), has_gpu: bool = Body(False)) -> dict:
    return catalogue.recommend(objective, ram_gb, has_gpu)


@app.get("/api/environment")
def environment(deep: bool = Query(False)) -> dict:
    return local_agent.inspect_environment(deep)


@app.post("/api/execute/review")
def exec_review(command: str = Body(..., embed=True), project_id: str | None = Body(None)) -> dict:
    return local_agent.review(command, project_id)


@app.post("/api/execute/run")
def exec_run(command: str = Body(...), approval_token: str = Body(...), cwd: str | None = Body(None),
             project_id: str | None = Body(None)) -> dict:
    try:
        return local_agent.execute(command, approval_token, cwd, None, project_id)
    except PermissionError as exc:
        raise HTTPException(403, str(exc))
    except Exception as exc:
        raise _err(exc)


@app.get("/api/execute/log")
def exec_log() -> dict:
    return {"commands": store.list_commands()}


# ===================================================================== notebook

class CodeIn(BaseModel):
    code: str
    session: str | None = None
    project_id: str | None = None


@app.post("/api/notebook/run")
def nb_run(body: CodeIn) -> dict:
    try:
        return notebook.run_python(body.code, body.session, None, body.project_id)
    except PermissionError as exc:
        raise HTTPException(403, str(exc))
    except Exception as exc:
        raise _err(exc)


@app.get("/api/notebook/{session}/files")
def nb_files(session: str) -> dict:
    return {"files": notebook.list_session_files(session)}


@app.get("/api/notebook/{session}/file/{name}")
def nb_file(session: str, name: str) -> dict:
    try:
        return notebook.read_session_file(session, name)
    except Exception as exc:
        raise _err(exc, 404)


# ===================================================================== workflows

@app.get("/api/workflow/templates")
def wf_templates() -> dict:
    return {"templates": workflow.list_templates()}


@app.post("/api/workflow/classify")
def wf_classify(objective: str = Body(..., embed=True)) -> dict:
    return workflow.classify(objective)


@app.post("/api/workflow/generate")
def wf_generate(objective: str = Body(...), template: str | None = Body(None)) -> dict:
    try:
        return workflow.generate(objective, template)
    except Exception as exc:
        raise _err(exc)


@app.post("/api/workflow/validate")
def wf_validate(wf: dict = Body(...)) -> dict:
    return workflow.validate(wf)


@app.post("/api/workflow/export")
def wf_export(wf: dict = Body(...), target: str = Body("snakemake")) -> dict:
    try:
        return workflow.export(wf, target)
    except Exception as exc:
        raise _err(exc)


# ===================================================================== projects

class ProjIn(BaseModel):
    name: str
    description: str = ""
    objective: str = ""
    sample_id: str | None = None


@app.post("/api/projects")
def proj_create(body: ProjIn) -> dict:
    return store.create_project(body.name, body.description, body.objective, body.sample_id)


@app.get("/api/projects")
def proj_list() -> dict:
    return {"projects": store.list_projects()}


@app.get("/api/projects/{pid}")
def proj_get(pid: str) -> dict:
    p = store.get_project(pid)
    if not p:
        raise HTTPException(404, "No such project")
    return {**p, "runs": store.list_runs(pid), "artifacts": store.list_artifacts(pid),
            "papers": store.list_papers(pid)}


@app.delete("/api/projects/{pid}")
def proj_delete(pid: str) -> dict:
    if not store.get_project(pid):
        raise HTTPException(404, "No such project")
    store.delete_project(pid)
    return {"deleted": True}


@app.get("/api/projects/{pid}/runs")
def proj_runs(pid: str) -> dict:
    return {"runs": store.list_runs(pid)}


@app.get("/api/runs/{rid}")
def run_get(rid: str) -> dict:
    r = store.get_run(rid)
    if not r:
        raise HTTPException(404, "No such run")
    return r


@app.get("/api/runs")
def runs_all(limit: int = Query(100)) -> dict:
    return {"runs": store.list_runs(None, limit)}


@app.post("/api/projects/{pid}/artifacts")
def art_save(pid: str, kind: str = Body(...), name: str = Body(...), content: Any = Body(...)) -> dict:
    if not store.get_project(pid):
        raise HTTPException(404, "No such project")
    return store.save_artifact(pid, kind, name, content)


@app.get("/api/projects/{pid}/artifacts")
def art_list(pid: str, kind: str | None = None, all_versions: bool = Query(False)) -> dict:
    return {"artifacts": store.list_artifacts(pid, kind, latest_only=not all_versions)}


@app.get("/api/projects/{pid}/artifacts/{kind}/{name}/history")
def art_history(pid: str, kind: str, name: str) -> dict:
    return {"history": store.artifact_history(pid, kind, name)}


@app.get("/api/projects/{pid}/report")
def proj_report(pid: str) -> PlainTextResponse:
    p = store.get_project(pid)
    if not p:
        raise HTTPException(404, "No such project")
    md = agent.build_report(p, store.list_runs(pid), store.list_papers(pid), store.list_artifacts(pid))
    return PlainTextResponse(md, media_type="text/markdown")


@app.get("/api/projects/{pid}/export")
def proj_export(pid: str) -> dict:
    p = store.get_project(pid)
    if not p:
        raise HTTPException(404, "No such project")
    return {"project": p, "runs": store.list_runs(pid, 1000),
            "artifacts": store.list_artifacts(pid, latest_only=False),
            "literature": store.list_papers(pid),
            "environment": {"python_libraries": {k: v for k, v in
                                                 local_agent.inspect_environment()["python_libraries"].items() if v}},
            "format": "BioIDE project export v1",
            "note": "Reproducing these runs requires the same library versions listed under environment."}


# ===================================================================== samples

@app.get("/api/samples")
def samples_list() -> dict:
    return {"samples": SAMPLE_PROJECTS}


@app.get("/api/samples/{sid}")
def samples_get(sid: str) -> dict:
    try:
        return sample_detail(sid)
    except KeyError as exc:
        raise _err(exc, 404)


@app.post("/api/samples/{sid}/open")
def samples_open(sid: str) -> dict:
    """Create (or reuse) a project for a sample and return it with the sample definition."""
    try:
        spec = sample_detail(sid)
    except KeyError as exc:
        raise _err(exc, 404)
    existing = store.find_sample_project(sid)
    project = existing or store.create_project(spec["title"], spec["summary"], spec["objective"], sid)
    return {"project": project, "sample": spec, "reused_existing": existing is not None}


@app.get("/api/samples/{sid}/data/{which}")
def samples_data(sid: str, which: str) -> FileResponse:
    spec = sample_detail(sid)
    files = {d["file"]: d for d in spec.get("data", []) if d.get("file")}
    if which not in files:
        raise HTTPException(404, f"Sample '{sid}' has no bundled file '{which}'. Available: {list(files)}")
    path = SAMPLES_DIR / which
    if not path.exists():
        raise HTTPException(404, f"Bundled file missing on disk: {which}")
    return FileResponse(path, filename=which)


# ===================================================================== static frontend

_static = Path(__file__).parent.parent / "static"
if _static.exists():
    app.mount("/", StaticFiles(directory=str(_static), html=True), name="static")
