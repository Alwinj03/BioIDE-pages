"""Workflow construction, validation and export.

A workflow is a DAG of steps. Each step names a catalogue tool, declares input
and output formats and carries parameters. Validation is structural and
format-based, so a workflow can be checked without running anything.

Export targets are real engines (Snakemake, Nextflow) plus plain Python and Bash.
BioIDE defines no execution language of its own.
"""
from __future__ import annotations

import json
import re
import textwrap
from typing import Any

from . import catalogue

# ------------------------------------------------------------------ templates
# Each template is a declarative DAG. Steps reference catalogue tool ids where a
# real tool exists; 'io' steps are inputs/outputs with no tool.

TEMPLATES: dict[str, dict] = {
    "rnaseq_de": {
        "title": "Bulk RNA-seq: reads to differential expression",
        "intent": ["rna-seq", "rnaseq", "differential expression", "transcriptom", "deg", "volcano", "gene expression"],
        "steps": [
            {"id": "fastq", "label": "FASTQ reads", "tool": None, "kind": "input", "outputs": ["FASTQ"]},
            {"id": "qc", "label": "Read QC and trimming", "tool": "fastp", "inputs": ["FASTQ"], "outputs": ["FASTQ", "JSON"],
             "params": {"detect_adapter_for_pe": True, "qualified_quality_phred": 15}},
            {"id": "quant", "label": "Transcript quantification", "tool": "salmon", "inputs": ["FASTQ"], "outputs": ["quant.sf"],
             "params": {"libType": "A", "validateMappings": True, "index": "<salmon index path>"}},
            {"id": "aggregate", "label": "Transcript to gene counts", "tool": None, "kind": "script",
             "inputs": ["quant.sf"], "outputs": ["count matrix"],
             "params": {"language": "R", "note": "tximport with a tx2gene map; countsFromAbundance='lengthScaledTPM'"}},
            {"id": "de", "label": "Differential expression", "tool": "pydeseq2", "inputs": ["count matrix", "sample metadata"],
             "outputs": ["results table"], "params": {"design": "~ condition", "alpha": 0.05, "lfc_shrink": True}},
            {"id": "viz", "label": "Volcano plot, heatmap, PCA", "tool": None, "kind": "native",
             "inputs": ["results table"], "outputs": ["figures"], "params": {}},
        ],
        "edges": [("fastq", "qc"), ("qc", "quant"), ("quant", "aggregate"), ("aggregate", "de"), ("de", "viz")],
        "notes": ["Steps 'de' and 'viz' run natively in BioIDE if you already have a count matrix.",
                  "Do not feed TPM or FPKM into the DE step; DESeq2-family methods require raw counts."],
    },
    "genome_annotation": {
        "title": "Bacterial genome annotation",
        "intent": ["genome annotat", "annotate a genome", "bacterial genome", "orf", "gene calling", "prokaryot"],
        "steps": [
            {"id": "assembly", "label": "Genome assembly (FASTA)", "tool": None, "kind": "input", "outputs": ["FASTA"]},
            {"id": "stats", "label": "Sequence statistics and GC profile", "tool": "biopython", "inputs": ["FASTA"],
             "outputs": ["JSON"], "params": {"window": "auto"}},
            {"id": "genecall", "label": "Protein-coding gene prediction", "tool": "pyrodigal", "inputs": ["FASTA"],
             "outputs": ["GFF", "protein FASTA"], "params": {"meta": False}},
            {"id": "annotate", "label": "Functional annotation", "tool": "bakta", "inputs": ["FASTA"],
             "outputs": ["GFF3", "GenBank", "TSV"], "params": {"db": "<bakta db path>", "genus": "", "species": ""}},
            {"id": "domains", "label": "Domain assignment", "tool": "hmmer", "inputs": ["protein FASTA"],
             "outputs": ["domtblout"], "params": {"E": 1e-5, "hmm": "Pfam-A.hmm"}},
            {"id": "report", "label": "Annotation report", "tool": None, "kind": "native", "inputs": ["GFF3", "TSV"],
             "outputs": ["report"], "params": {}},
        ],
        "edges": [("assembly", "stats"), ("assembly", "genecall"), ("assembly", "annotate"),
                  ("genecall", "domains"), ("annotate", "report"), ("domains", "report"), ("stats", "report")],
        "notes": ["Bakta performs its own gene calling; the explicit Pyrodigal step is for when you want protein FASTA alone.",
                  "BioIDE's native six-frame ORF scan is a teaching aid, not a substitute for Pyrodigal or Bakta."],
    },
    "metagenome_function": {
        "title": "Metagenomic taxonomic and functional profiling",
        "intent": ["metagenom", "microbiome", "functional profiling", "cazyme", "carbohydrate-active", "community profil"],
        "steps": [
            {"id": "fastq", "label": "Shotgun FASTQ", "tool": None, "kind": "input", "outputs": ["FASTQ"]},
            {"id": "qc", "label": "QC, trimming, host removal", "tool": "fastp", "inputs": ["FASTQ"], "outputs": ["FASTQ"],
             "params": {"length_required": 50}},
            {"id": "taxa", "label": "Taxonomic profiling", "tool": "metaphlan", "inputs": ["FASTQ"],
             "outputs": ["abundance profile"], "params": {"input_type": "fastq", "bowtie2db": "<metaphlan db>"}},
            {"id": "func", "label": "Functional profiling", "tool": "humann", "inputs": ["FASTQ", "abundance profile"],
             "outputs": ["gene families", "pathway abundance"], "params": {"nucleotide-database": "<chocophlan>", "protein-database": "<uniref>"}},
            {"id": "cazy", "label": "CAZyme annotation", "tool": "dbcan", "inputs": ["protein FASTA"],
             "outputs": ["CAZyme overview"], "params": {"db_dir": "<dbcan db>"}},
            {"id": "report", "label": "Diversity and pathway summary", "tool": None, "kind": "native",
             "inputs": ["abundance profile", "pathway abundance"], "outputs": ["figures", "report"], "params": {}},
        ],
        "edges": [("fastq", "qc"), ("qc", "taxa"), ("taxa", "func"), ("qc", "cazy"), ("func", "report"), ("cazy", "report")],
        "notes": ["Every tool in this workflow except the report needs a multi-gigabyte database on your own machine.",
                  "CAZyme annotation needs predicted proteins: assemble and gene-call first, or run dbCAN on reads-derived contigs.",
                  "HUMAnN consumes the MetaPhlAn profile, so that edge is a real data dependency, not just ordering."],
    },
    "variant_calling": {
        "title": "Short-read variant calling",
        "intent": ["variant", "snp", "resequenc", "mutation calling", "vcf"],
        "steps": [
            {"id": "fastq", "label": "FASTQ reads", "tool": None, "kind": "input", "outputs": ["FASTQ"]},
            {"id": "ref", "label": "Reference genome", "tool": None, "kind": "input", "outputs": ["FASTA"]},
            {"id": "qc", "label": "QC and trimming", "tool": "fastp", "inputs": ["FASTQ"], "outputs": ["FASTQ"], "params": {}},
            {"id": "align", "label": "Read alignment", "tool": "bwa-mem2", "inputs": ["FASTQ", "FASTA"], "outputs": ["BAM"], "params": {"threads": 4}},
            {"id": "sort", "label": "Sort and index", "tool": "samtools", "inputs": ["BAM"], "outputs": ["BAM"], "params": {}},
            {"id": "call", "label": "Variant calling", "tool": "bcftools", "inputs": ["BAM", "FASTA"], "outputs": ["VCF"],
             "params": {"ploidy": 1, "mpileup_q": 20}},
            {"id": "filter", "label": "Variant filtering", "tool": "bcftools", "inputs": ["VCF"], "outputs": ["VCF"],
             "params": {"include": "QUAL>20 && DP>10"}},
        ],
        "edges": [("fastq", "qc"), ("qc", "align"), ("ref", "align"), ("align", "sort"), ("sort", "call"), ("ref", "call"), ("call", "filter")],
        "notes": ["ploidy=1 suits bacteria; change it for diploid organisms.",
                  "For human data, nf-core/sarek implements the GATK best-practice route and is preferable to this minimal chain."],
    },
    "fba_strain_design": {
        "title": "Constraint-based model analysis",
        "intent": ["flux balance", "fba", "fva", "cobra", "metabolic model", "genome-scale", "strain design", "yield", "knockout"],
        "steps": [
            {"id": "model", "label": "SBML model", "tool": None, "kind": "input", "outputs": ["SBML"]},
            {"id": "quality", "label": "Model quality check", "tool": "cobrapy", "inputs": ["SBML"], "outputs": ["JSON"],
             "params": {"checks": ["mass balance", "orphans", "dead ends", "GPR coverage"]}},
            {"id": "medium", "label": "Define growth medium", "tool": "cobrapy", "inputs": ["SBML"], "outputs": ["bounds"],
             "params": {"carbon_source": "EX_glc__D_e", "uptake_rate": 10}},
            {"id": "fba", "label": "Flux balance analysis", "tool": "cobrapy", "inputs": ["SBML", "bounds"], "outputs": ["flux distribution"],
             "params": {"parsimonious": False}},
            {"id": "fva", "label": "Flux variability analysis", "tool": "cobrapy", "inputs": ["SBML", "bounds"], "outputs": ["flux ranges"],
             "params": {"fraction_of_optimum": 0.9, "loopless": False}},
            {"id": "deletions", "label": "Single gene deletion scan", "tool": "cobrapy", "inputs": ["SBML", "bounds"], "outputs": ["deletion table"], "params": {}},
            {"id": "envelope", "label": "Production envelope", "tool": "cobrapy", "inputs": ["SBML", "bounds"], "outputs": ["envelope"],
             "params": {"target": "<target exchange reaction>"}},
            {"id": "report", "label": "Comparison and report", "tool": None, "kind": "native",
             "inputs": ["flux distribution", "flux ranges", "deletion table"], "outputs": ["report"], "params": {}},
        ],
        "edges": [("model", "quality"), ("model", "medium"), ("medium", "fba"), ("medium", "fva"),
                  ("medium", "deletions"), ("medium", "envelope"), ("fba", "report"), ("fva", "report"), ("deletions", "report")],
        "notes": ["Every step here runs natively in BioIDE with real COBRApy calls.",
                  "Run FVA before quoting any single FBA flux: alternative optima are the norm.",
                  "MEMOTE is the standard quality report if you intend to publish the model."],
    },
    "structure_analysis": {
        "title": "Protein structure exploration",
        "intent": ["protein structure", "pdb", "structural", "alphafold", "fold", "visualise protein"],
        "steps": [
            {"id": "seqorid", "label": "Sequence or PDB ID", "tool": None, "kind": "input", "outputs": ["FASTA", "PDB ID"]},
            {"id": "retrieve", "label": "Retrieve structure", "tool": None, "kind": "native", "inputs": ["PDB ID"], "outputs": ["PDB"],
             "params": {"source": "RCSB PDB; AlphaFold DB for predicted models"}},
            {"id": "predict", "label": "Predict structure (if none exists)", "tool": "esmfold", "inputs": ["FASTA"], "outputs": ["PDB"],
             "params": {"note": "external GPU service"}},
            {"id": "parse", "label": "Chains, residues, properties", "tool": "biopython", "inputs": ["PDB"], "outputs": ["JSON"], "params": {}},
            {"id": "view", "label": "3D visualisation", "tool": "molstar", "inputs": ["PDB"], "outputs": ["interactive view"], "params": {}},
            {"id": "homologs", "label": "Structural homologue search", "tool": "foldseek", "inputs": ["PDB"], "outputs": ["alignment table"], "params": {}},
            {"id": "report", "label": "Structure report", "tool": None, "kind": "native", "inputs": ["JSON"], "outputs": ["report"], "params": {}},
        ],
        "edges": [("seqorid", "retrieve"), ("seqorid", "predict"), ("retrieve", "parse"), ("predict", "parse"),
                  ("parse", "view"), ("parse", "homologs"), ("parse", "report")],
        "notes": ["Check the PDB and AlphaFold DB before predicting a structure; it may already exist.",
                  "pLDDT stored in the B-factor column of a predicted model is confidence, not thermal motion."],
    },
    "amplicon_16s": {
        "title": "16S amplicon community analysis",
        "intent": ["16s", "amplicon", "qiime", "its", "asv", "diversity"],
        "steps": [
            {"id": "fastq", "label": "Demultiplexed FASTQ", "tool": None, "kind": "input", "outputs": ["FASTQ"]},
            {"id": "import", "label": "Import to QIIME 2", "tool": "qiime2", "inputs": ["FASTQ"], "outputs": ["qza"], "params": {}},
            {"id": "denoise", "label": "DADA2 denoising", "tool": "qiime2", "inputs": ["qza"], "outputs": ["feature table", "rep-seqs"],
             "params": {"trunc_len_f": 0, "trunc_len_r": 0, "note": "set truncation from the interactive quality plot"}},
            {"id": "taxonomy", "label": "Taxonomic classification", "tool": "qiime2", "inputs": ["rep-seqs"], "outputs": ["taxonomy"],
             "params": {"classifier": "<SILVA or GTDB classifier .qza>"}},
            {"id": "diversity", "label": "Alpha and beta diversity", "tool": "qiime2", "inputs": ["feature table"], "outputs": ["qzv"],
             "params": {"sampling_depth": "<choose from rarefaction curve>"}},
        ],
        "edges": [("fastq", "import"), ("import", "denoise"), ("denoise", "taxonomy"), ("denoise", "diversity")],
        "notes": ["Truncation lengths and rarefaction depth are judgement calls that must be made from your own quality plots.",
                  "nf-core/ampliseq wraps this same route as a reproducible pipeline."],
    },
}

