"""Omics analysis: count-matrix QC, differential expression (PyDESeq2), PCA,
clustering and enrichment over user-supplied gene sets.

Every number here comes from the named library. Nothing is interpolated.
"""
from __future__ import annotations

import io
from typing import Any

import numpy as np
import pandas as pd
import pydeseq2
import scipy
from pydeseq2.dds import DeseqDataSet
from pydeseq2.ds import DeseqStats
from scipy import stats as sstats
from scipy.cluster.hierarchy import leaves_list, linkage
from scipy.spatial.distance import pdist

from ..config import SAMPLES_DIR
from ..store import fingerprint, tracked_run

SAMPLE_DATASETS = {
    "airway": {
        "label": "Airway smooth muscle, dexamethasone vs control (GSE52778)",
        "citation": "Himes et al. (2014) PLoS ONE 9(6):e99625. GEO accession GSE52778.",
        "licence": "Public GEO submission; counts as distributed with the Bioconductor 'airway' package.",
        "counts": "airway_counts.csv.gz", "metadata": "airway_metadata.csv",
        "design": "~ celltype + dex", "contrast": ["dex", "treated", "control"],
        "note": "Four donor cell lines, each with an untreated and a dexamethasone-treated sample: a paired design, "
                "so include 'celltype' in the design formula.",
    }
}


# ----------------------------------------------------------------- loading

def read_table(content: bytes | str, filename: str = "table.csv") -> pd.DataFrame:
    if isinstance(content, str):
        content = content.encode()
    name = filename.lower()
    if name.endswith(".gz"):
        import gzip
        content = gzip.decompress(content)
        name = name[:-3]
    sep = "\t" if name.endswith((".tsv", ".txt")) else ","
    df = pd.read_csv(io.BytesIO(content), sep=sep, index_col=0)
    df.index = df.index.astype(str)
    return df


def load_sample_dataset(key: str) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    if key not in SAMPLE_DATASETS:
        raise ValueError(f"Unknown dataset '{key}'. Available: {list(SAMPLE_DATASETS)}")
    spec = SAMPLE_DATASETS[key]
    counts = read_table((SAMPLES_DIR / spec["counts"]).read_bytes(), spec["counts"])
    meta = read_table((SAMPLES_DIR / spec["metadata"]).read_bytes(), spec["metadata"])
    return counts, meta, spec


# ----------------------------------------------------------------- QC

def qc(counts: pd.DataFrame, metadata: pd.DataFrame | None = None, project_id: str | None = None) -> dict:
    """Library-size, detection and dispersion-independent QC on a raw count matrix."""
    problems: list[str] = []
    if counts.isna().any().any():
        problems.append(f"{int(counts.isna().sum().sum())} missing values present; DE tools require a complete matrix.")
    numeric = counts.apply(pd.to_numeric, errors="coerce")
    if numeric.isna().any().any() and not counts.isna().any().any():
        problems.append("Some columns are not numeric; check for a gene-symbol column that should be part of the index.")
    if (numeric.fillna(0) < 0).any().any():
        problems.append("Negative values present: this is not a raw count matrix.")
    frac_int = float(np.mean(np.isclose(numeric.fillna(0) % 1, 0)))
    if frac_int < 0.999:
        problems.append("Values are not integers. PyDESeq2 and DESeq2 model raw counts; "
                        "normalised values (TPM/FPKM/RPKM) or transcript-level estimates must not be used directly.")
    with tracked_run("omics_qc", "pandas+numpy", f"pandas {pd.__version__}",
                     {"genes": int(counts.shape[0]), "samples": int(counts.shape[1])},
                     fingerprint(counts.to_csv()), project_id) as run:
        lib = numeric.sum().astype(float)
        detected = (numeric > 0).sum()
        cpm = numeric.div(lib.replace(0, np.nan), axis=1) * 1e6
        log = np.log2(cpm.fillna(0) + 1)
        keep = (numeric.sum(axis=1) > 0)
        corr = log.loc[keep].corr(method="spearman") if keep.sum() > 10 else pd.DataFrame()
        top = numeric.loc[keep].sum(axis=1).sort_values(ascending=False).head(15)
        pct_top = (numeric.loc[top.index].sum() / lib.replace(0, np.nan) * 100).round(2)
        out = {
            "shape": {"genes": int(counts.shape[0]), "samples": int(counts.shape[1])},
            "samples": [
                {"sample": s, "library_size": int(lib[s]), "genes_detected": int(detected[s]),
                 "detection_rate": round(float(detected[s] / counts.shape[0]), 4),
                 "pct_counts_in_top15_genes": float(pct_top.get(s, float("nan")))}
                for s in counts.columns
            ],
            "library_size_ratio_max_min": round(float(lib.max() / lib.min()), 2) if lib.min() > 0 else None,
            "genes_all_zero": int((numeric.sum(axis=1) == 0).sum()),
            "genes_detected_in_all_samples": int(((numeric > 0).sum(axis=1) == counts.shape[1]).sum()),
            "log2cpm_boxplot": {s: _five_number(log[s][keep]) for s in counts.columns},
            "spearman_sample_correlation": {"samples": list(corr.columns), "matrix": corr.round(4).values.tolist()} if not corr.empty else None,
            "top_expressed_genes": [{"gene": g, "total_counts": int(v)} for g, v in top.items()],
            "problems": problems,
            "metadata_columns": {c: sorted(map(str, metadata[c].unique()))[:12] for c in metadata.columns} if metadata is not None else None,
        }
        run.summary = {"genes": out["shape"]["genes"], "samples": out["shape"]["samples"], "problems": len(problems)}
    out["provenance"] = run.provenance()
    return out


