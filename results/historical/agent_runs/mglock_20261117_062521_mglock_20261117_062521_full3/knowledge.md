# Knowledge bank

## Established (held up; effect sizes and cycles)
- CONFIRMED, temporal: condition donor sampling on context['sampling']=='heart_chambers' [w1_c00]. A fixed 0.05 relative weight goes on a curated clearly-non-cardiac label set, as an additive log-weight in flow.log_growth.
  - n=8: temporal +1.30 board, Δproxy +1.30, CI [+1.08,+1.52], z=11.0. Other boards 0.0. DE +1.15, distribution +0.45, size 0.0.
  - The DE mechanism is unproven: a fixed-weight pseudobulk check was counterevidence (change corr 0.127). Report as "gain; DE mechanism unproven".
- CONFIRMED, heart: small saturating donor-sampling tilt toward observed cardiac-neighbourhood donors [w2_c00]. It uses a smoothed 31-NN cardiomyocyte-field fraction, damped by F and (1−mu_b), with a 0.05·F TV budget and a 0.03 myocardial-share cap. It enters via `source_probabilities=None` in heart_transport.LatentFlow.predict.
  - n=8: heart +2.06 board, Δproxy +1.03, CI [+0.84,+1.21], z=10.6. Other boards 0.0.
  - By kind: distribution +1.26, DE +1.89, size +0.02. occupancy_dice −0.82.
  - It beat the forecast (+0.2–0.8) with a TV shift of only ~0.03–0.04. Attribution to geometry is not claimable, because the tilt does not change coordinates.
- CONFIRMED, perturbation: conserve knockout-exposed mass in local lineage rollback [w0_c02]. Per WT stratum, damp r_t=clip(e_t/f_t,0.5,2), keep affected mass conserved, and rescale probabilities. Off-panel or under-supported genes abstain to exact uniform WT.
  - n=8: perturbation +0.575 board, Δproxy +0.57, CI [+0.11,+1.04], z=2.3. DE +0.98, distribution +0.32, size 0.0. Other boards exactly 0.0.
  - Forecast was +0.1–0.4 and TV only ~0.01, so the gain exceeds what the intervention magnitude predicts. Gene-specificity +2.14. Null genes returned exactly WT noise.
  - Weak: 2 of 8 pairs negative (−0.32, −0.19). Evidence is on-panel Gata4 only, with no off-panel holdout. The pre-declared ≥16-seed and abstention-vs-rollback checks were not run.
- CONFIRMED, embryo: condition spatial correspondence on supported shared cell types [w3_c01]. Same-label conditional barycentric destinations plus same-label displacement smoothing (k=24). Deformation stays 0.5.
  - n=8: embryo +0.22 board, Δproxy +0.11, CI [+0.07,+0.15], z=5.5. Distribution +0.066, DE 0.0, size −0.01.
  - Modest, far below the forecast (+0.75–1.0). The Primitive Streak/SOM neighbourhood error did not move, so attribution is unproven.
- Expression-only metrics (mmd_u, variogram, DE) are bit-identical for any change after donor/expression selection or any coordinate-only change [w3_c01][w3_c02][w2_c01].
- Generalisation: all four confirmed gains are narrow, context-, label- or compartment-conditioned branches. Everything else keeps the parent path, and gains stay on the touched board (others exactly 0.0) [w1_c00][w2_c00][w3_c01][w0_c02].
- Donor-law changes that act on a large, well-defined sampling or composition error gave +0.57 to +2.1 board [w0_c02][w1_c00][w2_c00]. Coordinate-only changes gave ≤+0.22 [w3_c00][w3_c01][w3_c02][w2_c01].

## Dead ends (and the condition under which a retry is justified)
- Raising `deformation` 0.5→1.0 in `SpatialInterpolant.predict` [w3_c00], n=1. RMS radius 173.7→166.7 (target 147.2), but occupancy_dice only +1.9 (bar 5) and neighborhood_mmd −1.77 (allowed 0.5).
  - Retry only with a better correspondence, tested at f=0.5 on E7.5/E8.0 with paired seeds. Never the coefficient alone.
- Combined GO-programme residual tilt + parent complexity tilt [w0_c00], n=1. mmd −1.8, variogram −0.6, which broke the no-harm gate (no distribution term worse than −1.0).
  - Retry only if the combined arm passes the gate, keeps a positive de_direction increment, and is checked on a second knockout (e.g. off-panel Ctnnb1).
- VETOED, temporal: offset-only vascular calibration of Endocardium/BEC anchor drifts [w1_c01]. A ~0.039 log offset scaled by horizon fraction 0.18–0.44 becomes <0.02 log on a minority of rows (Δproxy 0.00).
  - The error is composition/state: EndoMT Endocardium is 0.2% predicted vs 5.8% target.
  - Retry only if the error is shown to be offset-dominated (post-horizon shift ≥0.1 log on a non-minority row set) and the intervention also changes EndoMT state.
- VETOED, embryo: atlas-derived enrichment tilt toward the LPM donor pool [w3_c03]. The 1.845-fold enrichment was read off atlas cells at the dev target E7.25 (target leakage). At test (E7.75) the atlas gap makes PCHIP pull the ratio toward 1, so the tilt is inert.
  - Retry only with atlas time points present in both dev and test brackets, r validated on a dev target the atlas does not contain, and an expected effect above resolution.