FORMAT_ALIASES = {
    "fastq": {"fastq", "fastq.gz", "fq", "reads"},
    "fasta": {"fasta", "fa", "fna", "faa", "assembly", "protein fasta", "transcriptome fasta", "genome fasta"},
    "bam": {"bam", "sam", "cram", "sam/bam", "sam/bam/cram"},
    "vcf": {"vcf", "bcf", "vcf/bcf"},
    "count matrix": {"count matrix", "quant.sf", "counts", "abundance.tsv"},
    "sbml": {"sbml", "xml", "cobra json"},
    "pdb": {"pdb", "mmcif", "cif", "pdb/mmcif"},
}


def _canon(fmt: str) -> str:
    f = fmt.strip().lower().lstrip(".")
    for canon, al in FORMAT_ALIASES.items():
        if f in al:
            return canon
    return f


# ------------------------------------------------------------------ generation

def classify(objective: str) -> dict:
    o = objective.lower()
    scores = []
    for key, tpl in TEMPLATES.items():
        matched = [k for k in tpl["intent"] if k in o]
        if matched:
            scores.append({"template": key, "title": tpl["title"], "score": len(matched), "matched_terms": matched})
    scores.sort(key=lambda s: -s["score"])
    return {"objective": objective, "candidates": scores,
            "best": scores[0]["template"] if scores else None,
            "method": "deterministic keyword match against workflow templates"}


