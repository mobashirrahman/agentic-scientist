# Late-stage (E14.5+) mouse heart spatial transcriptomics anchors

Research date: 2026-11-17. About 27 tool calls were used, more than the usual budget, because several primary pages were blocked (HTTP 429 rate limits on bioRxiv and PMC/synapsesocial, reCAPTCHA on NCBI GEO, login redirect on nature.com). Items marked UNVERIFIED come only from search snippets or aggregators. Search coverage of 2026 preprints is thin, so absence of a dataset here is not proof it does not exist.

## Key Question 1: Which mouse heart or heart-containing spatial datasets exist at E14.5 or later?

### Takeaway
Two usable mouse datasets reach the allowed late window with verified details. The first is MOSTA Stereo-seq whole-embryo sagittal sections at E9.5 and E14.5 to E16.5, with whole-transcriptome coverage. Heart presence in those sections is not verified. The second is a heart-specific Stereo-seq atlas at E20, P1, P4 and P14 (GigaScience 2025; CNGB STT0000062). I found no verified mouse developing-heart MERFISH, seqFISH, STARmap, Xenium, CosMx or Open-ST atlas at E14.5 or later. One mouse embryonic and neonatal Visium plus Slide-seq heart study exists per an aggregator, but I could not verify its stages or accession, so it is the top open item.

### Cited Findings

Catalogue (verified unless marked UNVERIFIED):

