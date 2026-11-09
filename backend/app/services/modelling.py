"""Constraint-based metabolic modelling with COBRApy.

Every flux value returned here comes from an LP/QP solved by COBRApy. The LLM
layer may configure an analysis through these functions; it never supplies numbers.
"""
from __future__ import annotations

import tempfile
import threading
import time
from pathlib import Path
from typing import Any

import cobra
from cobra import Metabolite, Reaction
from cobra.flux_analysis import (flux_variability_analysis, pfba, production_envelope,
                                 single_gene_deletion, single_reaction_deletion)
from cobra.io import load_json_model, load_model, read_sbml_model

from ..store import fingerprint, tracked_run

cobra.Configuration().processes = 1  # predictable behaviour inside a web worker

BUNDLED = {
    "e_coli_core": {
        "loader": "textbook",
        "label": "E. coli core (textbook, 95 reactions)",
        "source": "Orth, Fleming & Palsson (2010), EcoSal Plus; distributed with COBRApy",
    },
    "iJO1366": {
        "loader": "iJO1366",
        "label": "E. coli K-12 MG1655 iJO1366",
        "source": "Orth et al. (2011) Mol Syst Biol 7:535; distributed with COBRApy",
    },
    "salmonella": {
        "loader": "salmonella",
        "label": "Salmonella enterica Typhimurium STM_v1.0",
        "source": "Thiele et al. (2011) BMC Syst Biol; distributed with COBRApy",
    },
}

_models: dict[str, cobra.Model] = {}
_meta: dict[str, dict] = {}
_locks: dict[str, threading.Lock] = {}
_guard = threading.Lock()


def _lock(mid: str) -> threading.Lock:
    with _guard:
        return _locks.setdefault(mid, threading.Lock())


def _register(mid: str, m: cobra.Model, label: str, source: str) -> None:
    _models[mid] = m
    _meta[mid] = {"id": mid, "label": label, "source": source, "loaded_at": time.time()}


def get_model(model_id: str) -> cobra.Model:
    if model_id in _models:
        return _models[model_id]
    if model_id in BUNDLED:
        m = load_model(BUNDLED[model_id]["loader"])
        _register(model_id, m, BUNDLED[model_id]["label"], BUNDLED[model_id]["source"])
        return m
    raise KeyError(f"Model '{model_id}' is not available. Choose a bundled model or upload an SBML file.")


def model_meta(model_id: str) -> dict:
    get_model(model_id)
    return _meta[model_id]


def list_models() -> list[dict]:
    out = [{"id": k, "label": v["label"], "source": v["source"], "loaded": k in _models, "bundled": True}
           for k, v in BUNDLED.items()]
    out += [dict(v, loaded=True, bundled=False) for k, v in _meta.items() if k not in BUNDLED]
    return out


def import_model(filename: str, content: bytes) -> dict:
    suffix = Path(filename).suffix.lower()
    with tempfile.NamedTemporaryFile(suffix=suffix or ".xml", delete=False) as fh:
        fh.write(content)
        path = fh.name
    try:
        if suffix in {".xml", ".sbml", ""}:
            m = read_sbml_model(path)
        elif suffix == ".json":
            m = load_json_model(path)
        else:
            raise ValueError("Supported formats: SBML (.xml/.sbml) or COBRA JSON (.json)")
    finally:
        Path(path).unlink(missing_ok=True)
    mid = "upload_" + fingerprint(content).split(":")[1][:10]
    _register(mid, m, f"{m.id or filename} (uploaded)", f"user upload: {filename}")
    return mid


# ----------------------------------------------------------------- inspection

def _ex_bounds(m: cobra.Model, limit: int = 400) -> list[dict]:
    rows = []
    for r in m.exchanges:
        if r.lower_bound < 0 or r.upper_bound > 0:
            rows.append({"id": r.id, "name": r.name, "lower_bound": r.lower_bound, "upper_bound": r.upper_bound,
                         "open_uptake": r.lower_bound < 0})
    rows.sort(key=lambda x: (not x["open_uptake"], x["id"]))
    return rows[:limit]


