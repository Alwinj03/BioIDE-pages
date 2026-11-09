"""BioAgent: intent classification, tool-calling orchestration and reporting.

Two layers, deliberately separated:

  * `route()` is deterministic. It classifies a request with keyword rules and
    works with no API key at all. The UI uses it for navigation.
  * `chat()` is the LLM layer. The model may only act through the declared tools
    below, each of which calls the same verified compute services the REST API
    uses. The model never produces a flux value, a p-value or a citation itself;
    it configures a run and then explains what the run returned.

The system prompt states those rules, but the architecture is what enforces them:
results are attached to the response as structured `tool_results` with provenance,
and the UI renders those rather than the model's prose numbers.
"""
from __future__ import annotations

import asyncio
import json
import re
from typing import Any, Callable

import httpx

from ..config import settings
from . import catalogue, literature, modelling, workflow

SYSTEM_PROMPT = """You are BioAgent, the assistant inside BioIDE, a computational biology IDE.

Hard rules:
1. Never state a numerical result (a flux, a growth rate, a p-value, a fold change, a count) unless it came back from a tool call in this conversation. If you have not run the tool, say so and offer to run it.
2. Never invent a citation, DOI, author or year. Cite only records returned by search_literature, and cite them with their DOI or PMID.
3. Distinguish prediction from observation. FBA fluxes, docking scores, predicted structures and model-based essentiality are computational predictions. Say so every time.
4. If an input is missing (a count matrix, a model file, a design formula), ask for it. Do not guess a filename or substitute example data without saying clearly that it is example data.
5. If a tool fails, report the failure and the error. Never describe a failed run as if it succeeded.
6. When a tool cannot run here (it needs a large database, a GPU, or software on the user's own machine), say that plainly and give the install or execution route instead of pretending.
7. Explain why you chose a tool or method over the alternatives, in one or two sentences.
8. Be concise. Prefer a short answer plus a tool result over a long essay.

You are talking to biotechnology and bioinformatics students, computational biologists and researchers. Assume competence; do not over-explain basics unless asked."""

# ------------------------------------------------------------------ routing

ROUTES = {
    "literature": {"workspace": "research", "terms": ["literature", "paper", "papers", "publication", "review",
                                                      "find research", "what is known", "state of the art", "cite",
                                                      "doi", "pubmed", "role of", "evidence for"]},
    "modelling": {"workspace": "modelling", "terms": ["flux balance", "fba", "fva", "cobra", "metabolic model",
                                                      "genome-scale", "gem", "sbml", "knockout", "essentiality",
                                                      "yield", "strain design", "production envelope", "biomass"]},
    "omics": {"workspace": "omics", "terms": ["rna-seq", "rnaseq", "differential expression", "deg", "count matrix",
                                              "volcano", "heatmap", "pca", "proteomic", "metabolomic", "transcriptom",
                                              "enrichment", "deseq", "edger"]},
    "bioinformatics": {"workspace": "bioinformatics", "terms": ["fasta", "genbank", "genome", "orf", "gc content",
                                                                "annotat", "assembl", "variant", "blast", "alignment",
                                                                "sequence", "pdb", "structure", "protein"]},
    "workflow": {"workspace": "workflows", "terms": ["workflow", "pipeline", "nextflow", "snakemake", "steps",
                                                     "generate a pipeline", "reproducib", "dag"]},
    "tools": {"workspace": "bioinformatics", "terms": ["which tool", "what tool", "recommend", "compare",
                                                       "install", "software", "ram", "laptop", "gpu", "vs ", "versus"]},
    "code": {"workspace": "editor", "terms": ["script", "code", "python", "write a function", "r script", "bash"]},
}