def generate(objective: str, template: str | None = None) -> dict:
    cls = classify(objective)
    key = template or cls["best"]
    if not key:
        raise ValueError("No workflow template matches this objective. "
                         f"Available templates: {', '.join(f'{k} ({v['title']})' for k, v in TEMPLATES.items())}. "
                         "Pass one explicitly, or build a workflow step by step in the editor.")
    if key not in TEMPLATES:
        raise ValueError(f"Unknown template '{key}'. Available: {list(TEMPLATES)}")
    tpl = TEMPLATES[key]
    nodes = []
    for s in tpl["steps"]:
        tool = catalogue.TOOLS.get(s.get("tool") or "")
        nodes.append({
            "id": s["id"], "label": s["label"], "kind": s.get("kind", "tool"),
            "tool": s.get("tool"), "tool_name": tool.name if tool else None,
            "tool_description": tool.description if tool else None,
            "execution": tool.execution if tool else ("native" if s.get("kind") == "native" else s.get("kind", "io")),
            "inputs": s.get("inputs", []), "outputs": s.get("outputs", []),
            "params": s.get("params", {}),
            "install": tool.install if tool else {},
            "docs": tool.docs if tool else None,
            "resources": tool.resources if tool else "",
            "alternatives": tool.alternatives if tool else [],
            "status": "not_run",
        })
    wf = {"template": key, "title": tpl["title"], "objective": objective,
          "nodes": nodes, "edges": [{"source": a, "target": b} for a, b in tpl["edges"]],
          "notes": tpl["notes"], "classification": cls}
    wf["validation"] = validate(wf)
    return wf