def quality_report(m: cobra.Model) -> dict:
    """Structural checks that matter before trusting any simulation."""
    blocked_mass, no_formula = [], []
    for r in m.reactions:
        if r.boundary:
            continue
        try:
            imb = r.check_mass_balance()
        except Exception:
            no_formula.append(r.id)
            continue
        if imb:
            if any(k == "charge" or k.isalpha() for k in imb):
                blocked_mass.append({"id": r.id, "imbalance": {k: round(float(v), 4) for k, v in imb.items()}})
    orphans = [met.id for met in m.metabolites if not met.reactions]
    dead_ends = [met.id for met in m.metabolites
                 if met.reactions and (all(r.metabolites[met] < 0 for r in met.reactions)
                                       or all(r.metabolites[met] > 0 for r in met.reactions))]
    missing_gpr = [r.id for r in m.reactions if not r.boundary and not r.gene_reaction_rule]
    return {
        "mass_or_charge_imbalanced": {"count": len(blocked_mass), "examples": blocked_mass[:25]},
        "reactions_unverifiable_no_formula": {"count": len(no_formula), "examples": no_formula[:25]},
        "orphan_metabolites": {"count": len(orphans), "examples": orphans[:25]},
        "dead_end_metabolites": {"count": len(dead_ends), "examples": dead_ends[:25]},
        "reactions_without_gpr": {"count": len(missing_gpr), "examples": missing_gpr[:25]},
        "note": "Exchange and demand reactions are excluded from balance checks by design. "
                "Imbalances involving only H are common in curated models and usually benign.",
    }


def inspect(model_id: str, with_quality: bool = False) -> dict:
    m = get_model(model_id)
    with _lock(model_id):
        obj = [{"id": r.id, "name": r.name, "coefficient": r.objective_coefficient}
               for r in m.reactions if r.objective_coefficient]
        growth = m.slim_optimize()
        compartments = dict(m.compartments)
        subsystems: dict[str, int] = {}
        for r in m.reactions:
            subsystems[r.subsystem or "(unassigned)"] = subsystems.get(r.subsystem or "(unassigned)", 0) + 1
    out = {
        "id": model_id, "model_name": m.id, "label": _meta[model_id]["label"], "source": _meta[model_id]["source"],
        "counts": {"reactions": len(m.reactions), "metabolites": len(m.metabolites), "genes": len(m.genes),
                   "exchanges": len(m.exchanges)},
        "objective": obj, "objective_direction": m.objective_direction,
        "objective_value_default_medium": None if growth is None else round(float(growth), 6),
        "compartments": compartments,
        "subsystems": sorted(subsystems.items(), key=lambda kv: -kv[1])[:40],
        "exchanges": _ex_bounds(m),
        "solver": str(cobra.Configuration().solver.__name__ if hasattr(cobra.Configuration().solver, "__name__") else cobra.Configuration().solver),
        "cobrapy_version": cobra.__version__,
    }
    if with_quality:
        out["quality"] = quality_report(m)
    return out


def search_entities(model_id: str, query: str, kind: str = "reaction", limit: int = 50) -> list[dict]:
    m = get_model(model_id)
    q = query.lower().strip()
    rows = []
    if kind == "reaction":
        for r in m.reactions:
            if q in r.id.lower() or q in (r.name or "").lower() or q in (r.subsystem or "").lower():
                rows.append({"id": r.id, "name": r.name, "subsystem": r.subsystem, "reaction": r.build_reaction_string(True),
                             "lower_bound": r.lower_bound, "upper_bound": r.upper_bound, "gpr": r.gene_reaction_rule})
    elif kind == "metabolite":
        for met in m.metabolites:
            if q in met.id.lower() or q in (met.name or "").lower():
                rows.append({"id": met.id, "name": met.name, "formula": met.formula, "charge": met.charge,
                             "compartment": met.compartment, "n_reactions": len(met.reactions)})
    elif kind == "gene":
        for g in m.genes:
            if q in g.id.lower() or q in (g.name or "").lower():
                rows.append({"id": g.id, "name": g.name, "reactions": [r.id for r in g.reactions]})
    else:
        raise ValueError("kind must be reaction, metabolite or gene")
    return rows[:limit]


