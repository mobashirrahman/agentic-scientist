# Late-stage (E14.5+) mouse developing-heart single-cell / single-nucleus RNA-seq anchors

Research status, read first: about 26 tool calls were used. Several sites were blocked in this session: NCBI GEO web pages (reCAPTCHA), PubMed Central (bot check), Nature (cookie redirect loop), and Europe PMC full-text XML (HTTP 500). GEO existence was checked only through the GEO FTP index (HTTP status and file names). No data files were downloaded, so file sizes and licences are unverified. Anything not checked is listed under Gaps.

Competition window used here: external data from E10.5 to E13.5 inclusive is forbidden. E9.5 and E14.5 or later are allowed. E8.5 is before the window.

## KQ1: Which datasets exist?

### Takeaway
Few mouse developing-heart single-cell or single-nucleus datasets clearly reach E14.5 or later. The strongest verified late-stage candidates are Feulner et al. 2024 (bioRxiv, Drop-seq scRNA, E14.5 to P7, GEO files present) and Ren et al. 2023 (Sci Data, 10x scRNA, E8.5 to P3, GEO GSE230531). Goodyer et al. 2019 (Circ Res, conduction system, GEO GSE132658) is a candidate whose stages are still unverified. Qiu et al. 2024 (Nature, sci-RNA-seq3 single-nucleus atlas, E8 to birth) is the only single-nucleus embryonic atlas with late stages found, but its accession and heart subset are unverified. Hu et al. 2018 (Genes Dev) is a single-nucleus atlas of postnatal hearts, not embryonic hearts.