def list_templates() -> list[dict]:
    return [{"id": k, "title": v["title"], "n_steps": len(v["steps"]),
             "intent_terms": v["intent"],
             "native_steps": sum(1 for s in v["steps"]
                                 if s.get("kind") == "native" or
                                 (s.get("tool") and catalogue.TOOLS.get(s["tool"]) and catalogue.TOOLS[s["tool"]].execution == "native")),
             } for k, v in TEMPLATES.items()]


# ------------------------------------------------------------------ validation

def validate(wf: dict) -> dict:
    nodes = {n["id"]: n for n in wf.get("nodes", [])}
    edges = [(e["source"], e["target"]) for e in wf.get("edges", [])]
    errors: list[str] = []
    warnings: list[str] = []

    for s, t in edges:
        if s not in nodes:
            errors.append(f"Edge references unknown source step '{s}'.")
        if t not in nodes:
            errors.append(f"Edge references unknown target step '{t}'.")
    if errors:
        return {"ok": False, "errors": errors, "warnings": warnings, "order": []}

    # cycle detection / topological order
    indeg = {k: 0 for k in nodes}
    adj: dict[str, list[str]] = {k: [] for k in nodes}
    for s, t in edges:
        adj[s].append(t)
        indeg[t] += 1
    queue = sorted([k for k, v in indeg.items() if v == 0])
    order: list[str] = []
    while queue:
        n = queue.pop(0)
        order.append(n)
        for m in adj[n]:
            indeg[m] -= 1
            if indeg[m] == 0:
                queue.append(m)
        queue.sort()
    if len(order) != len(nodes):
        errors.append("The workflow contains a cycle; a workflow must be a directed acyclic graph.")

    # format compatibility
    for s, t in edges:
        produced = {_canon(f) for f in nodes[s].get("outputs", [])}
        required = {_canon(f) for f in nodes[t].get("inputs", [])}
        if required and produced and not (produced & required):
            warnings.append(
                f"'{nodes[s]['label']}' produces {sorted(produced)} but '{nodes[t]['label']}' expects {sorted(required)}. "
                "Either an intermediate conversion step is missing, or the missing input comes from another branch.")

    for nid, n in nodes.items():
        if n.get("kind") not in {"input", "io"} and indeg.get(nid, 0) == 0 and not any(e[1] == nid for e in edges):
            warnings.append(f"'{n['label']}' has no incoming data and is not declared as an input step.")
        for k, v in (n.get("params") or {}).items():
            if isinstance(v, str) and re.search(r"<.+>", v):
                warnings.append(f"'{n['label']}' has an unfilled parameter: {k} = {v}")
        if n.get("execution") == "local_db":
            warnings.append(f"'{n['label']}' needs a local reference database ({n.get('resources') or 'size varies'}).")

    unreachable = [nid for nid in nodes if nid not in order]
    return {"ok": not errors, "errors": errors, "warnings": sorted(set(warnings)),
            "order": order, "unreachable": unreachable,
            "executable_here": [nid for nid, n in nodes.items() if n.get("execution") == "native"],
            "needs_local_agent": [nid for nid, n in nodes.items() if n.get("execution") in {"local", "local_db"}],
            "needs_external": [nid for nid, n in nodes.items() if n.get("execution") == "external"]}


