# Research notes (round 2)

Started from the supplied round 1 checkpoint. The file reproduces round 1 s060's quantile model. Round 1's written final handoff describes s069, which scored 65.082 and used a separate in-bracket branch. The starting point for comparisons here is the delivered file and round 2 s001.

## Validation

The two splits share the same E10.5 specimen. Scores are means over three scoring seeds per split. Differences of a few tenths require split agreement or support from a released-stage backcast.

| Snapshot | Parent | Mean | Full | Chamber | Experiment |
|---|---|---:|---:|---:|---|
| s001 | Round 1 s060 | 65.112 | 64.580 | 65.643 | Reproduced the delivered baseline. |
| s002 | s001 | 65.098 | 64.640 | 65.557 | Predicted transcript gains from low-rank, exposure-adjusted count factors. Conserved per-gene gain budgets within lineages. Both splits moved by less than 0.1 in opposite directions. Reverted. |
| s003 | s001 | 65.067 | 64.613 | 65.520 | Weighted the bulk mixture correction by inferred RNA mass per lineage. The full change was negligible and the chamber score fell 0.123. Reverted. |
| s004 | s001 | 65.125 | 64.580 | 65.670 | Estimated changes in concentration heterogeneity from count factorial moments and used them to split downregulation into molecule loss and cell-level silencing. The official difference was 0.013 overall. |
| s005 | s001 | 65.083 | 64.833 | 65.333 | Smoothed lineage-level spatial growth across local interfaces. Full D2 improved 2.9 points. Chamber occupancy and neighbourhood skill fell. Reverted for the joint model. |
| s006 | s001 | 64.877 | 64.450 | 65.303 | Estimated curvature from E14.5–E15.5 lineage contrasts while conserving the existing E9.5–E14.5 endpoint contrast. Cell and neighbourhood MMD fell on both splits. Reverted the clock. |
| s008 | s001 | 65.228 | 64.793 | 65.663 | Estimated conditional single-cell contrasts with balanced replicate means and shrank genes with inconsistent changes. Cell MMD rose 0.9 full and 0.7 chamber. Overall chamber change was 0.020. Provisional parent with mixed backcast evidence. |
| s009 | s001 | 64.560 | 65.030 | 64.090 | Reweighted founder sites using within-lineage local cycling evidence at matched depth. Full score rose 0.450 and chamber D2 lost 14.7 points. Backcast cell and neighbourhood MMD also rose in both protocols. Reverted. |
| s010 | s001 | 64.558 | 64.937 | 64.180 | Ordered donor sampling with a spatial Morton key within each lineage. Full neighbourhood skill rose 1.5 and chamber D2 fell 13.3. Reverted. |
| s011 | s008 | 65.253 | 64.860 | 65.647 | Removed the native trend component parallel to the independent maturation prior. The mean change was 0.025 and the splits disagreed. Retained the s008 expression model for comparisons. |
| s012 | s008 | 64.643 | 64.217 | 65.070 | Fit the sliced spatial deformation to weighted quantiles of the complete scaffold. Both splits fell. Restored the compact scaffold fit. |
| s013 | s008 | 65.203 | 64.780 | 65.627 | Estimated within-lineage atlas changes from local expression averages. Both scores moved slightly down. Restored the lineage-level contrast. |
| s014 | s008 | 65.188 | 64.787 | 65.590 | Reallocated some expression to spatial peers advancing along native maturation and debited the realized shift from count turnover. Neither split improved. Reverted. |
| s016 | s008 | 64.780 | 64.323 | 65.237 | Blended the bulk expression direction with an expression-only contrast from the 10x atlas at matched cell composition. Both splits lost cell and neighbourhood MMD. Reverted. |
| s017 | s008 | 63.260 | 63.200 | 63.320 | Used hypergeometric probe rarefaction at common inferred exposure for donor diversity selection. Variogram and neighbourhood skill fell in both splits. Retained the measured detection-depth tilt. |
| s018 | s008 | 65.225 | 64.857 | 65.593 | Removed an independent Slide-seq biological contrast from the surrounding-tissue capture controls. Changes were small and opposite across splits. Restored the original controls. |
| s019 | s008 | 65.195 | 64.860 | 65.530 | Added the part of the independent Slide-seq contrast outside the measured native direction for surrounding lineages. A 0.067 full gain coincided with a 0.133 chamber loss. Reverted. |
| s020 | s008 | 65.205 | 64.807 | 65.603 | Learnt molecular substates within input lineages after regressing detection depth, then continued changes in matched substate contrasts. The splits moved by 0.014 and −0.060. Restored the simpler lineage model. |
| s021 | s008 | 65.168 | 65.050 | 65.287 | Assigned at most one epicardial descendant to each potential surface site in a draw. Full D2 improved and chamber D2 and neighbourhood skill fell. Reverted. |
| s022 | s008 | 65.165 | 64.657 | 65.673 | Fit bulk curvature with RNA-seq contrasts from a single assay, then used it with the combined maturation direction. The full and chamber scores moved by −0.137 and 0.010. Reverted the shared-clock change. |
| s023 | s008 | 65.217 | 64.783 | 65.650 | Correlated the Poisson gain draws with an exposure-adjusted native count copula. The full and chamber scores were essentially flat. Reverted the slower sampler. |
| s024 | s008 | 65.127 | 64.653 | 65.600 | Fit RNA-seq and ventricular-array clocks independently using their late same-assay replicates. Combined at the inherited total dose. Both splits declined. Reverted. |
| s025 | s008 | 65.205 | 64.797 | 65.613 | Sampled early-to-late metacell transition branches by native spatial patch. Variogram rose slightly and DE skill declined. Totals showed no consistent gain. Reverted. |
| s026 | s008 | 65.195 | 64.727 | 65.663 | Propagated cardiac expansion into nearby surrounding tissue with a distance-decaying displacement. Full occupancy rose 1.8 points and D2 fell 2.8. Restored the inherited deformation. |
| s027 | s008 | 65.207 | 64.763 | 65.650 | Routed expected positive molecule changes through exposure-adjusted structural activation. Both split totals were slightly lower. Kept the simpler count process. |
| s028 | s008 | 65.250 | 64.687 | 65.813 | Mapped single-cell contrasts into the in situ assay with a regularized transform estimated from age-matched lineage means. Chamber neighbourhood improved 0.5 points. Full total fell 0.106. Retained s008 pending a more specific variant. |
| s029 | s008 | 65.348 | 65.223 | 65.473 | Forecast relative lineage spread for geometric expansion. Full D2 rose 4.0 points and full total rose 0.430. Chamber total fell 0.190. Test whether the gain transfers when used with the surrounding field. |
| s030 | s008 | 65.443 | 65.223 | 65.663 | Applied the relative extent model to complete tissue fields, where the surrounding compartments are represented. The full gain survived and the chamber score reproduced s008. Advanced after the E12.5 check. |
| s032 | s030 | 65.473 | 65.300 | 65.647 | Let recurrent, ancestry-matched native expression changes revise the bulk target outside its independent maturation axis. The full increment was 0.077 and the chamber increment was −0.016. Keep s030 as the parent. |
| s033 | s030 | 65.482 | 65.260 | 65.703 | Matched regional expression residuals across whole tissue patches after accounting for their lineage mixture. Both splits gained about 0.04 points. Both backcast neighbourhood errors declined across five draws at reduced input coverage. |
| s034 | s030 | 65.368 | 65.120 | 65.617 | Used iterative proportional fitting to satisfy the bulk and lineage mean constraints while keeping forecast molecule budgets. Both splits declined slightly. Reverted. |
| s035 | s030 | 65.378 | 65.210 | 65.547 | Used cross-assay alignment only for differences among cardiac lineages, conserving their shared molecule forecast. Chamber cell MMD and neighbourhood fell. Reverted. |
| s037 | s033 | 65.487 | 65.293 | 65.680 | Pooled evidence for developmental curvature over functional gene neighbours at the inherited total dose. The mean shifted 0.005 with opposite split changes. Restored the simpler clock. |
| s038 | s033 | 65.477 | 65.310 | 65.643 | Conditioned the bulk clock on matched native heart changes and used an additive time integral below the reference interval. Full and chamber changes were small and opposite. No evidence to replace s033. |
| s039 | s033 | 65.403 | 65.333 | 65.473 | Removed the inherited within-lineage spatial autocorrelation forecast, leaving the new regional patch term. Chamber neighbourhood and total skill declined. Kept both terms. |
| s040 | s033 | 65.512 | 65.343 | 65.680 | Restricted the surrounding-tissue bulk response to probes shared with the heart while preserving the response dose. Full rose 0.083 and chamber fell 0.023. Run a transfer comparison before selection. |
| s041 | s033 | 65.403 | 65.170 | 65.637 | Used earlier, exposure-adjusted native cell states to guide placement of new transcripts. Both splits lost and runtime rose. Reverted. |
| s042 | s033 | 65.388 | 65.073 | 65.703 | Smoothed expansion only where native cardiac and surrounding cells meet. Full D2 fell 2.3 points despite slightly higher occupancy. Reverted. |
| s043 | s033 | 64.692 | 65.507 | 63.877 | Required fine annotations to have support within each coarse lineage. Full score rose 0.247, but resampling altered chamber shape and D2 fell 19.4. Keep the native geometry labels and isolate the small-lineage issue in expression matching. |
| s044 | s033 | 65.325 | 65.247 | 65.403 | Shrunk small fine-label signatures toward their coarse lineages for expression matching while retaining the native sampler. Chamber state and neighbourhood skill fell. Reverted. |
| s045 | s033 | 65.530 | 65.340 | 65.720 | Added matched regional maturation from independent E9.5 and E14.5 spatial sections. Both scores rose modestly. Check reduced-coverage transfer before adopting the spatial reference. |
| s046 | s033 | 65.380 | 65.273 | 65.487 | Imposed an independent ventricular expression constraint at fixed whole-heart molecular mass. Full was close to its parent and chamber cell MMD and variogram fell. Reverted. |
| s048 | s033 | 65.498 | 65.417 | 65.580 | Fit saturating induction windows at matched bulk dose. Full gained 0.157 and chamber fell 0.123. Retained the simpler inherited clock. |
| s049 | s033 | 65.468 | 65.273 | 65.663 | Fit two latent maturation states from native molecule counts, then routed part of the forecast through state transitions at fixed lineage means. Scores were flat to lower. Reverted. |
| s050 | s033 | 65.403 | 65.323 | 65.483 | Applied successive count updates with changing latent rates and lineage means. The full score barely moved and chamber DE and cell MMD fell. Reverted to the single transition. |
| s051 | s033 | 65.240 | 64.887 | 65.593 | Allocated integer transcripts by transport at the inherited per-cell molecule budget. Variogram improved, but neighbourhood skill fell in both dissections. Reverted. |
| s052 | s033 | 65.490 | 65.297 | 65.683 | Assigned independently predicted subtype growth to nearby expression donors at unchanged physical positions. Chamber cell MMD improved 0.2 points and DE skill fell 0.7. Overall change was 0.008 and the splits differed. Reverted the extra donor reassignment. |
| s053 | s045 | 65.530 | 65.340 | 65.720 | Added support for bracketed queries and unknown annotation vocabularies. Standard official extrapolation exactly reproduced s045 on both splits. |