def route(text: str) -> dict:
    t = text.lower()
    scored = []
    for intent, spec in ROUTES.items():
        hits = [k for k in spec["terms"] if k in t]
        if hits:
            scored.append({"intent": intent, "workspace": spec["workspace"], "score": len(hits), "matched": hits})
    scored.sort(key=lambda s: -s["score"])
    wf = workflow.classify(text)
    tools = catalogue.recommend(text)
    primary = scored[0] if scored else {"intent": "unclear", "workspace": "home", "score": 0, "matched": []}
    actions = []
    if primary["intent"] == "modelling":
        actions.append({"label": "Open the modelling workspace with the E. coli core model",
                        "endpoint": "/api/model/e_coli_core/inspect", "method": "GET"})
        actions.append({"label": "Run FBA on the core model", "endpoint": "/api/model/fba", "method": "POST",
                        "body": {"model_id": "e_coli_core"}})
    if primary["intent"] == "omics":
        actions.append({"label": "Load the airway RNA-seq sample dataset and run DE",
                        "endpoint": "/api/omics/sample/airway/de", "method": "POST"})
    if primary["intent"] == "literature":
        actions.append({"label": "Search Europe PMC and OpenAlex", "endpoint": "/api/literature/search",
                        "method": "POST", "body": {"query": text}})
    if wf["best"]:
        actions.append({"label": f"Generate the '{workflow.TEMPLATES[wf['best']]['title']}' workflow",
                        "endpoint": "/api/workflow/generate", "method": "POST", "body": {"objective": text}})
    return {"query": text, "intent": primary["intent"], "workspace": primary["workspace"],
            "all_intents": scored, "workflow_match": wf, "suggested_actions": actions,
            "tool_suggestions": tools["recommendations"][:5],
            "method": "deterministic keyword routing (no LLM call)",
            "llm_available": settings.llm_enabled}


# ------------------------------------------------------------------ tools

async def _t_search_literature(query: str, limit: int = 10, year_min: int | None = None,
                               providers: list[str] | None = None, **_: Any) -> dict:
    r = await literature.search(query, providers=providers, limit=min(limit, 25), year_min=year_min)
    return {"count": r["count"], "provider_errors": r["provider_errors"],
            "results": [{k: p[k] for k in ("title", "authors", "year", "journal", "doi", "pmid",
                                           "citations", "is_open_access", "abstract")}
                        for p in r["results"][:limit]]}


def _t_inspect_model(model_id: str = "e_coli_core", with_quality: bool = False, **_: Any) -> dict:
    out = modelling.inspect(model_id, with_quality)
    out.pop("exchanges", None)
    return out


def _t_search_model(model_id: str, query: str, kind: str = "reaction", **_: Any) -> dict:
    return {"matches": modelling.search_entities(model_id, query, kind, limit=25)}


def _t_run_fba(model_id: str = "e_coli_core", bounds: dict | None = None, knockouts: list[str] | None = None,
               gene_knockouts: list[str] | None = None, objective: str | None = None,
               parsimonious: bool = False, **_: Any) -> dict:
    r = modelling.run_fba(model_id, bounds=bounds, knockouts=knockouts, gene_knockouts=gene_knockouts,
                          objective=objective, parsimonious=parsimonious, top=25)
    r.pop("all_fluxes", None)
    r["active_reactions"] = r["active_reactions"][:25]
    return r


def _t_run_fva(model_id: str = "e_coli_core", reactions: list[str] | None = None,
               fraction: float = 0.9, loopless: bool = False, **_: Any) -> dict:
    r = modelling.run_fva(model_id, reactions=reactions, fraction=fraction, loopless=loopless)
    r["ranges"] = r["ranges"][:40]
    return r


def _t_run_deletions(model_id: str = "e_coli_core", level: str = "gene", ids: list[str] | None = None, **_: Any) -> dict:
    r = modelling.run_deletions(model_id, level=level, ids=ids)
    r["results"] = r["results"][:40]
    return r


def _t_production_envelope(model_id: str, target: str, carbon_source: str | None = None, points: int = 15, **_: Any) -> dict:
    return modelling.run_envelope(model_id, target=target, carbon_source=carbon_source, points=points)


def _t_recommend_tools(objective: str, ram_gb: float | None = None, has_gpu: bool = False, **_: Any) -> dict:
    r = catalogue.recommend(objective, ram_gb, has_gpu)
    r["recommendations"] = r["recommendations"][:8]
    return r