# ------------------------------------------------------------------ export

def _slug(s: str) -> str:
    return re.sub(r"\W+", "_", s).strip("_").lower()


def _cmd(node: dict) -> str:
    """Best-effort command line for a catalogue tool. Placeholders are explicit."""
    tid, p = node.get("tool"), node.get("params") or {}
    g = lambda k, d="": p.get(k, d)
    if tid == "fastp":
        return "fastp -i {input_r1} -I {input_r2} -o {out_r1} -O {out_r2} --json {out_json} " \
               f"--qualified_quality_phred {g('qualified_quality_phred', 15)} --length_required {g('length_required', 36)} --thread {g('threads', 4)}"
    if tid == "salmon":
        return f"salmon quant -i {g('index', '<index>')} -l {g('libType', 'A')} " \
               "-1 {input_r1} -2 {input_r2} --validateMappings -p " + str(g("threads", 4)) + " -o {outdir}"
    if tid == "star":
        return "STAR --genomeDir <star index> --readFilesIn {input_r1} {input_r2} --readFilesCommand zcat " \
               "--outSAMtype BAM SortedByCoordinate --quantMode GeneCounts --runThreadN " + str(g("threads", 4)) + " --outFileNamePrefix {prefix}"
    if tid == "hisat2":
        return "hisat2 -x <hisat2 index> -1 {input_r1} -2 {input_r2} -p " + str(g("threads", 4)) + " | samtools sort -o {out_bam}"
    if tid == "bwa-mem2":
        return "bwa-mem2 mem -t " + str(g("threads", 4)) + " {reference} {input_r1} {input_r2} | samtools sort -o {out_bam}"
    if tid == "bowtie2":
        return "bowtie2 -x <bt2 index> -1 {input_r1} -2 {input_r2} -p " + str(g("threads", 4)) + " | samtools sort -o {out_bam}"
    if tid == "samtools":
        return "samtools index {in_bam} && samtools flagstat {in_bam} > {out_stats}"
    if tid == "bcftools":
        if "include" in p:
            return f"bcftools view -i '{g('include')}' {{in_vcf}} -Oz -o {{out_vcf}} && bcftools index {{out_vcf}}"
        return f"bcftools mpileup -f {{reference}} -q {g('mpileup_q', 20)} {{in_bam}} | " \
               f"bcftools call -mv --ploidy {g('ploidy', 1)} -Oz -o {{out_vcf}}"
    if tid == "bakta":
        return f"bakta --db {g('db', '<bakta db>')} --output {{outdir}} --prefix {{sample}} --threads {g('threads', 4)} {{in_fasta}}"
    if tid == "prokka":
        return "prokka --outdir {outdir} --prefix {sample} --cpus " + str(g("threads", 4)) + " {in_fasta}"
    if tid == "pyrodigal":
        return "pyrodigal -i {in_fasta} -a {out_faa} -o {out_gff}" + ("" if not g("meta") else " -p meta")
    if tid == "hmmer":
        return f"hmmsearch --domtblout {{out_domtbl}} -E {g('E', 1e-5)} --cpu {g('threads', 4)} {g('hmm', 'Pfam-A.hmm')} {{in_faa}}"
    if tid == "metaphlan":
        return f"metaphlan {{in_fastq}} --input_type {g('input_type', 'fastq')} --bowtie2db {g('bowtie2db', '<db>')} " \
               "--bowtie2out {out_bt2} -o {out_profile} --nproc " + str(g("threads", 4))
    if tid == "humann":
        return f"humann --input {{in_fastq}} --output {{outdir}} --taxonomic-profile {{in_profile}} " \
               f"--nucleotide-database {g('nucleotide-database', '<chocophlan>')} --protein-database {g('protein-database', '<uniref>')} --threads {g('threads', 4)}"
    if tid == "kraken2":
        return "kraken2 --db <kraken2 db> --threads " + str(g("threads", 4)) + " --report {out_report} --paired {input_r1} {input_r2} > {out_class}"
    if tid == "bracken":
        return "bracken -d <kraken2 db> -i {in_report} -o {out_abundance} -r 150 -l S"
    if tid == "dbcan":
        return f"run_dbcan {{in_faa}} protein --db_dir {g('db_dir', '<dbcan db>')} --out_dir {{outdir}}"
    if tid == "eggnog-mapper":
        return "emapper.py -i {in_faa} -o {prefix} --cpu " + str(g("threads", 4)) + " --data_dir <eggnog data>"
    if tid == "mafft":
        return "mafft --auto {in_fasta} > {out_aln}"
    if tid == "muscle":
        return "muscle -align {in_fasta} -output {out_aln}"
    if tid == "blast":
        return "blastp -query {in_faa} -db <blast db> -outfmt 6 -evalue 1e-5 -num_threads " + str(g("threads", 4)) + " -out {out_tsv}"
    if tid == "diamond":
        return "diamond blastp -q {in_faa} -d <diamond db> -o {out_tsv} --outfmt 6 -p " + str(g("threads", 4))
    if tid == "foldseek":
        return "foldseek easy-search {in_pdb} <foldseek db> {out_tsv} tmp --format-output 'query,target,evalue,alntmscore'"
    if tid == "multiqc":
        return "multiqc {indir} -o {outdir}"
    if tid == "qiime2":
        return "# QIIME 2 steps are plugin calls; see https://docs.qiime2.org for the exact invocation\nqiime --help"
    if tid in {"cobrapy", "pydeseq2", "biopython", "molstar"}:
        return f"# '{node['label']}' runs natively inside BioIDE (library: {tid}); no shell command"
    return f"# TODO: command for {node['label']}" + (f" (tool: {tid})" if tid else "")