| Baseline metric | Full | Chamber |
|---|---:|---:|
| DE score | 57.1 | 65.7 |
| DE direction | 59.3 | 63.1 |
| Cell MMD | 63.7 | 52.0 |
| Variogram | 60.5 | 55.5 |
| Pair-distance shape | 65.5 | 92.5 |
| Occupancy | 52.3 | 50.0 |
| Scale | 99.5 | 97.8 |
| Neighbourhood MMD | 65.2 | 64.6 |

## Released-embryo diagnostics

The native count lattice gave median total panel molecules of 238, 132 and 74 across the three training specimens. The fifth percentiles were 69, 23 and 34. The decline was shared by heart and surrounding lineages, with a changing lower tail. In the three-draw E8.25/E8.75 → E9.5 backcast, s001 predicted 47.7 and 50.9 mean detected genes for the full and chamber protocols. The observations had 38.8 and 39.2. This check uses independent E9.5 anchors inherited from round 0. It informs transfer comparisons and cannot resolve how much of the across-embryo depth shift reflects capture.

Only three canonical cycling markers intersect the panel. Their detection ranges from 69% of chamber cells in the earliest input to 22% in the latest, alongside a change in capture depth. I used the broader, independently predicted maturation programme for the within-lineage phase mixture experiment.

s004 reduced backcast cell MMD from 0.03573 to 0.03547 in the full field and from 0.04129 to 0.04107 in chambers. Chamber neighbourhood MMD rose from 0.11413 to 0.11462. This is mixed evidence at the observed scale of the effect. s006 passed the E12.5 execution check. Its backcast neighbourhood MMD increased to 0.09707 and 0.11498 from 0.09675 and 0.11413.

