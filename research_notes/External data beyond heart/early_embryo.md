# Early mouse embryo (E6.5-E8.5) external data for T2-embryo

Status as of 2026-11-17. Search-based survey (16 tool calls). Verified items cite the page they came from. Items marked "not verified" were not confirmed in this session and must not be used for a compliance decision until checked. The verdicts in Key Question 4 are my reading of the rules. The organisers should confirm the inferred windows and the open questions listed there.

## Key Question 1: Single-cell atlases that refine cell states and timing

### Takeaway
The best-documented WT atlas for E6.5-E8.5 is Pijuan-Sala et al. 2019 (116,312 cells, nine timepoints from 6.5 to 8.5 dpc). It is usable only at its allowed timepoints, because it also contains E7.5 and E7.75. Imaz-Rosshandler et al. 2024 extends it to E9.5 and is the best candidate for E8.25-E9.5 cell-state timing. Mittnenzweig et al. 2021 is a single-embryo time series, but its time bins are only usable outside E7.5 and E7.75. Grosswendt et al. 2020 contains perturbation embryos that must be excluded.

### Cited Findings

**Pijuan-Sala et al. 2019, Nature 566:490-495 (PMID 30787436)**
- 116,312 single cells from nine sequential timepoints from 6.5 to 8.5 dpc; new captures cover TS9-TS12 (pre-streak/early streak, mid/late streak, neural plate, headfold/somitogenesis) — [ORA record](https://ora.ox.ac.uk/objects/uuid:34622b55-8d4f-4c75-9d5a-6223115fe096); PDF copy: [Babraham PDF](https://www.babraham.ac.uk/sites/default/files/media/files/30787436.pdf). The nine-timepoint stage labels (E6.5 to E8.5 in 0.25-day steps) are inferred from the brief, not read from the paper.
- Data statement per the paper (as quoted in search output): atlas raw reads E-MTAB-6967; Smart-seq2 endothelial cells E-MTAB-6970; Tal1-/- chimeras E-MTAB-7325; WT chimeras E-MTAB-7324 — [ORA record](https://ora.ox.ac.uk/objects/uuid:34622b55-8d4f-4c75-9d5a-6223115fe096).
- The user-supplied accession E-MTAB-7601 does not appear in that data statement. The BioStudies page did not load in WebFetch, so the accession is unresolved.
- Assay: scRNA-seq. No spatial coordinates. Cell-type labels are provided. Platform, cell-type count, file sizes and licence: not verified.

**Imaz-Rosshandler et al. 2024, Development 151(3) ("Tracking early mammalian organogenesis - prediction and validation of differentiation trajectories at whole organism scale")**
- About 300,000 scRNA-seq transcriptomes from E8.5-E9.5 embryos, sampled every 6 h; combined with the earlier E6.5-E8.5 data, an extended atlas of 430,339 cells across 13 timepoints over E6.5-E9.5 — [IMM record](https://www.imm.ox.ac.uk/publications/publication_modal/1573513); extended atlas resource: [Marioni lab ExtendedMouseAtlas](https://marionilab.github.io/ExtendedMouseAtlas).
- Grafting data (primitive streak grafts, scRNA-seq after 24 h culture): ArrayExpress E-MTAB-13645 — [OmicsDI](https://www.omicsdi.org/dataset/biostudies-arrayexpress/E-MTAB-13645).
- Interactive Shiny app and UCSC Cell Browser listed, with the project page described as still under development — [IMM record](https://www.imm.ox.ac.uk/publications/publication_modal/1573513).
- Not verified: an explicit E9.25 timepoint (the 6-hour spacing implies one by arithmetic only); the exact 13 timepoint values; the accession for the E6.5-E8.5 part.

**Mittnenzweig et al. 2021, Cell 184(11):2825-2842 (DOI 10.1016/j.cell.2021.04.004)**
- 153 individually sampled embryos; stages E6.5-E8.25, grouped into 13 temporal bins labelled E_t6.5 to E_t8.1; 3-36 embryos and 884-6,442 cells per bin; MARS-seq — [PMC8162424](https://pmc.ncbi.nlm.nih.gov/articles/PMC8162424/).
- Accession GEO GSE169210; code github.com/tanaylab/embflow with Zenodo DOI 10.5281/zenodo.4646177 — [PMC8162424](https://pmc.ncbi.nlm.nih.gov/articles/PMC8162424/).
- Cell count conflict inside the paper: Results say 33,700 cells; Methods say 33,900 — [PMC8162424](https://pmc.ncbi.nlm.nih.gov/articles/PMC8162424/).
- Perturbation content: Foxc1/Foxc2 double-knockout chimeras (2N, seven DKO plus four control injected chimeras; 4N tetraploid-complemented embryos dissected at E8) — [PMC8162424](https://pmc.ncbi.nlm.nih.gov/articles/PMC8162424/).
- Labels come from the Pijuan-Sala reference atlas (used for comparison) — [PMC8162424](https://pmc.ncbi.nlm.nih.gov/articles/PMC8162424/).

**Grosswendt et al. 2020, Nature 584:102-108 (DOI 10.1038/s41586-020-2552-x)**
- Zygotic CRISPR-Cas9 knockouts of ten chromatin regulators (including PRC1/PRC2 components), scRNA-seq of mutant embryos, and a wild-type reference of 88,779 single-cell transcriptomes separated by timepoint — [PMC7415732](https://pmc.ncbi.nlm.nih.gov/articles/PMC7415732).
- EED and RNF2 mutants gastrulate but largely stall around E7.5; PRC2 mutants are smaller and egg-shaped by about E8.5 — [PMC7415732](https://pmc.ncbi.nlm.nih.gov/articles/PMC7415732) (search-snippet level; full text not read).
- Not verified: the exact list of ten genes (to check for any Wnt-pathway or Ctnnb1/Gata4 member), the stage list of the WT reference, the accession.

**Qiu et al. 2024, Nature (Shendure lab; TOME resource)**
- Per search output: 12.4 million nuclei from 83 embryos staged at 2-6 h intervals, covering gastrulation to birth — [Shendure lab PDF](https://shendure-web.gs.washington.edu/documents/qiu_nature_february2024.pdf); portal [TOME](https://tome.gs.washington.edu/).
- This is a dense time series that is not in the user's list. Its identity relative to the "Qiu 2024 AnchorFlow" reference in the project memory is not verified.

**Argelaguet et al. 2019, Nature 576:487-491 (DOI 10.1038/s41586-019-1825-8)**
- scNMT-seq multi-omics on 1,105 single cells from four developmental stages, with MOFA applied to E7.5 cells — [Babraham PDF](https://babraham.ac.uk/sites/default/files/2020-09/31827285.pdf).
- GEO GSE121708 SuperSeries — [OmicsDI](https://www.omicsdi.org/dataset/geo/GSE121708). The link from this record to the paper was inferred, not confirmed.
- Stage list beyond the stated E7.5 endpoint not verified (user says E4.5-E7.5).

**Sladitschek et al. 2020, "MorphoSeq" (Cell)**
- This paper is about the ascidian *Phallusia mammillata*, not mouse — [PMC7237864](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC7237864/). Excluded under the mouse-only rule.

### Inferences
- For cell-state refinement at E7.25 and E8.0-E8.5, Pijuan-Sala (allowed timepoints only) and Imaz-Rosshandler (E8.25-E9.5 part) are the main atlas candidates. Both share the same group and likely overlap; deduplicate before use. The overlap is inferred from the description of the extended atlas as "earlier E6.5-E8.5 data plus new E8.5-E9.5".
- Mittnenzweig's single-embryo design is useful for timing, but its bin structure forces removal of the E7.5 and E7.75 bins.

### Gaps
- Scialdone 2016, Ibarra-Soria 2018 (E8.25 per user), Chan 2019, and Tyser 2021 (user-listed) were not searched in this session. Chan 2019 is, from memory, a blastocyst paper and so likely out of stage window. Tyser's user-stated E7.5-E8.25 span includes held-out cells. Not verified; the heart scope covers Tyser.
- Dominguez-Ojalvo: no match found. The McDole 2018 light-sheet paper (KQ3) is probably the intended reference.
- No 2025-2026 single-cell atlas of E6.5-E8.5 was found. Recency coverage is weak.

## Key Question 2: Spatial datasets (seqFISH, Stereo-seq, Slide-seq, MERFISH, Geo-seq)

### Takeaway
Three spatial sets are directly usable with the stage rules: Lohoff et al. 2022 seqFISH (E8.5-E8.75 sections), Harland et al. 2025 spatial transcriptomics (E7.25 usable, E7.5 forbidden), and Peng et al. 2019 Geo-seq (E5.5-E7.25 usable, E7.5 forbidden). All are 2D sections, not 3D. A 351-gene sequential-FISH panel (Harland) is the closest match to the 500-gene MERFISH panel of the challenge. No Stereo-seq or Slide-seq dataset at E6.5-E8.5 was found.

### Cited Findings

**Lohoff et al. 2022, Nature Biotechnology 40:74-85 (DOI 10.1038/s41587-021-01006-2)**
- seqFISH on sagittal sections from three embryos at the 8-12 somite stage (E8.5-E8.75); imputation of unmeasured genes — [Springer PDF](https://link.springer.com/content/pdf/10.1038/s41587-021-01006-2.pdf).
- Target genes: 387 in the paper; the MouseGastrulationData R package documents 351 for the seqFISH panel. The two numbers are unreconciled — [R docs](https://rdrr.io/github/MarioniLab/MouseGastrulationData/man/LohoffSeqFISHData.html).
- Format: 2D (x,y) per cell, released through the MouseGastrulationData Bioconductor package, which is easy to download.

**Harland et al. 2025, Cell Reports 44(8):116047 (DOI 10.1016/j.celrep.2025.116047)**
- Spatial transcriptomics on E7.25 and E7.5 embryos, integrated with an existing E8.5 spatial dataset and an E6.5-E9.5 scRNA-seq atlas; more than 150,000 cells; 82 refined cell-type annotations; interactive web portal — [DOI](https://doi.org/10.1016/j.celrep.2025.116047). Accession not found.
- 2024 bioRxiv preprint (10.1101/2024.12.12.628063): 88 annotations; a 351-marker panel chosen for sequential FISH; describes E6.5 and E7.5 measurements — [bioRxiv PDF](https://www.biorxiv.org/content/10.1101/2024.12.12.628063.full.pdf). **Conflict:** the preprint reports E6.5 and E7.5, the published version E7.25 and E7.5. Verify before use.
- Published article is also listed at [ScienceDirect](https://www.sciencedirect.com/science/article/pii/S2211124725008186) (data availability not read).

**Peng et al. 2019, Nature 572:528-532 (DOI 10.1038/s41586-019-1469-8)**
- Geo-seq spatial transcriptome of embryo sections at about 20-40 cells per sample, E5.5-E7.5 — [Nature PDF](https://www.nature.com/articles/s41586-019-1469-8.pdf).
- GEO GSE120963; CNGB STOmics dataset STDS0000077 — [CNGB](https://db.cngb.org/stomics/datasets/STDS0000077).
- Coordinates are regional/2D (per section, not per cell). Not usable for per-cell 3D neighbourhoods.

**Stereo-seq (MOSTA)**
- Search output describes MOSTA as a Stereo-seq organogenesis atlas — source [bioRxiv PDF](https://www.biorxiv.org/content/10.1101/2024.12.12.628063.full.pdf). Its stage range was not shown.

### Inferences
- Harland's E7.25 spatial data are the closest in platform (sequential FISH, 351 genes) to the challenge, and E7.25 is a released stage. This makes them the most useful spatial supplement, subject to the E7.25 ruling.
- Lohoff's E8.5-E8.75 sections are the only spatial set confirmed at an allowed late stage in this survey.

### Gaps
- No Slide-seq or Stereo-seq dataset at E6.5-E8.5 was confirmed. MOSTA is, from memory (not verified here), E9.5-E16.5, which would be excluded by the global rule.
- No 2023-2026 3D spatial gastrulation preprint beyond Harland was found.

## Key Question 3: 3D embryo shape and morphology references

### Takeaway
The eMouseAtlas EMAP 3D models give serial-section 3D anatomy at TS10-TS13. Their nominal ages are 7.0, 7.5, 8.0 and 8.5 dpc. The TS11 model (7.5 dpc) is held out. The McDole 2018 light-sheet in toto dataset is the strongest candidate for per-cell 3D shape and tracking, but its stage range and file sizes were not verified.

### Cited Findings

**eMouseAtlas EMAP 3D models (TS10-TS13)**
- Model IDs and nominal ages: TS10 = EMA10 at 7.0 dpc; TS11 = EMA17 at 7.5 dpc; TS12 = EMA21 at 8.0 dpc; TS13 = EMA24 at 8.5 dpc. Serial-section 3D reconstructions with delineated anatomy — [EMAP model summary](https://emouseatlas.org/emap/ema/modelsummary/modelsummary.html).
- Theiler stage day ranges: TS10 7 (6.5-7.75); TS11 7.5 (7.25-8); TS12 8 (7.5-8.75); TS13 8.5 (8-9.25) — [Theiler definition](https://emouseatlas.org/emap/ema/theiler_stages/StageDefinition/stagedefinition.html).
- Viewer: IIP3D allows arbitrary-plane sectioning. Voxel sizes vary; one TS12 model is 1x1x1 µm, and eight TS13-TS20 models are 4x4x7 µm — [EMAP model summary](https://emouseatlas.org/emap/ema/modelsummary/modelsummary.html).
- Zenodo record 4284379 (published 22 Nov 2020) provides models converted to .stl and a stage key — [Zenodo](https://zenodo.org/record/4284379). Licence not verified.
- Source note: the page warns that somite number is not a reliable global stage indicator after TS12 — [Theiler definition](https://emouseatlas.org/emap/ema/theiler_stages/StageDefinition/stagedefinition.html).

**McDole et al. 2018, Cell 175(3):859-876 (DOI 10.1016/j.cell.2018.09.031)**
- In toto light-sheet imaging from gastrulation through early organogenesis at cellular resolution, long-term cell tracking, fate maps, and a registered multi-embryo dynamic atlas — [Janelia lab page](https://janelia.org/lab/keller-lab/software/in-toto-imaging-and-reconstruction-of-post-implantation-mouse-development-at).
- HHMI states the microscope, computational tools and all imaging data are free and public — [HHMI](https://www.hhmi.org/node/1610).
- Not verified: the stage range (first and last timepoint), number of embryos, raw data accession, and file sizes. The Janelia PDF fetch failed (size limit); the EurekAlert release is at [EurekAlert](https://www.eurekalert.org/news-releases/779663).

### Inferences
- EMAP TS12 and TS13 models at nominal 8.0 and 8.5 dpc are the cleanest 3D shape references under the stage rules. TS10 (7.0) is allowed by its nominal label, but its range reaches 7.75. TS12 (8.0) is at a released stage, but its range reaches 8.75. Both need an organiser ruling (see KQ4).
- Note that the 3D shape score terms (pairwise distance, occupancy in a normalised frame, size) could be tuned on EMAP anatomy masks rather than on cell positions.

### Gaps
- McDole stage range and data size: unresolved; "do not download large files" applies to the raw imaging.
- No 3D shape reference at E7.5-E7.75 is usable (all forbidden).
- EMAP licence and whether the .stl models are the same as the web viewer models: not verified.

## Key Question 4: Compliance verdicts

### Takeaway
Under the rules as stated, usable external stages are E6.5 through E7.25 (E7.25 inclusive) and E8.0 through E9.5 (E9.5 inclusive). Everything from E7.25 to E8.0 (exclusive) is forbidden. Beyond E9.5 up to E13.5 is forbidden. Most multi-stage datasets therefore need to be split at E7.25/E8.0 and their E7.5/E7.75 parts removed. Perturbation subsets (Foxc1/2 DKO, Tal1 chimeras, epigenetic KOs, grafts) are flagged and recommended for exclusion. None of the surveyed datasets were found to contain Gata4 or Ctnnb1 perturbations, but the gene lists of several perturbation sets are unverified.

### Cited Findings
- Rules as given: external data strictly between E7.25 and E8.0 is forbidden; data closer to held-out E7.5 or E7.75 than to the nearest released stage counts as held out (example E7.375 < x < E7.875); E7.25 and E8.0 are released stages; nothing after E9.5 up to and including E13.5. Source: task brief (no URL).
- Midpoint-rule zones: E7.5 is held out for 7.375 < x < 7.75; E7.75 is held out for 7.5 < x < 7.875. Their union is 7.375-7.875, which is inside the bracket (7.25, 8.0).

### Inferences: allowed windows (my reading)
- **Allowed:** x <= 7.25 (E7.25 inclusive; practically E6.5-E7.25 in this context) and 8.0 <= x <= 9.5.
- **Forbidden:** 7.25 < x < 8.0 (bracket rule; subsumes the midpoint-rule zone, so the midpoint rule adds no extra exclusions outside the bracket).
- **Forbidden:** 9.5 < x <= 13.5 (global rule).
- **Ambiguous:** x > 13.5 is not covered by the wording. Treat as off-scope and ask the organisers.
- **Ambiguous:** Theiler or other stage labels whose day range straddles a held-out stage (TS10 6.5-7.75; TS12 7.5-8.75). I apply the nominal label, flagged as conditional.

### Inferences: perturbation screen
- Forbidden categories in the brief: Gata4, Ctnnb1 (beta-catenin), Wnt-pathway loss phenocopying beta-catenin.
- Flagged, not explicitly forbidden by the brief, recommended for exclusion pending organiser ruling:
  - Pijuan-Sala WT chimeras (E-MTAB-7324) and Tal1-/- chimeras (E-MTAB-7325) — [ORA record](https://ora.ox.ac.uk/objects/uuid:34622b55-8d4f-4c75-9d5a-6223115fe096).
  - Mittnenzweig Foxc1/Foxc2 DKO chimeras (2N and 4N) — [PMC8162424](https://pmc.ncbi.nlm.nih.gov/articles/PMC8162424/).
  - Grosswendt ten-regulator zygotic knockouts — [PMC7415732](https://pmc.ncbi.nlm.nih.gov/articles/PMC7415732). Gene list must be checked for any Wnt or Ctnnb1 member.
  - Imaz-Rosshandler primitive-streak grafts (E-MTAB-13645) — [OmicsDI](https://www.omicsdi.org/dataset/biostudies-arrayexpress/E-MTAB-13645).
- Nothing in the surveyed text mentions Gata4 or Ctnnb1 perturbations. This is not proof of absence for the full gene lists.

### Stage-level verdict table

| Dataset | Stage label(s) | Verdict |
|---|---|---|
| Pijuan-Sala 2019 (WT atlas) | E6.5, E6.75, E7.0, E7.25 | ALLOWED |
| Pijuan-Sala 2019 | E7.5, E7.75 | FORBIDDEN (held out) |
| Pijuan-Sala 2019 | E8.0, E8.25, E8.5 | ALLOWED |
| Pijuan-Sala 2019 chimeras (E-MTAB-7324, -7325) | any | EXCLUDE (perturbation flag) |
| Mittnenzweig 2021 (WT bins) | E_t6.5 to E_t7.25 bins; E_t8.0 and E_t8.1 bins | ALLOWED |
| Mittnenzweig 2021 | E_t7.5 and E_t7.75 bins | FORBIDDEN |
| Mittnenzweig 2021 Foxc1/2 chimeras | any | EXCLUDE (perturbation flag) |
| Imaz-Rosshandler 2024 (E8.25-E9.5 part) | E8.25 to E9.5 | ALLOWED (E9.25 not verified) |
| Imaz-Rosshandler 2024 (E6.5-E8.0 part) | E7.5, E7.75 | FORBIDDEN |
| Imaz-Rosshandler 2024 grafts | any | EXCLUDE (perturbation flag) |
| Imaz-Rosshandler 2024 | any timepoint >E9.5 | FORBIDDEN |
| Lohoff 2022 seqFISH | E8.5-E8.75 | ALLOWED |
| Harland 2025 spatial | E7.25 | ALLOWED (released stage; conflicting stage description in preprint) |
| Harland 2025 spatial | E7.5 | FORBIDDEN |
| Harland 2025 existing E8.5 spatial input | E8.5 | ALLOWED (inferred; source not verified) |
| Peng 2019 Geo-seq | E5.5 to E7.25 samples | ALLOWED (intermediate stages not verified) |
| Peng 2019 Geo-seq | E7.5 samples | FORBIDDEN |
| Argelaguet 2019 | E4.5, E5.5, E6.5 (verify) | ALLOWED, low relevance |
| Argelaguet 2019 | E7.5 | FORBIDDEN |
| Grosswendt 2020 WT reference | E<=7.25 or >=8.0 timepoints | ALLOWED (timepoints not verified) |
| Grosswendt 2020 WT reference | E7.5, E7.75 timepoints | FORBIDDEN |
| Grosswendt 2020 KO embryos | any | EXCLUDE (perturbation flag; gene list unverified) |
| Qiu 2024 TOME (2-6 h sampling) | per-timepoint | CONDITIONAL: E7.5-E7.75 and >E9.5 forbidden; rest allowed if stage labels confirmed |
| eMouseAtlas TS10 model | nominal 7.0 dpc | CONDITIONAL (allowed by label; range 6.5-7.75) |
| eMouseAtlas TS11 model | nominal 7.5 dpc | FORBIDDEN |
| eMouseAtlas TS12 model | nominal 8.0 dpc | CONDITIONAL (released stage; range 7.5-8.75) |
| eMouseAtlas TS13 model | nominal 8.5 dpc | ALLOWED (range 8.0-9.25) |
| McDole 2018 light-sheet | not verified | PENDING: stage range needed |
| Stereo-seq MOSTA | likely E9.5-E16.5 (memory, unverified) | EXCLUDED, provisional (global rule) |
| Sladitschek MorphoSeq | ascidian | EXCLUDED (not mouse) |
| Ibarra-Soria 2018 | E8.25 (user-stated, not verified) | ALLOWED if confirmed |
| Tyser 2021 (heart scope) | E7.5-E8.25 (user-stated) | PARTIAL: E7.5/E7.75 cells forbidden; E8.0-E8.25 allowed; heart team to confirm |
| Scialdone 2016, Chan 2019 | not searched | NOT VERIFIED |

### Gaps
- Open questions for organisers: (a) whether E7.25 and E8.0 external data count as allowed (the brief says they are released stages, so I treat them as allowed); (b) whether x > E13.5 is forbidden; (c) how nominal Theiler labels are applied when ranges straddle held-out stages; (d) whether Foxc1/2, Tal1, epigenetic and graft perturbation subsets are acceptable.
- Pijuan-Sala accession mismatch: E-MTAB-7601 (user) vs E-MTAB-6967 (paper data statement). Not resolved because the BioStudies page did not load.
- Imaz-Rosshandler E9.25: not explicitly verified.
- Licence, file size and download route for most datasets: not verified. Only Lohoff (R package) and the EMAP Zenodo .stl bundle have a known download route.
- Not searched: Scialdone 2016, Chan 2019, Tyser 2021 (heart scope), Ibarra-Soria 2018 accession, Argelaguet stage list and subseries accessions.
- McDole 2018: stage range, sample size, accession and file sizes unresolved (PDF fetch failed).
- Stereo-seq early-embryo and 2023-2026 3D spatial preprints: none found beyond Harland.
- No Gata4 or Ctnnb1 perturbation was identified in any surveyed dataset, but gene-level checks for Grosswendt and the Pijuan-Sala chimeras remain open.