def export(wf: dict, target: str) -> dict:
    v = validate(wf)
    nodes = {n["id"]: n for n in wf["nodes"]}
    order = v["order"]
    title = wf.get("title", "BioIDE workflow")
    header_notes = wf.get("notes", []) + [
        "Generated by BioIDE. Paths in angle brackets and {braces} are placeholders you must fill in.",
        "This file has not been executed by BioIDE. Review it before running it.",
    ]
    if target == "snakemake":
        code = _to_snakemake(title, nodes, order, header_notes)
        fn, lang = "Snakefile", "python"
    elif target == "nextflow":
        code = _to_nextflow(title, nodes, order, header_notes)
        fn, lang = "main.nf", "groovy"
    elif target == "bash":
        code = _to_bash(title, nodes, order, header_notes)
        fn, lang = "run_workflow.sh", "shell"
    elif target == "python":
        code = _to_python(title, wf, nodes, order, header_notes)
        fn, lang = "run_workflow.py", "python"
    elif target == "json":
        code = json.dumps({k: wf[k] for k in ("template", "title", "objective", "nodes", "edges", "notes") if k in wf}, indent=2)
        fn, lang = "workflow.json", "json"
    elif target == "cwl":
        raise ValueError("CWL export is not implemented. Use Nextflow or Snakemake, or export JSON and convert.")
    else:
        raise ValueError(f"Unsupported export target '{target}'. Choose snakemake, nextflow, bash, python or json.")
    return {"target": target, "filename": fn, "language": lang, "code": code, "validation": v,
            "disclaimer": "BioIDE generated this file but did not run it."}


