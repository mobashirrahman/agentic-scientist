# Knowledge bank

## Established (held up; effect sizes and cycles)

- **CONFIRMED — Temporal maturation.** Clipped, horizon-damped drift on positive nonglobin entries blends local/type means 50:50 over two stages with ≥100 rows/type/stage. Fixed k=50 and adaptive k=50–150 gave temporal Δ +.585 and +.599 [+.573,+.626] vs seed. Widening alone gave +.014 [+.008,+.020]. [w0_c00] [w0_c03]
- **CONFIRMED — Heart crop and growth.** Label/third-nearest cardiac-anchor crop and isotropic growth gave heart Δ +11.092, neighborhood MMD/MMD-U/scale +8.65/+8.93/−1.08. Use centroid-centered median log-RMS slopes from ≤3 stages, clipped to [0,.45]/day, damped by .8, horizon ≤3 days. A ventricular-radius floor added heart Δ +.552 and dissected scale Δ +11.92/+14.57. [w2_c00] [w2_c01]
- **CONFIRMED — Heart crop variants.** Landmark, ordering and two-hop contact packages gave heart Δ +10.278/+10.44/+10.27 vs seed. Added terms gave dissected neighborhood MMD Δ −.093/−.109/+.004 vs matched controls, short of +.80. [w2_c08] [w2_c09] [w2_c10]
- **CONFIRMED — Occupied-volume growth.** Extrapolate log(row count^(1/3) × median 15th-other-neighbor distance) from two crops, with slope [0,.45]/day, horizon ≤3 days, expansion ≤2×. Heart Δ +.527 vs crop parent, +.172 vs matched RMS. Scale Δ +6.26/+19.01. [w2_c07]
- **CONFIRMED — Hard-crop heart donors.** With full-input RMS and a 20% pseudobulk offset, post-blend label-only and vascular crops gave heart Δ +1.699/+1.730 vs soft sampling. Mask and renormalize composition weights before enrichment for heart Δ +2.101, neighborhood MMD/MMD-U/variogram/Dice Δ +1.75/+3.26/+2.63/−7.14. Vs row-matched post-blend crop, heart Δ +.389, Dice/neighborhood MMD +1.63/+.71. [w4_c00] [w4_c02] [w4_c05]
- **CONFIRMED — Heart depth matching.** Match extrapolated depth among 32 local same-label intact rows. Heart Δ +.743, depth p90 −6.26/−12.50 genes, neighborhood MMD +.84 vs parent/+4.26 vs shuffle. [w2_c04]
- **CONFIRMED — Intact embryo depth matching at fixed occupancy.** Embryo Δ, then variogram/neighborhood MMD/MMD-U Δ.
  - Scaffold-weighted Gaussian same-type sampling +5.498, +17.60/+2.82/+6.59. [w3_c01]
  - Same-type endpoint log-depth matching +5.651, +22.22/+1.50/+5.29. Depth p90 80–82→37–38 vs 30. [w3_c02]
  - Within-lineage interpolation with ≤63 donors +3.569, +9.32/+2.77/+5.57. Embryo/neighborhood MMD Δ −.27/−.314 vs pooled depth. [w3_c05]
  - Shared-label E8.0 matching +2.136, +5.28/+1.93/+2.97. Depth-only control reproduced gain. [w5_c03]
  - Later states without shared labels +1.816, +6.0/+1.7/+.9. [w5_c04]
- **CONFIRMED — Fixed-slot embryo reassignment.** Swap intact depth-matched rows and metadata to target variance of 15-neighbor means within focal-expression limits. Embryo Δ +.859, neighborhood MMD/MMD-U/variogram +2.50/+.21/−.23. Dev neighborhood MMD +.33 vs centroid. [w3_c06]

## Dead ends (and the condition under which a retry is justified)

- **NEGATIVE — Temporal growth shrinkage and conditional drift.** Temporal Δ −1.068 [−1.319,−.818]. Retry with label maps that distinguish relabeling from growth. Expressing-cell drift Δ −.138 [−.164,−.113]. Retry with a replicated direction beating magnitude control (Δ −.012). [w0_c02] [w0_c04]
- **NEGATIVE — Embryo dispersion and equal-depth replacement.** Embryo Δ −.560 [−.582,−.538] and −2.778 [−3.050,−2.506]. Retry dispersion with ≥2 genes of local p90 gap closure plus neighborhood MMD gains vs parent/focal-only. Retry replacement with positive board Δ, ≥+.80 neighborhood MMD vs cell-only and ≤.50 losses per distribution skill. [w5_c10] [w5_c06]
- **NEGATIVE — Embryo adjacency and deduplication.** Embryo Δ −.028 [−.048,−.008] for adjacency and −.173 for deduplication (−.069 locally). Retry at ≥+.80 neighborhood MMD vs matched placement for adjacency, or if deduplication improves neighborhood MMD and variogram at fixed depth/occupancy. [w5_c05] [w3_c04]
- **NEGATIVE — Heart offset edits and progenitor exclusion.** Heart Δ −.00667/−.01729/−.513 for shared-drift subtraction, mask preservation and aPHM/pPHM exclusion. Retry with gains vs matched shrinkage or unshifted rows, or with narrower dissection evidence and density parity, respectively. [w4_c04] [w4_c03] [w2_c05]
- **NEGATIVE — Intact WT resampling for knockout calibration.** Perturbation Δ −.0393 [−.0512,−.0275]. Retry with MMD-U/variogram gains at fixed means/quotas and preserved DE/severity. [w1_c04]

## Promising / inconclusive leads