def reaction_detail(model_id: str, rid: str) -> dict:
    m = get_model(model_id)
    r = m.reactions.get_by_id(rid)
    return {
        "id": r.id, "name": r.name, "subsystem": r.subsystem, "reaction": r.build_reaction_string(True),
        "lower_bound": r.lower_bound, "upper_bound": r.upper_bound, "reversible": r.reversibility,
        "gpr": r.gene_reaction_rule, "genes": [g.id for g in r.genes],
        "metabolites": [{"id": k.id, "name": k.name, "coefficient": v, "compartment": k.compartment} for k, v in r.metabolites.items()],
        "annotation": {k: v for k, v in list(r.annotation.items())[:12]},
    }


# ----------------------------------------------------------------- medium / edits

def _apply(m: cobra.Model, bounds: dict[str, list[float]] | None, knockouts: list[str] | None,
           gene_knockouts: list[str] | None, objective: str | None, added: list[dict] | None) -> list[str]:
    log: list[str] = []
    for spec in added or []:
        log.append(add_reaction(m, spec))
    for rid, (lb, ub) in (bounds or {}).items():
        r = m.reactions.get_by_id(rid)
        r.bounds = (float(lb), float(ub))
        log.append(f"bounds {rid} = ({lb}, {ub})")
    for rid in knockouts or []:
        m.reactions.get_by_id(rid).knock_out()
        log.append(f"reaction knockout {rid}")
    for gid in gene_knockouts or []:
        m.genes.get_by_id(gid).knock_out()
        log.append(f"gene knockout {gid}")
    if objective:
        m.objective = objective
        log.append(f"objective = {objective}")
    return log


def add_reaction(m: cobra.Model, spec: dict) -> str:
    """Add a user-specified reaction. `spec` must carry an id, a stoichiometry map
    of metabolite-id -> coefficient and bounds. New metabolites need a formula and
    compartment so mass-balance checking still works."""
    rid = spec["id"]
    if rid in m.reactions:
        return f"reaction {rid} already present; not modified"
    for met in spec.get("new_metabolites", []):
        if met["id"] not in m.metabolites:
            m.add_metabolites([Metabolite(met["id"], formula=met.get("formula"), name=met.get("name", met["id"]),
                                          charge=met.get("charge"), compartment=met.get("compartment", "c"))])
    unknown = [k for k in spec["stoichiometry"] if k not in m.metabolites]
    if unknown:
        raise ValueError(f"Unknown metabolites {unknown}. Declare them under new_metabolites with a formula and compartment.")
    r = Reaction(rid, name=spec.get("name", rid), subsystem=spec.get("subsystem", "user-added"),
                 lower_bound=float(spec.get("lower_bound", 0)), upper_bound=float(spec.get("upper_bound", 1000)))
    m.add_reactions([r])
    r.add_metabolites({m.metabolites.get_by_id(k): float(v) for k, v in spec["stoichiometry"].items()})
    if spec.get("gpr"):
        r.gene_reaction_rule = spec["gpr"]
    imb = r.check_mass_balance()
    return f"added reaction {rid}" + (f" (WARNING unbalanced: {imb})" if imb else " (mass/charge balanced)")


# ----------------------------------------------------------------- analyses

def _ctx(model_id: str, cfg: dict):
    m = get_model(model_id)
    return m, _lock(model_id)