s008 backcast direction agreement rose from 0.2202 to 0.2270 in the full field and from 0.7323 to 0.7345 in chambers. Neighbourhood MMD was 0.09657 and 0.11414. Variogram error rose slightly in both protocols. This remains a small and mixed change on released embryos.

The exact s008, s030, s033, s045 and s053 predictors passed the E12.5 execution check.

At 55% latest-input coverage, s030 preserved full-field molecular scores across five draws. Full-field neighbourhood MMD was 0.09409 versus 0.09413 for s008, while normalized pair-distance error was 0.05010 versus 0.04980. The released-stage geometry changes were small.

At 40% latest-input coverage across five draws, s033 reduced neighbourhood MMD from 0.09408 to 0.09297 in the full dissection and from 0.11376 to 0.11260 in chambers. Cell MMD and variogram error also fell slightly in both protocols. Geometry reproduced s030.

At 55% coverage, the s040 mean niche errors were 0.09274 full and 0.11212 chamber versus 0.09303 and 0.11202 for s033. This matched the direction of the small split disagreement in validation.

At 55% coverage, the s045 neighbourhood errors were 0.09320 full and 0.11186 chamber versus 0.09303 and 0.11202 for s033. The external patch effect is small and the released-stage evidence is mixed.

The compatibility revision recovers an unknown annotation from other supplied stages when possible. When every label vocabulary is unfamiliar, it compares the observed expression groups with cardiac and noncardiac states from the eligible Slide-seq sections. A completely unannotated specimen first uses joint expression and spatial clustering. With 8,500 cells sampled per released embryo, the E9.5 chamber-mask Jaccard was 0.852 when only its labels were renamed, 0.742 when all labels were renamed and 0.647 when all were removed. This is an approximate recovery of the labelled chamber set. Both protocols passed local checks for two and five inputs, reordered genes, missing labels, repeated seeds, bracketed queries and long horizons. Standard extrapolation reproduced s045 exactly on those inputs.

