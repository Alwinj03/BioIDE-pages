"""The six sample projects.

Each one declares which steps run for real in BioIDE and which are generated as
scripts for the user's own machine. Data is either bundled in the repo (public,
cited) or fetched live from a public archive.
"""
from __future__ import annotations

from .services import omics

SAMPLE_PROJECTS = [
    {
        "id": "genome_annotation",
        "number": "01",
        "title": "Bacterial Genome Analysis",
        "organism": "Yersinia pestis plasmid pPCP1 (bundled) or any NCBI accession",
        "summary": "Parse an annotated genome record, compute GC content and skew, scan six frames for ORFs, "
                   "and compare the scan against the record's curated CDS annotation.",
        "objective": "Inspect a bacterial genome record and understand what a naive ORF scan recovers and misses "
                     "relative to curated annotation.",
        "learning_objectives": [
            "Read FASTA and GenBank records and know what each format carries.",
            "Compute GC content and cumulative GC skew, and interpret the skew minimum/maximum.",
            "Understand why a six-frame ORF scan is not genome annotation.",
            "Read a Bakta or Pyrodigal command and know what each argument does.",
        ],
        "workflow_template": "genome_annotation",
        "runs_here": ["Record parsing", "GC content and skew profile", "Six-frame ORF scan",
                      "Codon usage of predicted ORFs", "Comparison against curated CDS features"],
        "needs_local_tools": ["Bakta or Prokka for functional annotation", "HMMER for Pfam domain assignment",
                              "Pyrodigal for proper gene calling (pip-installable, so it may already be present)"],
        "data": [
            {"name": "Yersinia pestis biovar Microtus str. 91001 plasmid pPCP1",
             "accession": "NC_005816", "file": "Ypestis_pPCP1_NC_005816.gb", "size": "9,609 bp, 10 CDS",
             "source": "NCBI RefSeq, redistributed in the Biopython test suite",
             "why": "Small enough to analyse instantly, and carries real curated CDS features to check the ORF scan against."},
        ],
        "expected_outputs": ["Sequence statistics table", "GC and skew plot", "ORF table with coordinates and strand",
                             "Recovery rate against annotated CDS", "Generated annotation workflow"],
        "biology": "GC skew changes sign at the replication origin and terminus in most bacterial chromosomes, because "
                   "leading and lagging strands have different mutational biases. Plasmids such as pPCP1 may not show "
                   "this cleanly, which is itself informative. A six-frame ORF scan finds open reading frames but has no "
                   "model of ribosome binding sites, operon structure or overlapping genes, so it over-predicts short ORFs "
                   "and misses genes with non-ATG starts.",
        "entry_points": [
            {"label": "Analyse the bundled pPCP1 record", "endpoint": "/api/sequence/sample/pPCP1", "method": "GET"},
            {"label": "Fetch any NCBI accession", "endpoint": "/api/sequence/fetch/{accession}", "method": "GET",
             "note": "Requires outbound access to NCBI E-utilities."},
            {"label": "Generate the annotation workflow", "endpoint": "/api/workflow/generate", "method": "POST",
             "body": {"objective": "annotate a bacterial genome", "template": "genome_annotation"}},
        ],
    },
    {
        "id": "rnaseq_de",
        "number": "02",
        "title": "Differential Gene Expression",
        "organism": "Human airway smooth muscle cells",
        "summary": "Load a real published count matrix, run QC and PCA, then run a PyDESeq2 negative-binomial "
                   "differential expression test on a paired design and explore the results.",
        "objective": "Identify genes responding to dexamethasone treatment in airway smooth muscle cells, and "
                     "quantify the uncertainty in those estimates.",
        "learning_objectives": [
            "Tell a raw count matrix from normalised values, and know why DESeq2-family methods need raw counts.",
            "Spot a paired design and include the pairing factor in the formula.",
            "Read size factors, dispersion estimates and shrunken log fold changes.",
            "Understand why padj is NA for some genes rather than treating it as non-significant.",
        ],
        "workflow_template": "rnaseq_de",
        "runs_here": ["Count-matrix QC", "Library-size and detection summary", "Sample correlation", "PCA",
                      "PyDESeq2 differential expression with LFC shrinkage", "Volcano plot", "Clustered heatmap",
                      "Fisher over-representation on your own gene sets"],
        "needs_local_tools": ["fastp, Salmon or STAR if you start from FASTQ rather than counts",
                              "tximport (R) to aggregate transcript quantification to gene level"],
        "data": [
            {"name": "Airway smooth muscle, dexamethasone vs untreated",
             "accession": "GSE52778", "file": "airway_counts.csv.gz", "size": "38,694 genes x 8 samples",
             "source": omics.SAMPLE_DATASETS["airway"]["citation"],
             "why": "A real, well-characterised paired design: four donor cell lines, each treated and untreated. "
                    "Small enough to analyse in seconds, and the expected top hits are documented in the literature."},
            {"name": "Sample metadata", "file": "airway_metadata.csv", "size": "8 rows",
             "source": "Accompanies the counts", "why": "Carries the treatment and donor cell line for the design formula."},
        ],
        "expected_outputs": ["QC report", "PCA plot coloured by treatment and donor", "DE results table",
                             "Volcano plot", "Heatmap of top genes", "Reproducible DE script"],
        "biology": "Dexamethasone is a synthetic glucocorticoid; in airway smooth muscle it acts through the "
                   "glucocorticoid receptor to change transcription of inflammatory and metabolic genes. Because each "
                   "donor cell line contributes both a treated and an untreated sample, donor identity must enter the "
                   "design, otherwise between-donor variation inflates the dispersion estimates and costs power.",
        "entry_points": [
            {"label": "Inspect the dataset", "endpoint": "/api/omics/dataset/airway", "method": "GET"},
            {"label": "Run QC", "endpoint": "/api/omics/qc", "method": "POST", "body": {"dataset": "airway"}},
            {"label": "Run differential expression", "endpoint": "/api/omics/sample/airway/de", "method": "POST"},
        ],
    },
    {
        "id": "metagenomics",
        "number": "03",
        "title": "Microbial Community Functional Profiling",
        "organism": "Shotgun metagenome (your own data)",
        "summary": "Plan a taxonomic and functional profiling workflow, check whether the tools and databases exist "
                   "on this machine, and export runnable Snakemake or Nextflow.",
        "objective": "Produce an executable, honestly-scoped metagenomic profiling pipeline including CAZyme annotation, "
                     "with the database and memory requirements stated up front.",
        "learning_objectives": [
            "Understand why metagenomic tools are database-bound rather than CPU-bound.",
            "Tell Kraken2 read counts from MetaPhlAn relative abundances.",
            "See why HUMAnN consumes a MetaPhlAn profile as a real data dependency.",
            "Choose tools against a hardware constraint rather than a citation count.",
        ],
        "workflow_template": "metagenome_function",
        "runs_here": ["Workflow generation and DAG validation", "Format-compatibility checks",
                      "Tool feasibility check against this machine's RAM and PATH",
                      "Install-command and database-size planning", "Snakemake / Nextflow / Bash export"],
        "needs_local_tools": ["fastp", "MetaPhlAn 4 (~20 GB database)", "HUMAnN 3 (ChocoPhlAn ~16 GB + UniRef90 ~20 GB)",
                              "run_dbcan (~10 GB database)", "Kraken2 + Bracken if you prefer k-mer classification (~70 GB)"],
        "data": [
            {"name": "No dataset is bundled", "file": None, "size": "-",
             "source": "Bring your own FASTQ, or use a public SRA accession",
             "why": "Shotgun metagenomes are gigabytes per sample. Bundling a subsample that cannot produce a real "
                    "profile would mean showing you numbers that do not mean anything. BioIDE plans the run instead."},
        ],
        "expected_outputs": ["Validated workflow DAG", "Per-step resource and database requirements",
                             "Feasibility verdict for this machine", "Exported Snakemake and Nextflow files",
                             "Install plan for each missing tool"],
        "biology": "Taxonomic profiling answers who is present; functional profiling answers what the community can do. "
                   "They disagree often, because distantly related organisms share functions through horizontal transfer. "
                   "CAZymes are a good example: carbohydrate-active enzyme families cut across taxonomy and are what you "
                   "actually want when the question concerns polysaccharide degradation.",
        "entry_points": [
            {"label": "Generate the workflow", "endpoint": "/api/workflow/generate", "method": "POST",
             "body": {"objective": "Perform metagenomic functional profiling and identify carbohydrate-active enzymes"}},
            {"label": "Check what is installed here", "endpoint": "/api/environment?deep=true", "method": "GET"},
            {"label": "Recommend tools for 8 GB RAM", "endpoint": "/api/tools/recommend", "method": "POST",
             "body": {"objective": "metagenomic functional profiling", "ram_gb": 8}},
        ],
    },
    {
        "id": "protein_structure",
        "number": "04",
        "title": "Protein Structure Exploration",
        "organism": "HIV-1 capsid C-terminal domain (bundled) or any PDB entry",
        "summary": "Parse a structure, inspect chains, residues, hetero groups and B-factors, compute "
                   "sequence-derived physicochemical properties, and view it in 3D in the browser.",
        "objective": "Characterise a protein structure and understand which of its properties come from coordinates "
                     "and which from sequence alone.",
        "learning_objectives": [
            "Navigate the PDB hierarchy: structure, model, chain, residue, atom.",
            "Read B-factors, and know that pLDDT in a predicted model's B-factor column means something different.",
            "Distinguish coordinate-derived measures from sequence-derived estimates.",
            "Know when to predict a structure and when to look it up.",
        ],
        "workflow_template": "structure_analysis",
        "runs_here": ["PDB/mmCIF parsing", "Chain and residue inventory", "Hetero-group detection",
                      "Per-residue B-factor profile", "Radius of gyration from CA coordinates",
                      "ProtParam properties (MW, pI, GRAVY, instability index, extinction coefficient)",
                      "Interactive 3D rendering in the browser"],
        "needs_local_tools": ["DSSP for real secondary-structure assignment from coordinates",
                              "Foldseek for structural homologue search (database required)",
                              "ESMFold or AlphaFold via a hosted service for prediction"],
        "data": [
            {"name": "HIV capsid C-terminal domain", "accession": "1A8O", "file": "1A8O.pdb",
             "size": "70 residues, 1 chain, X-ray at 1.7 Å",
             "source": "RCSB PDB, redistributed in the Biopython test suite",
             "why": "Small, single-chain, solved by crystallography, so B-factors carry their usual meaning."},
        ],
        "expected_outputs": ["Chain and residue table", "B-factor plot", "Physicochemical property panel",
                             "3D view", "Structure report"],
        "biology": "The HIV-1 capsid C-terminal domain mediates CA-CA dimerisation during capsid assembly, which makes "
                   "it a drug target. Crystallographic B-factors report positional uncertainty and genuine mobility "
                   "together; flexible loops show high values. A predicted model stores pLDDT in the same column, where "
                   "high means confident, so the colour scale has to be read the opposite way.",
        "entry_points": [
            {"label": "Analyse the bundled 1A8O structure", "endpoint": "/api/structure/sample", "method": "GET"},
            {"label": "Fetch any PDB entry", "endpoint": "/api/structure/fetch/{pdb_id}", "method": "GET",
             "note": "Requires outbound access to files.rcsb.org."},
        ],
    },
    {
        "id": "metabolic_modelling",
        "number": "05",
        "title": "Constraint-Based Metabolic Analysis",
        "organism": "Escherichia coli (core model and iJO1366)",
        "summary": "Inspect a genome-scale model, check its structural quality, run FBA and pFBA, bound the answer "
                   "with FVA, scan gene deletions, and compute a growth-versus-product envelope. All of it real COBRApy.",
        "objective": "Predict metabolic flux distributions and product trade-offs, and quantify how much of the "
                     "prediction is actually determined by the model.",
        "learning_objectives": [
            "Set up a growth medium by constraining exchange reactions, and see how the prediction moves.",
            "Understand that an FBA optimum is usually one of many equally optimal flux distributions.",
            "Use FVA to decide which fluxes may be reported as predictions at all.",
            "Read a production envelope as a stoichiometric ceiling rather than an achievable titre.",
            "Add a heterologous reaction with declared stoichiometry and see mass balance checked.",
        ],
        "workflow_template": "fba_strain_design",
        "runs_here": ["Model inspection and structural quality report", "Medium definition via exchange bounds",
                      "FBA and pFBA", "FVA with optional loopless constraints",
                      "Single gene and reaction deletion scans", "Production envelope",
                      "Flux-weighted network visualisation", "Run-to-run flux comparison",
                      "Validated addition of user-specified reactions"],
        "needs_local_tools": ["MEMOTE for a publication-grade model quality report",
                              "HiGHS or Gurobi for faster large-model FVA",
                              "CarveMe or gapseq to build a draft model for an organism with no published GEM"],
        "data": [
            {"name": "E. coli core model", "accession": "e_coli_core", "file": None, "size": "95 reactions, 72 metabolites, 137 genes",
             "source": "Orth, Fleming & Palsson (2010) EcoSal Plus; ships with COBRApy",
             "why": "Central carbon metabolism only, so every analysis runs in under a second and the results are "
                    "small enough to read by hand."},
            {"name": "E. coli iJO1366", "accession": "iJO1366", "file": None, "size": "2,583 reactions, 1,805 metabolites, 1,367 genes",
             "source": "Orth et al. (2011) Mol Syst Biol 7:535; ships with COBRApy",
             "why": "A genome-scale reconstruction, for when the question needs full metabolic scope."},
        ],
        "expected_outputs": ["Model summary and quality report", "Flux table with exchange breakdown",
                             "FVA interval table", "Essentiality classification", "Production envelope plot",
                             "Flux-coloured network", "Reproducible COBRApy script"],
        "biology": "Flux balance analysis assumes metabolism is at steady state and that the cell behaves as though "
                   "maximising a biomass objective. That assumption holds reasonably for exponential growth on a "
                   "single carbon source and poorly elsewhere. Switching oxygen off in the core model is the clearest "
                   "demonstration: predicted growth drops several-fold and the model starts secreting fermentation "
                   "products, which is the behaviour E. coli actually shows.",
        "entry_points": [
            {"label": "Inspect the core model with quality checks",
             "endpoint": "/api/model/e_coli_core/inspect?with_quality=true", "method": "GET"},
            {"label": "Run FBA", "endpoint": "/api/model/fba", "method": "POST", "body": {"model_id": "e_coli_core"}},
            {"label": "Run FBA anaerobically", "endpoint": "/api/model/fba", "method": "POST",
             "body": {"model_id": "e_coli_core", "bounds": {"EX_o2_e": [0, 1000]}}},
            {"label": "Run FVA at 90% of optimum", "endpoint": "/api/model/fva", "method": "POST",
             "body": {"model_id": "e_coli_core", "fraction": 0.9}},
            {"label": "Acetate production envelope", "endpoint": "/api/model/envelope", "method": "POST",
             "body": {"model_id": "e_coli_core", "target": "EX_ac_e"}},
        ],
    },
    {
        "id": "pathway_engineering",
        "number": "06",
        "title": "Heterologous Pathway Analysis",
        "organism": "Escherichia coli",
        "summary": "Add a heterologous reaction set to a genome-scale model with explicit stoichiometry, let BioIDE "
                   "check mass and charge balance, then compare flux distributions and yields with and without it.",
        "objective": "Evaluate whether a proposed heterologous route is stoichiometrically and energetically coherent "
                     "in the host model before any experimental commitment.",
        "learning_objectives": [
            "Write a reaction specification with balanced stoichiometry, formulas and compartments.",
            "See why an unbalanced reaction can create a thermodynamically impossible yield.",
            "Compare two model states rather than reading one number.",
            "Separate a stoichiometric result from the kinetic and regulatory questions it cannot answer.",
            "Find the published evidence for a pathway before modelling it.",
        ],
        "workflow_template": "fba_strain_design",
        "runs_here": ["Reaction specification validation with mass and charge balance checks",
                      "FBA and FVA with the added reactions", "Yield and envelope comparison against the base model",
                      "Flux difference table between model states",
                      "Literature search for the enzymes and the route (needs network access)"],
        "needs_local_tools": ["cameo or straindesign for automated pathway prediction and knockout strategies",
                              "A MILP solver licence for OptKnock-style designs",
                              "MEMOTE to check the modified model before publishing it"],
        "data": [
            {"name": "E. coli iJO1366 as the host model", "accession": "iJO1366", "file": None,
             "size": "2,583 reactions", "source": "Orth et al. (2011) Mol Syst Biol 7:535; ships with COBRApy",
             "why": "Genome-scale scope is needed: a heterologous route usually draws on cofactors and precursors "
                    "that the core model does not represent."},
            {"name": "Reaction stoichiometry", "file": None, "size": "-",
             "source": "You supply it, from the literature",
             "why": "BioIDE deliberately ships no built-in engineered pathways. A route you specify from a cited "
                    "paper is traceable; one BioIDE invented for you is not."},
        ],
        "expected_outputs": ["Balance-check verdict per added reaction", "Side-by-side flux comparison",
                             "Yield and envelope comparison", "Literature collection for the route",
                             "Reproducible COBRApy script"],
        "biology": "A stoichiometric model can tell you whether a route is possible given mass, charge and redox "
                   "balance, and what the ceiling on yield would be. It cannot tell you whether the enzymes are "
                   "expressed, soluble, fast enough, or whether an intermediate is toxic. Those are the usual reasons "
                   "a route that looks good in silico fails on the bench, which is exactly why the model is worth "
                   "running first: it is cheap, and it rules things out.",
        "entry_points": [
            {"label": "Validate a reaction specification", "endpoint": "/api/model/add_reaction", "method": "POST",
             "body": {"model_id": "iJO1366",
                      "spec": {"id": "EXAMPLE_RXN", "name": "replace with your reaction",
                               "stoichiometry": {"accoa_c": -1, "coa_c": 1},
                               "lower_bound": 0, "upper_bound": 1000,
                               "new_metabolites": []}}},
            {"label": "Search for the route in the literature", "endpoint": "/api/literature/search", "method": "POST",
             "body": {"query": "heterologous pathway expression Escherichia coli flux"}},
            {"label": "Compare flux distributions", "endpoint": "/api/model/compare", "method": "POST"},
        ],
    },
]

_BY_ID = {s["id"]: s for s in SAMPLE_PROJECTS}


def sample_detail(sid: str) -> dict:
    if sid not in _BY_ID:
        raise KeyError(f"Unknown sample project '{sid}'. Available: {list(_BY_ID)}")
    from .services import workflow
    s = dict(_BY_ID[sid])
    if s.get("workflow_template"):
        s["workflow"] = workflow.generate(s["objective"], s["workflow_template"])
    s["honesty_note"] = ("Steps listed under 'runs_here' execute real library calls and are recorded with provenance. "
                         "Steps under 'needs_local_tools' are not run by BioIDE: it generates the commands and checks "
                         "whether the tool exists on this machine.")
    return s