def _to_snakemake(title: str, nodes: dict, order: list[str], notes: list[str]) -> str:
    lines = [f'"""{title}', ""] + [f"- {n}" for n in notes] + ['"""', "",
             'configfile: "config.yaml"', "", 'SAMPLES = config.get("samples", [])', "",
             "rule all:", "    input:", '        expand("results/{sample}/done.txt", sample=SAMPLES)', ""]
    for nid in order:
        n = nodes[nid]
        if n.get("kind") in {"input", "io"}:
            continue
        cmd = _cmd(n)
        lines += [f"rule {_slug(nid)}:",
                  f'    """{n["label"]}' + (f' — {n.get("tool_name")}' if n.get("tool_name") else "") + '"""',
                  f"    # expects: {', '.join(n.get('inputs') or ['(declare inputs)'])}",
                  f"    # produces: {', '.join(n.get('outputs') or ['(declare outputs)'])}",
                  "    output:", f'        touch("results/{{sample}}/{_slug(nid)}.done")']
        if n.get("tool") and n["tool"] in catalogue.TOOLS and n["execution"] != "native":
            lines += ["    conda:", f'        "envs/{_slug(nid)}.yaml"']
        lines += ["    threads: 4", "    shell:", '        r"""',
                  f"        mkdir -p results/{{wildcards.sample}}",
                  *[f"        {l}" for l in cmd.splitlines()],
                  f"        touch results/{{wildcards.sample}}/{_slug(nid)}.done", '        """', ""]
    envs = {}
    for nid in order:
        n = nodes[nid]
        t = catalogue.TOOLS.get(n.get("tool") or "")
        if t and t.execution != "native" and "conda" in t.install:
            envs[_slug(nid)] = t.install["conda"]
    if envs:
        lines += ["# Conda environment files to create under envs/:"]
        lines += [f"#   envs/{k}.yaml  ->  {v}" for k, v in envs.items()]
    return "\n".join(lines)