The bracketed-query branch uses a proper rotation between enclosing inputs, aligned by matched type landmarks where available, and interpolates densely sampled native cells at the requested dissection. On the five-draw E8.25/E9.5 → E8.75 diagnostic, full cell and neighbourhood MMD fell from 0.05636/0.13256 to 0.03360/0.11773. Chamber errors fell from 0.03361/0.08884 to 0.02165/0.06665. Normalized pair-distance error fell in both modes. Chamber size error rose from 0.01247 to 0.13490.

On the three-draw backcast at native coverage, the s028 assay transform improved chamber cell MMD from 0.04149 to 0.03999 and neighbourhood MMD from 0.11414 to 0.11139. Full errors moved from 0.03586/0.09657 to 0.03566/0.09589. This contrasts with the small full validation loss and motivates preserving the shared bulk composition when transferring the within-lineage correction.

The released-stage diagnostic supplied the true E9.5 mean profile per supported anatomical role to the count generator, holding positions and donor lineage mix fixed. That reduced cell MMD from 0.03586/0.04149 to 0.01226/0.01570 and neighbourhood MMD from 0.09657/0.11414 to 0.04811/0.06417, full/chamber. Replacing the inferred molecule-budget quantiles alone increased detected genes and distributional errors. These are diagnostic uses of the released E9.5 observation. The official predictor receives only its supplied inputs.

## References