### Cited Findings
- Feulner et al. 2024 (bioRxiv, v2): scRNA-seq (Drop-seq) of whole hearts at E14.5, E16.5, E18.5, P0, P4 and P7; 49,769 cells after QC — [bioRxiv](https://www.biorxiv.org/content/10.1101/2024.03.05.583423.full)
- Ren et al. 2023 (Sci Data 10:577): 10x 3' v3 scRNA-seq of E8.5, E10.5, E12.5, E14.5, E16.5 and P3, wild type only — [PMC10477280](https://pmc.ncbi.nlm.nih.gov/articles/PMC10477280); DOI 10.1038/s41597-023-02333-6
- Goodyer et al. 2019 (Circ Res 125(4):379-397): conduction-system scRNA-seq, 25,957 cells in the Expression Atlas record — [EBI GXA E-HCAD-16](https://www.ebi.ac.uk/gxa/sc/experiments/E-HCAD-16); [PMC6675655](https://pmc.ncbi.nlm.nih.gov/articles/PMC6675655) (search snippet only, page blocked)
- Qiu et al. 2024 (Nature 626(8001):1084-93; DOI 10.1038/s41586-024-07069-w): sci-RNA-seq3 single-nucleus time-lapse, 12.4 million nuclei from 83 embryos, E8 to birth — [paper PDF](https://shendure-web.gs.washington.edu/documents/qiu_nature_february2024.pdf) (search snippet; PDF redirected and not read)
- Hu et al. 2018 (Genes Dev 32:1344): "Single-nucleus transcriptomic survey of cell diversity and functional maturation in postnatal mammalian hearts" — [Genes Dev](https://genesdev.cshlp.org/content/32/19-20/1344); Broad SCP283 — [SCP283](https://singlecell.broadinstitute.org/single_cell/study/SCP283)
- Xiao et al. 2018 (Dev Cell 45(2):153-169.e6; Lats1/2 mutant, Drop-seq at E13.5 and E14.5): [press summary](https://m.medicalxpress.com/news/2018-04-hippo-pathway-essential-orchestrate-heart.html); DOI 10.1016/j.devcel.2018.03.019 as given in the search snippet, not opened
- DeLaughter et al. 2016 (Dev Cell 39(4):480-490; DOI 10.1016/j.devcel.2016.10.001; PMID 27840107; PMC5198784): about 1,200 cells across E9.5 to P21 — [Europe PMC record](https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=DOI:10.1016/j.devcel.2016.10.001&resultType=core&format=json); [DOI](https://doi.org/10.1016/j.devcel.2016.10.001)
- Li et al. 2016 (Dev Cell 39(4):491-507; PMID 27840109; PMC5130110): single-cell RNA-seq of E8.5 (118 cells), E9.5 (949) and E10.5 (1,166) hearts — [PubMed](https://pubmed.ncbi.nlm.nih.gov/27840109/); SuperSeries GSE89468, subseries GSE76118 (RNA) and GSE89465 (qPCR) per OmicsDI/Pluto mirrors
- Xiong et al. 2019 (Circ Res 125(4):398-410), "Single-Cell Transcriptomics Reveals Chemotaxis-Mediated Intraorgan Crosstalk During Cardiogenesis": a GEO entry dated June 2019 exists, accession not identified in the snippet — [PMC6697751 link from search](https://pmc.ncbi.nlm.nih.gov/articles/PMC6697751) (unverified that this is the Xiong paper)
- Nature Communications 2023 (DOI 10.1038/s41467-023-42658-9): scRNA-seq plus Stereo-seq across E8.5, E10.5, E12.5, E14.5, E16.5 and P3, with Wei Feng named — [Nature](https://www.nature.com/articles/s41467-023-42658-9) (not opened); [SciencePOD summary](https://magazine.sciencepod.net/?p=505277). This is the closest match found for the requested "Feng W. 2022".
- MULTI-seq study of embryonic and neonatal hearts, Nature Communications 2022: the snippet names E18 and P1 hearts — [PMC9794824](https://pmc.ncbi.nlm.nih.gov/articles/PMC9794824) (snippet only, not opened)

### Inferences
- The embryonic heart datasets with late stages that were found are scRNA-seq. The single-nucleus embryonic dataset with late stages is Qiu et al. 2024, and its heart subset is unverified.
- The brief's attributions need correcting; see KQ5.

### Gaps
- Cui et al. 2019, Farah et al. 2024, de Soysa et al. 2019, Tyser et al. 2021, Jia et al. 2018, Su et al. 2018, Liu et al. 2019, Hulin et al. 2019, MOCA (Cao et al. 2019), Tabula Muris Senis and CELLxGENE collections were not searched. Any statements about them are from memory and unverified: Cui 2019 and Farah 2024 are human; MOCA is E9.5 to E13.5, which would be forbidden; Tyser 2021 and de Soysa 2019 are early-stage mouse data.
- No single-nucleus fetal or embryonic mouse heart dataset at E14.5 to E16.5 was found other than Qiu 2024. The search returned no match.

## KQ2: Practical details per dataset

### Takeaway
Ren et al. 2023 and Feulner et al. 2024 are the best-documented late-stage datasets. Both are wild type, scRNA-seq, and contain E14.5 and E16.5 with per-stage cell counts. Feulner's GEO folder has processed UMI matrices and cell metadata. Ren's GEO folder has raw tar and matrices. Goodyer 2019 and Qiu 2024 need their accessions and stage lists confirmed before use. DeLaughter 2016 has too few cells for an anchor.

### Cited Findings

**A. Feulner et al. 2024 (bioRxiv), "Transcriptional dynamics of the murine heart during perinatal development at single-cell resolution"**
- Authors: Lara Feulner (first), Gregor Andelfinger (last, corresponding). DOI 10.1101/2024.03.05.583423 (v2). Peer-reviewed publication not confirmed — [bioRxiv](https://www.biorxiv.org/content/10.1101/2024.03.05.583423.full)
- Stages and cells after QC: E14.5 8,889; E16.5 8,396; E18.5 6,058; P0 9,213; P4 8,922; P7 8,291; total 49,769; six biological replicates per stage, 36 samples — [bioRxiv](https://www.biorxiv.org/content/10.1101/2024.03.05.583423.full)
- Assay: Drop-seq on dissociated whole hearts. This is scRNA-seq, not snRNA-seq — [bioRxiv](https://www.biorxiv.org/content/10.1101/2024.03.05.583423.full)
- Genotype: wild type C57Bl/6NJ only; no mutants or perturbations. The E14.5 data include six wild-type replicates reused from GSE109247 (identity of GSE109247 not verified) — [bioRxiv](https://www.biorxiv.org/content/10.1101/2024.03.05.583423.full)
- Labels: manual marker-based annotation in Table S2 (supplement not seen). Categories include atrial, ventricular, trabecular and conduction-system cardiomyocytes, fibroblasts, smooth muscle, pericytes, valve interstitial cells, epicardial cells, endothelial subtypes, immune cells, Schwann and neuronal cells — [bioRxiv](https://www.biorxiv.org/content/10.1101/2024.03.05.583423.full)
- Accession: text says data "are to be available from NCBI Geo (GSE150817)". The GEO FTP folder GSE150817 exists (HTTP 200). Its suppl folder lists `GSE150817_perinatheart.metadata.final_cells.tsv.gz` and `GSE150817_perinatheart.raw_umi_counts.final_cells.tsv.gz`. Release status and file sizes are not verified — [GEO FTP suppl](https://ftp.ncbi.nlm.nih.gov/geo/series/GSE150nnn/GSE150817/suppl/); the GEO web page was blocked.
- Planned CELLxGENE Discover upload and GitHub code release are stated as "in future" — [bioRxiv](https://www.biorxiv.org/content/10.1101/2024.03.05.583423.full)

**B. Ren et al. 2023, "Single-cell RNA sequencing of murine hearts for studying the development of the cardiac conduction system", Sci Data 10:577**
- Authors: Huiying Ren, Xiaolin Zhou, ..., Xianhong Ou (corresponding). Published 4 September 2023. DOI 10.1038/s41597-023-02333-6; PMID 37666871 — [PMC10477280](https://pmc.ncbi.nlm.nih.gov/articles/PMC10477280)
- Stages: E8.5, E10.5, E12.5, E14.5, E16.5, P3. Two samples per stage. Cell Ranger counts from Table 1: E8.5 5,643 and 5,380; E10.5 14,906 and 14,703; E12.5 5,674 and 7,212; E14.5 6,529 and 6,286; E16.5 7,259 and 7,720; P3 4,400 and 5,469. These sum to about 91,000 cells. The paper also says "~0.5 million" cells in one place, which conflicts with Table 1 — [PMC10477280](https://pmc.ncbi.nlm.nih.gov/articles/PMC10477280)
- Assay: 10x Chromium 3' v3, Illumina NovaSeq 6000. scRNA-seq from enzymatically dissociated cells, not nuclei — [PMC10477280](https://pmc.ncbi.nlm.nih.gov/articles/PMC10477280)
- Dissection: E8.5 and E10.5 whole embryos; E12.5, E14.5 and E16.5 hearts removed; P3 hearts from the aortic root. No chamber or reporter sorting — [PMC10477280](https://pmc.ncbi.nlm.nih.gov/articles/PMC10477280)
- Genotype: wild-type C57BL/6J only. No Gata4 or Ctnnb1 alleles — [PMC10477280](https://pmc.ncbi.nlm.nih.gov/articles/PMC10477280)
- Labels: clusters annotated by marker genes (Table 5), with some manual assignment. Abstract reports 20 to 26 cell types across stages, 10 of which contribute to the conduction system. No deposited annotation file is mentioned — [PMC10477280](https://pmc.ncbi.nlm.nih.gov/articles/PMC10477280)
- Files: 148 raw FASTQ files at SRA PRJNA890252. GEO GSE230531 contains exonic and intronic matrices (format not specified). The GEO FTP folder exists and lists `GSE230531_RAW.tar` and `filelist.txt` — [GEO FTP](https://ftp.ncbi.nlm.nih.gov/geo/series/GSE230nnn/GSE230531/suppl/); [PMC10477280](https://pmc.ncbi.nlm.nih.gov/articles/PMC10477280)
- Note: the Data Availability statement lists software only. Accessions are in the Data Records section — [PMC10477280](https://pmc.ncbi.nlm.nih.gov/articles/PMC10477280)

**C. Goodyer et al. 2019, "Transcriptomic Profiling of the Developing Cardiac Conduction System at Single-Cell Resolution", Circ Res 125(4):379-397**
- Venue correction: this is Circulation Research, not Developmental Cell as in the brief. Europe PMC ID MED/31284824; PMC6675655 — [EBI GXA](https://www.ebi.ac.uk/gxa/sc/experiments/E-HCAD-16); [PMC6675655](https://pmc.ncbi.nlm.nih.gov/articles/PMC6675655) (search snippet; page blocked)
- Cells: 25,957 in the Expression Atlas record, Mus musculus, data type "Single-cell RNA-Seq mRNA baseline". The search snippet says ">22,000" cells. The discrepancy is unresolved — [EBI GXA](https://www.ebi.ac.uk/gxa/sc/experiments/E-HCAD-16)
- Stages: not shown on the Expression Atlas page. The search snippet did not confirm E16.5. Stages are unverified.
- Protocol: not specified on the Expression Atlas page. The search snippet says the scRNA-seq raw data are in GEO GSE132658. The GEO FTP folder exists and lists `GSE132658_RAW.tar` and `filelist.txt` — [GEO FTP](https://ftp.ncbi.nlm.nih.gov/geo/series/GSE132nnn/GSE132658/suppl/)
- Genotype: not verified; the page was blocked.

**D. Qiu et al. 2024 (Nature), "A single-cell time-lapse of mouse prenatal development from gastrula to birth"**
- Authors include Chengxiang Qiu and Jay Shendure (University of Washington). DOI 10.1038/s41586-024-07069-w. Nature 626(8001):1084-93. Published 14 February 2024 — [DOI](https://doi.org/10.1038/s41586-024-07069-w); [press/PDF](https://shendure-web.gs.washington.edu/documents/qiu_nature_february2024.pdf)
- Naming: the brief calls this the "JAX whole-embryo atlas". The search results list a Shendure lab (UW) paper with no JAX affiliation. Please check which dataset the TS23 subset in use actually comes from.
- Scope: 12.4 million nuclei from 83 embryos, E8 (late gastrulation) to birth (P0) — [PDF](https://shendure-web.gs.washington.edu/documents/qiu_nature_february2024.pdf)
- Assay: sci-RNA-seq3, single-nucleus combinatorial indexing. This is the only snRNA embryonic atlas with late stages found — [PDF](https://shendure-web.gs.washington.edu/documents/qiu_nature_february2024.pdf)
- Accession: not found. The PDF redirected to shendurelab.github.io and was not read. The Data Availability section is unverified.
- Heart subset counts at E14.5 to E16.5: unverified.

**E. Hu et al. 2018 (Genes Dev), "Single-nucleus transcriptomic survey of cell diversity and functional maturation in postnatal mammalian hearts"**
- Postnatal, not embryonic. First author Peng Hu, with Liming Pei (per snippet). Model: a pediatric mitochondrial cardiomyopathy model (per snippet, genotype unverified) — [Genes Dev](https://genesdev.cshlp.org/content/32/19-20/1344)
- Single-nucleus RNA-seq. Broad SCP283 — [SCP283](https://singlecell.broadinstitute.org/single_cell/study/SCP283)
- Exact postnatal ages: unverified.

**F. Xiao et al. 2018 (Dev Cell), Hippo / Lats1-Lats2 study**
- Drop-seq of E13.5 and E14.5 control and Lats1/2-deficient hearts (per press summary). E13.5 is forbidden. E14.5 is allowed but mutant. Accession not found. Source: [press summary](https://m.medicalxpress.com/news/2018-04-hippo-pathway-essential-orchestrate-heart.html)

**G. DeLaughter et al. 2016 (Dev Cell)**
- Authors (Europe PMC): DeLaughter DM, Bick AG, Wakimoto H, McKean D, Gorham JM, Kathiriya IS, Hinson JT, Homsy J, Gray J, Pu W, Bruneau BG, Seidman JG, Seidman CE — [Europe PMC](https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=DOI:10.1016/j.devcel.2016.10.001&resultType=core&format=json)
- About 1,200 cells (search summary). The stage list conflicts across sources. One summary lists seven stages, E9.5 to P21: E9.5, E11.5, E14.5, P0, P3, P7, P21. Another summary cites five stages: E9.5, E11.5, E14.5, P0, P21. Neither was verified in the paper. Platform (C1 versus 10x) unverified.
- Accession: Europe PMC says a GEO accession exists but does not list it. OmicsDI lists GSE150817 under "DeLaughter DM" (OmicsDI page not opened). This conflicts with GSE150817 being the Feulner deposit. Unresolved.

**H. Li et al. 2016 (Dev Cell)**
- E8.5 (118 cells), E9.5 (949), E10.5 (1,166). Only E8.5 and E9.5 are usable. E10.5 is forbidden. Mutant cells (Nkx2-5-deficient cardiomyocytes) are included, per the abstract — [PubMed](https://pubmed.ncbi.nlm.nih.gov/27840109/)
- Accession: SuperSeries GSE89468 (RNA GSE76118, qPCR GSE89465), per OmicsDI and Pluto mirrors. GEO FTP folders for GSE76118 and GSE89468 returned HTTP 404 in this session. This conflicts with the mirror data and is unresolved.

**I. Nature Communications 2023 (s41467-023-42658-9)**
- Stages per snippet: E8.5, E10.5, E12.5, E14.5, E16.5, P3. Stereo-seq plus scRNA-seq. Not opened; authors, counts and accession unverified — [Nature](https://www.nature.com/articles/s41467-023-42658-9)

### Inferences
- For a practical scRNA late anchor, Feulner 2024 has the cleanest allowed-stage set (no forbidden stages) and post-QC counts. Ren 2023 has more raw Cell Ranger cells at E14.5 and E16.5, but these are pre-QC and include forbidden stages in the same deposit. Counts are not directly comparable. Ren 2023 provides separate exonic and intronic matrices, which may allow nuclear-like counting. Neither has been checked beyond the text.
- Qiu 2024 is the best snRNA match for T1 if its E14.5 to E16.5 heart subset is accessible. Its accession must be found first.

### Gaps
- DeLaughter 2016 accession and platform not verified. The GSE75478 guess from memory returned HTTP 404 and is dropped.
- Goodyer 2019 stages, cell counts per stage and protocol are not verified. The GEO folder exists but was not opened.
- Qiu 2024 accession, heart subset and count are not found.
- Xiong 2019 GEO accession not identified.
- Ren 2023 and Goodyer 2019 file sizes and licences not checked.
- Feulner 2024 GEO release status and file sizes not checked.

## KQ3: Single-nucleus versus single-cell

### Takeaway
Only two datasets found are single-nucleus: Qiu et al. 2024 (embryonic, E8 to birth, sci-RNA-seq3) and Hu et al. 2018 (postnatal, snRNA-seq). All late embryonic heart datasets found are single-cell (Drop-seq or 10x). Single-cell data differ from single-nucleus in cytoplasmic and intronic content.

### Cited Findings
- Qiu 2024 uses sci-RNA-seq3 on nuclei — [PDF](https://shendure-web.gs.washington.edu/documents/qiu_nature_february2024.pdf)
- Hu 2018 is single-nucleus, postnatal — [Genes Dev](https://genesdev.cshlp.org/content/32/19-20/1344)
- Feulner 2024 is Drop-seq on dissociated cells — [bioRxiv](https://www.biorxiv.org/content/10.1101/2024.03.05.583423.full)
- Ren 2023 is 10x 3' v3 on dissociated cells and provides intronic and exonic matrices — [PMC10477280](https://pmc.ncbi.nlm.nih.gov/articles/PMC10477280)

### Inferences
- Ren's intronic matrix may approximate nuclear counting, but this has not been validated against snRNA.

### Gaps
- No embryonic snRNA-seq dataset at E14.5 to E16.5 was found, other than the unverified Qiu subset.

## KQ4: Most cells at E14.5 to E16.5, and allowed-stage usability

### Takeaway
Ren 2023 and Feulner 2024 have the most verified cells at E14.5 and E16.5. Qiu 2024 likely has the most cells overall, but the heart subset is unverified. E14.5 is the earliest allowed late stage, and E9.5 is the only other allowed stage found in the early datasets.

### Cited Findings
- Feulner 2024 (after QC): E14.5 8,889; E16.5 8,396 — [bioRxiv](https://www.biorxiv.org/content/10.1101/2024.03.05.583423.full)
- Ren 2023 (Cell Ranger counts, two samples each): E14.5 6,529 and 6,286 (12,815 total); E16.5 7,259 and 7,720 (14,979 total); P3 9,869 total — [PMC10477280](https://pmc.ncbi.nlm.nih.gov/articles/PMC10477280)
- Goodyer 2019: 25,957 cells total, stage distribution unknown — [EBI GXA](https://www.ebi.ac.uk/gxa/sc/experiments/E-HCAD-16)
- Qiu 2024: 12.4 million nuclei across 83 embryos, E8 to P0. Heart subset unknown — [PDF](https://shendure-web.gs.washington.edu/documents/qiu_nature_february2024.pdf) (search snippet)
- DeLaughter 2016: about 1,200 cells across all stages — search summary only
- Li 2016: E9.5 949 cells (allowed); E10.5 1,166 (forbidden) — [PubMed](https://pubmed.ncbi.nlm.nih.gov/27840109/)
- Xiao 2018: E14.5 allowed (mutant); E13.5 forbidden. Cell counts not verified — [press summary](https://m.medicalxpress.com/news/2018-04-hippo-pathway-essential-orchestrate-heart.html)

### Inferences
- Among verified datasets, Ren 2023 (pre-QC, about 27,800 cells at E14.5 and E16.5 combined) and Feulner 2024 (post-QC, about 17,300) are the most cell-rich at these stages. Goodyer 2019 could be larger at E14.5 to E16.5 if most of its 25,957 cells come from those stages, but this is unverified.

### Gaps
- Stage distribution in Goodyer 2019 and heart-subset counts in Qiu 2024 are unverified.

## KQ5: Corrections to the brief and compliance flags

### Takeaway
Several attributions in the brief are wrong or unverified. Forbidden-window stages are present in most candidate datasets, so subsetting is required. No Gata4 or Ctnnb1 alleles were found in the datasets checked, but several are not fully checked.

### Cited Findings

**Corrections**
- Hu P. et al. 2018 (Genes Dev) is a postnatal single-nucleus survey, not an embryonic Hippo study. The embryonic Hippo study is Xiao et al. 2018 (Dev Cell), a Lats1/2 mutant at E13.5 and E14.5 — [Genes Dev](https://genesdev.cshlp.org/content/32/19-20/1344); [press summary](https://m.medicalxpress.com/news/2018-04-hippo-pathway-essential-orchestrate-heart.html)
- Goodyer et al. 2019 is in Circulation Research, not Developmental Cell — [PMC6675655](https://pmc.ncbi.nlm.nih.gov/articles/PMC6675655)
- Li G. et al. was published in 2016 (Dev Cell), not 2019, and covers E8.5 to E10.5 only — [PubMed](https://pubmed.ncbi.nlm.nih.gov/27840109/)
- Ren et al. 2023 appeared as a search hit for "Goodyer" but is a separate paper — [PMC10477280](https://pmc.ncbi.nlm.nih.gov/articles/PMC10477280)
- "Feng W. et al. 2022": no match found. The closest is the 2023 Nature Communications paper in KQ1 (Wei Feng named per SciencePOD) — [SciencePOD](https://magazine.sciencepod.net/?p=505277)
- Qiu et al. 2024 is by Shendure lab (UW) per author list; no JAX affiliation found — [PDF](https://shendure-web.gs.washington.edu/documents/qiu_nature_february2024.pdf)

**Theiler TS23 mapping (affects the already-used Qiu subset)**
- TS23 is listed at 15 days post coitum (dpc) in eMouseAtlas — [eMouseAtlas](https://emouseatlas.org/emap/ema/theiler_stages/StageDefinition/stagedefinition.html)
- TS22 is listed at 13.5 to 15 dpc in a Theiler chart from search, and TS22 maps to 13.5 to 14 dpc in an Anderson 2016 table. Theiler stages are not one-to-one with days — [Mouse Timeline](https://embryology.med.unsw.edu.au/embryology/index.php/Mouse_Timeline_Detailed)
- Implication: a TS23 subset could be E14.5 to E15.5, which is allowed. Any TS22 samples or day-labelled E13.5 samples are forbidden. Per-sample ages should be checked in the metadata.

**Forbidden-window (E10.5 to E13.5) stages present**
- Ren 2023: E10.5 and E12.5 forbidden. E8.5 before window. E14.5, E16.5 and P3 allowed.
- Feulner 2024: none forbidden (E14.5 to P7).
- DeLaughter 2016: E11.5 forbidden (per both stage-list versions). E9.5, E14.5 and postnatal allowed.
- Li 2016: E10.5 forbidden.
- Xiao 2018: E13.5 forbidden.
- Nature Communications 2023: E10.5 and E12.5 forbidden (per snippet).
- Qiu 2024: E10.5 to E13.5 forbidden. Subsetting required.
- Goodyer 2019: unverified.

**Gata4 / Ctnnb1 and other mutants**
- Gata4 or Ctnnb1 alleles: none found in Ren 2023 (wild type only) or Feulner 2024 (wild type only). Not checked in Goodyer 2019, Qiu 2024, DeLaughter 2016 or Xiong 2019 (full text blocked or not opened).
- Other genetic mutants found, not on the forbidden list but to be flagged: Xiao 2018 (Lats1/2 deficiency); Li 2016 (Nkx2-5-deficient cardiomyocytes); Hu 2018 (mitochondrial cardiomyopathy model, per snippet); GSE125321 (Sox17-null endocardium, E8.5; a separate study, not Xiong).

### Inferences
- The TS23 subset may already be compliant if it is E14.5 to E15.5 only. This needs confirmation before any further use.

### Gaps
- The Gata4 and Ctnnb1 check is incomplete for Goodyer 2019, Qiu 2024 and DeLaughter 2016.
- Per-sample ages for the Qiu TS23 subset are unverified.