def _five_number(s: pd.Series) -> dict:
    q = s.quantile([0, 0.25, 0.5, 0.75, 1]).round(3)
    return {"min": float(q.iloc[0]), "q1": float(q.iloc[1]), "median": float(q.iloc[2]),
            "q3": float(q.iloc[3]), "max": float(q.iloc[4])}


# ----------------------------------------------------------------- DE

def differential_expression(counts: pd.DataFrame, metadata: pd.DataFrame, design: str,
                            contrast: list[str], min_count_sum: int = 10, alpha: float = 0.05,
                            lfc_shrink: bool = True, project_id: str | None = None) -> dict:
    """Negative-binomial differential expression with PyDESeq2.

    design: an R-style formula over metadata columns, e.g. '~ celltype + dex'
    contrast: [factor, test_level, reference_level]
    """
    meta = metadata.copy()
    meta.index = meta.index.astype(str)
    counts = counts.copy()
    counts.columns = [str(c) for c in counts.columns]
    shared = [s for s in counts.columns if s in meta.index]
    if len(shared) < 2:
        raise ValueError("Count matrix columns do not match metadata row names. "
                         f"Counts: {list(counts.columns)[:5]}; metadata index: {list(meta.index)[:5]}")
    counts, meta = counts[shared], meta.loc[shared]

    factors = [t.strip() for t in design.replace("~", "").split("+") if t.strip()]
    missing = [f for f in factors if f not in meta.columns]
    if missing:
        raise ValueError(f"Design factors {missing} are not metadata columns. Available: {list(meta.columns)}")
    factor, test_level, ref_level = contrast
    if factor not in meta.columns:
        raise ValueError(f"Contrast factor '{factor}' is not a metadata column.")
    levels = set(map(str, meta[factor].unique()))
    if not {test_level, ref_level} <= levels:
        raise ValueError(f"Contrast levels {test_level}/{ref_level} not found in '{factor}' (levels: {sorted(levels)}).")
    for f in factors:
        meta[f] = meta[f].astype(str)
    n_per = meta[factor].value_counts().to_dict()
    if min(n_per.get(test_level, 0), n_per.get(ref_level, 0)) < 2:
        raise ValueError(f"Each contrast group needs at least 2 replicates (found {n_per}). "
                         "Dispersion cannot be estimated without replication.")

    keep = counts.sum(axis=1) >= min_count_sum
    filtered = counts.loc[keep].T.astype(int)
    params = {"design": design, "contrast": contrast, "min_count_sum": min_count_sum, "alpha": alpha,
              "lfc_shrink": lfc_shrink, "genes_tested": int(keep.sum()), "samples": len(shared)}
    with tracked_run("differential_expression", "pydeseq2", pydeseq2.__version__, params,
                     fingerprint(counts.to_csv()), project_id) as run:
        dds = DeseqDataSet(counts=filtered, metadata=meta, design=design, refit_cooks=True, quiet=True)
        dds.deseq2()
        st = DeseqStats(dds, contrast=[factor, test_level, ref_level], alpha=alpha, quiet=True)
        st.summary()
        res = st.results_df.copy()
        if lfc_shrink:
            try:
                st.lfc_shrink(coeff=f"{factor}[T.{test_level}]")
                res = st.results_df.copy()
                shrunk = True
            except Exception as exc:  # shrinkage is optional; report honestly if it fails
                shrunk = False
                res.attrs["shrink_error"] = str(exc)
        else:
            shrunk = False
        res.index.name = "gene"
        res = res.replace([np.inf, -np.inf], np.nan)
        sig = res[(res["padj"] < alpha)]
        norm = pd.DataFrame(dds.layers["normed_counts"], index=dds.obs_names, columns=dds.var_names).T
        disp = pd.Series(np.asarray(dds.var["dispersions"], dtype=float), index=dds.var_names)
        disp_fit = pd.Series(np.asarray(dds.var["fitted_dispersions"], dtype=float), index=dds.var_names)
        size_factors = pd.Series(np.asarray(dds.obs["size_factors"], dtype=float), index=dds.obs_names)
        out = {
            "method": "PyDESeq2 Wald test, Benjamini–Hochberg adjusted",
            "pydeseq2_version": pydeseq2.__version__,
            "design": design, "contrast": {"factor": factor, "test": test_level, "reference": ref_level},
            "group_sizes": n_per, "alpha": alpha, "lfc_shrinkage_applied": shrunk,
            "genes_input": int(counts.shape[0]), "genes_after_filter": int(keep.sum()),
            "filter": f"sum of raw counts across samples >= {min_count_sum}",
            "n_significant": int(len(sig)),
            "n_up": int((sig["log2FoldChange"] > 0).sum()), "n_down": int((sig["log2FoldChange"] < 0).sum()),
            "n_padj_na": int(res["padj"].isna().sum()),
            "size_factors": {s: round(float(v), 4) for s, v in size_factors.items()},
            "dispersion_trend_type": dds.uns.get("disp_function_type"),
            "n_cooks_outlier_genes": int(np.asarray(dds.var["_outlier_genes"], dtype=bool).sum()) if "_outlier_genes" in dds.var else None,
            "results": _de_rows(res, 4000),
            "results_truncated": bool(len(res) > 4000),
            # Compact arrays covering EVERY tested gene, so the volcano plot is the
            # whole result and its counts agree with n_up / n_down above.
            "volcano": _volcano(res, alpha),
            "top_up": _de_rows(sig.sort_values("log2FoldChange", ascending=False), 25),
            "top_down": _de_rows(sig.sort_values("log2FoldChange"), 25),
            "most_significant": _de_rows(res.sort_values("padj"), 40),
            "dispersion_plot": {"gene": [str(g) for g in res.index[:6000]],
                                "base_mean": [_f(v) for v in res["baseMean"][:6000]],
                                "dispersion": [_f(v) for v in disp.reindex(res.index)[:6000]],
                                "fitted": [_f(v) for v in disp_fit.reindex(res.index)[:6000]]},
            "normalised_counts_top": {g: {s: round(float(norm.loc[g, s]), 2) for s in norm.columns}
                                      for g in res.sort_values("padj").index[:40] if g in norm.index},
            "metadata": meta.reset_index().rename(columns={"index": "sample"}).to_dict("records"),
        }
        run.summary = {"significant": out["n_significant"], "up": out["n_up"], "down": out["n_down"],
                       "tested": out["genes_after_filter"]}
    out["provenance"] = run.provenance()
    out["caveats"] = [
        "padj is NA where PyDESeq2 applied independent filtering or flagged a Cook's-distance outlier; those genes were not tested.",
        "A significant fold change is a statistical association under this design, not a mechanism.",
        f"{int(len(sig))} genes pass padj < {alpha}; with {len(shared)} samples, effect sizes for low-count genes stay poorly determined even after shrinkage.",
    ]
    return out


