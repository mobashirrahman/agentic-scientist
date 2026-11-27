# Mouse embryonic knockout single-cell perturbation library: candidates and compliance flags

Research date: 2026-11-17. Scope: mouse only, embryonic stages (focus E6.5–E9.5). No large files downloaded.

Evidence labels:
- **Verified (text)**: read from the primary article text in this session (WebFetch of the article HTML).
- **Verified (metadata)**: accession or title read from a database listing (omicsdi) in this session.
- **Snippet**: seen only in a search-result summary. Not opened.
- **Unverified**: not checked. Listed from search titles or memory.

Access limits: every ncbi.nlm.nih.gov GEO page returned a reCAPTCHA page, and several PMC and bioRxiv pages returned 403/429/reCAPTCHA. Nature pages redirected to a login page, which was not followed. Accessions marked "paper text" were taken from the article's own data statement.

Rule text: the challenge rule quotes are taken from the sibling note `/scratch/user/virtual-embryo/research_notes/Late stage heart anchors/atlases_and_rules.md`, which records raw challenge pages. They were not re-fetched here.

Gene-name check: no candidate below is a Gata4 or Ctnnb1 (beta-catenin) dataset, as far as the text read shows.

---

## Key Question 1: Which embryonic knockout or perturbation single-cell and spatial datasets, with matched wild type, exist at E6.5–E9.5?

### Takeaway
Six usable-looking datasets come from chimera or whole-embryo designs with matched wild type: Pijuan-Sala 2019 Tal1 chimeras (E8.5, E-MTAB-7325), Grosswendt 2020 zygotic CRISPR knockouts of ten epigenetic regulators (E8.5, GSE137337), Cheng 2022 Tet1/2/3 knockouts (E7.5–E8.5, GSE205917), Sox17 Mesp1-Cre conditional at E8.5 (GSE125323, but a microarray platform, not sequencing), Hand2-null at E7.75/E8.25/E9.25 (de Soysa 2019, accession not verified), and Mittnenzweig 2021 Foxc1/Foxc2 chimeras. Most of these need a stage flag. Pitx2 (Hill 2019) and Hand1 (E11.5) are blocked by the stage window. No embryonic single-cell knockout was found for Isl1, Tbx20, Nkx2-5 (null), Etv2 (embryo), Foxh1, Gata6 (mouse), Fgf8, Hey1/2, or Smarcd3. Rule caveat: the data page says external single-cell training is allowed only for Task 1, so no dataset here is cleared for Task 3 until the organisers answer (see Key Question 2).

### Cited Findings

**A. Chimera and whole-embryo knockout designs with internal or stage-matched wild type**

