"""Sequence analysis executed with Biopython (real computation, no LLM involvement)."""
from __future__ import annotations

import io
from collections import Counter
from typing import Any

import Bio
import httpx
from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqUtils import gc_fraction

from ..config import SAMPLES_DIR, settings
from ..store import fingerprint, tracked_run

STOPS_11 = {"TAA", "TAG", "TGA"}


def detect_format(text: str) -> str:
    t = text.lstrip()
    if t.startswith(">"):
        return "fasta"
    if t.startswith("LOCUS"):
        return "genbank"
    raise ValueError("Unrecognised sequence format: expected FASTA ('>') or GenBank ('LOCUS').")


def parse_records(text: str) -> tuple[str, list]:
    fmt = detect_format(text)
    records = list(SeqIO.parse(io.StringIO(text), fmt))
    if not records:
        raise ValueError("No sequence records found.")
    for r in records:
        bad = set(str(r.seq).upper()) - set("ACGTNRYKMSWBDHV")
        if bad:
            raise ValueError(f"Record {r.id} contains non-nucleotide characters {sorted(bad)[:5]}; protein FASTA is not supported here.")
    return fmt, records


def find_orfs(seq: str, min_aa: int = 100, starts: tuple[str, ...] = ("ATG",), circular: bool = False) -> list[dict]:
    """Stop-to-stop scan in six frames; ORF = first start codon after previous stop
    to the next in-frame stop. Bacterial translation table 11. Ignores ORFs that
    wrap the origin (documented limitation)."""
    seq = seq.upper()
    n = len(seq)
    out: list[dict] = []
    for strand, s in ((1, seq), (-1, str(Seq(seq).reverse_complement()))):
        for frame in range(3):
            start_pos = None
            for i in range(frame, n - 2, 3):
                codon = s[i:i + 3]
                if start_pos is None and codon in starts:
                    start_pos = i
                if codon in STOPS_11:
                    if start_pos is not None:
                        aa_len = (i - start_pos) // 3
                        if aa_len >= min_aa:
                            end = i + 3
                            if strand == 1:
                                lo, hi = start_pos, end
                            else:
                                lo, hi = n - end, n - start_pos
                            out.append({
                                "start": lo + 1, "end": hi, "strand": strand, "frame": frame + 1,
                                "length_nt": end - start_pos, "length_aa": aa_len,
                                "start_codon": s[start_pos:start_pos + 3],
                                "protein": str(Seq(s[start_pos:i]).translate(table=11))[:60] + ("…" if aa_len > 60 else ""),
                            })
                    start_pos = None
    out.sort(key=lambda o: o["start"])
    return out