def _volcano(res: pd.DataFrame, alpha: float) -> dict:
    """Every gene with a computed padj, as parallel arrays.

    p-values that underflow to 0 in double precision cannot be plotted on a
    -log10 axis, so they are capped and counted separately rather than drawn at
    an arbitrary height without comment.
    """
    d = res[res["padj"].notna() & res["log2FoldChange"].notna()]
    padj = d["padj"].to_numpy(dtype=float)
    underflow = padj <= 0
    floor = 1e-300
    neglog = -np.log10(np.where(underflow, floor, padj))
    return {
        "gene": [str(g) for g in d.index],
        "log2fc": [round(float(v), 4) for v in d["log2FoldChange"]],
        "neglog10_padj": [round(float(v), 4) for v in neglog],
        "significant": [bool(v < alpha) for v in padj],
        "at_precision_floor": [bool(v) for v in underflow],
        "n_at_precision_floor": int(underflow.sum()),
        "n_plotted": int(len(d)),
        "n_excluded_padj_na": int(len(res) - len(d)),
        "floor_value": floor,
    }


def _de_rows(df: pd.DataFrame, n: int) -> list[dict]:
    rows = []
    for g, r in df.head(n).iterrows():
        rows.append({"gene": str(g),
                     "baseMean": _f(r.get("baseMean")), "log2FoldChange": _f(r.get("log2FoldChange")),
                     "lfcSE": _f(r.get("lfcSE")), "stat": _f(r.get("stat")),
                     "pvalue": _f(r.get("pvalue")), "padj": _f(r.get("padj"))})
    return rows