- I used the public metric implementations to interpret how gain placement affects cell-state MMD, the variogram and the neighbourhood distribution. [T2 metrics](https://github.com/aristoteleo/veckit/blob/main/T2/metrics.py) · [Core metrics](https://github.com/aristoteleo/veckit/blob/main/common/core_metrics.py)
- The previous rounds' evaluations and reference asset provenance are recorded in [round 0](history/r00_NOTES.md) and [round 1](history/r01_NOTES.md). I consulted the supplied heart knowledge bank and public method journal for prior failures around geometry extrapolation, depth changes and cross-assay donor replacement. [Public method journal](https://github.com/wqty123/virtual-embryo-challenge-methods/blob/main/experiments_t2_heart_extrap.en.md)
- Epicardial and endocardial derivatives arise along different surfaces and meet other lineages at the atrioventricular junction. I used this qualitative anatomy to motivate continuous growth across a shared interface and to keep the inner and outer wall spatial models distinct. [Epicardial lineage study](https://pmc.ncbi.nlm.nih.gov/articles/PMC4051323/) · [Early cardiac lineage tracing](https://doi.org/10.1016/j.devcel.2025.05.002)
- Spatially balanced sampling and space-filling curve resampling motivate preserving lineage and local tissue mass when selecting a finite donor population. [Stevens and Olsen](https://doi.org/10.1198/016214504000000250) · [Gerber, Chopin and Whiteley](https://arxiv.org/abs/1707.01845)
- scDesign3's count-marginal and copula formulation motivates a gain model with correlated transcript responses and the same marginal Poisson rates. [Song et al.](https://doi.org/10.1038/s41587-023-01772-1)
- Cross-technology integration through shared expression contrasts motivates estimating the assay translation within cardiac populations and validating it on held-out lineages. [Butler et al.](https://doi.org/10.1038/nbt.4096) · [Haghverdi et al.](https://doi.org/10.1038/nbt.4091)

### Independent lineage reference

I processed seven individually age-labelled whole-heart 10x matrices. The early group is wild-type E9.5 GSM7999705–07. The late groups are E14.5 GSM6211349 and GSM6793114 and E15.5 GSM6211350 and GSM6793115. I restricted counts to the 500 probes and retained cells with at least 20 panel molecules. I used both age-specific clustering and a shared lineage projection trained on the inherited E14.5 metacell assignments. The asset stores per-replicate metacell means and support. Individual stage counts after filtering were 1,187, 5,392 and 3,669 at E9.5, 3,997 and 23,700 at E14.5, and 4,974 and 11,999 at E15.5. I use distinct replicates to estimate agreement before transferring rates. [E9.5 study](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE252341) · [E14.5 and E15.5 study](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE205394) · [E15.5 replicate 1](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSM6211350) · [E15.5 replicate 2](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSM6793115)

### Independent early spatial reference

I opened only separately staged E9.0 and E9.5 arrays from the Slide-seq collection. A section had to contain at least 30 beads annotated as Heart. I retained panel counts from each heart and nearby tissues out to one within-section heart RMS radius, then aggregated by the original state annotation. This gave 610 state-by-section summaries from 110,281 beads in 23 E9.0 sections, and 189 summaries from 39,267 beads in 13 E9.5 sections. The section summaries estimate sampling variation across a small number of embryos. [Kumar, Tian, Bolondi et al.](https://doi.org/10.1038/s41588-023-01435-6) · [Stage-separated CELLxGENE arrays](https://cellxgene.cziscience.com/collections/d74b6979-efba-47cd-990a-9d80ccf29055)

The later spatial comparison used the 13 eligible E9.5 Slide-seq arrays and the stage-separated CD1 wild-type E14.5 Visium sample GSM8645799. I grouped only Heart-labelled beads in the younger sections and in-tissue spots in the two large connected Visium sections. This yielded 140 early patches from 5,720 beads and 17 late patches from 446 spots. Each reference uses spatially aggregated panel counts. I treated the age-specific difference in average probe levels as an assay offset when comparing regional enrichments. [Visium study](https://doi.org/10.1038/s42003-026-10259-z) · [E14.5 raw data](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSM8645799)

### Independent ventricular timing

I processed 18 individually verified raw ventricular arrays from GSE51483. The three left and three right samples per age were GSM1246314–19 at E9.5, GSM1246326–31 at E14.5 and GSM1246332–37 at E18.5. Quantile normalization used only those arrays. I mapped perfect-match probe coordinates through the Entrez-based mouse array annotation and used panel-gene medians after soft background correction. The E9.5–E14.5 directions correlated 0.942 and 0.948 with the inherited left and right contrasts across 466 shared probes. [GSE51483](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE51483) · [Probe map](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GPL29970) · [NCBI mouse gene symbols](https://ftp.ncbi.nlm.nih.gov/gene/DATA/GENE_INFO/Mammalia/Mus_musculus.gene_info.gz)

### Functional annotation

For the functional clock trial I propagated stage-independent mouse biological-process annotations through the GO `is_a` hierarchy. I excluded expression-pattern evidence, electronic inference and negated associations. The May 21, 2026 MGI GAF and ontology release 2026-07-26 yielded 1,607 distinct panel gene groups, covering 465 probes. The functional groups are independent of developmental expression measurements. [MGI annotations](https://current.geneontology.org/annotations/mgi.gaf.gz) · [GO ontology](https://purl.obolibrary.org/obo/go/go-basic.obo) · [GO consortium](https://doi.org/10.1093/genetics/iyad031)