def run_fba(model_id: str, bounds=None, knockouts=None, gene_knockouts=None, objective=None,
            added_reactions=None, parsimonious: bool = False, top: int = 60, project_id: str | None = None) -> dict:
    params = {"model": model_id, "bounds": bounds, "knockouts": knockouts, "gene_knockouts": gene_knockouts,
              "objective": objective, "added_reactions": added_reactions, "parsimonious": parsimonious}
    m = get_model(model_id)
    with tracked_run("fba", "cobrapy", cobra.__version__, params, fingerprint(repr(params)), project_id) as run:
        with _lock(model_id), m:
            log = _apply(m, bounds, knockouts, gene_knockouts, objective, added_reactions)
            t0 = time.time()
            sol = pfba(m) if parsimonious else m.optimize()
            elapsed = time.time() - t0
            status = sol.status
            fluxes = sol.fluxes if status == "optimal" else None
            obj_val = float(sol.objective_value) if status == "optimal" else None
            shadow = {}
            reduced = {}
            if status == "optimal" and not parsimonious:
                try:
                    shadow = {k: round(float(v), 6) for k, v in sol.shadow_prices.items() if abs(v) > 1e-9}
                    reduced = {k: round(float(v), 6) for k, v in sol.reduced_costs.items() if abs(v) > 1e-9}
                except Exception:
                    pass
            active = []
            if fluxes is not None:
                nz = fluxes[fluxes.abs() > 1e-9]
                active = [{"id": k, "flux": round(float(v), 6), "name": m.reactions.get_by_id(k).name,
                           "subsystem": m.reactions.get_by_id(k).subsystem,
                           "equation": m.reactions.get_by_id(k).build_reaction_string(True)}
                          for k, v in nz.reindex(nz.abs().sort_values(ascending=False).index).items()]
            exch = []
            if fluxes is not None:
                for r in m.exchanges:
                    f = float(fluxes.get(r.id, 0.0))
                    if abs(f) > 1e-9:
                        exch.append({"id": r.id, "name": r.name, "flux": round(f, 6),
                                     "direction": "uptake" if f < 0 else "secretion"})
                exch.sort(key=lambda x: -abs(x["flux"]))
        out = {
            "model": model_id, "method": "pFBA" if parsimonious else "FBA",
            "status": status, "objective_value": None if obj_val is None else round(obj_val, 6),
            "objective_reactions": [r.id for r in m.reactions if r.objective_coefficient] if not objective else [objective],
            "solve_seconds": round(elapsed, 3),
            "modifications": log,
            "active_reactions": active[:top], "active_reaction_count": len(active),
            "exchange_fluxes": exch,
            "shadow_prices_top": sorted(shadow.items(), key=lambda kv: -abs(kv[1]))[:20],
            "reduced_costs_top": sorted(reduced.items(), key=lambda kv: -abs(kv[1]))[:20],
            "all_fluxes": {k: round(float(v), 8) for k, v in fluxes.items()} if fluxes is not None else {},
        }
        if status != "optimal":
            out["interpretation"] = (f"The LP is {status}: with these constraints no feasible steady-state flux "
                                     "distribution supports the objective. Check that required uptake exchanges are open.")
        run.summary = {"status": status, "objective_value": out["objective_value"], "active": len(active)}
    out["provenance"] = run.provenance()
    out["caveats"] = [
        "FBA predicts a flux distribution that is optimal under the stated objective; it is not a measurement.",
        "Optimal flux distributions are frequently non-unique. Use FVA or pFBA before reading individual fluxes as predictions.",
        "Growth is in the model's own units, normally mmol gDW^-1 h^-1 for fluxes and h^-1 for biomass.",
    ]
    return out


def run_fva(model_id: str, reactions: list[str] | None = None, fraction: float = 0.9, loopless: bool = False,
            bounds=None, knockouts=None, gene_knockouts=None, objective=None, added_reactions=None,
            project_id: str | None = None) -> dict:
    params = {"model": model_id, "reactions": reactions, "fraction_of_optimum": fraction, "loopless": loopless,
              "bounds": bounds, "knockouts": knockouts, "gene_knockouts": gene_knockouts, "objective": objective}
    m = get_model(model_id)
    if reactions is None and len(m.reactions) > 600:
        raise ValueError(f"FVA over all {len(m.reactions)} reactions is expensive. "
                         "Pass an explicit reaction list (a subsystem's reactions, say) or use the core model.")
    with tracked_run("fva", "cobrapy", cobra.__version__, params, fingerprint(repr(params)), project_id) as run:
        with _lock(model_id), m:
            _apply(m, bounds, knockouts, gene_knockouts, objective, added_reactions)
            rxns = [m.reactions.get_by_id(r) for r in reactions] if reactions else None
            t0 = time.time()
            df = flux_variability_analysis(m, reaction_list=rxns, fraction_of_optimum=fraction, loopless=loopless)
            elapsed = time.time() - t0
            rows = []
            for rid, row in df.iterrows():
                lo, hi = float(row["minimum"]), float(row["maximum"])
                span = hi - lo
                rows.append({"id": rid, "name": m.reactions.get_by_id(rid).name,
                             "subsystem": m.reactions.get_by_id(rid).subsystem,
                             "minimum": round(lo, 6), "maximum": round(hi, 6), "span": round(span, 6),
                             "classification": ("blocked" if abs(hi) < 1e-9 and abs(lo) < 1e-9 else
                                                "fixed" if span < 1e-9 else
                                                "variable_reversible" if lo < -1e-9 < 1e-9 < hi else "variable")})
        rows.sort(key=lambda r: -r["span"])
        out = {"model": model_id, "fraction_of_optimum": fraction, "loopless": loopless,
               "n_reactions": len(rows), "solve_seconds": round(elapsed, 3), "ranges": rows,
               "summary_counts": {k: sum(1 for r in rows if r["classification"] == k)
                                  for k in ("blocked", "fixed", "variable", "variable_reversible")}}
        run.summary = out["summary_counts"] | {"n": len(rows)}
    out["provenance"] = run.provenance()
    out["caveats"] = ["A wide FVA interval means the flux is not determined by the model, so a single FBA value for it should not be reported as a prediction.",
                      "Without loopless=True, intervals can be inflated by thermodynamically infeasible internal cycles."]
    return out