def _f(v: Any) -> float | None:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if f != f or abs(f) == float("inf") else round(f, 6)


# ----------------------------------------------------------------- PCA / clustering

def pca(counts: pd.DataFrame, metadata: pd.DataFrame | None = None, n_top: int = 500,
        transform: str = "log2cpm", project_id: str | None = None) -> dict:
    """PCA on the most variable features. Used for RNA-seq, proteomics and
    metabolomics matrices alike, but the transform must suit the technology."""
    num = counts.apply(pd.to_numeric, errors="coerce").fillna(0)
    with tracked_run("pca", "numpy", f"numpy {np.__version__}",
                     {"n_top": n_top, "transform": transform}, fingerprint(counts.to_csv()), project_id) as run:
        if transform == "log2cpm":
            lib = num.sum().replace(0, np.nan)
            X = np.log2(num.div(lib, axis=1) * 1e6 + 1)
        elif transform == "log2":
            X = np.log2(num.clip(lower=0) + 1)
        elif transform == "none":
            X = num
        else:
            raise ValueError("transform must be log2cpm, log2 or none")
        var = X.var(axis=1).sort_values(ascending=False)
        X = X.loc[var.index[:n_top]]
        M = X.T.values
        M = M - M.mean(0)
        U, S, Vt = np.linalg.svd(M, full_matrices=False)
        scores = U * S
        evr = (S ** 2) / (S ** 2).sum()
        k = min(4, scores.shape[1])
        out = {
            "transform": transform, "n_features_used": int(X.shape[0]),
            "explained_variance_ratio": [round(float(v), 4) for v in evr[:k]],
            "samples": [
                {"sample": s, **{f"PC{i+1}": round(float(scores[j, i]), 4) for i in range(k)},
                 "metadata": (metadata.loc[s].astype(str).to_dict() if metadata is not None and s in metadata.index else {})}
                for j, s in enumerate(X.columns)
            ],
            "top_loadings_pc1": sorted(
                [{"feature": f, "loading": round(float(l), 5)} for f, l in zip(X.index, Vt[0])],
                key=lambda d: -abs(d["loading"]))[:25],
        }
        run.summary = {"features": out["n_features_used"], "pc1_evr": out["explained_variance_ratio"][0]}
    out["provenance"] = run.provenance()
    return out


