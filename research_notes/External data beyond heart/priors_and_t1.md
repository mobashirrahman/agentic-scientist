# External gene-level priors (Part A) and T1 extras (Part B): verified catalogue and compliance flags

Research date: 2026-11-17. Scope: mouse first; human resources flagged. No large files downloaded: GEO annotation files were fetched only where under about 5 MB, and the Census queries read metadata columns only (no expression matrices).

**Evidence labels.** Verified = read from the page, the GEO FTP index, the PMC full text, or a local Census metadata query in this session. Snippet = seen only in a search-result summary. Unverified = not checked.

**Compliance flags** (rules section 10 as recorded in `Late stage heart anchors/atlases_and_rules.md`):
- **GREEN**: allowed by the letter; no held-out measurement expected. Still disclose.
- **AMBER**: allowed by the letter, but needs stage or genotype filtering, a source check, or an organiser ruling before use.
- **RED**: do not use. Covers measured data from E10.5 to E13.5 (any genotype, any route, including ChIP and accessibility), Ctnnb1 or Gata4 alleles, loss-of-function data, and phenocopies.

**Two standing rules that decide most of the flags below.** (1) Measured data from the window E9.5 < t <= E13.5 is excluded, E9.5 exactly is allowed, and E14.0 and later are allowed with disclosure. (2) Any Gata4 or Ctnnb1 data, including other alleles and phenocopies, is held out. Binding or accessibility data count as measured data, so a WT ChIP at E12.5 is RED.

---

## Key Question A1: Wnt/beta-catenin target gene sets (mouse embryo and heart)

### Takeaway
The only curated Wnt-target list I could open is the Nusse lab table, which is from 2009 and mixes gain-of-function, Xenopus, cell-line and loss-of-function sources. GO and Reactome canonical-Wnt membership sets are the cleanest option (GREEN as annotation). I found no WT beta-catenin or TCF ChIP from mouse embryonic cardiac progenitors. Every beta-catenin ChIP I found is in ES cells, uses a Ctnnb1 knock-in or CHIR99021 treatment, or is from a loss-of-function arm.

