"""Protein structure parsing and sequence-derived properties (Biopython Bio.PDB + ProtParam)."""
from __future__ import annotations

import io
import warnings

import Bio
import httpx
import numpy as np
from Bio.PDB import MMCIFParser, PDBParser, PPBuilder
from Bio.PDB.PDBExceptions import PDBConstructionWarning
from Bio.SeqUtils.ProtParam import ProteinAnalysis

from ..config import SAMPLES_DIR
from ..store import fingerprint, tracked_run

WATER = {"HOH", "WAT", "DOD"}


def protein_properties(seq: str) -> dict:
    clean = "".join(ch for ch in seq.upper() if ch in "ACDEFGHIKLMNPQRSTVWY")
    if len(clean) < 5:
        return {}
    pa = ProteinAnalysis(clean)
    helix, turn, sheet = pa.secondary_structure_fraction()
    return {
        "length": len(clean),
        "molecular_weight_da": round(pa.molecular_weight(), 1),
        "isoelectric_point": round(pa.isoelectric_point(), 2),
        "instability_index": round(pa.instability_index(), 2),
        "gravy": round(pa.gravy(), 3),
        "aromaticity": round(pa.aromaticity(), 3),
        "extinction_coeff_reduced": pa.molar_extinction_coefficient()[0],
        "propensity_fractions": {"helix": round(helix, 3), "turn": round(turn, 3), "sheet": round(sheet, 3)},
        "aa_percent": {k: round(v * 100, 2) for k, v in sorted(pa.amino_acids_percent.items())},
    }


def analyze_structure(text: str, fmt: str | None = None, structure_id: str = "structure", project_id: str | None = None) -> dict:
    fmt = fmt or ("cif" if text.lstrip().startswith("data_") else "pdb")
    with tracked_run("structure_analysis", "biopython.PDB", Bio.__version__, {"format": fmt, "id": structure_id}, fingerprint(text), project_id) as run:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", PDBConstructionWarning)
            parser = MMCIFParser(QUIET=True) if fmt == "cif" else PDBParser(QUIET=True)
            s = parser.get_structure(structure_id, io.StringIO(text))
        header = getattr(s, "header", {}) or {}
        model = next(iter(s))
        chains = []
        ppb = PPBuilder()
        all_ca = []
        for ch in model:
            residues = [r for r in ch if r.id[0] == " "]
            het = sorted({r.get_resname() for r in ch if r.id[0] != " " and r.get_resname() not in WATER})
            seq = "".join(str(pp.get_sequence()) for pp in ppb.build_peptides(ch))
            bf = [round(float(np.mean([a.get_bfactor() for a in r])), 2) for r in residues]
            ca = [r["CA"].coord for r in residues if "CA" in r]
            all_ca.extend(ca)
            chains.append({
                "chain_id": ch.id, "n_residues": len(residues), "n_atoms": sum(len(r) for r in residues),
                "sequence": seq, "hetero_groups": het,
                "first_residue": residues[0].id[1] if residues else None,
                "last_residue": residues[-1].id[1] if residues else None,
                "residue_numbers": [r.id[1] for r in residues], "bfactors": bf,
                "properties": protein_properties(seq),
            })
        rg = None
        if all_ca:
            xyz = np.array(all_ca)
            rg = round(float(np.sqrt(((xyz - xyz.mean(0)) ** 2).sum(1).mean())), 2)
        out = {
            "id": structure_id, "format": fmt,
            "header": {k: header.get(k) for k in ("name", "head", "structure_method", "resolution", "deposition_date") if header.get(k) is not None},
            "n_models": len(s), "chains": chains, "radius_of_gyration_ca_A": rg,
            "notes": ["Secondary-structure 'propensity_fractions' are sequence-composition estimates (ProtParam), not DSSP assignments from coordinates.",
                      "B-factors from NMR or predicted models (pLDDT stored in the B-factor column) have different meanings than crystallographic B-factors."],
        }
        run.summary = {"chains": len(chains), "residues": sum(c["n_residues"] for c in chains)}
    out["provenance"] = run.provenance()
    return out


def load_sample() -> tuple[str, str]:
    return (SAMPLES_DIR / "1A8O.pdb").read_text(), "1A8O"


async def fetch_rcsb(pdb_id: str) -> str:
    pid = "".join(ch for ch in pdb_id if ch.isalnum())[:4].upper()
    if len(pid) != 4:
        raise ValueError("PDB IDs are 4 characters, e.g. 1UBQ")
    async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
        r = await client.get(f"https://files.rcsb.org/download/{pid}.pdb")
        if r.status_code == 404:
            r = await client.get(f"https://files.rcsb.org/download/{pid}.cif")
        r.raise_for_status()
        return r.text