def _to_nextflow(title: str, nodes: dict, order: list[str], notes: list[str]) -> str:
    procs, calls = [], []
    for nid in order:
        n = nodes[nid]
        if n.get("kind") in {"input", "io"}:
            continue
        name = _slug(nid).upper()
        t = catalogue.TOOLS.get(n.get("tool") or "")
        container = ""
        if t and "docker" in (t.install or {}):
            container = f"    container '{t.install['docker'].replace('docker pull ', '')}'\n"
        elif t and t.execution != "native" and t.install.get("conda"):
            spec = (t.install["conda"].replace("conda install -c bioconda ", "bioconda::")
                    .replace("conda install -c conda-forge ", "conda-forge::"))
            container = f"    conda '{spec}'\n"
        elif t and t.execution != "native" and t.install.get("pip"):
            container = f"    // install with: {t.install['pip']}\n"
        elif t and t.execution != "native":
            container = f"    // install: see {t.docs}\n"
        procs.append(textwrap.dedent(f"""
        process {name} {{
            tag "${{meta.id}}"
            publishDir "${{params.outdir}}/{_slug(nid)}", mode: 'copy'
        """).rstrip() + "\n" + container + textwrap.dedent(f"""
            input:
            tuple val(meta), path(reads)

            output:
            tuple val(meta), path("*"), emit: out

            script:
            \"\"\"
            # {n['label']}{(' — ' + n['tool_name']) if n.get('tool_name') else ''}
            {_cmd(n)}
            \"\"\"
        }}
        """))
        calls.append(name)
    body = "\n".join(procs)
    chain = []
    prev = "ch_input"
    for c in calls:
        chain.append(f"    {c}({prev})")
        prev = f"{c}.out.out"
    return textwrap.dedent(f"""\
        #!/usr/bin/env nextflow
        // {title}
        //
        """) + "".join(f"// - {n}\n" for n in notes) + textwrap.dedent("""
        nextflow.enable.dsl = 2

        params.input  = 'samplesheet.csv'
        params.outdir = 'results'
        """) + body + textwrap.dedent(f"""
        workflow {{
            ch_input = Channel
                .fromPath(params.input)
                .splitCsv(header: true)
                .map {{ row -> tuple([id: row.sample], [file(row.fastq_1), file(row.fastq_2)]) }}

        {chr(10).join(chain)}
        }}
        """)


def _to_bash(title: str, nodes: dict, order: list[str], notes: list[str]) -> str:
    lines = ["#!/usr/bin/env bash", f"# {title}"] + [f"# {n}" for n in notes] + [
        "set -euo pipefail", "", 'SAMPLE="${1:?usage: run_workflow.sh <sample>}"',
        'OUTDIR="results/${SAMPLE}"', 'mkdir -p "$OUTDIR"', ""]
    for nid in order:
        n = nodes[nid]
        if n.get("kind") in {"input", "io"}:
            lines += [f"# input: {n['label']} ({', '.join(n.get('outputs', []))})"]
            continue
        lines += [f"echo '==> {n['label']}'", _cmd(n), ""]
    return "\n".join(lines)


def _to_python(title: str, wf: dict, nodes: dict, order: list[str], notes: list[str]) -> str:
    native = [nid for nid in order if nodes[nid].get("execution") == "native"]
    body = [f'"""{title}', ""] + [f"- {n}" for n in notes] + ['"""',
            "import subprocess, sys, shlex", "from pathlib import Path", "",
            "OUT = Path('results'); OUT.mkdir(exist_ok=True)", "",
            "def run(label, cmd):",
            "    print(f'==> {label}', flush=True)",
            "    if cmd.lstrip().startswith('#'):",
            "        print('    (native BioIDE step - see the Python API section below)')",
            "        return",
            "    subprocess.run(cmd, shell=True, check=True)", "", ""]
    for nid in order:
        n = nodes[nid]
        if n.get("kind") in {"input", "io"}:
            continue
        body.append(f"run({n['label']!r}, {_cmd(n)!r})")
    if native:
        body += ["", "", "# --- Native BioIDE steps, as direct library calls ---"]
        if wf.get("template") == "fba_strain_design":
            body += ["# from cobra.io import load_model, read_sbml_model",
                     "# from cobra.flux_analysis import flux_variability_analysis, single_gene_deletion",
                     "# model = read_sbml_model('model.xml')",
                     "# solution = model.optimize()",
                     "# fva = flux_variability_analysis(model, fraction_of_optimum=0.9)"]
        elif wf.get("template") == "rnaseq_de":
            body += ["# from pydeseq2.dds import DeseqDataSet",
                     "# from pydeseq2.ds import DeseqStats",
                     "# dds = DeseqDataSet(counts=counts.T, metadata=meta, design='~ condition')",
                     "# dds.deseq2(); DeseqStats(dds, contrast=['condition','treated','control']).summary()"]
        else:
            body += [f"# {nodes[n]['label']}" for n in native]
    return "\n".join(body)