| # | Dataset / citation | Accession and access | Stages | Assay and resolution | Size / genes | Labels | Allowed under competition rule |
|---|---|---|---|---|---|---|---|
| 1 | MOSTA, Chen A, Liao S, Cheng M et al., Cell 2022;185(10):1777-1792.e21, DOI 10.1016/j.cell.2022.04.003 ([Cell abstract via Bohrium](https://bohrium.dp.tech/paper/arxiv/35512705)) | STOmicsDB STDS0000058, project CNP0001543 ([dataset page](https://db.cngb.org/stomics/datasets/STDS0000058/)); portal at [db.cngb.org/stomics/mosta](https://db.cngb.org/stomics/mosta/) | Eight stages E9.5, E10.5, E11.5, E12.5, E13.5, E14.5, E15.5, E16.5 (portal, via search summary) | Stereo-seq (DNBSEQ-T1), mm10, whole-embryo sagittal sections | 351,014 spots; 28,879 genes (dataset page) | Not stated on dataset page (UNVERIFIED) | E9.5 and E14.5-E16.5 only. E10.5-E13.5 forbidden. |
| 2 | Murine cardiac Stereo-seq atlas, GigaScience 2025, giaf012, DOI 10.1093/gigascience/giaf012, PMID 39960664 ([PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC11831923/)) | Processed: CNSA/CNGBdb STT0000062 ([project](https://db.cngb.org/stomics/project/STT0000062)). Raw: NCBI SRA PRJNA1148773. | E20, P01, P04, P14 (two male C57BL/6 per timepoint). Paper uses P01/P04 in results and P1/P4 in methods. | Stereo-seq (MGI DNBSEQ), bin50 (about 25 µm), 330,857 bins; 22 sections after QC | 6.46 GB total (project page). Gene count not reported in text. | Yes: 14 cell types; subtypes for ventricular CM (9), atrial CM (7), fibroblasts (5). Not all subtypes functionally annotated. | All stages allowed (after E13.5). |
| 3 | Stereo-seq plus scRNA-seq, conduction system formation, Nature Communications 2023, s41467-023-42658-9 ([article](https://www.nature.com/articles/s41467-023-42658-9); page redirected to login, so details are from search snippet only) | Not verified | E8.5, E10.5, E12.5, E14.5, E16.5, P3 (snippet, UNVERIFIED) | Stereo-seq plus scRNA-seq | Not verified | Not verified | Stages E10.5 and E12.5 forbidden. E14.5, E16.5 and P3 allowed. E8.5 is before the window. |
| 4 | Postnatal Stereo-seq cardiac dataset, Zheng et al., Scientific Data 2025, DOI 10.1038/s41597-025-05838-4 (snippet, UNVERIFIED for DOI) | GEO GSE298650 ([OmicsDI](https://www.omicsdi.org/dataset/geo/GSE298650)); provider date 2025/06/10; title "A dataset of spatially resolved transcriptomics of post-natal cardiac development in mice" | Three unnamed postnatal stages | Stereo-seq; about 0.186 million cells; 93,826 cardiomyocytes in one section | Not stated | Cell types mapped (per OmicsDI description) | Postnatal, allowed. |
| 5 | GEO GSE178636, "Spatiotemporal transcriptomes of mouse embryo", provider date 2023/02/19 ([OmicsDI](https://www.omicsdi.org/dataset/geo/GSE178636)) | GEO GSE178636 | Stages not on page. The GigaScience paper cites "mouse embryo spatial data (E9.5-E12.5)" under this accession (UNVERIFIED mapping). | Platform not stated; probably Stereo-seq (UNVERIFIED) | Not stated | Not stated | E10.5-E12.5 forbidden. E9.5 allowed. Not a late-stage source. |
| 6 | Whole-embryo Slide-seq, sc3D digital embryo, GEO GSE197353 ([ASAP](https://asap.epfl.ch/exp_entries/78)) | GEO GSE197353 | E8.5 and E9.5 whole embryos | Slide-seq; 3D reconstruction (sc3D) | Not stated | Not stated | E9.5 allowed. E8.5 is before the window. Too early for a heart beyond the heart tube. Includes Prdm8 and Tbx6 mutant work (see constraint flags). |
| 7 | 3D whole-embryo preprint, Liu, Chen, Xu et al., bioRxiv 2024.08.17.608366 ([Bohrium](https://bohrium.dp.tech/paper/arxiv/2024.08.17.608366)) | Not verified | E9.5 and E11.5 (search summary, UNVERIFIED). Full text was blocked (HTTP 429). | Serial block-face imaging for 3D maps | Not verified | Not verified | E11.5 forbidden. E9.5 allowed. |
| 8 | Digital reconstruction of full embryos, Cell 2025 ([PubMed 40920635](https://pubmed.ncbi.nlm.nih.gov/40920635/)) | Not verified | E7.5-E8.0 (snippet) | Serial sections, 3D whole embryo, single-cell resolution (authors' claim) | Slice count conflicts: 285 (PubMed snippet) vs 360 (OmicsDI snippet) | Not verified | Pre-window and too early for a heart. Not useful for E14.5+. |
| 9 | Visium plus Curio Slide-seq (Seeker) embryonic and neonatal mouse heart, attributed to "Hu et al." (UNVERIFIED). Source is an aggregator with a garbled author line: [synapsesocial W7161294153](https://synapsesocial.com/papers/W7161294153). Re-fetch was blocked (HTTP 429). | Not identified | Embryonic and neonatal; exact ages not in snippet (UNVERIFIED) | Visium (about 55 µm spots) and Slide-seq (beads) | Not verified | Conduction-system cell types (cardiac neurons, SAN, AVN, Purkinje), compact and trabecular myocardium signatures (snippet) | Stages unknown. Could include E10-E13. Must verify before any use. |
| 10 | Bruker CosMx mouse embryo (AACR 2026 poster, not peer-reviewed) ([poster](https://brukerspatialbiology.com/wp-content/uploads/2026/04/AACR_2026_ProductDevelopment_MouseEmbryo_MusWTx_mpatrick_60x45.pdf)) | No public accession found | E11 to E14 | CosMx Mouse WTX, more than 20,000 genes, cell-level | Not stated | Cell types per embryo (heart-specific not shown) | E11, E12 and E13 forbidden. E14 allowed. Not public as far as found. |
| 11 | Kosuri lab MERFISH, healthy adult mouse heart, 128-gene panel, Circulation Research 2023 abstract P1185 ([Bohrium](https://bohrium.dp.tech/paper/arxiv/949051879873052678)) | Not found | Adult, not developmental | MERFISH, 10 µm sections, single-cell | 128 genes | Cell types (per abstract) | Stage-allowed but not developmental. Not usable as a developmental anchor. |
| 12 | 3D-Cardiomics, "A spatial transcriptional atlas of the mammalian heart", bioRxiv 792002 ([PDF](https://www.biorxiv.org/content/10.1101/792002.full.pdf)) | Not verified | Not verified | Spatial, 3D (per title) | Not verified | Not verified | Unverified lead for the 3D question. Check species and stages. |

Excluded (not mouse or not spatial):
- Human developing heart Visium, Asp-style: [STDS0000015](https://db.cngb.org/stomics/datasets/STDS0000015). Excluded as human.
- Human developing heart MERFISH+ preprint, 2025: [bioRxiv 2025.11.02.686137](https://www.biorxiv.org/content/10.1101/2025.11.02.686137.full.pdf). 3.1 million cells, more than 1,800 genes. Excluded as human.
- Nature 2024 "Spatially organized cellular communities form the developing human heart" (Farah et al. per search summary, no URL retrieved). Excluded as human.
- Chick cardiac Visium (search snippet, no URL retrieved). Excluded as non-mouse.
- Adult zebrafish regeneration Visium and MERFISH preprint ([ORA record](https://ora.ox.ac.uk/objects/uuid:4263f746-97f1-4c54-93c8-c902248e1f27)). Excluded as zebrafish and adult.
- "Patterning defects in mice with defective ventricular wall maturation" ([bioRxiv 2025.05.22.655570](https://www.biorxiv.org/content/10.1101/2025.05.22.655570.full.pdf)). In-situ hybridization study of mutants, not a spatial atlas. Genotype not checked.

Panel coverage for a 500-gene MERFISH-like panel:
- MOSTA: 28,879 genes on the dataset page, so a 500-gene panel should be fully covered. This is an inference from whole-transcriptome Stereo-seq.
- Heart Stereo-seq (STT0000062): gene count not reported. Whole-transcriptome Stereo-seq is likely. Check supplementary Table S2.
- Visium, Slide-seq and CosMx: all whole-transcriptome or large-panel, but the datasets are not verified.

Download and access:
- MOSTA (STDS0000058): the dataset page lists totals only. The Data tab contents, file formats, sizes, licence and download registration were not retrieved. A login link is present, but download registration is not stated.
- STT0000062: total 6.46 GB. Formats not listed. Terms and registration not stated. Authors not listed. Only "Jingmin Kang. Spatial transcriptomics" appears.
- GEO records (GSE178636, GSE197353, GSE298650): GEO is open, but the pages I could reach gave no file lists (reCAPTCHA on NCBI, so unverified).

### Constraint flags (competition rule and exclusions)
- Forbidden window (after E9.5 up to and including E13.5). Any use must filter by section stage.
  - MOSTA: E10.5 to E13.5 sections are forbidden. E9.5 and E14.5 to E16.5 are allowed.
  - Nature Communications 2023 conduction atlas: E10.5 and E12.5 forbidden.
  - GSE178636: E10.5 to E12.5 forbidden.
  - 3D whole-embryo preprint 2024.08.17: E11.5 forbidden.
  - CosMx embryo poster: E11 to E13 forbidden.
  - Hu et al. Visium and Slide-seq: stages unknown. Could include forbidden stages.
- Gata4 or Ctnnb1 (beta-catenin) knockouts or phenocopies: none of the verified candidates is a Gata4 or Ctnnb1 perturbation. GSE197353 includes Prdm8 and Tbx6 mutants. These are not on the forbidden list, but they are perturbations and should be noted. The bioRxiv "Patterning defects" mutant genotype was not checked.
- The MOSTA STOmicsDB page lists 16 samples and 6 sections. The MOSTA portal, via search summary, describes 53 sagittal sections. Check which sections are actually in the downloadable subset.

### Inferences
- For late-stage anchoring, MOSTA E14.5 to E16.5 is the only verified whole-embryo, whole-transcriptome, sagittal source in the allowed window. It supports cell-type composition and tissue-level context. Heart presence still needs checking in those sections.
- STT0000062 (E20 to P14) is the best heart-specific reference. It is 5.5 or more days later than E14.5, so use it for direction of maturation rather than for matched timepoints.
- The Nature Communications 2023 study (E14.5, E16.5, P3 allowed subset) could be a heart-specific bridge if its data are accessible. Verify accession first.
- The Hu et al. Visium and Slide-seq study is the most likely heart-specific embryonic source, but it cannot be used until its stages are confirmed.

### Gaps
- Heart presence and cell-type labels in MOSTA E14.5 to E16.5 sections: not verified.
- MOSTA download file formats, sizes, bin levels, annotation availability and access terms: not verified (Data tab not retrieved).
- Hu et al. Visium and Slide-seq study: journal, DOI, authors, stages and accession not identified.
- Nature Communications 2023 conduction atlas: accession, sample counts and data availability not verified (login redirect).
- STT0000062 and GigaScience paper: author list not retrieved, and the stage naming inconsistency needs confirming in the methods.
- No mouse developing-heart MERFISH, seqFISH, STARmap, Xenium, Open-ST, or Slide-seqV2 atlas at E14.5 or later was found. Xenium, Open-ST and Slide-seqV2 heart were not searched specifically.
- CELLxGENE, Broad Single Cell Portal, SODB and SpatialDB were not searched in this pass.
- The Farah et al. 2024 Nature human heart paper and the Asp et al. human heart study were identified only from search snippets or as human, and no article URL was retrieved for Farah.

## Key Question 2: Which datasets are cell-resolved versus spot-level?

### Takeaway
MOSTA and the heart Stereo-seq atlas are bin-based (Stereo-seq bins), not cell-segmented. The MOSTA authors claim single-cell resolution, but cell segmentation for the downloaded data was not verified. The heart atlas uses bin50 (about 25 µm), which is coarser than a cell. Neighbourhood metrics from either will need cell segmentation or bin aggregation. Visium is spot-level (about 55 µm), and Slide-seq is bead-level. The CosMx embryo poster is cell-level but is unpublished and forbidden in part.

### Cited Findings
- MOSTA is described by its authors as single-cell resolution (summary of [Cell abstract via Bohrium](https://bohrium.dp.tech/paper/arxiv/35512705)). The STOmicsDB page reports 351,014 spots, which suggests bins ([dataset page](https://db.cngb.org/stomics/datasets/STDS0000058/)).
- The heart Stereo-seq atlas uses bin50 (about 25 µm), 330,857 bins, and says these are "bins, not single cells" ([PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC11831923/)).
- The GSE178636 whole-embryo Stereo-seq dataset is listed as a spatial embryo dataset (details unverified, [OmicsDI](https://www.omicsdi.org/dataset/geo/GSE178636)).
- Slide-seq is used in GSE197353 for E8.5 and E9.5 whole embryos ([ASAP](https://asap.epfl.ch/exp_entries/78)).
- The CosMx embryo poster describes cell-level resolution ([poster](https://brukerspatialbiology.com/wp-content/uploads/2026/04/AACR_2026_ProductDevelopment_MouseEmbryo_MusWTx_mpatrick_60x45.pdf)).
- The Visium 55 µm spot size is general 10x knowledge and was not verified against a retrieved source.

### Inferences
- For neighbourhood metrics on E14.5+ data, MOSTA needs cell segmentation from the ssDNA or staining images, or bin aggregation at about 10 to 25 µm. Segmentation status must be checked in the download.
- The heart atlas, at bin50, is best for tissue-scale composition and niche structure, not single-cell neighbourhoods.

### Gaps
- MOSTA bin sizes available for download and segmentation status: not verified.
- Whether MOSTA annotations are cell-level or bin-level: not verified.

## Key Question 3: Does any dataset include a 3D heart (serial sections registered)?

### Takeaway
I found no verified mouse heart 3D spatial transcriptomics dataset at E14.5 or later. The verified 3D whole-embryo datasets (sc3D Slide-seq GSE197353 at E8.5 and E9.5, and the Cell 2025 digital embryo at E7.5 to E8.0) are too early for a developed heart. The 3D whole-embryo preprint covers E9.5 and E11.5, and E11.5 is forbidden.

### Cited Findings
- GSE197353 provides a 3D "digital embryo" from sagittal Slide-seq sections, reconstructed with sc3D. It covers E8.5 and E9.5 only ([ASAP](https://asap.epfl.ch/exp_entries/78)).
- The Cell 2025 digital embryo covers E7.5 to E8.0 and was built from serial sections ([PubMed](https://pubmed.ncbi.nlm.nih.gov/40920635/)).
- The 3D preprint (E9.5 and E11.5, serial block-face imaging, UNVERIFIED) is listed at [Bohrium](https://bohrium.dp.tech/paper/arxiv/2024.08.17.608366).
- The 3D-Cardiomics bioRxiv preprint is titled as a 3D spatial transcriptional atlas of the mammalian heart. Stages and species were not verified ([PDF](https://www.biorxiv.org/content/10.1101/792002.full.pdf)).

### Inferences
- A 3D heart at E14.5+ would need either a new reconstruction from the MOSTA sagittal sections (serial sections at a given stage) or the 3D-Cardiomics method, which should be checked for stage and species.
- Reconstructing 3D from the MOSTA sections is possible in principle, because MOSTA has sagittal sections at E14.5 to E16.5, but this is an inference and not a verified 3D dataset.

### Gaps
- 3D-Cardiomics: species, stages, assay and data availability not verified.
- No 3D spatial transcriptomics heart dataset at E14.5 or later was found. The search did not exhaustively cover 2026 preprints.

## Recommended next steps (for the coordinator)
1. Identify the Hu et al. Visium and Slide-seq study (journal, DOI, stages, accession). This is the top priority because it is the only mouse embryonic and neonatal heart study with Visium and Slide-seq.
2. Open the STOmicsDB MOSTA Data tab to check file formats, sizes, bin levels, annotation and whether the E14.5 to E16.5 sections containing the heart are included.
3. Check the Nature Communications 2023 conduction atlas accession and stages in a browser (login redirect blocked the fetch).
4. Confirm the GigaScience heart atlas author list and stage naming in methods, and check Supplementary Table S2 for gene coverage.