def _t_tool_details(tool_id: str, **_: Any) -> dict:
    return catalogue.get(tool_id)


def _t_generate_workflow(objective: str, template: str | None = None, **_: Any) -> dict:
    wf = workflow.generate(objective, template)
    return {"template": wf["template"], "title": wf["title"],
            "steps": [{k: n[k] for k in ("id", "label", "tool", "execution", "inputs", "outputs", "params")} for n in wf["nodes"]],
            "edges": wf["edges"], "notes": wf["notes"], "validation": wf["validation"]}


def _t_export_workflow(objective: str, target: str = "snakemake", template: str | None = None, **_: Any) -> dict:
    wf = workflow.generate(objective, template)
    return workflow.export(wf, target)


def _t_check_environment(deep: bool = False, **_: Any) -> dict:
    from . import local_agent
    env = local_agent.inspect_environment(deep=deep)
    return {"resources": env["resources"], "tools_found": sorted(env["tools_found"]),
            "tools_missing": env["tools_missing"],
            "python_libraries": {k: v for k, v in env["python_libraries"].items() if v},
            "where_this_runs": env["where_this_runs"], "permissions": env["permissions"]}


def _t_install_plan(tool_id: str, **_: Any) -> dict:
    from . import local_agent
    return local_agent.install_plan(tool_id)


def _t_run_python(code: str, session: str | None = None, **_: Any) -> dict:
    from . import notebook
    r = notebook.run_python(code, session=session)
    return {k: r[k] for k in ("status", "stdout", "stderr", "duration_s", "session", "new_files", "run_id")}