### Cited Findings
- Nusse lab table: a curated HTML table (about 115 rows) of Wnt/beta-catenin targets, last updated December 2009, no download option. Entries come from mouse, Xenopus, human colon cancer lines, zebrafish and Drosophila, plus rat cardiomyocyte and mouse ES cells. The stated criterion is "Direct targets are defined as those with Tcf binding sites and demonstrating that these sites are important." Direct/indirect fields are often blank or "?". Example rows: Brachyury (Wnt-3A-treated mouse embryos, up), Nkx2.2 (neural tube, down, Lei 2006), E-cadherin (hair follicle, down, Jamora 2003). [Nusse targets](https://web.stanford.edu/~rnusse/pathways/targets.html) (verified via WebFetch summary; per-row experimental system not checked)
- MSigDB mouse GO sets exist for canonical Wnt. Verified names: GOBP_CANONICAL_WNT_SIGNALING_PATHWAY (mouse page exists; partial gene list includes Axin1, Axin2, Ctnnb1, Btrc, Dkk1; total count not seen), GOCC_WNT_SIGNALOSOME (11 mouse genes, GO release 2024-04-24), GOBP_NEGATIVE_REGULATION_OF_CANONICAL_WNT_SIGNALING_PATHWAY, and REACTOME_REPRESSION_OF_WNT_TARGET_GENES (mouse, 10 genes). Some GO canonical-Wnt variants are human-only; use the /mouse/ URLs. MSigDB notes that some sets have special access terms. [MSigDB mouse GOBP canonical Wnt](https://www.gsea-msigdb.org/gsea/msigdb/mouse/geneset/GOBP_CANONICAL_WNT_SIGNALING_PATHWAY.html); [GOCC_WNT_SIGNALOSOME](https://gsea-msigdb.org/gsea/msigdb/mouse/geneset/GOCC_WNT_SIGNALOSOME.html); [REACTOME repression](https://www.gsea-msigdb.org/gsea/msigdb/mouse/geneset/REACTOME_REPRESSION_OF_WNT_TARGET_GENES.html) (snippets; gene counts incomplete)
- Beta-catenin ChIP in mouse ES cells, WT with CHIR99021 treatment: GEO GSE43565, submitted 2013-03-01, serum+LIF conditions. [GEO GSE43565 via OmicsDI](https://omicsdi.org/dataset/geo/GSE43565) (snippet; not opened)
- Biotin-FLAG Ctnnb1 knock-in ChIP-seq in mouse ES cells, with beta-catenin at Lef/Tcf-motif elements under Wnt stimulation. [PMC3830733](https://pmc.ncbi.nlm.nih.gov/articles/PMC3830733) (snippet; accession not captured)
- TCF7 and TCF7L1 3xFLAG knock-in ChIP in mESC, with GSK3 inhibition. [bioRxiv 10.1101/473801](https://www.biorxiv.org/content/10.1101/473801v1.full.pdf) (snippet; no accession captured)
- E-MTAB-10575: beta-catenin ChIP-seq in WT mESC and in TCF/LEF quadruple-knockout mESC; listed next to GSE241025 and GSE241026 (2024), contents not checked. [E-MTAB-10575 via OmicsDI](https://www.omicsdi.org/dataset/biostudies-arrayexpress/E-MTAB-10575) (snippet)
- GSE97761: TCF7L2 occupancy in adult ventricular cardiomyocytes after beta-catenin stabilisation. [GEO GSE97761 via OmicsDI](https://www.omicsdi.org/dataset/geo/GSE97761) (snippet)
- A search result described a beta-catenin loss-of-function study in Isl1-expressing cells, with downstream genes Tbx2, Tbx3, Wnt11, Shh and Pitx2. The source URL was not captured. I did not search for Mesp1-Cre or Isl1-Cre beta-catenin mutant expression lists, because they fall in the forbidden category.

### Inferences
- GO and Reactome membership sets are pathway annotation, not measured perturbation data. They are GREEN, and the held-out risk is only that the membership of a set could be drawn from a Ctnnb1 experiment. Recommended: use GOBP_CANONICAL_WNT_SIGNALING_PATHWAY and similar annotation sets, and avoid any set that was built from an expression experiment.
- The Nusse table is not safe as a gene set without provenance. Its "down" entries may come from loss-of-function or Wnt-inhibition experiments, and that has not been checked row by row. Up-direction direct targets are a better bet, and only after an organiser ruling.
- ChIP from CHIR-treated or knock-in ES cells is a different biology from embryonic cardiac progenitors. It also needs a ruling: CHIR is pharmacological pathway activation rather than a Ctnnb1 allele, so it is probably not a phenocopy, but the rules do not say so.

### Gaps
- No WT beta-catenin or TCF ChIP from mouse embryonic cardiac progenitors or heart was found in this session.
- I did not open GSE43565, E-MTAB-10575 or GSE241025/6, so their contents and accessions are unverified.
- Per-row provenance of the Nusse table is not verified.

---

## Key Question A2: Cardiac and mouse gene regulatory networks, TF binding atlases, enhancer data

### Takeaway
Motif-based GRN resources (cisTarget/SCENIC databases and CellOracle base GRNs) are the lowest-risk GRN priors, because they contain no expression or perturbation data. Cardiac TF ChIP is largely at E12.5, which is RED. The only post-window cardiac data I verified are E14.5 heart histone ChIP from ENCODE (GREEN or AMBER, with disclosure) and adult P42 TF ChIP (AMBER).

### Cited Findings
- **Akerberg et al. 2019, Nat Commun (doi:10.1038/s41467-019-12812-3)**: bioChIP-seq of seven cardiac TFs (GATA4, NKX2-5, MEF2A, MEF2C, SRF, TBX5, TEAD1) in fetal E12.5 ventricular apexes and adult P42, from heterozygous knock-in tagged animals. Adult MEF2C profiling failed. Data availability: GEO GSE124008. [PMC6817842](https://pmc.ncbi.nlm.nih.gov/articles/PMC6817842/) (verified via PMC text; Nat Commun page redirected to login)
- A 2016 eLife paper immunoprecipitated Nkx2-5, Tbx5 and Gata4 from E12.5 hearts and compared peak overlap. Search summary only; article link not identified; accession not captured (snippet)
- PRJNA292836: ChIP-exo for TBX5, NKX2-5 and GATA4 in differentiating WT, Nkx2-5 KO, Tbx5 KO and double-KO cells at cardiac precursor and cardiomyocyte stages. These are in vitro cells, not embryos. [OmicsDI PRJNA292836](https://www.omicsdi.org/dataset/omics_ena_project/PRJNA292836) (snippet)
- **ENCODE E14.5 heart histone ChIP** (bulk tissue, B6NCrl background): H3K27ac ENCSR000CDK (two isogenic replicates), H3K4me1 ENCSR000CDL, plus a second H3K4me1 ENCSR080GQM and H3K36me3 ENCSR641EME. Input control via OmicsDI. [ENCSR000CDK](https://www.encodeproject.org/experiments/ENCSR000CDK/); [ENCSR000CDL](https://www.encodeproject.org/experiments/ENCSR000CDL/) (snippets)
- **CellOracle** provides pre-built promoter base GRNs for 10 species, loaded through the package's data-loading function. The docs do not name mouse, the source atlas, the motif database or the licence. The demo base GRN is described as built from a "Mouse sci-ATAC-seq atlas", per a search summary of the CellOracle documentation. [CellOracle base GRN tutorial](https://morris-lab.github.io/CellOracle.documentation/tutorials/base_grn.html) (tutorial verified via WebFetch summary; mouse membership and source unverified)
- **SCENIC / cisTarget**: resources.aertslab.org hosts cisTarget databases. The site recommends v10nr_clust. It states the files are "quite big (most of them 1-100GB)". No licence or terms are stated on the page, and no mm10 file list was visible. [cisTarget](https://resources.aertslab.org/cistarget/) (verified via WebFetch summary)
- Mouse tissue ATAC atlas CNP0000198 (CNGB, CC BY 4.0 per snippet, 296,574 accessible elements). [CNGB CNP0000198](https://db.cngb.org/cnsa/project/CNP0000198/public) (snippet)

### Inferences
- **GREEN**: motif-only resources (cisTarget motif-ranking and annotation databases). They contain no measured expression, so they carry no held-out content by themselves.
- **AMBER**: CellOracle base GRNs and any ATAC-derived prior. Accessibility is a measurement, so if the source ATAC contains embryonic tissue at E10.5 to E13.5, it is RED. Check the source's stage composition before use.
- **AMBER**: regulons built with SCENIC from co-expression need an input scRNA dataset. They inherit that dataset's compliance, so they must be built from GREEN inputs only (E8.5 for T1, E9.5 exactly, E14.0 and later).
- **RED**: Akerberg E12.5 data and the 2016 E12.5 ChIP, because E12.5 is a held-out test stage for T1 and heart. Also RED because the Gata4 knock-in tagged allele is an allele of a forbidden gene.
- **AMBER**: Akerberg adult P42 data. It is after E13.5 (disclosure needed), but it uses a Gata4 tagged allele at an adult stage. Ask before use.
- **GREEN or AMBER**: ENCODE E14.5 heart histone marks. E14.5 is allowed with disclosure. Histone marks are not perturbation data, so this is a region-level prior only.

### Gaps
- No mouse embryonic cardiac TF ChIP outside E12.5 was found, apart from the in-vitro ChIP-exo set.
- The CellOracle mouse base GRN is not confirmed; the ATAC source stages are unknown.
- The licence for cisTarget/SCENIC databases is not stated on the page.
- The Akerberg GEO accession GSE124008 was read from the PMC text, not from GEO (GEO web is reCAPTCHA-blocked to automated clients).

---

## Key Question A3: Expression, phenotype and lethality resources (mouse)

### Takeaway
MGI GXD and Eurexpress are the best post-window expression priors (E14.5 whole-embryo ISH). IMPC is a phenotype resource, not expression, and its window-of-lethality timepoints fall inside the protected window. The Mouse Gene Atlas (Hume) was not found.

### Cited Findings
- **MGI GXD** (Gene Expression Database): literature curation plus direct submissions and bulk data. Scale in 2015: about 70,000 experiments and 1.5 million expression results for about 13,900 genes. It incorporates RNA-seq and microarray metadata from GEO and ArrayExpress. Export via GXD BioMart. [GXD 2015](https://pmc.ncbi.nlm.nih.gov/articles/PMC4534488); [GXD BioMart FAQ](https://www.informatics.jax.org/faq/GXD_biomart.shtml); [MGI reports index](https://www.informatics.jax.org/downloads/reports/index.shtml) (snippets; current file list not checked)
- **IMPC**: all data are free without embargo, via mousephenotype.org, the FTP at ftp.ebi.ac.uk/pub/databases/impc, and an API. Lethal means no homozygous pups at weaning; subviable means under 12.5% of a litter. Lines without live homozygotes get an embryo viability screen over several embryonic time points to set a window of lethality. All embryonic-lethal lines are assessed for gross morphology at E12.5. [IMPC embryo intro](https://mousephenotype.org/embryo); [EBI IMPC news](https://www.ebi.ac.uk/about/news/research-highlights/impc-essential-genes-2016/) (snippets; the FTP and API access statements and the 65.3% viability headline, from the 2016 Nature paper, come from the same search summaries)
- **Eurexpress** (E14.5 whole-embryo ISH): genome-wide in situ atlas at E14.5, more than 18,000 coding genes and over 400 microRNAs (2011 paper). The site reports 19,440 RNA in situ assays and 15,775 annotated assays as of 12/08/2023. Search by keyword, anatomy tree, sequence, or BioMart 7.0. No bulk download is described. No licence is stated; the footer reads "Copyright 1994-2008 Eurexpress project". [Eurexpress home](https://www.eurexpress.org/) (verified via WebFetch); [Eurexpress 2011 paper search summary](https://pubmed.ncbi.nlm.nih.gov/21267068/) (snippet)
- **DMDD / EMBL-EBI Expression Atlas** whole-embryo RNA-seq baseline: somite numbers 4 to 36 excluding 29 to 33, roughly E8.5 to E10.5. [Search summary](https://www.ebi.ac.uk/gxa) (snippet; accession not verified)
- **eMouseAtlas / EMAGE**: 26 Theiler stages of in situ expression. [eMouseAtlas](https://emouseatlas.org/emap/ema/theiler_stages/StageDefinition/stagedefinition.html) (snippet)

### Inferences
- **GXD**: GREEN only after filtering. Keep WT assays at E9.5 exactly and at E14.0 and later. Drop all E10.0 to E13.5 assays, drop every Gata4 or Ctnnb1 mutant assay, and drop any phenocopy genotype. GXD carries mutant-genotype assays, so the filter is mandatory.
- **IMPC**: AMBER. Lethality calls for non-Gata4, non-Ctnnb1 and non-phenocopy genes are a weak prior. The E12.5 gross morphology and the window-of-lethality timepoints from E10.5 to E13.5 are RED.
- **Eurexpress**: GREEN for E14.5 under the letter (disclosure). It is qualitative and image-based, and the licence is unstated, so ask before use.
- **DMDD/Expression Atlas**: AMBER. The somite range reaches E9.5 and beyond, so per-sample staging is needed.

### Gaps
- Mouse Gene Atlas (Hume): no source found in this session. The search returned only Eurexpress, EMAGE and DMDD.
- IMPC data release number, file sizes and licence are not verified.
- GXD file list and licence not verified; the MGI reports page was not read in full.

---

## Key Question A4: Perturb-seq and CRISPR screens in mouse mesoderm or cardiac differentiation

### Takeaway
I found no mouse ES-derived cardiac Perturb-seq. The closest mouse study is a targeted CRISPR knockout screen of transcription factors in mESC for haemato-endothelial mesoderm (GEO GSE287036). Cardiac single-cell CRISPR screens are human (CRISPRi in hPSC cardiomyocyte differentiation; BRD4 in iPSC).

### Cited Findings
- Targeted CRISPR-Cas9 knockout screen in murine ES cells for haemato-endothelial fate commitment. Regulators identified: ETV2, LDB1, SMAD1, SIX4, ZBTB7b. The readout is described as transcriptome analysis; a single-cell readout is not confirmed. Dataset GEO GSE287036. [OmicsDI GSE287036](https://www.omicsdi.org/dataset/geo/GSE287036) (snippet; the preprint link was not confirmed)
- Human CRISPRi Perturb-seq benchmark in H9 ESC and WTC11 iPSC, covering cardiomyocyte and neuron differentiation; BioProject PRJNA734618 reports about 2.0 million sequenced cells. [bioRxiv 10.1101/2025.01.21.633969](https://www.biorxiv.org/content/10.1101/2025.01.21.633969.full.pdf); [OmicsDI PRJNA734618](https://www.omicsdi.org/dataset/project/PRJNA734618) (snippets)
- Single-cell CRISPRi of 25 CHD-associated enhancers in hESC-to-cardiomyocyte differentiation (human). (search summary; source link not identified; snippet)
- BRD4 genome-wide CRISPR screen in human iPSC-to-cardiomyocyte differentiation, with single-cell follow-up. A mouse ESC cardiac-progenitor experiment with BET inhibition is mentioned in the same summary. [Padmanabhan et al. 2024](https://www.aminer.org/pub/65d8f987939a5f40824eec1c/a-genome-wide-crispr-screen-identifies-brd-as-a-regulator-of-cardiomyocyte) (snippet)
- LncCPR single-gene knockout in mouse ESC reduces Mesp1 and cardiac TFs and reduces contractility. This is not a pooled screen. [Search summary](https://www.omicsdi.org/dataset/geo/GSE79499) (snippet)

### Inferences
- GSE287036: AMBER. ESC-derived, not stage-matched to an embryo, and its readout type is unconfirmed. Gata4 and Ctnnb1 are not among its named factors (per the snippet), so it is not an automatic phenocopy, but check the full TF list.
- Human CRISPRi and BRD4 data: AMBER. Use only as gene-level or design priors, with human flags.

### Gaps
- No mouse embryonic or ESC cardiac Perturb-seq with a single-cell readout was found in this session.
- GSE287036 readout, cell number and TF list not verified.

---

## Key Question B1: Qiu et al. 2024: access, licence, size and stage metadata

### Takeaway
Qiu 2024 is reachable three ways: GEO (the 2024 time course is GSE228590, and GSE186069 is an E8.5-only set), the Shendure-lab portal, and CELLxGENE Census (31 datasets). The GEO count matrices are about 61 GB, so use the annotation files. Stage granularity is per-cell E-day (day label) and per-run embryo ID in GEO, but only Theiler-stage labels in Census. An accession I guessed from memory, GSE223922, is not Qiu: it is a different (Sur 2023) dataset.

### Cited Findings
- Paper: Nature 626(8001):1084-1093, doi:10.1038/s41586-024-07069-w, PMCID PMC10901739. Data availability (verified from the PMC full text): "deposited into NCBI GEO under accession numbers GSE186069 and GSE228590" (raw and processed); also at omg.gs.washington.edu, which has a visual browser and downloads, and CELLxGENE. Code: github.com/ChengxiangQiu/JAX_code. Source data XLSX; Supplementary Tables 1 to 27 (XLSX, 1.8 MB); Supplementary Information PDF (504 KB). [PMC10901739](https://pmc.ncbi.nlm.nih.gov/articles/PMC10901739/) (verified)
- Qiu also reanalyses public data: GSE44183, GSE100597, GSE109071, the EmbryoTimecourse2018 GitHub repository, and the STOmics MOSTA portal. [PMC10901739](https://pmc.ncbi.nlm.nih.gov/articles/PMC10901739/) (verified). Any of these in a Census or GEO subset carries the window rule too.
- Staging: 45 temporal bins at 6-h increments from E8 to P0. Embryos staged by somite number up to about E10 and by limb-bud geometry after. [PMC10901739](https://pmc.ncbi.nlm.nih.gov/articles/PMC10901739/) (verified)
- OmicsDI describes GSE228590 as sampling at 2-h resolution during somitogenesis, 6-h through to birth, and 20-min resolution after birth. [OmicsDI GSE228590](https://www.omicsdi.org/dataset/geo/GSE228590) (snippet)
- **GEO GSE228590** (2024 time course; FTP index verified via curl HTTP 200): 19 cell-annotation files (run_4, run_13 to run_29, with run_17 split into sub1 and sub2), about 74 MB in total. Gene-count MTX files are 0.16 to 5.7 GB each, about 61 GB in total. Gene annotation 0.93 MB. Verified columns of run_4: cell_id, day (e.g. E8.5), embryo_id (run-scoped), experimental_id. Cell-type labels are not in the run_4 file. [GEO GSE228590 suppl](https://ftp.ncbi.nlm.nih.gov/geo/series/GSE228nnn/GSE228590/suppl/) (verified)
- **GEO GSE186069** (2021 deposit; FTP verified): cell_annotate.csv.gz (4.5 MB), gene_annotate (0.94 MB), gene_count.mtx.gz (2.1 GB). I read the whole cell annotation (239,533 barcodes). Columns: sample, UMI_count, gene_count, unmatched_rate, doublet_score, somite_number, embryo_sex, development_stage, celltype, removed_by_low_quality_or_doublets, RT_group. development_stage is 8.5 for every row. 85,220 rows are flagged removed (celltype NA); 154,313 kept. [GEO GSE186069 suppl](https://ftp.ncbi.nlm.nih.gov/geo/series/GSE186nnn/GSE186069/suppl/) (verified). I believe this is the E8.5 nuclei set from Qiu et al. 2022 Nat Genet (snippet only).
- **CELLxGENE Census** (census version 2025-11-08, the version the team's loader uses): 31 datasets carry the Qiu collection DOI. These are 26 "Major cell cluster" datasets (cardiomyocytes, endothelium, hepatocytes, mesoderm, epithelial, primitive erythroid, neural crest PNS neurons and glia, CNS neurons, definitive erythroid, and others), plus four "Whole dataset: Normalized subset 1 to 4" and one "Whole dataset: Raw counts only" with 11,441,407 cells. The 11.44 M count matches the paper's Results count (74 embryos) and not the abstract's 12.4 M / 83. Stage labels are Theiler stages TS12 to TS27. Cell_type labels are the Census vocabulary. [CELLxGENE Census](https://chanzuckerberg.github.io/cellxgene-census/) (verified by local metadata query; do not sum across datasets, because the major-cluster and whole-dataset collections overlap)
- The team's loader `scripts/v2/fetch_qiu2024.py` reads six major-cluster datasets via Census with server-side stage filters TS12, TS13 (calibration) and TS23 (anchor). Its comment says Census carries only Theiler stages, which are coarse. [Local file](/scratch/user/virtual-embryo/scripts/v2/fetch_qiu2024.py) (verified by reading)
- The organisers (rules page, per earlier notes) are the Qiu lab at Stanford. Their affiliation with the 2024 dataset is not verified here.
- Affiliation: the "JAX whole-embryo atlas" label used in the earlier notes is not supported by the paper. JAX appears only in the GitHub repository name and the portal path (/jax/public/).

### Inferences
- Per-embryo ages are available in GEO via day plus embryo_id. embryo_id is run-scoped, so map it to embryos carefully before use. Census gives only TS, so it cannot resolve days within TS14 to TS16.
- Census donor_id counts per TS stage in the whole dataset are 12 (TS12), 2 (TS13), 7 (TS14), 8 (TS15), 4 (TS16) and 4 (TS23). If donor_id is an embryo, representation at TS13 and TS16 is thin. This is unverified.
- Practical access: GEO annotation and metadata with curl (the GEO web pages return a reCAPTCHA page to automated clients, but the FTP index returns HTTP 200). Use Census for expression, with stage filters applied server-side.

### Gaps
- Licence of the dataset: the article is CC BY 4.0 (snippet). The dataset and Census terms are not verified.
- Whether GSE228590 has cell-type labels: run_4 has none. Labels probably come from the portal or Census, but this is unverified.
- The Supplementary Table 1 embryo-level ages were not read.
- The Census TS-to-E mapping for TS14 to TS16 is not verified. The team's loader comment treats TS12 and TS13 as about E8.0 to E9.0 and TS23 as about E15.

---

## Key Question B2: Qiu 2024 cell types at allowed stages (T1 heart-region relevance)

### Takeaway
At TS12 to TS15 (E8.0 to about E9.5, boundary to be checked per embryo), Qiu contains many heart-relevant lineages: splanchnic, lateral and intermediate mesoderm, endocardial cells, endothelium, primitive erythroid and hematopoietic progenitors. Cardiac muscle cells are absent from TS12 to TS16 in the whole dataset (across all Qiu datasets the first cardiac muscle label is at TS17), fibroblasts are under 100 cells at TS12 to TS16, and no mesothelial or epicardial label appears at those stages. At TS23 (the team's E15 anchor), cardiac muscle cells, endocardium, fibroblasts, myofibroblasts and HSCs appear. The team's TS12/13 "cardiomyocytes" subset contains only splanchnic mesodermal cells.

### Cited Findings (CELLxGENE Census 2025-11-08, whole-dataset "Raw counts only" obs; counts are cells)
| cell_type | TS12 | TS13 | TS14 | TS15 | TS16 | TS23 |
|---|---|---|---|---|---|---|
| lateral mesodermal cell | 31,207 | 8,833 | 72,837 | 159,150 | 80,170 | 33,693 |
| mesodermal cell | 30,165 | 9,600 | 95,234 | 256,069 | 230,018 | 23,392 |
| splanchnic mesodermal cell | 2,269 | 1,139 | 6,610 | 14,521 | 5,426 | 41 |
| intermediate mesodermal cell | 536 | 239 | 2,181 | 4,489 | 3,388 | 20 |
| endocardial cell | 95 | 240 | 1,490 | 3,983 | 1,916 | 394 |
| endothelial cell | 776 | 1,030 | 10,775 | 28,778 | 16,338 | 3,533 |
| endothelial cell of artery | 911 | 430 | 3,046 | 6,670 | 3,445 | 892 |
| embryonic blood vessel endothelial progenitor cell | 3,420 | 820 | 3,203 | 1,684 | 427 | 0 |
| primitive erythroid progenitor | 2,847 | 755 | 10,388 | 27,766 | 33,135 | 20 |
| erythroid progenitor cell | 2 | 1 | 15 | 121 | 669 | 219,851 |
| hematopoietic stem cell | 4 | 1 | 70 | 1,102 | 1,244 | 9,705 |
| fibroblast | 1 | 0 | 0 | 3 | 90 | 65,210 |
| myofibroblast cell | 0 | 0 | 0 | 1 | 20 | 4,209 |
| cardiac muscle cell | 0 | 0 | 0 | 0 | 0 | 339 |
| mesothelial / epicardial (any label) | not present | not present | not present | not present | not present | not present |
| neural crest (any label) | not present | not present | not present | not present | not present | not present |

- The TS12 and TS13 "cardiomyocytes" dataset (Census id 57b15e23-7838-4cae-8d72-9d4735b6d0f4) contains only splanchnic mesodermal cell labels: 2,269 at TS12 and 1,139 at TS13. At TS23 it contains 339 cardiac muscle cell and 41 splanchnic mesodermal cell rows. [Census, local metadata query](https://chanzuckerberg.github.io/cellxgene-census/) (verified)
- GEO GSE186069 (E8.5 only, 154,313 kept cells) has 31 labels, including First heart field (2,165 cells), Second heart field (1,781), Splanchnic mesoderm (9,390), Endothelium (2,693), Hematoendothelial progenitors (2,525), Primitive erythroid cells (2,862), Neural crest (6,461). There is no cardiomyocyte label at E8.5. [GEO GSE186069](https://ftp.ncbi.nlm.nih.gov/geo/series/GSE186nnn/GSE186069/suppl/) (verified; these label counts are for the 154,313 kept cells, because removed rows carry celltype NA)

### Inferences
- **TS12 and TS13** are the safest allowed stages (before E9.5). The project loader already uses them. **TS14 and TS15** may contain embryos past E9.5. Filter per embryo with the GEO `day` label (or somite number) and keep only embryos at E9.5 or earlier, otherwise they are RED. **TS16** straddles E9.5 to E10 and is RED unless every embryo is at or before E9.5.
- For T1 (E8.5 is a released training stage), GSE186069 E8.5 cells add first and second heart field, splanchnic and endocardial coverage. They are GREEN for T1. E8.5 is a held-out stage for the heart setting of Task 2, so they are RED for heart.
- **TS23** (about E15): cardiac muscle cells, endocardium and fibroblasts are present, so the team's TS23 anchor covers the cardiac lineages that are missing from the early stages. TS23 is GREEN (after E13.5, disclosure), subject to the TS-to-E mapping.
- The "cardiomyocytes" TS12/13 subset in the project loader is not cardiomyocytes. Its label is splanchnic mesoderm, so calibration rows labelled cardiomyocyte should be checked.

### Gaps
- Per-embryo TS-to-day mapping for TS12 to TS16 is not verified.
- Census donor_id meaning is not verified.
- GSE186069 label counts above are for kept cells only (154,313); the per-stage donor and embryo structure of this E8.5 set is not checked.

---

## Key Question B3: Other snRNA or scRNA mouse heart datasets at E14.5 or later, or E9.5 or earlier

### Takeaway
No embryonic mouse heart snRNA-seq dataset at E14.5 or later, or at E9.5 or earlier, was found except the whole-embryo sci-RNA-seq3 atlases (Qiu 2024 and MOCA, which is nuclei-based). The late-stage heart scRNA datasets (Feulner 2024, Ren 2023) are whole-cell, not nuclei. The E9.5 usable data in MOCA is restricted to exactly E9.5.

### Cited Findings
- **MOCA (Cao et al. 2019, Nature 566:496-502)**: sci-RNA-seq3 on nuclei ("Given that we are profiling RNA in nuclei"). About 2 million cells from 61 embryos staged E9.5 to E13.5. GEO GSE119945; ENA PRJNA490754. Median 35,272 profiled cells per embryo. The 0.8x coverage estimate at E9.5 is per the paper's own calculation. [Cao 2019 PDF](https://krishna.gs.washington.edu/documents/cao_nature_2019.pdf); [OmicsDI PRJNA490754 / GSE119945](https://db.cngb.org/data_resources/project/PRJNA490754) (snippets; stage-level counts and heart label not verified)
- **Feulner et al. 2024 (bioRxiv 10.1101/2024.03.05.583423)**: Drop-seq scRNA-seq of whole hearts at E14.5, E16.5, E18.5, P0, P4, P7; 49,769 cells after QC (E14.5 8,889). Wild type only. GEO GSE150817 (metadata and UMI tables). [bioRxiv](https://www.biorxiv.org/content/10.1101/2024.03.05.583423.full) (snippet; from the earlier session's notes; not re-verified)
- **Ren et al. 2023 (Sci Data 10:577; doi 10.1038/s41597-023-02333-6)**: 10x 3' v3 scRNA-seq of E8.5, E10.5, E12.5, E14.5, E16.5 and P3 wild type, two samples each. Exonic and intronic matrices (GEO GSE230531), FASTQ at SRA PRJNA890252. Intronic counts may approximate nuclei, not validated. [PMC10477280](https://pmc.ncbi.nlm.nih.gov/articles/PMC10477280) (snippet from earlier notes)
- **Li et al. 2016 (Dev Cell)**: C1 scRNA-seq of E8.5 (118 cells), E9.5 (949), E10.5 (1,166) hearts; ATLAS-seq. Accession GSE76118 / GSE89468 (FTP 404 in the earlier session). [PubMed 27840109](https://pubmed.ncbi.nlm.nih.gov/27840109/) (snippet)
- **DeLaughter et al. 2016 (Dev Cell)**: about 1,200 whole cells at E9.5 to P21 (stage lists differ between sources). E11.5 is RED. [Search summary](https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=DOI:10.1016/j.devcel.2016.10.001&resultType=core&format=json) (snippet; accession conflict with GSE150817 unresolved)
- **Hu et al. 2018 (Genes Dev 32:1344)**: single-nucleus RNA-seq of postnatal hearts (about 20,000 nuclei, Broad SCP283). Postnatal, not embryonic. A mitochondrial cardiomyopathy model is mentioned in an earlier snippet (genotype unverified). [Genes Dev](https://genesdev.cshlp.org/content/32/19-20/1344) (snippet)
- **Xiao et al. 2018 (Dev Cell, Lats1/2)**: mutant Drop-seq at E13.5 (RED) and E14.5 (mutant; AMBER). [Press summary](https://m.medicalxpress.com/news/2018-04-hippo-pathway-essential-orchestrate-heart.html) (snippet from earlier notes)
- **Cyp26b1 knockout scRNA (Sci Data 2025)**: hearts from E11.5 to E14.5 pooled. Window stages are RED; mutant. Search summary (snippet; link from the same search, match to the Sci Data paper not confirmed)
- **Nat Commun 2022 MULTI-seq embryonic and neonatal hearts (PMC9794824)**: the snippet names E18 and P1 hearts; stage list unverified. [PMC9794824](https://pmc.ncbi.nlm.nih.gov/articles/PMC9794824) (snippet; not opened)
- **Nat Commun 2023 (s41467-023-42658-9)**: scRNA and Stereo-seq at E8.5, E10.5, E12.5, E14.5, E16.5 and P3 (snippet; authors and accession unverified). [Nature](https://www.nature.com/articles/s41467-023-42658-9) (snippet)

### Inferences
- **Usable for T1 or heart, with disclosure**: Feulner 2024 (E14.5 to P7); Ren 2023 at E14.5, E16.5 and P3; GSE186069 and Qiu TS12/13 (E8.5 and early; T1 only for E8.5); MOCA at E9.5 exactly (a nuclei dataset, GREEN for E9.5 cells only).
- **RED**: any E10.5 to E13.5 cells from MOCA, Ren, Li, DeLaughter, Xiao, the Cyp26b1 set, Nat Commun 2023, and Qiu bins at E10 to E13.5.
- Feulner 2024 is the cleanest allowed late-stage heart scRNA set (no window stages, WT only), and it is whole-cell rather than nuclear.
- Human fetal-heart snRNA-seq (for example Cui 2019, Farah 2024) was not checked. Use only as gene-level priors, flagged as human.

### Gaps
- No nucleus-based embryonic heart dataset at E14.5 or later, or at E9.5 or earlier, besides the whole-embryo atlases, was found.
- MOCA heart subset at E9.5, stage counts, licence and file sizes are not verified.
- Feulner 2024 accession status (GEO release) is from the earlier session and not re-checked.

---

## Consolidated catalogue and compliance flags

| # | Resource | Citation / accession / URL | Content and size | Access | Flag | Notes |
|---|---|---|---|---|---|---|
| A1a | Nusse lab Wnt target table | [web.stanford.edu/~rnusse/pathways/targets.html](https://web.stanford.edu/~rnusse/pathways/targets.html) | About 115 rows, 2009, curated | HTML only | AMBER (up-direct rows); RED (down rows until checked) | Mixed provenance, including Wnt-3A embryos and loss-of-function sources |
| A1b | MSigDB mouse GO canonical-Wnt sets; GOCC_WNT_SIGNALOSOME; REACTOME repression | [gsea-msigdb mouse](https://www.gsea-msigdb.org/gsea/msigdb/mouse/geneset/GOBP_CANONICAL_WNT_SIGNALING_PATHWAY.html) | Annotation sets; 5 to 11 genes seen in partial lists | MSigDB download (registration) | GREEN (GO); AMBER (Reactome repression) | Some sets have special access terms; licence per set not checked |
| A1c | GSE43565, beta-catenin ChIP in WT mESC with CHIR99021 | [OmicsDI GSE43565](https://omicsdi.org/dataset/geo/GSE43565) | ChIP-seq, ES | GEO | AMBER | Pharmacological activation; ask organisers; ES not embryo |
| A1d | Ctnnb1 biotin-FLAG knock-in ChIP in mESC | [PMC3830733](https://pmc.ncbi.nlm.nih.gov/articles/PMC3830733) | ChIP-seq, ES | Accession not captured | RED (allele of Ctnnb1) unless ruled otherwise | |
| A1e | TCF7 / TCF7L1 3xFLAG knock-in ChIP in mESC | [bioRxiv 10.1101/473801](https://www.biorxiv.org/content/10.1101/473801v1.full.pdf) | ChIP-seq, ES | Accession not captured | AMBER | Knock-in TCF alleles; GSK3 arm |
| A1f | E-MTAB-10575 beta-catenin ChIP, WT and TCF/LEF quadruple KO mESC | [OmicsDI E-MTAB-10575](https://www.omicsdi.org/dataset/biostudies-arrayexpress/E-MTAB-10575) | ChIP-seq | ArrayExpress | WT arm AMBER; KO arm RED | KO arm phenocopies canonical Wnt loss |
| A1g | GSE97761 TCF7L2 occupancy after beta-catenin stabilisation, adult ventricle | [OmicsDI GSE97761](https://www.omicsdi.org/dataset/geo/GSE97761) | ChIP-seq, adult | GEO | RED | Stabilised Ctnnb1 is another allele |
| A1h | Isl1-lineage beta-catenin loss-of-function study (downstream Tbx2, Tbx3, Wnt11, Shh, Pitx2) | URL not captured | Expression | n/a | RED | Do not use; recorded only to flag the category |
| A2a | Akerberg 2019 cardiac TF bioChIP, E12.5 fetal ventricle | [GEO GSE124008](https://pmc.ncbi.nlm.nih.gov/articles/PMC6817842/) | ChIP-seq, 7 TFs, tagged het knock-ins | GEO | RED (E12.5) | Test stage for T1 and heart |
| A2b | Akerberg 2019, adult P42 ventricle | GEO GSE124008 | ChIP-seq, 6 TFs | GEO | AMBER | Post-window; Gata4 tagged allele; disclosure |
| A2c | 2016 eLife Nkx2-5, Tbx5, Gata4 ChIP, E12.5 hearts | snippet only | ChIP | not captured | RED | |
| A2d | PRJNA292836 TBX5, NKX2-5, GATA4 ChIP-exo in vitro WT and KO | [OmicsDI PRJNA292836](https://www.omicsdi.org/dataset/omics_ena_project/PRJNA292836) | ChIP-exo, CP and CM stages in vitro | ENA | AMBER | In vitro; KO arms of other genes |
| A2e | ENCODE E14.5 heart H3K27ac (ENCSR000CDK), H3K4me1 (ENCSR000CDL, ENCSR080GQM), H3K36me3 (ENCSR641EME) | [ENCSR000CDK](https://www.encodeproject.org/experiments/ENCSR000CDK/) | Histone ChIP, bulk | ENCODE portal | GREEN (E14.5, disclosure) | Region-level prior |
| A2f | CellOracle base GRN (10 species, mouse unconfirmed) | [CellOracle docs](https://morris-lab.github.io/CellOracle.documentation/tutorials/base_grn.html) | Motif-based GRN | Package data loader | AMBER | Check ATAC source stages; licence not stated |
| A2g | SCENIC / cisTarget mm10 motif databases | [resources.aertslab.org/cistarget](https://resources.aertslab.org/cistarget/) | Motif rankings; 1 to 100 GB each | Direct download | GREEN (motif-only) | No licence stated; co-expression regulons need GREEN inputs |
| A2h | Mouse tissue ATAC atlas CNP0000198 | [CNGB CNP0000198](https://db.cngb.org/cnsa/project/CNP0000198/public) | Accessibility, tissues | CNGB | AMBER | Check for embryonic stages in window; CC BY 4.0 (snippet) |
| A3a | MGI GXD expression database | [informatics.jax.org](https://www.informatics.jax.org/downloads/reports/index.shtml) | About 70,000 experiments (2015) | BioMart, reports | AMBER (filter required) | WT, E9.5 exact or E14.0+; drop mutants of Gata4 and Ctnnb1 |
| A3b | IMPC viability, lethality and E12.5 morphology | [mousephenotype.org](https://mousephenotype.org/embryo); [ftp.ebi.ac.uk/pub/databases/impc](https://ftp.ebi.ac.uk/pub/databases/impc) | Phenotypes, no expression | FTP, API | AMBER (lethality calls); RED (E10.5 to E13.5 timepoints) | Release and licence not verified |
| A3c | Eurexpress E14.5 whole-embryo ISH | [eurexpress.org](https://www.eurexpress.org/) | More than 18,000 genes, images | Search and BioMart 7.0; no bulk | GREEN (E14.5, disclosure) | Licence not stated; qualitative |
| A3d | DMDD / Expression Atlas whole-embryo RNA-seq (somites 4 to 36, excluding 29 to 33) | [EBI Expression Atlas](https://www.ebi.ac.uk/gxa) | Bulk RNA-seq | EBI | AMBER | Range reaches E9.5 to E10; per-sample staging |
| A3e | Mouse Gene Atlas (Hume) | not found | n/a | n/a | n/a | Gap |
| A4a | GSE287036 targeted CRISPR-Cas9 TF screen, mESC haemato-endothelial | [OmicsDI GSE287036](https://www.omicsdi.org/dataset/geo/GSE287036) | Screen, transcriptome readout (unconfirmed) | GEO | AMBER | ESC-derived; not embryonic stage |
| A4b | Human CRISPRi Perturb-seq, hPSC cardiomyocyte differentiation (PRJNA734618) | [OmicsDI PRJNA734618](https://www.omicsdi.org/dataset/project/PRJNA734618) | About 2.0 M cells, human | ENA | AMBER (human) | Gene-level priors only |
| A4c | BRD4 human iPSC CM screen | [aminer summary](https://www.aminer.org/pub/65d8f987939a5f40824eec1c/a-genome-wide-crispr-screen-identifies-brd-as-a-regulator-of-cardiomyocyte) | Screen, human | n/a | AMBER (human) | |
| B1a | Qiu 2024 time course, GEO GSE228590 | [GSE228590 suppl](https://ftp.ncbi.nlm.nih.gov/geo/series/GSE228nnn/GSE228590/suppl/) | Annotation about 74 MB; counts about 61 GB; per-cell day and embryo_id | curl or ftp | GREEN (E8.0 to E9.5 by per-embryo day; E14.0+ with disclosure); RED (E10 to E13.5 bins); AMBER (TS14 to TS16 boundary) | Do not download the MTX unless needed |
| B1b | Qiu 2024 via CELLxGENE Census 2025-11-08 (31 datasets) | [CELLxGENE Census](https://chanzuckerberg.github.io/cellxgene-census/) | 11,441,407 cells (raw whole dataset); TS12 to TS27 | Census API | As B1a | Do not sum across datasets; cardiomyocyte TS12/13 subset is splanchnic mesoderm |
| B1c | Qiu 2024 GEO GSE186069 (E8.5 nuclei) | [GSE186069 suppl](https://ftp.ncbi.nlm.nih.gov/geo/series/GSE186nnn/GSE186069/suppl/) | 239,533 barcodes; 31 labels; 4.5 MB annotation; 2.1 GB counts | curl | GREEN for T1; RED for heart (E8.5 held out) | Includes first and second heart field and splanchnic labels |
| B1d | Qiu 2024 portal | [omg.gs.washington.edu](https://omg.gs.washington.edu/jax/public/about.html) | Visual browser; download page unread | Web | Not checked | |
| B2 | Other Qiu-derived reanalysed public data (GSE44183, GSE100597, GSE109071, EmbryoTimecourse2018, MOSTA) | [PMC10901739](https://pmc.ncbi.nlm.nih.gov/articles/PMC10901739/) | Reanalysed | n/a | Check stages before use | Window rule applies |
| B3a | MOCA (Cao 2019), nuclei | GEO GSE119945; ENA PRJNA490754 | About 2 M nuclei, 61 embryos, E9.5 to E13.5 | GEO / ENA | GREEN (E9.5 exact only); RED (E10.5 to E13.5) | Heart subset and format unverified |
| B3b | Feulner 2024, whole-heart Drop-seq | GEO GSE150817 ([bioRxiv](https://www.biorxiv.org/content/10.1101/2024.03.05.583423.full)) | 49,769 cells, E14.5 to P7, WT | GEO | GREEN (E14.5+, disclosure) | Whole-cell, not nuclei |
| B3c | Ren 2023, whole-embryo and heart 10x scRNA | GEO GSE230531; SRA PRJNA890252 ([PMC10477280](https://pmc.ncbi.nlm.nih.gov/articles/PMC10477280)) | About 91,000 cells, E8.5 to P3, WT | GEO / SRA | E8.5 (T1 only); E10.5 and E12.5 RED; E14.5, E16.5, P3 GREEN | Exonic and intronic matrices |
| B3d | Li 2016, C1 scRNA of heart, E8.5 to E10.5 | GEO GSE76118 / GSE89468 | 2,233 cells | GEO (404 earlier) | E8.5 and E9.5 (T1 or GREEN); E10.5 RED | |
| B3e | DeLaughter 2016, E9.5 to P21 | Accession conflict (GSE150817 claimed) | About 1,200 cells | GEO | E9.5 GREEN; E11.5 RED | Accession unresolved |
| B3f | Goodyer 2019, conduction system scRNA | GEO GSE132658; EBI E-HCAD-16 | 25,957 cells | GEO | HOLD (stages unverified) | |
| B3g | Hu 2018, postnatal snRNA-seq | [Broad SCP283](https://singlecell.broadinstitute.org/single_cell/study/SCP283) | About 20,000 nuclei, postnatal | Broad | AMBER (post-E13.5, postnatal; exclude mutants) | Not embryonic |
| B3h | Xiao 2018, Lats1/2 mutant | press summary only | Drop-seq, E13.5 and E14.5 | not captured | RED (E13.5); AMBER (E14.5 mutant) | |
| B3i | Cyp26b1 KO scRNA, E11.5 to E14.5 (Sci Data 2025) | [PMC12241566](https://pmc.ncbi.nlm.nih.gov/articles/PMC12241566) | Pooled scRNA | not checked | RED (window); mutant | |
| B3j | Nat Commun 2022 MULTI-seq embryonic and neonatal hearts | [PMC9794824](https://pmc.ncbi.nlm.nih.gov/articles/PMC9794824) | E18, P1 per snippet | not checked | HOLD (stages unverified) | |
| B3k | Nat Commun 2023 scRNA and Stereo-seq, E8.5 to P3 | [Nature s41467-023-42658-9](https://www.nature.com/articles/s41467-023-42658-9) | Mixed | not checked | RED for E10.5 and E12.5; GREEN for others (disclosure) | Accession unverified |

---

## Questions for the organisers (before using AMBER or HOLD items)
1. Does the data-page sentence "Task 1 is the only task where training on external public single-cell data is allowed" override rules section 10 for Tasks 2 and 3? This governs Qiu and MOCA for heart and T3.
2. Are gene-level priors (GO sets, motif-based GRNs, ChIP-derived peak sets, bulk histone ChIP) "external data" that need the window rule, or only single-cell data?
3. Is a WT beta-catenin ChIP from CHIR99021-treated ES cells a "phenocopy" or a Ctnnb1 "other allele"?
4. Is a heterozygous knock-in tagged allele of Gata4 or Ctnnb1 at an adult stage (for example Akerberg P42) an "other allele at a comparable stage"?
5. Are Qiu TS14 to TS16 embryos acceptable when their per-embryo day (GEO `day`) is at or before E9.5?

## Next steps
1. Filter GSE228590 `day` and `embryo_id` to build a per-embryo list of embryos at or before E9.5, and check whether the team's TS12 and TS13 calibration rows match it.
2. Correct the TS12/13 "cardiomyocytes" subset label. In Census it is splanchnic mesoderm, so it should not be treated as cardiomyocyte calibration without a check.
3. Read the MOCA E9.5 heart subset and the Feulner 2024 GEO release status.
4. Record which Nusse-table rows are up-direction direct targets, and decide whether to use the GO canonical-Wnt annotation sets instead.
5. Ask the organisers the five questions above.