- **A1. Pijuan-Sala et al. 2019, Nature 566:490–495, DOI 10.1038/s41586-019-0933-9 (atlas and Tal1 chimeras).**
  - Verified (text): atlas of 116,312 cells passing QC, nine time points E6.5, E6.75, E7.0, E7.25, E7.5, E7.75, E8.0, E8.25, E8.5, plus two "Mixed" samples ([Source](https://pmc.ncbi.nlm.nih.gov/articles/PMC6522369)).
  - Verified (text): accessions ArrayExpress E-MTAB-6967 (atlas) and E-MTAB-7325 (Tal1-/- chimeras) ([Source](https://pmc.ncbi.nlm.nih.gov/articles/PMC6522369)).
  - Verified (text): Tal1-/- chimeras harvested at E8.5 (7 embryos). After QC, 27,817 host (tdTomato-) cells and 28,305 Tal1-/- (tdTomato+) cells. Figure 4b shows 25,078 WT and 26,326 KO cells ([Source](https://pmc.ncbi.nlm.nih.gov/articles/PMC6522369)).
  - Design: Tal1 mutant ES cells in a wild-type host embryo, so the perturbation is cell-autonomous and the host cells are a matched control in the same embryo.
  - Labels: cell-type annotation not verified in this session.
  - Atlas site (Snippet): https://marionilab.cruk.cam.ac.uk/MouseGastrulation2018/ ([Source](https://marionilab.cruk.cam.ac.uk/MouseGastrulation2018/)).

- **A2. Grosswendt et al. 2020, Nature 584:102–108, DOI 10.1038/s41586-020-2552-x ("Epigenetic regulator function through mouse gastrulation").**
  - Verified (text): ten regulators, Dnmt1, Dnmt3a, Dnmt3b, G9a, Rnf2, Eed, Kdm2b, L3mbtl2, Kmt2a, Kmt2b ([Source](https://pmc.ncbi.nlm.nih.gov/articles/PMC7415732)).
  - Verified (text): zygotic CRISPR-Cas9 injection with 3–4 sgRNAs per gene. Knockouts sampled at E8.5 (Eed also at E6.5 and E7.5). 8–12 E8.5 embryos per KO, 7,548–25,408 cells per KO. Total of 103 KO embryos ([Source](https://pmc.ncbi.nlm.nih.gov/articles/PMC7415732)).
  - Verified (text): matched wild-type compendium of 88,779 cells from 50 embryos, E6.5–E8.5 at 12-hour intervals, 9–11 embryos per time point ([Source](https://pmc.ncbi.nlm.nih.gov/articles/PMC7415732)).
  - Verified (text): accession GSE137337. Code on GitHub (per the paper) ([Source](https://pmc.ncbi.nlm.nih.gov/articles/PMC7415732)).
  - Caveat: zygotic CRISPR gives a mosaic, biallelic-variable knockout, not a clean null. Treat as a perturbation-response dataset.

- **A3. Cheng et al. 2022, Cell 185(17):3169–3185, DOI 10.1016/j.cell.2022.06.049 ("The intrinsic and extrinsic effects of TET proteins during gastrulation").**
  - Verified (text): whole-embryo Tet1/2/3 triple-knockout chimeras from E7.5 to E8.5. 30 TKO and 18 control embryos, with 7,480 control and 9,793 TKO cells (Fig. 1C). Fig. 1F compares 16 control and 15 mutant embryos at E7.5 ([Source](https://pmc.ncbi.nlm.nih.gov/articles/PMC9432429)).
  - Verified (text): mixed diploid chimeras at E7.5, 44 embryos, with 7,008 mutant, 4,334 control and 4,834 host cells. Host cells come from the same embryos and serve as matched controls ([Source](https://pmc.ncbi.nlm.nih.gov/articles/PMC9432429)).
  - Verified (text): accession GEO GSE205917 for scRNA-seq and PBAT ([Source](https://pmc.ncbi.nlm.nih.gov/articles/PMC9432429)).
  - Verified (text): the paper reports Lefty2, Dppa4, Gdf3, Fgf3, Fgf15, Spry4, Dll1, Jag1, Hand2 and Pitx2 changes, and no Wnt or beta-catenin genes in the portion read. The Methods were truncated in the read, so later mentions are not ruled out ([Source](https://pmc.ncbi.nlm.nih.gov/articles/PMC9432429)).
  - Stage note: the double knockout is dissected at "~E8.0", so it is borderline for the open interval (E7.25, E8.0).

- **A4. Mittnenzweig et al. 2021, Cell 184(11):2825–2842 ("A single-embryo, single-cell time-resolved model for mouse gastrulation"), PMID 33932341.**
  - Snippet: 153 individually sampled embryos, E6.5–E8.25. Time-matched Foxc1/Foxc2-mutant chimeras used to test combinatorial TF control of mesoderm multifurcation ([Source](https://pmc.ncbi.nlm.nih.gov/articles/pmid/33932341)).
  - Unverified: exact chimera stage, cell counts, accession and code repository. The PMC full text returned a browser check.

- **A5. Guibentif and Griffiths et al. 2021, "Diverse routes towards early somites in the mouse embryo" (PMC7808755). Journal and year not confirmed in tool output.**
  - Snippet: T-/- chimeras profiled at E7.5 and E8.5. Anterior somites form without T ([Source](https://pmc.ncbi.nlm.nih.gov/articles/PMC7808755)).
  - Snippet: the ArrayExpress entry E-MTAB-8811 is described as scRNA-seq of T knockout chimeric embryos at E7.5 and E8.5. The same entry lists the donor genotype as Tal1-/-, which conflicts with a T-knockout design ([Source](https://www.omicsdi.org/dataset/biostudies-arrayexpress/E-MTAB-8811)). Check the genotype before any use.

- **A6. Strauss et al., "A single-cell and tissue-scale analysis suite resolves Mixl1's role in heart development" (Marioni and Göttgens labs). Journal not confirmed.**
  - Snippet: single-cell profiling of T-/- and Mixl1-/- chimeric embryos through gastrulation and early organogenesis. Mixl1-null chimeras show a disrupted juxta-cardiac field ([Source](https://doaj.org/article/cdf9611159a1457f9b97fa4821d68230)).
  - Snippet: code and processed data on GitHub (MarioniLab/analysis_chimera_data) and Zenodo DOI 10.5281/zenodo.15008256 ([Source](https://doaj.org/article/cdf9611159a1457f9b97fa4821d68230)).
  - bioRxiv preprint 10.1101/2022.08.22.504863 ([Source](https://www.biorxiv.org/content/10.1101/2022.08.22.504863v1.full.pdf)). Stages, cell counts and journal unverified (both fetches failed).

**B. Cardiac and mesoderm mutant embryos**

- **B1. de Soysa et al. 2019, Nature 572(7767):120–124, DOI 10.1038/s41586-019-1414-x ("Single-cell analysis of cardiogenesis reveals basis for organ-level developmental defects"). Hand2-null.**
  - Snippet: cardiogenic region dissected at E7.75, E8.25 and E9.25. Single-cell profiling of wild type and Hand2-null. Extended Data legend lists n=5 WT and n=3 Hand2-null embryos at E7.75 ([Source](https://pmc.ncbi.nlm.nih.gov/articles/PMC6719697)).
  - Snippet: 10x write-up reports over 36,000 cells ([Source](https://www.10xgenomics.com/cn/blog/uncovering-the-role-of-hand2-in-congenital-heart-defects)).
  - Snippet: Hand2-null loses outflow tract myocardium specification ([Source](https://pmc.ncbi.nlm.nih.gov/articles/PMC6719697)).
  - Accession: not verified (gap).

- **B2. Sox17 conditional, Mesp1-Cre, Sci Rep 2019, DOI 10.1038/s41598-019-48321-y ("Endocardium differentiation through Sox17 expression in endocardium precursor cells regulates heart development in mice"). First author not confirmed in this session.**
  - Verified (text): Mesp1Cre/+;Sox17fl/fl (mesoderm deletion). Controls are Sox17fl/fl for single-cell work and Mesp1+/+;Sox17fl/fl for morphology. Single-cell profiling at E8.5 (nine-somite), with heart phenotypes at E9.5 ([Source](https://pmc.ncbi.nlm.nih.gov/articles/PMC6697751)).
  - Verified (text): platform is an Agilent SurePrint G3 Mouse GE v2 8x60K microarray. This contradicts the search snippet that calls it scRNA-seq, so treat the data as microarray-type (not count data) ([Source](https://pmc.ncbi.nlm.nih.gov/articles/PMC6697751)).
  - Verified (text): accession GEO GSE125323. Search snippet: sub-series GSE125321 (endocardium) and GSE125322 (myocardium) ([Source](https://www.omicsdi.org/dataset/geo/GSE125321)).
  - Verified (text): at a 5-fold cutoff, 285 probes change in endocardium (114 up, 171 down) and 358 in myocardium (84 up, 274 down). Per-genotype cell numbers were not reported in the text read ([Source](https://pmc.ncbi.nlm.nih.gov/articles/PMC6697751)).
  - Note: GSE125321 is already listed in the heart notes at `/scratch/user/virtual-embryo/research_notes/Late stage heart anchors/heart_singlecell.md`.

- **B3. Hill et al. 2019, Development 146(12), "A cellular atlas of Pitx2-dependent cardiac development". Pitx2hd-/-.**
  - Verified (text): scRNA-seq at E10.5 (22,797 cells, 18 clusters) and E13.5 (54,325 cells). GEO GSE131181 ([Source](https://pmc.ncbi.nlm.nih.gov/articles/PMC6602352)).
  - Verified (text): allele is Pitx2hd-/-. Controls are wild-type and heterozygous embryos. Littermate status not stated ([Source](https://pmc.ncbi.nlm.nih.gov/articles/PMC6602352)).
  - Stage: both time points are in the forbidden window. E10.5 is after E9.5, and E13.5 is excluded by the rule text. FORBIDDEN by stage.

- **B4. Muncie-Vasic et al., 2025, Genes and Development (MEF2C networks in heart tube development). Mef2c-null snRNA-seq plus snATAC-seq.**
  - Verified (metadata): GEO GSE280543 (snRNA-seq) with WT and MEF2C-null embryos. Title and organism confirmed. Stage not stated on the page, only "distinct stages". Date 2024/11/04 ([Source](https://www.omicsdi.org/dataset/geo/GSE280543)).
  - Snippet: outflow tract severely hypoplastic by E9 ([Source](https://genesdev.cshlp.org/cgi/content/full/39/23-24/1397)). Sample count and exact stages unverified.

- **B5. Chea et al. 2024, Sci Adv 10(12):eadl4239, DOI 10.1126/sciadv.adl4239 ("Gastrulation-stage gene expression in Nipbl+/- mouse embryos").**
  - Snippet: scRNA-seq of WT and Nipbl+/- embryos at late bud (E7.5) and cardiac crescent (E7.75). Mesoderm depleted in mutants. Nanog overexpression is a likely driver of many changes ([Source](https://par.nsf.gov/servlets/purl/10503825)).
  - Heterozygous allele (haploinsufficiency), not a null. Accession not verified.

- **B6. Guzzetta et al. 2020, PNAS (PMID 32561646), "Hedgehog-FGF signaling axis patterns anterior mesoderm during gastrulation".**
  - Snippet: scRNA-seq of WT and Hh-mutant mesoderm at the end of gastrulation. Fewer anterior mesoderm lineages in mutants ([Source](https://www.pubmed.gov/32561646/)).
  - Snippet: GEO GSE149335 ([Source](https://pluto.bio/product/curated-data-sets/explore/experiment/gse149335-a-hedgehog-fgf-signaling-axis-patterns-anterior-mesoderm-during-gastrulation)). ENA PRJNA627968 covers the Fgf4/Fgf8 double-mutant experiment ([Source](https://www.omicsdi.org/dataset/omics_ena_project/PRJNA627968)).
  - Gene and allele for the Hh-mutant (for example, Smo) and stages unverified.

- **B7. Tbx6 spatial mutant embryos (Slide-seq). Nature Genetics 2023 (DOI from URL s41588-023-01435-6).**
  - Snippet: Slide-seq spatial maps of complete E8.5 and E9.0 embryos and partial E9.5 embryos, examining ectopic neural tubes in Tbx6 mutants ([Source](https://www.nature.com/articles/s41588-023-01435-6.pdf)).
  - Spatial, not single-cell. Accession, cell counts and matched wild-type design unverified. Stages are inside the allowed range.

- **B8. Chd7, cardiac neural crest.**
  - Snippet: GSE297891, single-cell profiling of Chd7-inactivated cardiac neural crest (SOX5 self-activation paper). Stage unverified ([Source](https://www.omicsdi.org/dataset/geo/GSE297891)).
  - Snippet: GSE229629, bulk RNA-seq of E9.5 cardiopharyngeal mesoderm from Mesp1-Cre;Chd7 fl/fl. Not single-cell ([Source](https://www.omicsdi.org/dataset/geo/GSE229629)).

- **B9. Tbx1 mutant heart time course, GSE198562.**
  - Snippet: scRNA-seq time course of heart development in Tbx1 mutant mice ([Source](https://www.omicsdi.org/dataset/geo/GSE198562)). Stages unverified.

- **B10. Hand1 myocardial knockout, GSE128571 / E-MTAB-7454.**
  - Snippet: E11.5 myocardial Hand1 knockout, bulk RNA-seq. Cre is Nkx2-5-Cre or alpha-MHC-Cre ([Source](https://www.omicsdi.org/dataset/geo/GSE128571)). E11.5 is in the forbidden window. Not single-cell, so no single-cell Hand1 mutant embryo was found.

- **B11. Bmp4 temporal, Hadas et al. (Nature, year unverified), GEO GSE267870.**
  - Snippet: about 68,000 cells from 287 individually processed embryos, plus extraembryonic tissue. Embryo-derived BMP4 from E7.5 onward ([Source](https://mskeducation.mskcc.org/mod/resource/view.php?id=2481); [GEO listing](https://omicsdi.org/dataset/geo/GSE267870)).
  - Allele and Cre (conditional or inducible) unverified. Some stages fall in the (E7.25, E8.0) window.

- **B12. Wls deletion in Mesp1+ cells (bioRxiv 10.1101/2021.01.31.428968, 2021).**
  - Snippet: Wnt secretion knocked out in Mesp1 lineage (Wls), with scRNA-seq of anterior and posterior SHF trajectories ([Source](https://www.biorxiv.org/content/10.1101/2021.01.31.428968v1.full.pdf)). Fetch returned 429; design and stages unverified.

- **B13. Notch and Etv2 and Foxh1 and Eomes (no embryonic single-cell knockout found).**
  - Etv2: EB-based and reporter-based scRNA-seq at E7.75 and E8.25 ([Source](https://link.springer.com/article/10.1038/s41598-019-45841-5)). No Etv2-null embryo single-cell dataset found.
  - Foxh1: original knockout dies during gestation; no single-cell dataset found (snippet, no URL identified).
  - Eomes: conditional Eomes allele lacks definitive endoderm (snippet, no URL identified). No single-cell dataset found.
  - Notch: Rbpj gain-of-function, 2015 Development (snippet). Single-cell status unverified. No Rbpj loss single-cell dataset found.

**C. Candidates that do not qualify as embryonic single-cell knockouts**

- **Isl1.** GSE123771 is Hdac3 deletion in Isl1 lineage, E9.5 whole heart (snippet). Not an Isl1 knockout, and probably bulk. No Isl1 null single-cell embryo found ([Source](https://omicsdi.org/dataset/geo/GSE123771)).
- **Tbx5 and Nkx2-5.** GSE77576 (ES-derived embryos, microarray) and GSE77547 (RNA-seq). GSE222373 is a neonatal Tbx5 knockout multiome, which is out of embryonic scope ([Source](https://www.omicsdi.org/dataset/geo/GSE222373)). GSE108961 is an Nkx2-5 enhancer deletion with scRNA-seq, not a null ([Source](https://www.omicsdi.org/dataset/geo/GSE108961)).
- **Tbx20.** No dataset found.
- **Smarcd3 (Baf60c).** Bulk and phenotypic only. Null embryos are recovered at E9.5 and survive to E12.5–13.5 ([Source](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC5829499/)). No single-cell dataset found.
- **Gata6.** No mouse-embryo single-cell knockout found. Gata6 is a close paralog of Gata4 (background knowledge; not verified in this session).
- **Hey1/Hey2.** Double mutants die near E9.5 (secondary source: [Source](https://en.wikipedia.org/wiki/HEY2)). No mouse single-cell dataset found.
- **Shh.** Not searched directly. The Hh-mutant study (B6) is the closest.
- **Mesp1 knockout.** Not searched directly.

### Inferences
- The chimera designs (A1, A3, A4, A5, A6) give the strongest matched wild-type controls, because the host cells sit in the same embryo. But their perturbation is cell-autonomous, so they test "response concentrated in the cells that express the gene" well and whole-embryo loss poorly. Cheng 2022 (A3) and Grosswendt 2020 (A2) are closer to whole-embryo loss.
- The closest design analogue to the held-out Mesp1-Cre conditional beta-catenin knockout is Sox17 Mesp1-Cre at E8.5 (B2). It shares the driver and stage range, but its platform is microarray, which limits transfer to count-based scoring.
- The Wls-in-Mesp1 study (B12) is the closest analogue to the held-out phenotype and is probably forbidden as a phenocopy. See Key Question 2.
- For gene-level priors, the only broad resource found is the IMPC E9.5 whole-embryo RNA-seq set (Key Question 3). No embryonic single-cell perturbation atlas spanning many genes was found.

### Gaps
- GEO records were unreachable in this session, so the accessions for GSE125321/GSE125322, GSE149335, GSE198562, GSE297891, GSE229629, GSE267870, GSE108961 and GSE123771 are unverified against GEO itself. GSE137337, GSE205917, GSE131181 and GSE125323 are verified from the paper text.
- Not verified for: de Soysa 2019 accession, Chea 2024 accession and cell counts, Guibentif journal and accession, Mittnenzweig accession and chimera stage, Strauss journal and stages, Muncie-Vasic stages and sample count, Guzzetta allele and stages, Tbx6 Slide-seq accession and design, Bmp4 Hadas design and year, Tbx1 time-course stages, Chd7 GSE297891 stages.
- Not searched in depth: Shh ligand, Mesp1 knockout, Tbx2, Eomes single-cell, Notch loss-of-function single-cell.
- Search index may miss 2026 publications.

---

## Key Question 2: Compliance flags per dataset

### Takeaway
Five datasets pass the genotype screen with no window problem: Tal1 chimeras (A1, E8.5), Grosswendt 2020 (A2, KO E8.5), Cheng 2022 (A3, E7.5 flag), Hand2 (B1, E7.75 flag) and Sox17 (B2, E8.5). Hill 2019 (Pitx2) and Hand1 are forbidden by stage. Wls-in-Mesp1 (B12) is forbidden as a phenocopy, pending organiser confirmation. The Regalado in vitro screen (C1) very likely contains Gata4 and probably canonical Tcf/Lef members, so it needs gene-level removal. Rule caveat: the data page says external single-cell training is allowed only for Task 1, so no dataset here is cleared for Task 3 until the organisers answer. Stages in the open interval (E7.25, E8.0) are flagged explicitly, as the task requires. Note: E7.25 and E8.0 themselves are bracketing stages and are permitted by the sibling-note rule reading.

### Rules applied
- Held-out for Task 3: the Gata4 and beta-catenin (Ctnnb1) knockouts at E8.75, any allele at a comparable stage, and any perturbation that phenocopies them ([Source](https://virtualembryo.ai/challenge/rules), quoted in the sibling note).
- Window: external data is excluded from after E9.5 up to and including E13.5. E9.5 exactly is permitted. E13.5 exactly is not ([Source](https://virtualembryo.ai/challenge/rules), quoted in the sibling note).
- Bracketing: embryo data strictly between E7.25 and E8.0 is treated as held out for interpolation targets. The bracketing stages are permitted ([Source](https://virtualembryo.ai/challenge/rules), quoted in the sibling note).
- Data-page conflict: the data page says external single-cell training is allowed only for Task 1. The rules text allows external data generally. Unresolved in the sibling note, which treats Tasks 2 and 3 external training as not cleared ([Source](https://virtualembryo.ai/challenge/data), quoted in the sibling note).
- Spanning resources: cells inside a held-out window must be removed before training and the removal described ([Source](https://virtualembryo.ai/challenge/rules), quoted in the sibling note).

### Cited Findings

| # | Dataset | Gene(s) | Stages | Flag: E7.25 < x < E8.0 | Flag: E9.5 < x <= E13.5 | Genotype screen (Gata4, Ctnnb1, phenocopy) | Flag |
|---|---|---|---|---|---|---|---|
| A1 | Pijuan-Sala atlas (WT) | none (WT reference) | E6.5–E8.5 | E7.5, E7.75 | none | n/a | SAFE, stage-flagged |
| A1 | Pijuan-Sala Tal1 chimeras | Tal1 | E8.5 | none | none | SAFE (not Wnt or Gata) | SAFE |
| A2 | Grosswendt 2020 zygotic KOs | 10 epigenetic regulators | KO E8.5; WT E6.5–E8.5 | WT E7.5, E7.75 | none | SAFE (no Wnt or Gata) | SAFE, stage-flagged (WT) |
| A3 | Cheng 2022 Tet TKO | Tet1/2/3 | E7.5–E8.5 | E7.5; ~E8.0 (borderline) | none | SAFE (Wnt not reported in text read) | SAFE, stage-flagged |
| A4 | Mittnenzweig 2021 Foxc1/2 chimeras | Foxc1, Foxc2 | E6.5–E8.25 | probable (in-band time points within E6.5–E8.25) | none | SAFE (no Wnt or Gata) | SAFE, stage-flagged; accession unverified |
| A5 | Guibentif 2021 T chimeras | T (Brachyury) | E7.5, E8.5 | E7.5 | none | RISKY: T is a direct TCF/beta-catenin target; posterior truncation overlaps with beta-catenin-loss phenotypes (background); genotype label conflict in E-MTAB-8811 | RISKY |
| A6 | Strauss Mixl1/T chimeras | Mixl1, T | unverified | unverified | unverified | Mixl1 provisional SAFE (Wnt/Nodal target, not a Wnt pathway gene); T as A5 | RISKY (T); stages unverified |
| B1 | de Soysa 2019 Hand2 | Hand2 | E7.75, E8.25, E9.25 | E7.75 | none | SAFE | SAFE, stage-flagged (E7.75) |
| B2 | Sox17 Mesp1-Cre | Sox17 | E8.5 (E9.5 morph.) | none | none | SAFE. Sox17 is reported to bind beta-catenin and act as an antagonist (background, unverified here), so loss is expected to increase Wnt rather than phenocopy its loss | SAFE (microarray platform) |
| B3 | Hill 2019 Pitx2 | Pitx2hd-/- | E10.5, E13.5 | none | both excluded | SAFE genotype | FORBIDDEN (stage) |
| B4 | Muncie-Vasic 2025 Mef2c | Mef2c-null | not stated | unknown | unknown | SAFE genotype | UNVERIFIED stage (hold until checked) |
| B5 | Chea 2024 Nipbl+/- | Nipbl (het) | E7.5, E7.75 | E7.5, E7.75 | none | SAFE (heterozygous; different allele type) | SAFE, stage-flagged |
| B6 | Guzzetta 2020 Hh-mutant | Hh pathway (gene unverified) | end of gastrulation | probable | none | SAFE (Hh is not Wnt) | SAFE, stage-flag probable; allele unverified |
| B7 | Tbx6 Slide-seq (Nat Genet 2023) | Tbx6 | E8.5, E9.0 (partial E9.5) | none | none | SAFE genotype | SAFE (accession and design unverified) |
| B8 | Chd7 cardiac NCC sc (GSE297891) | Chd7 | unknown | unknown | unknown | SAFE genotype | UNVERIFIED stage |
| B8 | Chd7 Mesp1-Cre bulk (GSE229629) | Chd7 | E9.5 | none | none | SAFE genotype | SAFE (bulk, not single-cell) |
| B9 | Tbx1 time course (GSE198562) | Tbx1 | unknown | unknown | unknown (time course; may extend past E9.5) | SAFE genotype | UNVERIFIED (check for stages > E9.5) |
| B10 | Hand1 myocardial KO (GSE128571) | Hand1 | E11.5 | none | E11.5 excluded | SAFE genotype | FORBIDDEN (stage); bulk |
| B11 | Bmp4 temporal (GSE267870) | Bmp4 (allele unverified) | E6.5–E8.5 (probable) | probable | unknown | SAFE (BMP/Smad is not Wnt) | SAFE, stage-flagged; design unverified |
| B12 | Wls in Mesp1+ cells (bioRxiv 2021) | Wls (Wnt secretion) | ~E8 (unverified) | probable | none | FORBIDDEN as a phenocopy (proposed): removes Wnt ligand secretion in the same Mesp1 lineage as the held-out knockout. Conservative call | FORBIDDEN (phenocopy, pending organisers) |
| C1 | Regalado 2025 in vitro TF screen (EB day 21) | 1,644 TFs; includes Gata4 (very likely) and probably canonical Tcf/Lef members | not embryo stage | n/a | n/a | Contains forbidden genes; must be removed gene-by-gene | RISKY (usable only after removing Gata4 and Wnt-pathway TFs) |
| C2 | IMPC E9.5 whole-embryo RNA-seq | 73 mutant lines | E9.5 (exact) | none | none (E9.5 permitted) | Must screen each line | RISKY per line (bulk; accession unverified) |

Notes for the table:
- The E7.25 and E8.0 bracket stages are permitted. The flagged in-band stages are E7.5 and E7.75 in most datasets, plus any fractional stage such as 7.6.
- E8.5 is a held-out stage for Task 2 heart in the sibling note. For Task 3 it is not blocked by the stage letter, but the sibling note flags it as unresolved if the held-out status is task-wide.
- No candidate is at exactly E8.75, the held-out Task 3 stage. The released WT reference stages for Task 3 are E8.75 and E9.5 (data page, quoted in the sibling note).

### Inferences
- Five datasets pass the genotype screen and carry no window problem: A1 Tal1 (E8.5), A2 Grosswendt (KO E8.5), A3 Cheng (E7.5–E8.5, flagged), B1 Hand2 (flagged at E7.75), B2 Sox17 (E8.5). Each is still blocked for Task 3 by the data-page conflict until resolved.
- The Gata6 and Tcf/Lef/Wls/Wnt-secretion families are the phenocopy risks. Only Wls is a clear hit in the search results. Canonical Wnt ligands and Lef/Tcf loss are not present in any candidate found, except inside the Regalado TF library (C1).
- Hand1 and Pitx2 would be the most informative heart knockouts, but both are excluded by the window. Their datasets cannot be used for Task 3.

### Gaps
- Stage for B4 (Mef2c), B9 (Tbx1), B8 (Chd7 sc), A6 (Strauss) and B7 (Tbx6 Slide-seq) is unverified.
- The Wls (B12) design, Guzzetta (B6) allele, and Bmp4 (B11) allele are unverified.
- Organiser confirmation needed: (1) whether external single-cell training is allowed for Task 3 at all, given the data-page conflict; (2) whether Wls loss counts as a phenocopy; (3) whether E8.5 held-out status is task-wide; (4) whether a bulk E9.5 source (C2) counts as external training data.

---

## Key Question 3: Gene-level and perturbation-level priors

### Takeaway
A gene-level prior is available from the IMPC E9.5 whole-embryo RNA-seq set (73 mutant lines, more than 1,000 transcriptomes, with an E9.5 wild-type baseline by somite count) and from the in vitro Regalado 2025 TF screen (1,644 TFs, 190,387 cells). Both are usable only after gene-level screening for Gata4, Ctnnb1 and phenocopy genes. No embryonic single-cell cross-gene atlas was found.

### Cited Findings
- **IMPC E9.5 whole-embryo RNA-seq.** 73 mutant lines, more than 1,000 transcriptomes, WT baseline across 4 to 36 somites, available in Expression Atlas (snippet; paper not identified in the search output, probably Nat Commun 2019, DOI 10.1038/s41467-019-10642-x, unverified) ([Source](https://www.mousephenotype.org)). Portal: https://www.mousephenotype.org.
- **IMPC pre-E9.5 lethal lines.** Preprint of 21 pre-E9.5 lethal lines. Most phenotypes fall between implantation and gastrulation. Not peer reviewed at the time of the snippet ([Source](https://www.biorxiv.org/content/10.1101/2020.10.08.331587.full.pdf)).
- **Regalado et al. 2025 bioRxiv (DOI 10.1101/2025.05.23.655669; PMC12139999, PMID 40475436).** Verified (text): pooled CROP-seq screen of 1,644 DNA- or RNA-binding genes (three gRNAs each plus non-targeting controls) in mosaic embryoid bodies from mouse ES cells at day 21. 190,387 cells (10x 3' v3). 140,129 with gRNA assignment. EB profiles compared with E6.5–8.5 and E8–10 embryo atlases. No accession found in the text read ([Source](https://pmc.ncbi.nlm.nih.gov/articles/PMC12139999)).
- **MGI expression data (GXD).** Aggregated expression, not knockout data (example: [Source](https://www.informatics.jax.org/assay/MGI:1340265)). Prior only.

### Inferences
- The Regalado screen is the only broad single-cell perturbation resource found. It is in vitro, its EB day labels do not map cleanly to embryonic stages, and it contains Gata4 and probably canonical Tcf/Lef TFs. It would need per-gene removal.
- The IMPC E9.5 set is bulk, but it gives a broad gene-level direction prior at E9.5, which is an allowed stage. Each line needs a genotype screen.

### Gaps
- Regalado accession and per-gene library list not found.
- IMPC expression data accession and the exact paper not identified.
- No embryonic single-cell perturbation atlas spanning many genes found.