TOOLS: dict[str, dict] = {
    "search_literature": {
        "fn": _t_search_literature, "async": True,
        "description": "Search Europe PMC and OpenAlex for peer-reviewed literature. Returns real records only. Use this before making any claim about published work.",
        "schema": {"type": "object", "properties": {
            "query": {"type": "string", "description": "Search terms or research question"},
            "limit": {"type": "integer", "description": "Max records (<=25)"},
            "year_min": {"type": "integer"},
            "providers": {"type": "array", "items": {"type": "string", "enum": list(literature.PROVIDERS)}},
        }, "required": ["query"]},
    },
    "inspect_model": {
        "fn": _t_inspect_model, "async": False,
        "description": "Inspect a genome-scale metabolic model: counts, objective, compartments, subsystems, default growth. Set with_quality for mass-balance and dead-end checks.",
        "schema": {"type": "object", "properties": {
            "model_id": {"type": "string", "description": "e_coli_core, iJO1366, salmonella, or an uploaded model id"},
            "with_quality": {"type": "boolean"}}, "required": []},
    },
    "search_model": {
        "fn": _t_search_model, "async": False,
        "description": "Find reactions, metabolites or genes in a loaded model by id or name. Use this to get exact reaction ids before configuring an analysis.",
        "schema": {"type": "object", "properties": {
            "model_id": {"type": "string"}, "query": {"type": "string"},
            "kind": {"type": "string", "enum": ["reaction", "metabolite", "gene"]}}, "required": ["model_id", "query"]},
    },
    "run_fba": {
        "fn": _t_run_fba, "async": False,
        "description": "Run flux balance analysis with COBRApy. Returns the solved objective value and active fluxes. Optionally change exchange bounds, knock out reactions or genes, or set a different objective.",
        "schema": {"type": "object", "properties": {
            "model_id": {"type": "string"},
            "bounds": {"type": "object", "description": "Map of reaction id to [lower, upper], e.g. {\"EX_o2_e\": [0, 1000]} for anaerobic"},
            "knockouts": {"type": "array", "items": {"type": "string"}},
            "gene_knockouts": {"type": "array", "items": {"type": "string"}},
            "objective": {"type": "string", "description": "Reaction id to maximise instead of biomass"},
            "parsimonious": {"type": "boolean", "description": "Run pFBA for a unique minimal-flux solution"}}, "required": []},
    },
    "run_fva": {
        "fn": _t_run_fva, "async": False,
        "description": "Run flux variability analysis to find the feasible range of each flux. Use this before presenting any single FBA flux as a prediction. Pass an explicit reaction list for large models.",
        "schema": {"type": "object", "properties": {
            "model_id": {"type": "string"}, "reactions": {"type": "array", "items": {"type": "string"}},
            "fraction": {"type": "number"}, "loopless": {"type": "boolean"}}, "required": []},
    },
    "run_deletions": {
        "fn": _t_run_deletions, "async": False,
        "description": "Single gene or reaction deletion scan, returning growth ratio relative to wild type and an essentiality classification.",
        "schema": {"type": "object", "properties": {
            "model_id": {"type": "string"}, "level": {"type": "string", "enum": ["gene", "reaction"]},
            "ids": {"type": "array", "items": {"type": "string"}}}, "required": []},
    },
    "production_envelope": {
        "fn": _t_production_envelope, "async": False,
        "description": "Compute the growth versus product trade-off (theoretical stoichiometric limit) for a target exchange reaction.",
        "schema": {"type": "object", "properties": {
            "model_id": {"type": "string"}, "target": {"type": "string", "description": "Target exchange reaction id"},
            "carbon_source": {"type": "string"}, "points": {"type": "integer"}}, "required": ["model_id", "target"]},
    },
    "recommend_tools": {
        "fn": _t_recommend_tools, "async": False,
        "description": "Recommend bioinformatics software for an objective, filtered by available RAM and GPU. Explains why each tool matched and flags infeasible ones.",
        "schema": {"type": "object", "properties": {
            "objective": {"type": "string"}, "ram_gb": {"type": "number"}, "has_gpu": {"type": "boolean"}},
            "required": ["objective"]},
    },
    "tool_details": {
        "fn": _t_tool_details, "async": False,
        "description": "Full catalogue entry for one tool: inputs, outputs, install commands, database size, execution class and alternatives.",
        "schema": {"type": "object", "properties": {"tool_id": {"type": "string"}}, "required": ["tool_id"]},
    },
    "generate_workflow": {
        "fn": _t_generate_workflow, "async": False,
        "description": "Generate a validated workflow DAG for an objective, with per-step tools, formats, parameters and a feasibility breakdown.",
        "schema": {"type": "object", "properties": {
            "objective": {"type": "string"},
            "template": {"type": "string", "enum": list(workflow.TEMPLATES)}}, "required": ["objective"]},
    },
    "export_workflow": {
        "fn": _t_export_workflow, "async": False,
        "description": "Export a generated workflow as a Snakemake, Nextflow, Bash or Python file. The file is generated, not executed.",
        "schema": {"type": "object", "properties": {
            "objective": {"type": "string"},
            "target": {"type": "string", "enum": ["snakemake", "nextflow", "bash", "python", "json"]},
            "template": {"type": "string", "enum": list(workflow.TEMPLATES)}}, "required": ["objective"]},
    },
    "check_environment": {
        "fn": _t_check_environment, "async": False,
        "description": "Inspect the machine the BioIDE backend runs on: CPU, RAM, disk, installed bioinformatics tools and Python libraries. Use this before claiming something can or cannot run.",
        "schema": {"type": "object", "properties": {"deep": {"type": "boolean"}}, "required": []},
    },
    "install_plan": {
        "fn": _t_install_plan, "async": False,
        "description": "Produce installation commands and database requirements for a tool. Generates commands only; it never installs anything.",
        "schema": {"type": "object", "properties": {"tool_id": {"type": "string"}}, "required": ["tool_id"]},
    },
    "run_python": {
        "fn": _t_run_python, "async": False,
        "description": "Execute Python in the BioIDE notebook sandbox (COBRApy, Biopython, pandas, numpy, scipy, PyDESeq2 available). Returns real stdout and stderr. Use for calculations and plots rather than doing arithmetic yourself.",
        "schema": {"type": "object", "properties": {
            "code": {"type": "string"}, "session": {"type": "string", "description": "Reuse a session to keep variables"}},
            "required": ["code"]},
    },
}