def heatmap(counts: pd.DataFrame, genes: list[str], metadata: pd.DataFrame | None = None,
            scale: str = "zscore", cluster: bool = True, project_id: str | None = None) -> dict:
    num = counts.apply(pd.to_numeric, errors="coerce").fillna(0)
    present = [g for g in genes if g in num.index]
    if not present:
        raise ValueError("None of the requested features are present in the matrix.")
    lib = num.sum().replace(0, np.nan)
    X = np.log2(num.loc[present].div(lib, axis=1) * 1e6 + 1)
    if scale == "zscore":
        sd = X.std(axis=1).replace(0, np.nan)
        X = X.sub(X.mean(axis=1), axis=0).div(sd, axis=0).fillna(0)
    rows, cols = list(X.index), list(X.columns)
    if cluster and len(rows) > 2:
        rows = [rows[i] for i in leaves_list(linkage(pdist(X.values, "correlation"), "average"))]
        X = X.loc[rows]
    if cluster and len(cols) > 2:
        cols = [cols[i] for i in leaves_list(linkage(pdist(X.T.values, "euclidean"), "average"))]
        X = X[cols]
    return {"features": rows, "samples": cols, "scale": scale, "clustered": cluster,
            "values": X.round(4).values.tolist(),
            "column_annotations": ({s: metadata.loc[s].astype(str).to_dict() for s in cols if s in metadata.index}
                                   if metadata is not None else {}),
            "note": "Rows are log2 CPM" + (", z-scored across samples." if scale == "zscore" else ".")}


# ----------------------------------------------------------------- enrichment

def enrichment(selected: list[str], background: list[str], gene_sets: dict[str, list[str]],
               min_set_size: int = 5, project_id: str | None = None) -> dict:
    """One-sided Fisher's exact over-representation test with BH correction.

    Gene sets must be supplied by the caller (uploaded GMT or pasted lists).
    BioIDE ships no built-in annotation database, so there is nothing to go stale.
    """
    bg = set(background) | set(selected)
    sel = set(selected) & bg
    if not sel:
        raise ValueError("No selected genes are present in the background.")
    rows = []
    for name, members in gene_sets.items():
        m = set(members) & bg
        if len(m) < min_set_size:
            continue
        a = len(sel & m)
        if a == 0:
            continue
        b, c = len(sel) - a, len(m) - a
        d = len(bg) - a - b - c
        odds, p = sstats.fisher_exact([[a, b], [c, d]], alternative="greater")
        rows.append({"gene_set": name, "set_size_in_background": len(m), "overlap": a,
                     "expected": round(len(sel) * len(m) / len(bg), 2),
                     "odds_ratio": None if odds in (float("inf"),) else round(float(odds), 3),
                     "pvalue": float(p), "genes": sorted(sel & m)[:40]})
    if not rows:
        raise ValueError(f"No gene set had at least {min_set_size} background genes and one hit.")
    rows.sort(key=lambda r: r["pvalue"])
    n = len(rows)
    best = 1.0
    for i in range(n - 1, -1, -1):
        best = min(best, rows[i]["pvalue"] * n / (i + 1))
        rows[i]["padj"] = round(min(1.0, best), 6)
        rows[i]["pvalue"] = round(rows[i]["pvalue"], 8)
    return {"method": "Fisher's exact test (one-sided, greater), Benjamini–Hochberg correction",
            "scipy_version": scipy.__version__,
            "n_selected": len(sel), "n_background": len(bg), "n_sets_tested": n, "results": rows[:200],
            "caveats": ["Over-representation of a user-supplied gene set, with the background you provided; "
                        "the background choice changes the result materially.",
                        "This is not GSEA: it ignores the ranking and uses a hard significance cut."]}
