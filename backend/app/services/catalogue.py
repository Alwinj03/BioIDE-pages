"""Bioinformatics software catalogue.

`execution` states honestly where a tool can run from BioIDE:
  native      - runs inside the BioIDE backend process (installed Python library)
  local       - must run on the user's own machine via the local execution agent
  local_db    - as local, and additionally needs a large reference database
  external    - a hosted service or API BioIDE does not call for you
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass
class Tool:
    id: str
    name: str
    category: str
    description: str
    biological_application: str
    execution: str
    inputs: list[str]
    outputs: list[str]
    docs: str
    install: dict[str, str] = field(default_factory=dict)
    alternatives: list[str] = field(default_factory=list)
    resources: str = ""
    notes: str = ""
    languages: list[str] = field(default_factory=list)


T = [
    # ---------------- sequence analysis
    Tool("biopython", "Biopython", "Sequence analysis",
         "Python library for sequence records, parsers, translation and structure handling.",
         "Parsing FASTA/GenBank, GC content, ORF scanning, translation, PDB parsing.",
         "native", ["FASTA", "GenBank", "PDB", "mmCIF"], ["JSON", "FASTA", "tables"],
         "https://biopython.org/wiki/Documentation",
         {"pip": "pip install biopython", "conda": "conda install -c conda-forge biopython"},
         ["scikit-bio", "pyfastx"], "negligible", "Used directly by the BioIDE Bioinformatics workspace.", ["Python"]),
    Tool("blast", "NCBI BLAST+", "Sequence analysis",
         "Local sequence similarity search against formatted databases.",
         "Homology search, annotation transfer, primer specificity checks.",
         "local_db", ["FASTA"], ["tabular (outfmt 6)", "XML", "pairwise"],
         "https://www.ncbi.nlm.nih.gov/books/NBK279690/",
         {"conda": "conda install -c bioconda blast", "docker": "docker pull ncbi/blast"},
         ["DIAMOND", "MMseqs2", "foldseek (structures)"],
         "nr/nt are hundreds of GB; a bacterial proteome subset is a few hundred MB.",
         "The NCBI web BLAST URL API has strict rate limits and is not suitable for batch jobs."),
    Tool("diamond", "DIAMOND", "Sequence analysis",
         "Accelerated protein aligner, 100–10,000x faster than BLASTP at comparable sensitivity.",
         "Large-scale protein annotation, metagenome functional assignment.",
         "local_db", ["FASTA"], ["tabular", "DAA", "SAM"],
         "https://github.com/bbuchfink/diamond/wiki",
         {"conda": "conda install -c bioconda diamond"}, ["BLAST+", "MMseqs2"],
         "Index of UniRef90 ≈ 60 GB; needs RAM proportional to block size.", "", []),
    Tool("mafft", "MAFFT", "Sequence analysis", "Multiple sequence alignment.",
         "Phylogenetics, conserved-motif discovery, profile construction.",
         "local", ["FASTA"], ["aligned FASTA", "CLUSTAL"], "https://mafft.cbrc.jp/alignment/software/",
         {"conda": "conda install -c bioconda mafft"}, ["MUSCLE", "Clustal Omega", "FAMSA"],
         "Seconds for tens of sequences; --auto picks a strategy by input size.", "", []),
    Tool("muscle", "MUSCLE", "Sequence analysis", "Multiple sequence alignment (v5 uses ensemble alignment).",
         "Protein family alignment, consensus building.", "local", ["FASTA"], ["aligned FASTA"],
         "https://drive5.com/muscle/", {"conda": "conda install -c bioconda muscle"}, ["MAFFT", "Clustal Omega"], "", "", []),
    Tool("hmmer", "HMMER", "Sequence analysis", "Profile hidden Markov model search.",
         "Pfam domain annotation, remote-homology detection, family assignment.",
         "local_db", ["FASTA", "HMM"], ["domtblout", "tblout"], "http://hmmer.org/documentation.html",
         {"conda": "conda install -c bioconda hmmer"}, ["InterProScan", "Foldseek"],
         "Pfam-A.hmm ≈ 1.5 GB.", "", []),

    # ---------------- genome analysis
    Tool("bakta", "Bakta", "Genome analysis", "Rapid, standardised annotation of bacterial genomes.",
         "Structural and functional annotation of bacterial and plasmid assemblies.",
         "local_db", ["FASTA (assembly)"], ["GFF3", "GenBank", "TSV", "faa", "ffn"],
         "https://github.com/oschwengers/bakta",
         {"conda": "conda install -c bioconda bakta", "docker": "docker pull oschwengers/bakta"},
         ["Prokka", "PGAP", "RAST/DFAST"],
         "Full database ≈ 70 GB (light ≈ 2 GB); 8+ GB RAM.",
         "Actively maintained; preferred over Prokka for new bacterial projects.", []),
    Tool("prokka", "Prokka", "Genome analysis", "Pipeline wrapper for rapid prokaryotic annotation.",
         "Legacy-compatible bacterial genome annotation.", "local_db", ["FASTA"], ["GFF3", "GenBank", "TSV"],
         "https://github.com/tseemann/prokka", {"conda": "conda install -c bioconda prokka"},
         ["Bakta", "PGAP"], "Bundled databases ≈ 2 GB.",
         "No longer actively developed; its author recommends Bakta for new work.", []),
    Tool("pyrodigal", "Pyrodigal", "Genome analysis", "Python bindings to Prodigal gene prediction.",
         "Protein-coding gene calling in bacterial and archaeal genomes.",
         "local", ["FASTA"], ["GFF", "protein FASTA"], "https://pyrodigal.readthedocs.io/",
         {"pip": "pip install pyrodigal"}, ["Prodigal", "GeneMarkS-2"],
         "negligible; seconds per bacterial genome, no reference database",
         "A proper gene caller: it models start codons and RBS motifs, unlike BioIDE's six-frame ORF scan. "
         "Classed as 'local' rather than 'native' because BioIDE does not call it: it is not a backend "
         "dependency. A single pip install makes it available to the notebook sandbox.", ["Python"]),
    Tool("bwa-mem2", "BWA-MEM2", "Genome analysis", "Short-read aligner to a reference genome.",
         "Variant calling pipelines, resequencing, coverage analysis.",
         "local", ["FASTQ", "reference FASTA"], ["SAM/BAM"], "https://github.com/bwa-mem2/bwa-mem2",
         {"conda": "conda install -c bioconda bwa-mem2"}, ["Bowtie2", "minimap2", "BWA"],
         "Index of a human genome needs ~40 GB RAM to build; bacterial genomes are trivial.", "", []),
    Tool("bowtie2", "Bowtie2", "Genome analysis", "Gapped short-read aligner.",
         "ChIP-seq, ATAC-seq and metagenomic read mapping.", "local",
         ["FASTQ", "reference FASTA"], ["SAM/BAM"], "https://bowtie-bio.sourceforge.net/bowtie2/manual.shtml",
         {"conda": "conda install -c bioconda bowtie2"}, ["BWA-MEM2", "HISAT2"], "", "", []),
    Tool("minimap2", "minimap2", "Genome analysis", "Long-read and assembly-to-assembly aligner.",
         "Nanopore/PacBio mapping, whole-genome comparison.", "local", ["FASTQ", "FASTA"], ["SAM/BAM", "PAF"],
         "https://lh3.github.io/minimap2/", {"conda": "conda install -c bioconda minimap2"}, ["BWA-MEM2", "winnowmap"], "", "", []),
    Tool("samtools", "SAMtools", "Genome analysis", "Manipulation of SAM/BAM/CRAM alignments.",
         "Sorting, indexing, filtering, coverage and consensus from alignments.",
         "local", ["SAM/BAM/CRAM"], ["BAM", "stats", "pileup"], "https://www.htslib.org/doc/samtools.html",
         {"conda": "conda install -c bioconda samtools"}, ["sambamba", "pysam (Python)"], "", "", []),
    Tool("bcftools", "BCFtools", "Genome analysis", "Variant calling and VCF/BCF manipulation.",
         "SNP and indel calling, filtering, consensus sequence generation.",
         "local", ["BAM", "VCF/BCF"], ["VCF/BCF", "stats"], "https://samtools.github.io/bcftools/bcftools.html",
         {"conda": "conda install -c bioconda bcftools"}, ["GATK HaplotypeCaller", "FreeBayes", "DeepVariant"], "", "", []),
    Tool("fastp", "fastp", "Genome analysis", "All-in-one FASTQ quality control and trimming.",
         "Adapter removal, quality filtering and QC reporting before any mapping.",
         "local", ["FASTQ"], ["FASTQ", "HTML/JSON report"], "https://github.com/OpenGene/fastp",
         {"conda": "conda install -c bioconda fastp"}, ["Trim Galore", "cutadapt", "fastqc + trimmomatic"],
         "Fast and low memory; a few minutes per sample.", "", []),
    Tool("multiqc", "MultiQC", "Genome analysis", "Aggregates QC reports from many tools into one report.",
         "Project-level QC review across samples.", "local", ["tool logs"], ["HTML report"],
         "https://multiqc.info/", {"pip": "pip install multiqc"}, [], "", "", ["Python"]),

    # ---------------- transcriptomics
    Tool("salmon", "Salmon", "Transcriptomics", "Selective-alignment transcript quantification.",
         "RNA-seq expression estimates without a full genome alignment.",
         "local", ["FASTQ", "transcriptome FASTA"], ["quant.sf (TPM, counts)"],
         "https://salmon.readthedocs.io/", {"conda": "conda install -c bioconda salmon"},
         ["kallisto", "STAR + featureCounts", "RSEM"],
         "Index of a human transcriptome ≈ 15 GB RAM to build, ~3 GB on disk.",
         "Import to gene level with tximport before DESeq2; do not feed TPM to DESeq2.", []),
    Tool("kallisto", "kallisto", "Transcriptomics", "Pseudoalignment-based quantification.",
         "Fast RNA-seq quantification, bootstrap uncertainty estimates.",
         "local", ["FASTQ", "transcriptome FASTA"], ["abundance.tsv/h5"], "https://pachterlab.github.io/kallisto/",
         {"conda": "conda install -c bioconda kallisto"}, ["Salmon", "sleuth (downstream)"], "", "", []),
    Tool("star", "STAR", "Transcriptomics", "Splice-aware RNA-seq read aligner.",
         "Genome-aligned RNA-seq, splice-junction and fusion detection.",
         "local", ["FASTQ", "genome FASTA", "GTF"], ["BAM", "junctions", "ReadsPerGene"],
         "https://github.com/alexdobin/STAR",
         {"conda": "conda install -c bioconda star"}, ["HISAT2", "Salmon (alignment-free)"],
         "Human genome index needs ~32 GB RAM. Not viable on an 8 GB laptop.", "", []),
    Tool("hisat2", "HISAT2", "Transcriptomics", "Memory-efficient splice-aware aligner.",
         "RNA-seq alignment where STAR's memory footprint is prohibitive.",
         "local", ["FASTQ", "HISAT2 index"], ["SAM/BAM"], "http://daehwankimlab.github.io/hisat2/",
         {"conda": "conda install -c bioconda hisat2"}, ["STAR", "Salmon"],
         "Human index ≈ 8 GB RAM, far lighter than STAR.", "", []),
    Tool("featurecounts", "featureCounts (Subread)", "Transcriptomics", "Counts reads per genomic feature.",
         "Gene-level count matrices from aligned RNA-seq.", "local", ["BAM", "GTF/SAF"], ["count matrix"],
         "https://subread.sourceforge.net/", {"conda": "conda install -c bioconda subread"}, ["HTSeq-count", "Salmon"], "", "", []),
    Tool("pydeseq2", "PyDESeq2", "Transcriptomics",
         "Python reimplementation of the DESeq2 negative-binomial differential expression method.",
         "Differential gene expression from raw count matrices with replicates.",
         "native", ["count matrix (genes x samples)", "sample metadata"],
         ["results table (log2FC, p, padj)", "normalised counts"],
         "https://pydeseq2.readthedocs.io/", {"pip": "pip install pydeseq2"},
         ["DESeq2 (R)", "edgeR (R)", "limma-voom (R)"],
         "Seconds to minutes for a typical bulk experiment.",
         "Used directly by the BioIDE Omics workspace. Requires raw integer counts, never TPM or FPKM.", ["Python"]),
    Tool("deseq2", "DESeq2", "Transcriptomics", "Reference R implementation of negative-binomial DE testing.",
         "Differential expression, the method most reviewers expect to see cited.",
         "local", ["count matrix", "colData"], ["results table", "rlog/VST matrices"],
         "https://bioconductor.org/packages/DESeq2/",
         {"conda": "conda install -c bioconda bioconductor-deseq2",
          "R": "BiocManager::install('DESeq2')"}, ["PyDESeq2", "edgeR", "limma-voom"], "",
         "PyDESeq2 covers the common designs; complex designs and some shrinkage options remain R-only.", ["R"]),
    Tool("edger", "edgeR", "Transcriptomics", "Negative-binomial DE with empirical Bayes moderation (quasi-likelihood).",
         "DE analysis, especially with few replicates or complex designs.",
         "local", ["count matrix", "design"], ["topTags table"],
         "https://bioconductor.org/packages/edgeR/", {"R": "BiocManager::install('edgeR')"},
         ["DESeq2", "limma-voom"], "", "", ["R"]),

    # ---------------- metagenomics
    Tool("kraken2", "Kraken2", "Metagenomics", "k-mer based taxonomic classification of reads.",
         "Community composition from shotgun metagenomes.",
         "local_db", ["FASTQ/FASTA"], ["classification report", "kreport"],
         "https://github.com/DerrickWood/kraken2/wiki/Manual",
         {"conda": "conda install -c bioconda kraken2"}, ["MetaPhlAn", "Centrifuge", "sourmash", "Kaiju"],
         "Standard database ≈ 70 GB and must fit in RAM; the 8 GB capped database trades sensitivity for feasibility.",
         "Read counts are not abundances. Pair with Bracken for abundance estimation.", []),
    Tool("bracken", "Bracken", "Metagenomics", "Bayesian re-estimation of abundance from Kraken2 reports.",
         "Species- and genus-level relative abundance.", "local_db", ["kraken2 report"], ["abundance table"],
         "https://github.com/jenniferlu717/Bracken", {"conda": "conda install -c bioconda bracken"},
         ["MetaPhlAn"], "Needs a Bracken database built from the matching Kraken2 database.", "", []),
    Tool("metaphlan", "MetaPhlAn 4", "Metagenomics", "Marker-gene based taxonomic profiling.",
         "Species-level relative abundance, strain-level profiling with StrainPhlAn.",
         "local_db", ["FASTQ"], ["relative abundance profile", "SGB table"],
         "https://github.com/biobakery/MetaPhlAn",
         {"conda": "conda install -c bioconda metaphlan"}, ["Kraken2 + Bracken", "mOTUs"],
         "Marker database ≈ 20 GB; a Bowtie2 index build is needed on first run.",
         "Reports relative abundance directly, which Kraken2 does not.", []),
    Tool("humann", "HUMAnN 3", "Metagenomics", "Functional profiling of microbial communities.",
         "Pathway and gene-family abundance (UniRef, MetaCyc) from metagenomes or metatranscriptomes.",
         "local_db", ["FASTQ", "MetaPhlAn profile"], ["gene families", "pathway abundance/coverage"],
         "https://github.com/biobakery/humann",
         {"conda": "conda install -c bioconda humann"}, ["MEGAN", "eggNOG-mapper", "SqueezeMeta"],
         "ChocoPhlAn ≈ 16 GB plus UniRef90 ≈ 20 GB; CPU-hours per sample.",
         "Requires a MetaPhlAn taxonomic profile as input for the tiered search.", []),
    Tool("qiime2", "QIIME 2", "Metagenomics", "Plugin-based platform for microbiome analysis.",
         "Amplicon (16S/ITS) processing, diversity analysis, provenance-tracked artifacts.",
         "local", ["FASTQ (demultiplexed)", "metadata TSV"], ["qza/qzv artifacts", "feature tables"],
         "https://docs.qiime2.org/", {"conda": "see QIIME 2 release-specific environment file",
                                      "docker": "docker pull quay.io/qiime2/amplicon"},
         ["mothur", "DADA2 in R", "nf-core/ampliseq"],
         "Reference classifiers (SILVA, GTDB) are several GB.",
         "QIIME 2's own provenance model is a close analogue of what BioIDE records for native runs.", []),
    Tool("eggnog-mapper", "eggNOG-mapper", "Metagenomics", "Orthology-based functional annotation.",
         "GO, KEGG KO, COG and CAZy assignment for predicted proteins.",
         "local_db", ["protein FASTA"], ["annotations TSV"], "https://github.com/eggnogdb/eggnog-mapper",
         {"conda": "conda install -c bioconda eggnog-mapper"}, ["InterProScan", "DRAM", "dbCAN"],
         "eggNOG database ≈ 50 GB.", "A practical route to CAZyme assignment alongside dbCAN.", []),
    Tool("dbcan", "run_dbcan", "Metagenomics", "Carbohydrate-active enzyme (CAZyme) annotation.",
         "CAZyme family assignment and polysaccharide-utilisation locus prediction.",
         "local_db", ["protein or nucleotide FASTA"], ["CAZyme overview TSV", "CGC predictions"],
         "https://github.com/bcb-unl/run_dbcan", {"pip": "pip install dbcan"},
         ["eggNOG-mapper", "HMMER vs dbCAN HMMs", "CUPP"],
         "dbCAN database ≈ 10 GB.", "", ["Python"]),

    # ---------------- proteomics
    Tool("fragpipe", "FragPipe (MSFragger)", "Proteomics", "Fast database search for shotgun proteomics.",
         "Peptide identification, open and PTM searches, DIA support.",
         "local", ["mzML", "RAW", "protein FASTA"], ["PSM/peptide/protein tables"],
         "https://fragpipe.nesvilab.org/", {"manual": "Download the FragPipe GUI/CLI release"},
         ["MaxQuant", "OpenMS", "DIA-NN", "AlphaPept"],
         "Needs 16+ GB RAM for large DIA datasets.", "MSFragger requires a licence for commercial use.", []),
    Tool("maxquant", "MaxQuant", "Proteomics", "Quantitative proteomics suite (Andromeda search engine).",
         "Label-free and TMT/SILAC quantification.", "local", ["RAW", "mzML", "FASTA"], ["proteinGroups.txt", "evidence.txt"],
         "https://www.maxquant.org/", {"manual": "Windows installer; Linux via .NET"},
         ["FragPipe", "OpenMS", "DIA-NN"], "16+ GB RAM typical.", "Windows-first; Linux support is limited.", []),
    Tool("openms", "OpenMS / pyOpenMS", "Proteomics", "Open-source framework for LC-MS data processing.",
         "Feature detection, alignment, identification and quantification workflows.",
         "local", ["mzML", "idXML"], ["featureXML", "consensusXML", "tables"],
         "https://openms.readthedocs.io/", {"conda": "conda install -c bioconda openms",
                                            "pip": "pip install pyopenms"},
         ["FragPipe", "MaxQuant"], "", "pyOpenMS is scriptable from Python, so it fits BioIDE notebooks well.", ["Python", "C++"]),

    # ---------------- protein engineering / structure
    Tool("alphafold", "AlphaFold 2 / 3", "Protein engineering", "Deep-learning protein structure prediction.",
         "Structure prediction for proteins and complexes.",
         "external", ["protein FASTA"], ["PDB/mmCIF", "PAE and pLDDT"],
         "https://github.com/google-deepmind/alphafold",
         {"docker": "Official Docker image; local install needs genetic databases",
          "hosted": "AlphaFold DB for precomputed models; ColabFold for on-demand runs"},
         ["ColabFold", "ESMFold", "Boltz-2", "Chai-1", "OpenFold"],
         "Local AF2 needs ~2.6 TB of genetic databases and a GPU. AlphaFold 3 weights require an application to DeepMind.",
         "BioIDE does not run AlphaFold. For known proteins, check AlphaFold DB first; it may already hold the model.", []),
    Tool("esmfold", "ESMFold / ESM-2", "Protein engineering", "Language-model based structure prediction and embeddings.",
         "Single-sequence structure prediction, variant effect scoring, embeddings for ML.",
         "external", ["protein FASTA"], ["PDB", "embeddings", "pLDDT"],
         "https://github.com/facebookresearch/esm",
         {"pip": "pip install fair-esm", "hosted": "ESM Metagenomic Atlas API"},
         ["AlphaFold/ColabFold", "OmegaFold", "Boltz-2"],
         "ESMFold needs ~16 GB GPU memory; ESM-2 650M embeddings run on CPU slowly.",
         "Faster than AlphaFold because it skips MSA search, and usually less accurate for shallow-MSA targets.", ["Python"]),
    Tool("proteinmpnn", "ProteinMPNN", "Protein engineering", "Graph neural network for fixed-backbone sequence design.",
         "Designing sequences that fold to a chosen backbone; stability redesign.",
         "external", ["PDB backbone"], ["designed sequences, scores"],
         "https://github.com/dauparas/ProteinMPNN",
         {"manual": "git clone the repository and download weights"},
         ["LigandMPNN", "RFdiffusion (backbone generation)", "ESM-IF"],
         "Runs on a modest GPU; CPU is feasible for small designs.",
         "Designs are computational hypotheses and need experimental validation.", ["Python"]),
    Tool("foldseek", "Foldseek", "Structural biology", "Fast structural similarity search.",
         "Finding structural homologues when sequence similarity is undetectable.",
         "local_db", ["PDB/mmCIF"], ["alignment table"], "https://github.com/steineggerlab/foldseek",
         {"conda": "conda install -c bioconda foldseek"}, ["DALI", "TM-align", "US-align"],
         "AlphaFold DB index is hundreds of GB; PDB100 is a few GB.", "", []),
    Tool("pymol", "PyMOL", "Structural biology", "Molecular visualisation and scripting.",
         "Figure preparation, structural inspection, distance and contact analysis.",
         "local", ["PDB", "mmCIF", "MAE"], ["images", "sessions", "scripts"],
         "https://pymol.org/", {"conda": "conda install -c conda-forge pymol-open-source"},
         ["ChimeraX", "Mol* (web)", "VMD"], "", "Open-source PyMOL is free; incentive builds are commercial.", ["Python"]),
    Tool("molstar", "Mol*", "Structural biology", "Web-native molecular viewer.",
         "In-browser 3D structure display and annotation.", "native", ["PDB", "mmCIF", "BinaryCIF"], ["interactive view"],
         "https://molstar.org/", {"npm": "npm install molstar"}, ["NGL Viewer", "3Dmol.js"],
         "Runs client-side.", "BioIDE embeds a WebGL viewer for structures in the browser.", ["TypeScript"]),
    Tool("gromacs", "GROMACS", "Structural biology", "Molecular dynamics simulation engine.",
         "Protein dynamics, stability, membrane and solvation studies.",
         "local", ["GRO/PDB", "TOP", "MDP"], ["XTC/TRR trajectories", "EDR energies"],
         "https://manual.gromacs.org/", {"conda": "conda install -c bioconda gromacs"},
         ["OpenMM", "AMBER", "NAMD"],
         "GPU strongly recommended; microsecond trajectories are GPU-days and tens of GB.",
         "Not runnable from a web backend in any practical sense.", []),
    Tool("openmm", "OpenMM", "Structural biology", "Python-first molecular dynamics toolkit.",
         "Scriptable MD, free-energy calculations, custom force terms.",
         "local", ["PDB", "force field XML"], ["trajectories", "state data"],
         "http://docs.openmm.org/", {"conda": "conda install -c conda-forge openmm"},
         ["GROMACS", "AMBER"], "GPU recommended.", "", ["Python"]),
    Tool("vina", "AutoDock Vina", "Structural biology", "Protein–ligand docking.",
         "Virtual screening, binding-pose and affinity-score prediction.",
         "local", ["PDBQT receptor and ligand"], ["docked poses", "affinity scores"],
         "https://autodock-vina.readthedocs.io/", {"conda": "conda install -c conda-forge vina"},
         ["smina", "GNINA", "DiffDock", "Glide (commercial)"],
         "CPU-minutes per ligand; screening libraries needs a cluster.",
         "Docking scores correlate only weakly with measured affinity; treat them as a ranking heuristic.", ["Python"]),

    # ---------------- metabolic / systems
    Tool("cobrapy", "COBRApy", "Metabolic engineering", "Constraint-based reconstruction and analysis.",
         "FBA, FVA, gene deletion, production envelopes on genome-scale models.",
         "native", ["SBML", "COBRA JSON", "MAT"], ["flux distributions", "FVA ranges", "deletion tables"],
         "https://cobrapy.readthedocs.io/", {"pip": "pip install cobra", "conda": "conda install -c bioconda cobra"},
         ["COBRA Toolbox (MATLAB)", "cameo", "straindesign", "optlang"],
         "Seconds for core models; genome-scale FVA over all reactions takes minutes.",
         "Used directly by the BioIDE Modelling workspace. Solver defaults to GLPK; HiGHS or Gurobi are faster.", ["Python"]),
    Tool("cameo", "cameo", "Metabolic engineering", "Computational strain design built on COBRApy.",
         "Heterologous pathway prediction, OptKnock/OptGene-style design, flux scanning.",
         "local", ["SBML"], ["design predictions", "target tables"], "https://cameo.bio/",
         {"pip": "pip install cameo"}, ["straindesign", "OptFlux", "ARTomo"],
         "Some strategies need a commercial MILP solver to be practical.",
         "Maintenance has been intermittent; check compatibility with your COBRApy version.", ["Python"]),
    Tool("micom", "MICOM", "Metabolic engineering", "Community-level metabolic modelling with cooperative tradeoff.",
         "Microbial community growth rates and metabolite exchange from abundance data.",
         "local", ["SBML models", "taxonomic abundance table"], ["growth rates", "exchange fluxes"],
         "https://micom-dev.github.io/micom/", {"pip": "pip install micom"},
         ["SteadyCom", "MICOM-flux", "BacArena", "SMETANA"],
         "Community models are large QPs; a commercial solver or HiGHS is advisable.",
         "Relevant to community reconstruction work such as gut microbiota modelling.", ["Python"]),
    Tool("memote", "MEMOTE", "Metabolic engineering", "Standardised quality test suite for metabolic models.",
         "Scoring a reconstruction's consistency, annotation and biomass sanity before publishing it.",
         "local", ["SBML"], ["HTML/JSON report", "score"], "https://memote.readthedocs.io/",
         {"pip": "pip install memote"}, ["cobra.io validation", "FROG reports"],
         "Minutes per model.",
         "The expected evidence of model quality for a reconstruction paper; the BioIDE quality check is a small subset.", ["Python"]),
    Tool("carveme", "CarveMe", "Metabolic engineering", "Automated genome-scale model reconstruction.",
         "Draft GEMs from annotated genomes or proteomes.",
         "local", ["protein FASTA", "GenBank"], ["SBML model"], "https://carveme.readthedocs.io/",
         {"pip": "pip install carveme"}, ["gapseq", "ModelSEED/KBase", "AuReMe", "Merlin"],
         "Needs DIAMOND and a CPLEX or Gurobi licence for best results.",
         "Draft models need manual curation; MEMOTE scores them honestly.", ["Python"]),
    Tool("escher", "Escher", "Metabolic engineering", "Pathway map visualisation for metabolic models.",
         "Overlaying flux distributions on curated metabolic maps.",
         "external", ["COBRA JSON", "flux data"], ["interactive maps", "SVG"],
         "https://escher.github.io/", {"pip": "pip install escher"}, ["Cytoscape", "MetExplore", "Fluxer"],
         "Client-side.", "BioIDE draws its own force-directed network; Escher maps are hand-curated and clearer for canonical pathways.", ["JavaScript"]),
    Tool("tellurium", "Tellurium / libRoadRunner", "Systems biology", "Kinetic (ODE) modelling environment for SBML.",
         "Dynamic simulation, parameter scans, bifurcation analysis.",
         "local", ["SBML", "Antimony"], ["time courses", "steady states"],
         "https://tellurium.readthedocs.io/", {"pip": "pip install tellurium"},
         ["COPASI", "BasiCO", "PySB", "AMICI"],
         "Fast for small models.",
         "Kinetic models need rate constants; constraint-based models do not. The two answer different questions.", ["Python"]),
    Tool("copasi", "COPASI / BasiCO", "Systems biology", "Simulation and parameter estimation for biochemical networks.",
         "ODE and stochastic simulation, parameter fitting, sensitivity analysis.",
         "local", ["SBML", "CPS"], ["time courses", "fitted parameters", "reports"],
         "http://copasi.org/", {"pip": "pip install basico", "manual": "COPASI desktop installer"},
         ["Tellurium", "PySB", "AMICI"], "", "BasiCO exposes COPASI to Python, so it is scriptable from a notebook.", ["Python"]),

    # ---------------- workflow infrastructure
    Tool("nextflow", "Nextflow", "Workflow engine", "Dataflow workflow language with container and HPC support.",
         "Reproducible, portable, resumable bioinformatics pipelines.",
         "local", ["workflow .nf", "params", "samplesheet"], ["results", "trace/timeline reports"],
         "https://www.nextflow.io/docs/latest/",
         {"conda": "conda install -c bioconda nextflow", "curl": "curl -s https://get.nextflow.io | bash"},
         ["Snakemake", "WDL/Cromwell", "CWL"],
         "Needs Java 17+; containers via Docker, Singularity/Apptainer or Conda.",
         "nf-core provides peer-reviewed pipelines; prefer one over a hand-written workflow where it exists.", ["Groovy DSL2"]),
    Tool("snakemake", "Snakemake", "Workflow engine", "Python-based make-style workflow manager.",
         "Rule-driven reproducible analyses with cluster and cloud execution.",
         "local", ["Snakefile", "config.yaml"], ["results", "reports", "DAG"],
         "https://snakemake.readthedocs.io/", {"conda": "conda install -c bioconda snakemake",
                                               "pip": "pip install snakemake"},
         ["Nextflow", "CWL", "Make"],
         "Python 3.11+; per-rule Conda environments or containers.", "", ["Python"]),
    Tool("nf-core", "nf-core pipelines", "Workflow engine", "Community-curated, peer-reviewed Nextflow pipelines.",
         "Production RNA-seq (rnaseq), variant calling (sarek), amplicon (ampliseq), assembly (mag) and more.",
         "local", ["samplesheet CSV", "reference genome"], ["QC reports", "count matrices", "VCFs"],
         "https://nf-co.re/", {"nextflow": "nextflow run nf-core/rnaseq -profile docker"},
         ["hand-written Nextflow", "Snakemake workflow catalog"],
         "Reference genomes via iGenomes, or build your own; expect tens of GB.",
         "Running an nf-core pipeline is almost always better than writing a new one.", []),
]

TOOLS = {t.id: t for t in T}
CATEGORIES: dict[str, list[str]] = {}
for t in T:
    CATEGORIES.setdefault(t.category, []).append(t.id)

EXECUTION_MEANING = {
    "native": "Runs inside the BioIDE backend now. Results carry a provenance record.",
    "local": "Must run on your own machine through the local execution agent. BioIDE generates the command and you approve it.",
    "local_db": "As 'local', and additionally needs a large reference database you download yourself.",
    "external": "A hosted service, GPU job or desktop application. BioIDE does not run it for you; it prepares inputs and explains the route.",
}


def listing(category: str | None = None, execution: str | None = None, query: str | None = None) -> dict:
    rows = list(TOOLS.values())
    if category:
        rows = [t for t in rows if t.category == category]
    if execution:
        rows = [t for t in rows if t.execution == execution]
    if query:
        q = query.lower()
        rows = [t for t in rows if q in t.name.lower() or q in t.description.lower()
                or q in t.biological_application.lower() or q in t.id.lower()
                or any(q in a.lower() for a in t.alternatives)]
    return {"count": len(rows), "tools": [asdict(t) for t in rows],
            "categories": {k: len(v) for k, v in CATEGORIES.items()},
            "execution_meaning": EXECUTION_MEANING,
            "native_tools": [t.id for t in TOOLS.values() if t.execution == "native"]}


def get(tool_id: str) -> dict:
    if tool_id not in TOOLS:
        raise KeyError(f"Unknown tool '{tool_id}'")
    t = asdict(TOOLS[tool_id])
    t["execution_meaning"] = EXECUTION_MEANING[t["execution"]]
    t["alternatives_in_catalogue"] = [
        {"id": o.id, "name": o.name, "execution": o.execution}
        for o in TOOLS.values() if o.id != tool_id and (o.name in TOOLS[tool_id].alternatives
                                                        or any(a.lower() in o.name.lower() for a in TOOLS[tool_id].alternatives))
    ]
    return t


def recommend(objective: str, ram_gb: float | None = None, has_gpu: bool = False) -> dict:
    """Keyword-driven recommendation that stays explainable: every hit says why it matched.
    The LLM layer can refine this, but the ranking itself is deterministic."""
    o = objective.lower()
    topic_map = {
        "Transcriptomics": ["rna-seq", "rnaseq", "transcriptom", "differential expression", "deg", "gene expression", "volcano"],
        "Metagenomics": ["metagenom", "microbiome", "16s", "amplicon", "taxonom", "community", "cazyme", "carbohydrate-active"],
        "Proteomics": ["proteom", "mass spec", "peptide", "lc-ms"],
        "Metabolic engineering": ["metabolic model", "flux", "fba", "fva", "cobra", "gem", "genome-scale", "strain design", "yield"],
        "Genome analysis": ["genome", "annotat", "assembl", "variant", "snp", "align", "fastq"],
        "Sequence analysis": ["blast", "homolog", "alignment", "orf", "gc content", "fasta", "motif", "domain"],
        "Protein engineering": ["protein design", "structure predict", "alphafold", "esm", "mutant", "stability"],
        "Structural biology": ["docking", "molecular dynamics", "pdb", "visualis", "visualiz", "binding"],
        "Systems biology": ["kinetic", "ode", "dynamic model", "simulation", "parameter estimation"],
        "Workflow engine": ["pipeline", "workflow", "nextflow", "snakemake", "reproducib"],
    }
    hits: list[tuple[int, str, list[str]]] = []
    for cat, kws in topic_map.items():
        matched = [k for k in kws if k in o]
        if matched:
            hits.append((len(matched), cat, matched))
    hits.sort(reverse=True)
    cats = [h[1] for h in hits] or ["Sequence analysis"]
    reasons = {h[1]: h[2] for h in hits}

    out = []
    for cat in cats[:3]:
        for tid in CATEGORIES.get(cat, []):
            t = TOOLS[tid]
            warn = []
            if ram_gb is not None:
                if tid in {"star", "kraken2"} and ram_gb < 16:
                    warn.append(f"Needs considerably more than {ram_gb:g} GB RAM for standard references. "
                                + ("Use HISAT2 or Salmon instead." if tid == "star" else "Use the capped 8 GB database, or MetaPhlAn."))
                if tid in {"humann", "eggnog-mapper", "bakta"} and ram_gb < 8:
                    warn.append(f"Database and memory requirements exceed {ram_gb:g} GB comfortably.")
            if not has_gpu and tid in {"alphafold", "esmfold", "proteinmpnn", "gromacs", "openmm"}:
                warn.append("Practically requires a GPU; use a hosted service or precomputed data instead.")
            out.append({"id": tid, "name": t.name, "category": cat, "execution": t.execution,
                        "why": f"category '{cat}' matched on {reasons.get(cat, [])}",
                        "description": t.description, "warnings": warn,
                        "feasible_here": t.execution == "native"})
    out.sort(key=lambda r: (not r["feasible_here"], len(r["warnings"])))
    return {"objective": objective, "matched_categories": cats,
            "constraints": {"ram_gb": ram_gb, "has_gpu": has_gpu},
            "recommendations": out,
            "method": "deterministic keyword match over the catalogue, then re-ranked by feasibility under your stated constraints",
            "caveat": "This ranking is a heuristic over a hand-curated catalogue of "
                      f"{len(TOOLS)} tools, not an exhaustive survey of the field."}