- **INCONCLUSIVE — Heart sampling refinements.** Local spacing, vascular rim and ventricular tilt gave heart Δ −.040 [−.215,+.135], −.071 [−.153,+.011] and −.020 [−.196,+.157]. Vascular vs label-only Δ +.031 (lower −.150), neighborhood MMD −2.68. Removing within-crop tilt gave heart Δ −.078 [−.225,+.070], E8.75 Dice/split −4.23/−.697. [w2_c06] [w2_c02] [w2_c03] [w4_c02] [w4_c08]
- **Heart offset refinements.** PROMISING depth-specific drift gave heart Δ +.265 [+.261,+.270] and neighborhood MMD +.484 vs magnitude control. Quartering the full offset gave +.051, E9.5 Δ −.255. Residual-only quartering was INCONCLUSIVE, heart Δ +.00042 [−.00370,+.00453]. [w4_c06] [w4_c01] [w4_c07]
- **PROMISING — Temporal detection additions.** Temporal Δ +.046 [+.031,+.062], short of +.25. [w0_c01]
- **PROMISING — Embryo placement.** Same-type density and assembled context gave embryo Δ +.289/+.513 (lower bounds +.20/+.44), neighborhood MMD +.56/+.61 vs expression-only/centroid. Other variants +.016 to +.383. [w3_c11] [w5_c01] [w3_c00] [w5_c00] [w5_c02] [w3_c03] [w3_c07] [w5_c07] [w5_c08]
- **INCONCLUSIVE — Embryo refinements.** Embryo Δ for interface −.0011 [−.0151,+.0129], covariance −.0006 [−.0136,+.0125], fractional ranking −.003 [−.107,+.100], local depth cap −.041 [−.128,+.046], marker ranking +.001 [−.074,+.076] and half-depth jump −.027 [−.099,+.044]. [w5_c11] [w5_c09] [w5_c03] [w3_c08] [w3_c09] [w3_c10]
- **PROMISING — Knockout delay and calibration.** Earlier depth-matched WT donors gave perturbation Δ +.608 [+.28,+.93], Gata4/Hand2/Mef2c Δ −2.36/−.96/+5.75. Ridge delay gave +.689 [+.38,+1.00], Hand2 −.287. Expected WT amplitude gave +.666 [+.17,+1.17], distribution contribution −.038. Calibration, trend allocation and positive-expression spread gave +.012/+.027/+.00052. Cross-fitted stage odds gave +.349 [+.07,+.63], with 1.23% held-out Mef2c coverage, gain +.639→+.023 without Mab21l2 (4 pairs). [w1_c01] [w1_c03] [w1_c02] [w1_c00] [w1_c05] [w1_c07] [w1_c08]
- **INCONCLUSIVE — Knockout composition bridge and GO rotation.** Perturbation Δ −.511 [−1.34,+.31] and +.051 [−.03,+.13]. Bridge Mab21l2 severity −3.72. GO DE direction −.018 vs shuffle. [w1_c06] [w1_c09]
- **INCONCLUSIVE — Knockout delay spread.** WT donor reweighting within lineage/depth closed 9% of earlier/latest mixture variance gap at fixed mass and projected mean. Perturbation Δ −.225 [−.757,+.308], n=8, other boards Δ 0. Matched-race MMD-U/variogram −.073/−.086 vs parent, reverse +.037/+.044. Evaluator signature +.11/+.07 also missed +1.5. [w1_c10]

## Per-board state of the art and weakest metrics

- Temporal **w0_c03 53.73**, adaptive maturation (Δ +.599). Split scores only, temporal_val 48.88 and heartonly 58.58. [w0_c03] [w0_c04]
- Heart **w4_c05 62.97**, pre-enrichment hard crop, full-input RMS and 20% pseudobulk offset, Δ +2.101 vs soft parent. Weakest D2 47.12, Dice 48.15, variogram 61.87. [w4_c05]
- Embryo **w3_c06 59.36**, local same-type log-depth matching and fixed-slot variance swaps, Δ +.859 over w3_c02. Weakest scored skills variogram 41.51, DE score 57.72 and MMD-U 59.06. [w3_c02] [w3_c06]
- Perturbation **seed 61.74**, WT composition rollback, depth-matched maturation tilt and bounded amplitude calibration. Weakest MMD-U 51.73, variogram 52.07 and DE score 57.19. [w1_c01] [w1_c02] [w1_c10]

## Method pitfalls (statistics, evaluation, reasoning traps)

- Treat n=1 as a scoring-seed screen that understates variance. Use repeated prediction/fit pairs (n≥3) and one-sided 95% bounds for promotion (embryo Δ +.513, lower +.44). [w5_c01]
- Use cell folds for within-snapshot reproducibility and independent specimens for mutant spread. Audit genes and gates per seed (Mef2c E9.0 Δ −2.575, Mab21l2 gate 2/8→1/8). [w1_c10]

## Implementation pitfalls (crashes, helper quirks, contract)

- Copy the pandas anchor mask before mutation and apply the scorer’s organ filter to helper targets (heart Δ +11.092). [w2_c00] [w2_c01]
- Keep ordered scaffold slots, exclude self by index and move expression with metadata (embryo Δ +.859). [w3_c06] [w5_c10]
- Align genes before drift, preserve CSR support and globins and update each donor once before restoring draw order (temporal Δ +.599). [w0_c00] [w0_c03]

## Open questions

- Can independent embryos or held-out mutants identify spread direction and size, with both distribution skills beating parent and reverse and gates preserved (perturbation Δ −.225)? [w1_c10]
- Can placement gain ≥+.80 neighborhood MMD vs matched control while preserving variogram (embryo Δ +.513)? Can higher exposure 