def tool_specs(provider: str) -> list[dict]:
    if provider == "anthropic":
        return [{"name": k, "description": v["description"], "input_schema": v["schema"]} for k, v in TOOLS.items()]
    return [{"type": "function", "function": {"name": k, "description": v["description"], "parameters": v["schema"]}}
            for k, v in TOOLS.items()]


async def call_tool(name: str, args: dict) -> dict:
    spec = TOOLS.get(name)
    if not spec:
        return {"error": f"Unknown tool '{name}'"}
    try:
        if spec["async"]:
            return await spec["fn"](**args)
        return await asyncio.to_thread(spec["fn"], **args)
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}",
                "note": "The tool call failed. Report this failure to the user; do not substitute an estimated result."}


# ------------------------------------------------------------------ LLM loop

async def chat(messages: list[dict], project_context: str | None = None, max_iterations: int = 6) -> dict:
    """Run the agent loop. `messages` is [{role, content}, ...]."""
    if not settings.llm_enabled:
        last = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
        r = route(last)
        return {"llm": False, "reply": None, "routing": r, "tool_results": [],
                "message": "No LLM provider is configured, so BioAgent fell back to deterministic routing. "
                           "Set ANTHROPIC_API_KEY or OPENAI_API_KEY (and optionally BIOIDE_LLM_MODEL) to enable "
                           "conversational orchestration. Every analysis endpoint works without it."}
    system = SYSTEM_PROMPT + (f"\n\nCurrent project context:\n{project_context}" if project_context else "")
    if settings.llm_provider == "anthropic":
        return await _anthropic_loop(system, messages, max_iterations)
    return await _openai_loop(system, messages, max_iterations)


async def _anthropic_loop(system: str, messages: list[dict], max_iterations: int) -> dict:
    url = (settings.llm_base_url or "https://api.anthropic.com") + "/v1/messages"
    headers = {"x-api-key": settings.anthropic_api_key, "anthropic-version": "2023-06-01",
               "content-type": "application/json"}
    convo = [{"role": m["role"], "content": m["content"]} for m in messages]
    collected, trace = [], []
    async with httpx.AsyncClient(timeout=180) as client:
        for _ in range(max_iterations):
            body = {"model": settings.llm_model, "max_tokens": 4096, "system": system,
                    "messages": convo, "tools": tool_specs("anthropic")}
            r = await client.post(url, headers=headers, json=body)
            if r.status_code >= 400:
                return {"llm": True, "error": f"LLM provider returned {r.status_code}: {r.text[:400]}",
                        "tool_results": collected, "trace": trace}
            data = r.json()
            blocks = data.get("content", [])
            convo.append({"role": "assistant", "content": blocks})
            calls = [b for b in blocks if b.get("type") == "tool_use"]
            if not calls:
                text = "".join(b.get("text", "") for b in blocks if b.get("type") == "text")
                return {"llm": True, "provider": "anthropic", "model": settings.llm_model,
                        "reply": text, "tool_results": collected, "trace": trace,
                        "stop_reason": data.get("stop_reason"), "usage": data.get("usage")}
            results = []
            for c in calls:
                res = await call_tool(c["name"], c.get("input") or {})
                trace.append({"tool": c["name"], "input": c.get("input"), "ok": "error" not in res})
                collected.append({"tool": c["name"], "input": c.get("input"), "result": res})
                results.append({"type": "tool_result", "tool_use_id": c["id"],
                                "content": json.dumps(res, default=str)[:60000],
                                "is_error": "error" in res})
            convo.append({"role": "user", "content": results})
    return {"llm": True, "provider": "anthropic", "reply": None, "tool_results": collected, "trace": trace,
            "error": f"Stopped after {max_iterations} tool-calling rounds without a final answer."}