def gc_windows(seq: str, window: int, step: int) -> dict:
    seq = seq.upper()
    xs, gc, skew = [], [], []
    for i in range(0, max(1, len(seq) - window + 1), step):
        w = seq[i:i + window]
        g, c = w.count("G"), w.count("C")
        xs.append(i + window // 2)
        gc.append(round(gc_fraction(w) * 100, 3))
        skew.append(round((g - c) / (g + c), 4) if g + c else 0.0)
    cum, acc = [], 0.0
    for v in skew:
        acc += v
        cum.append(round(acc, 4))
    return {"position": xs, "gc_percent": gc, "gc_skew": skew, "cumulative_skew": cum}


def compare_to_annotation(record, orfs: list[dict]) -> dict | None:
    cds = [f for f in record.features if f.type == "CDS"]
    if not cds:
        return None
    orf_stops = {(o["strand"], o["end"] if o["strand"] == 1 else o["start"]) for o in orfs}
    matched = []
    for f in cds:
        strand = f.location.strand
        stop = int(f.location.end) if strand == 1 else int(f.location.start) + 1
        hit = (strand, stop) in orf_stops
        matched.append({
            "locus_tag": f.qualifiers.get("locus_tag", [""])[0],
            "product": f.qualifiers.get("product", [""])[0],
            "start": int(f.location.start) + 1, "end": int(f.location.end), "strand": strand,
            "length_aa": (len(f.location) // 3) - 1, "recovered_by_orf_scan": hit,
        })
    n_hit = sum(m["recovered_by_orf_scan"] for m in matched)
    return {"annotated_cds": len(cds), "recovered": n_hit,
            "note": "A CDS counts as recovered when an ORF shares its strand and stop coordinate. "
                    "Unrecovered CDS are typically shorter than the minimum ORF length or use alternative start codons.",
            "features": matched}


def analyze(text: str, min_aa: int = 100, alt_starts: bool = False, window: int | None = None, project_id: str | None = None, source: str = "upload") -> dict:
    fmt, records = parse_records(text)
    params = {"min_aa": min_aa, "alt_starts": alt_starts, "window": window, "source": source, "translation_table": 11}
    with tracked_run("sequence_analysis", "biopython", Bio.__version__, params, fingerprint(text), project_id) as run:
        results = []
        for r in records:
            s = str(r.seq).upper()
            n = len(s)
            comp = Counter(s)
            w = window or max(100, min(10000, n // 200 or 100))
            orfs = find_orfs(s, min_aa, ("ATG", "GTG", "TTG") if alt_starts else ("ATG",))
            coding_nt = sum(o["length_nt"] for o in orfs)
            codon_counts: Counter = Counter()
            for o in orfs[:2000]:
                sub = s[o["start"] - 1:o["end"]]
                if o["strand"] == -1:
                    sub = str(Seq(sub).reverse_complement())
                codon_counts.update(sub[i:i + 3] for i in range(0, len(sub) - 2, 3))
            results.append({
                "id": r.id, "description": r.description, "length": n,
                "gc_percent": round(gc_fraction(s) * 100, 3),
                "composition": {b: comp.get(b, 0) for b in "ACGTN"},
                "ambiguous_bases": n - sum(comp.get(b, 0) for b in "ACGT"),
                "topology": r.annotations.get("topology"),
                "organism": r.annotations.get("organism"),
                "orf_count": len(orfs), "orf_coding_fraction": round(coding_nt / n, 4) if n else 0,
                "orfs": orfs[:500], "orfs_truncated": len(orfs) > 500,
                "windows": gc_windows(s, w, max(1, w // 2)), "window_size": w,
                "codon_usage_top": codon_counts.most_common(64),
                "annotation_comparison": compare_to_annotation(r, orfs) if fmt == "genbank" else None,
            })
        run.summary = {"records": len(results), "total_length": sum(x["length"] for x in results),
                       "orfs": sum(x["orf_count"] for x in results)}
    return {"format": fmt, "records": results, "provenance": run.provenance(),
            "interpretation_notes": [
                "ORFs are computational predictions from a six-frame scan, not validated genes.",
                "Use a dedicated annotator (Bakta, Prokka, Pyrodigal) for genome annotation; it models RBS, start choice and overlaps.",
            ]}


def load_sample(name: str) -> str:
    files = {"pPCP1": "Ypestis_pPCP1_NC_005816.gb"}
    if name not in files:
        raise ValueError(f"Unknown sample {name}")
    return (SAMPLES_DIR / files[name]).read_text()


async def fetch_ncbi(accession: str, rettype: str = "gbwithparts") -> str:
    """Fetch a nucleotide record from NCBI E-utilities (requires network access to NCBI)."""
    acc = "".join(ch for ch in accession if ch.isalnum() or ch in "._")
    params: dict[str, Any] = {"db": "nuccore", "id": acc, "rettype": rettype, "retmode": "text", "tool": "BioIDE"}
    if settings.contact_email:
        params["email"] = settings.contact_email
    if settings.ncbi_api_key:
        params["api_key"] = settings.ncbi_api_key
    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi", params=params)
        r.raise_for_status()
        text = r.text
    if not (text.lstrip().startswith("LOCUS") or text.lstrip().startswith(">")):
        raise ValueError(f"NCBI did not return a sequence record for {acc}: {text[:200]}")
    return text