def run_deletions(model_id: str, level: str = "gene", ids: list[str] | None = None, method: str = "fba",
                  bounds=None, objective=None, project_id: str | None = None) -> dict:
    params = {"model": model_id, "level": level, "ids": ids, "method": method, "bounds": bounds, "objective": objective}
    m = get_model(model_id)
    pool = len(m.genes) if level == "gene" else len(m.reactions)
    if ids is None and pool > 1500:
        raise ValueError(f"A genome-wide {level} deletion scan over {pool} targets is expensive here. Pass an explicit id list.")
    with tracked_run(f"{level}_deletion", "cobrapy", cobra.__version__, params, fingerprint(repr(params)), project_id) as run:
        with _lock(model_id), m:
            _apply(m, bounds, None, None, objective, None)
            wt = m.slim_optimize()
            t0 = time.time()
            if level == "gene":
                df = single_gene_deletion(m, gene_list=ids, method=method)
            else:
                df = single_reaction_deletion(m, reaction_list=ids, method=method)
            elapsed = time.time() - t0
        rows = []
        for _, row in df.iterrows():
            raw = row["ids"] if "ids" in df.columns else _
            name = ";".join(sorted(raw)) if isinstance(raw, (frozenset, set, list, tuple)) else str(raw)
            g = row.get("growth")
            g = None if g is None or (isinstance(g, float) and g != g) else float(g)
            ratio = None if (g is None or not wt) else g / wt
            label = name
            if level == "gene":
                try:
                    gene = m.genes.get_by_id(name)
                    if gene.name and gene.name != name:
                        label = f"{name} ({gene.name})"
                except Exception:
                    pass
            rows.append({"id": name, "label": label, "growth": None if g is None else round(g, 6),
                         "ratio_to_wildtype": None if ratio is None else round(ratio, 4),
                         "status": row.get("status"),
                         "phenotype": ("lethal" if ratio is not None and ratio < 0.01 else
                                       "severe" if ratio is not None and ratio < 0.5 else
                                       "mild" if ratio is not None and ratio < 0.95 else "neutral") if ratio is not None else "unsolved"})
        rows.sort(key=lambda r: (r["ratio_to_wildtype"] is None, r["ratio_to_wildtype"]))
        out = {"model": model_id, "level": level, "method": method,
               "wildtype_objective": None if wt is None else round(float(wt), 6),
               "solve_seconds": round(elapsed, 3), "results": rows,
               "counts": {k: sum(1 for r in rows if r["phenotype"] == k) for k in ("lethal", "severe", "mild", "neutral", "unsolved")}}
        run.summary = out["counts"]
    out["provenance"] = run.provenance()
    out["caveats"] = ["In-silico essentiality depends on the simulated medium; a gene essential on minimal glucose may be dispensable on rich medium.",
                      "Model essentiality predictions disagree with experimental screens for a meaningful fraction of genes."]
    return out