async def _openai_loop(system: str, messages: list[dict], max_iterations: int) -> dict:
    base = settings.llm_base_url or "https://api.openai.com/v1"
    url = base.rstrip("/") + "/chat/completions"
    headers = {"Content-Type": "application/json"}
    if settings.openai_api_key:
        headers["Authorization"] = f"Bearer {settings.openai_api_key}"
    convo: list[dict] = [{"role": "system", "content": system}] + [
        {"role": m["role"], "content": m["content"]} for m in messages]
    collected, trace = [], []
    async with httpx.AsyncClient(timeout=180) as client:
        for _ in range(max_iterations):
            body = {"model": settings.llm_model, "messages": convo, "tools": tool_specs("openai"), "tool_choice": "auto"}
            r = await client.post(url, headers=headers, json=body)
            if r.status_code >= 400:
                return {"llm": True, "error": f"LLM provider returned {r.status_code}: {r.text[:400]}",
                        "tool_results": collected, "trace": trace}
            data = r.json()
            msg = data["choices"][0]["message"]
            convo.append(msg)
            calls = msg.get("tool_calls") or []
            if not calls:
                return {"llm": True, "provider": "openai-compatible", "model": settings.llm_model,
                        "reply": msg.get("content"), "tool_results": collected, "trace": trace,
                        "usage": data.get("usage")}
            for c in calls:
                name = c["function"]["name"]
                try:
                    args = json.loads(c["function"].get("arguments") or "{}")
                except json.JSONDecodeError:
                    args = {}
                res = await call_tool(name, args)
                trace.append({"tool": name, "input": args, "ok": "error" not in res})
                collected.append({"tool": name, "input": args, "result": res})
                convo.append({"role": "tool", "tool_call_id": c["id"],
                              "content": json.dumps(res, default=str)[:60000]})
    return {"llm": True, "provider": "openai-compatible", "reply": None, "tool_results": collected, "trace": trace,
            "error": f"Stopped after {max_iterations} tool-calling rounds without a final answer."}


# ------------------------------------------------------------------ reporting

def build_report(project: dict, runs: list[dict], papers: list[dict], artifacts: list[dict]) -> str:
    """Assemble a Markdown report purely from recorded runs. No model is involved,
    so nothing in it can be fabricated."""
    lines = [f"# {project['name']}", ""]
    if project.get("objective"):
        lines += ["## Research objective", "", project["objective"], ""]
    if project.get("description"):
        lines += [project["description"], ""]
    lines += ["## Computational provenance", "",
              "Every row below is a recorded execution in this project. "
              "Results not listed here were not produced by BioIDE.", "",
              "| Run | Analysis | Tool | Version | Status | Duration (s) | Summary |",
              "|---|---|---|---|---|---|---|"]
    for r in runs:
        summary = json.dumps(r.get("summary")) if r.get("summary") else (r.get("error") or "")
        lines.append(f"| `{r['id'][:8]}` | {r['kind']} | {r['tool']} | {r['tool_version']} | "
                     f"{r['status']} | {r.get('duration_s', '')} | {str(summary)[:110].replace('|', '/')} |")
    failed = [r for r in runs if r["status"] == "failed"]
    if failed:
        lines += ["", f"**{len(failed)} run(s) failed.** Failures are listed above with their status; "
                      "their outputs are not included in any result below.", ""]
    if artifacts:
        lines += ["", "## Artifacts", "", "| Kind | Name | Version |", "|---|---|---|"]
        for a in artifacts:
            lines.append(f"| {a['kind']} | {a['name']} | v{a['version']} |")
    if papers:
        lines += ["", "## Literature collected", ""]
        for p in papers:
            auth = ", ".join((p.get("authors") or [])[:3]) + (" et al." if len(p.get("authors") or []) > 3 else "")
            ident = f"https://doi.org/{p['doi']}" if p.get("doi") else (f"PMID {p['pmid']}" if p.get("pmid") else "")
            lines.append(f"- {auth} ({p.get('year', 'n.d.')}). {p.get('title')}. *{p.get('journal') or ''}*. {ident}")
    lines += ["", "## Interpretation limits", "",
              "- Constraint-based results (FBA, FVA, deletion scans) are predictions under an assumed objective and medium, not measurements.",
              "- Differential expression results are statistical associations under the stated design.",
              "- ORF predictions and structure predictions are computational hypotheses requiring validation.",
              "- Any step marked as needing a local database or GPU did not run in BioIDE.", ""]
    return "\n".join(lines)