## Promising / inconclusive leads
- PROMISING but REJECTED, heart [w2_c02]: add endothelial-marker-supported endocardial seeds (Pecam1/Cdh5/Emcn) to the CM-only 31-NN field. All other limits unchanged.
  - n=8: pooled Δproxy +0.062, CI [+0.013,+0.110], z=2.4. Heart +0.123 board. Rejected because the E8.75 target mean was −0.22, breaking the pre-registered two-target nonnegativity.
  - By kind: DE +0.023, distribution −0.068, size −0.018. 2 of 8 heart diffs negative.
  - The Endo donor-mass increment was only +0.002–0.004, so Chamber-Endo stayed 0.021 vs 0.055. The gain is not attributable to endocardial composition (likely resampling noise and DE).
  - Retry only with a materially larger Endo increment, or together with a Foregut/SE excess fix (0.250 vs 0.050), validated Endo labels at true E9.5/E10.5 inputs, and nonnegative means on E8.75 and E9.5.
- INCONCLUSIVE, temporal [w1_c02]: bounded, complexity-stratified, within-Endocardium donor tilt toward an 8-gene EndoMT program (TV ≤0.03·s, displacement ≤0.25). n=8: Δproxy −0.294, CI [−0.84,+0.25], z=−1.0. Not a confirmed harm.
  - The diagnostic moved the right way (EndoMT Endocardium 0.002→0.006, target 0.058), but still ~10x short.
  - Per kind: distribution +0.185, DE +0.284, size 0.0, yet the composite fell (177.63 vs 177.93 parent). Composition TV worsened 0.413→0.418.
  - The achievable program rise under the 0.03·s cap was never verified to reach ≥0.08. temporal_heartonly was not run.
  - Retry only with ≥8 seeds on both temporal splits (or a lower-variance proxy), a verified rise ≥0.08 under the unchanged cap, and ideally the real E12.5 heart_chambers horizon (~7% EndoMT/Early VIC in target, like-for-like E9.5→E10.5 trend).
  - Together with [w1_c01], a small mass-preserving EndoMT push is unlikely to close the 0.2–0.6% vs 5.8–6.9% gap. A larger state or composition mechanism is needed.
- INCONCLUSIVE (weak: the final run scored the reverted parent), heart [w2_c01]: 2x same-lineage weight in the 24-anchor smoother with RMS rescale. Ad-hoc 4-seed: heart_long −0.023, e875 +0.022. d2_shape −0.570 on heart_long (guard 0.5).
  - The strain cap shrank post-cap RMS by 25–30%. The dominant heart error is composition (Foregut 25% vs 5%, composition TV 0.44 on heart_long), which smoothing cannot reach.
  - Retry only if scored before any revert, paired with a Foregut-composition change, with a pre-declared d2_shape tolerance.
- INCONCLUSIVE, embryo [w3_c02]: per-anchor relative-mass guard (≥5% coupling) replacing the whole-label veto. Embryo +0.047 board [−0.01,+0.10], Δproxy +0.023, z=1.6, n=8. Forecast was +0.2–0.4.
  - Distribution −0.074, size −0.018. SOM niche error improved 0.5607→0.5270 but Primitive Streak regressed 0.5605→0.5685. Seam discontinuity +33%.
  - Retry with an absolute mass floor plus the 5% fraction, or require per-label niche movement before scoring. It needs ~3x more seed pairs. Do not sweep the threshold.
- INCONCLUSIVE, perturbation [w0_c01]: graded knockout-detection lineage depletion with uniform WT for off-panel genes. Mean +0.30 board, CI [−0.24,+0.84], n=8. DE +1.17, distribution +0.48.
  - The +1.20 screen did not hold up. Credit is mostly the gene-blind complexity tilt: depletion vs uniform WT was +2.26 on gata4_1 and −0.21 on gata4_2.
  - Retry with depletion-only on uniform WT, 8+ pairs, and an explanation of gata4_2.
- Abstention (uniform WT for off-panel genes) is likely a separate contributor to [w0_c02] and [w0_c01]. Score uniform-vs-parent separately before crediting the rollback.
- GO-only arm, perturbation [w0_c00]: at most +0.5 total and +2.0 de_direction on Gata4. It is the only gene-specific signal (parent tilt gene_specificity 0.14). Test it GO-only for off-panel genes and against [w0_c02].
- Perturbation residuals [w0_c02]: CM fraction predicted 0.141/0.143 vs 0.059/0.084, severity R2 −1.197/−0.760, and a gata4_2 Neural Tube excess (0.172 vs 0.084).
- Embryo endpoint separation is real [w3_c00]: median centroid gap 0.588 RMS, and 72.8% of neighbours share an endpoint. Label conditioning [w3_c01] fixed only a small part.

## Per-board state of the art and weakest metrics
- Program ids are not recorded in the cycle records. Boards are from the latest paired runs [w2_c02][w1_c02]. Seed dev proxy 176.32. Best accepted per worker: w0 177.62, w1 177.93, w2 177.91, w3 176