def run_envelope(model_id: str, target: str, carbon_source: str | None = None, points: int = 20,
                 bounds=None, project_id: str | None = None) -> dict:
    """Production envelope: the trade-off between growth and a target exchange/demand flux."""
    params = {"model": model_id, "target": target, "carbon_source": carbon_source, "points": points, "bounds": bounds}
    m = get_model(model_id)
    with tracked_run("production_envelope", "cobrapy", cobra.__version__, params, fingerprint(repr(params)), project_id) as run:
        with _lock(model_id), m:
            _apply(m, bounds, None, None, None, None)
            t0 = time.time()
            df = production_envelope(m, reactions=[target], carbon_sources=carbon_source, points=points)
            elapsed = time.time() - t0
        cols = [c for c in df.columns]
        rows = df.astype(object).where(df.notna(), None).to_dict("records")

        def _clean(v: Any) -> Any:
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                f = float(v)
                return None if f != f or f in (float("inf"), float("-inf")) else round(f, 6)
            return v

        out = {"model": model_id, "target": target, "carbon_source": carbon_source, "columns": cols,
               "points": [{k: _clean(v) for k, v in r.items()} for r in rows],
               "solve_seconds": round(elapsed, 3)}
        run.summary = {"points": len(rows), "target": target}
    out["provenance"] = run.provenance()
    out["caveats"] = ["The envelope is the theoretical stoichiometric limit, not an achievable titre; it ignores kinetics, regulation and toxicity."]
    return out


def network_graph(model_id: str, fluxes: dict | None = None, subsystem: str | None = None,
                  seed_reactions: list[str] | None = None, max_nodes: int = 160,
                  hub_degree: int = 12) -> dict:
    """Bipartite reaction/metabolite graph for visualisation. Highly connected
    cofactors are dropped, otherwise the layout is unreadable."""
    m = get_model(model_id)
    if seed_reactions:
        rxns = [m.reactions.get_by_id(r) for r in seed_reactions if r in m.reactions]
    elif subsystem:
        rxns = [r for r in m.reactions if (r.subsystem or "") == subsystem]
    elif fluxes:
        ranked = sorted(((k, abs(v)) for k, v in fluxes.items() if abs(v) > 1e-9), key=lambda kv: -kv[1])
        rxns = [m.reactions.get_by_id(k) for k, _ in ranked if k in m.reactions]
    else:
        rxns = [r for r in m.reactions if not r.boundary]
    rxns = rxns[:max_nodes]
    degree: dict[str, int] = {}
    for r in rxns:
        for met in r.metabolites:
            degree[met.id] = degree.get(met.id, 0) + 1
    hubs = {k for k, v in degree.items() if v > hub_degree}
    nodes, edges = [], []
    for r in rxns:
        f = float((fluxes or {}).get(r.id, 0.0))
        nodes.append({"id": r.id, "type": "reaction", "label": r.id, "name": r.name,
                      "subsystem": r.subsystem, "flux": round(f, 6)})
        for met, coeff in r.metabolites.items():
            if met.id in hubs:
                continue
            if not any(n["id"] == met.id for n in nodes):
                nodes.append({"id": met.id, "type": "metabolite", "label": met.name or met.id,
                              "formula": met.formula, "compartment": met.compartment})
            src, tgt = (met.id, r.id) if coeff < 0 else (r.id, met.id)
            if f < 0:
                src, tgt = tgt, src
            edges.append({"source": src, "target": tgt, "coefficient": coeff, "flux": round(abs(f), 6)})
    return {"model": model_id, "nodes": nodes, "edges": edges,
            "omitted_hub_metabolites": sorted(hubs)[:40],
            "note": f"Metabolites appearing in more than {hub_degree} shown reactions were omitted as cofactor hubs."}


def compare_runs(model_id: str, runs: list[dict], top: int = 40) -> dict:
    """Compare flux dictionaries from two or more completed FBA runs."""
    if len(runs) < 2:
        raise ValueError("Provide at least two runs to compare.")
    m = get_model(model_id)
    keys = set().union(*[set(r.get("fluxes", {})) for r in runs])
    rows = []
    for k in keys:
        vals = [float(r.get("fluxes", {}).get(k, 0.0)) for r in runs]
        spread = max(vals) - min(vals)
        if spread > 1e-6:
            rows.append({"id": k, "name": m.reactions.get_by_id(k).name if k in m.reactions else k,
                         "subsystem": m.reactions.get_by_id(k).subsystem if k in m.reactions else None,
                         "values": [round(v, 6) for v in vals], "spread": round(spread, 6)})
    rows.sort(key=lambda r: -r["spread"])
    return {"labels": [r.get("label", f"run {i+1}") for i, r in enumerate(runs)],
            "differences": rows[:top], "n_differing": len(rows)}
