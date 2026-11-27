# Knowledge bank

## Established (held up; effect sizes and cycles)
- **Heart cardiac-centred radial crop of latest donors (CONFIRMED [w2_c00]).** Δproxy +2.09 [+1.94, +2.24], z 26.0, n=8. Heart +4.18 (52.09→56.00). Other boards 0.0.
  - Gains: distribution +2.60, de_based +1.33, size -0.02.
  - Mechanism: marker-centred crop, radius = max(q95 seed distance, q75 distance), multiplied into the parent's cardiac donor probabilities and renormalised. Deformation unchanged.
  - It helps only with RMS restoration (rescale about the centroid to the parent's predicted RMS, factor 1.056-1.188). Without it the scale score breaks.
- **Heart detection-state donor tilt inside the crop (CONFIRMED [w2_c01]).** Δproxy +1.34 [+1.24, +1.45], z 24.6, n=8. Heart +2.69 (to 58.59). Other boards 0.0.
  - Gains: distribution +1.78, de_based +0.81.
  - Mechanism: within each annotation, donors are tilted toward lower log-detected-gene states (half-trend, cap log 1.5, mass-preserving, real donors only). It abstains per stratum if ESS < 0.5.
  - Read it as an empirical low-detection prior, not maturation. The gain rides on cell-cycle genes (Top2a, Cenpf, Rdx). H19, Ttn and Col3a1 fall. It beat the pre-registered ≈+1, so stay suspicious.
- Combined heart R (crop + tilt): 52.09→58.59 (+6.50 heart, ≈+3.25 proxy) [w2_c00][w2_c01].
- **Heart tissue-graph crop (CONFIRMED but CONFOUNDED [w1_c05]).** Δproxy +3.51 [+3.33, +3.68], z 38.2, n=8. Heart +7.02 (to 58.83). Other boards 0.0.
  - The parent lacked R, so most of the gain re-measures R. The graph increment alone is ≈+0.24 heart (58.83 vs 58.59), ≈+0.12 proxy, and was never isolated. Credit R, not graph connectivity.
- Seed boards: temporal 58.98, heart 52.09, embryo 81.15, perturbation 55.24 [w1_c00]. Seed dev proxy 180.84.
- Orthogonality: an edit on one board leaves the other three at exactly 0.0 in every record.
- Every confirmed gain so far is heart-only. Heart edits that moved the distribution broadly gave +1.3 to +7 board points. Temporal, embryo and perturbation edits have all been at noise or negative.

## Dead ends (and the condition under which a retry is justified)
- **Temporal decoder in additive log units (NEGATIVE [w2_c05], n=1 screen).** Δproxy -2.42 (z -4.0, 181.67 vs 184.09), all on temporal (-2.42). Distribution -1.88, de_based -0.54, size 0.
  - Mechanism: additive ±0.35-clipped shift on donor-positive entries instead of multiplicative exp(shift). Surrogates improved: type rank corr 0.654→0.777, sign agreement 0.661→0.917, Myl7/Ttn wrong-sign increments shrank (+0.209→+0.038, +0.109→+0.021). The response amplitude shrank ~35% (std Δtrue 0.201 vs 0.315), and the score is amplitude-dominated, so a better-signed but weaker displacement loses.
  - Seed 101 mmd_u and variogram regressed ~4x the allowed 0.5. n=1 understates variance, but the sign and size make a hidden win unlikely.
  - Retry only with the amplitude restored (per-type rescale to the parent's retained pseudobulk displacement). Score the k-scaled multiplicative control and state=0 on both splits. Add a distribution/variogram gate. Do not retry the coordinate-only operator.
- **Temporal OT vascular-ancestry label mask (NEGATIVE [w3_c02]).** Δproxy -0.46 [-0.48, -0.44], z -45.5, n=8. Distribution -0.28, de_based -0.16.
  - The relevant break is E8.5→E9.5, which does not recur at the E9.5→E10.5 test pair. Rewriting the cost also shifts Sinkhorn marginals for non-vascular types.
  - Retry only if scoped to pairs active at the deployment pair with test-side lineage evidence and the full paired protocol.
- **Embryo spatial-support grafting, two designs (both effectively dead).**
  - Single-native-anatomy swap [w0_c05]: Δproxy +0.023 [-0.004, +0.051], n=8. Dice +0.050 (0.815→0.865), but seed-101 neighborhood_mmd -7.32, d2_shape -6.81, embryo -1.76. Expression rows moved onto foreign anatomy broke local neighbourhoods.
  - ~128-cell native-patch relocation with an input-only abstention certificate [w0_c06]: shipped OFF, recorded Δ exactly 0 (n=1, not a measurement). At the one applied seed (101) embryo fell 81.61→80.38 (-1.23), occupancy_dice 60.03→56.63 (-3.40), d2_shape 89.77→74.12 (-15.65). The certificate passed there and abstained at seed 1009.
  - Generalisation: moving cells or patches onto one scaffold does not raise occupancy skill and costs d2_shape, even when patches stay intact.
  - Retry only with a validation signal predictive of occupancy_dice/d2_shape, 16 paired seeds, a per-seed application rate, and a distinct mechanism such as abundance deficits (Primitive Streak/SOM).
- **Donor-level "developmental delay" on the perturbation sampler.**
  - Fixed d=0.5 real-E8.5 delay plus composition rollback: NEGATIVE [w0_c00], Δproxy -6.62 (z -5.9, n=1), all on perturbation. Distribution -3.21, de_based -3.40, gene_specific 2.14→0.17. The rollback is to blame.
  - ~0.10 mass swapped to earlier same-annotation WT cells: INCONCLUSIVE [w1_c00] (arm off, Δ 0). Seed-101 gata4_1 -0.68, gata4_2 -0.43. A ≤12% swap moves pseudobulk ≈0.013; the response ratio was 0.47 against the needed ≈1.
  - Retry only with batch/run/complexity-matched donors, a latest-stage swap control, no global rollback, and 5-8 paired seeds with the arm on.
- **Heart growth extrapolation from crop radii.** Measured rate 0.0/day [w2_c00]. Retry only with a different growth-rate data source.
- **Exposure depletion as a T3 gain.** The scored gene Ctnnb1 is off-panel, so the shipped gain is 0 by construction [w1_c04][w0_c04]. Do not spend more T3 cycles on it.

## Promising / inconclusive leads
- **Heart extraembryonic whole-donor halving, PROMISING but rejected [w2_c03].** Δproxy +0.16 [+0.04, +0.28], z 2.45, n=8. Heart +0.32. The gain was E8.75-only, the E9.5 mean was -0.67, and heart_long d2_shape fell 43.75→34.48. Retry only with a design that preserves d2_shape and an E9.5 mean ≥0.
- **Heart patch-mass conservation under the tilt: UNTESTED [w2_c04].** Shipped disabled (Δ 0, n=1). Surrogate: patch-mass TV 0.043/0.034/0.017 removed, 93.6-96.3% of the shift retained. Native D2 improved early (0.00413→0.00200) and long (0.00238→0.00185) but worsened on e875 (0.00117→0.00149). Predicted +0.15-0.30 proxy is a hypothesis. Retry with 16 seeds per split, a positive pooled lower bound, both target-group means ≥0, and unchanged Top2a/Cenpf/Rdx signs.
- **Graph-vs-radial crop increment [w1_c05].** Predicted +0.25 proxy, never isolated. Retry with R as the parent, 8 paired seeds and a Euclidean ablation.
- **Temporal same-stage entropic self-drift subtraction: UNMEASURED, leaning negative [w3_c03].** Shipped identical to the parent (Δ 0, n=1). The one-seed smoke was -0.72 proxy (mmd_u -1.98, variogram -0.62). The state-only covariance gain (7.56%) did not survive the full pipeline. Retry only with ≥8 paired seeds on two splits and a full-pipeline covariance gain ≥3%.
- **Temporal donor-tilt family (INCONCLUSIVE).** Compartment tilt [w3_c00] +0.33 [-0.11, +0.77], n=8 (single-seed +0.98 was ~3x too high). Matrix tilt [w3_c01] +0.26 [-0.14, +0.66]. Donor-law increments do not survive the multiplicative decoder, and [w2_c05] shows the decoder is amplitude-dominated. Do not stack them.
- **Perturbation GO-conditioned compartment rollback: UNMEASURED [w1_c06].** Δ 0 (n=1). The gate never ran because the quick_eval budget was exhausted. The Gata4 alignment is circular. Retry only with scorer budget reserved up front, 16 paired seeds, equal-TV gene-blind and permuted-map controls, and a non-cardiac on-panel sham gene. A gain above +0.5 is unlikely.
- **Exposure-depletion law (perturbation), DEMOTED [w0_c04].** 8-pair +0.81 [-0.17, +1.78] [w1_c03][w1_c04] became +0.050 (LB -0.278) at n=32, which is regression to the mean. The equal-TV placebo flipped sign by split.
- **Heart ECM restoration after crop+tilt [w2_c02].** Δproxy -0.056 [-0.164, +0.053], n=8. Col3a1 sign agreement 0.74→0.79, no score gain.
- **Perturbation small-edit family, at noise floor.** [w0_c01] +0.22, [w1_c01] +0.40, [w1_c02] +0.04, [w0_c02][w0_c03] +0.26. Pseudobulk increments are 0.004-0.03 log units against true deviations of 0.2-0.9.

## Per-board state of the art and weakest metrics
- **Heart.** Best is the w1 program (58.83, dev proxy 184.21) [w1_c05]. The w2 R-stack is 58.59 (184.09) [w2_c01][w2_c04]. Mechanisms: radial or graph crop, RMS restoration, detection tilt. Weakest: de_based (Col3a1, Ttn, H19 wrong-signed), size, and fragile heart_long d2_shape (43.8) and neighborhood_mmd (59.4) [w2_c03].
- **Temporal.** Best is the seed program (58.98). No accepted gain [w3_c00][w3_c01][w3_c02][w3_c03][w2_c05]. Weakest: de_based (48.0 at seed 101) and distribution (variogram 56.3, mmd_u). Contractile genes (Ttn, Myl7, Actc1) are wrong-signed, but fixing the sign without keeping the amplitude loses [w2_c05].
- **Embryo.** Best is the seed program (81.15). No accepted gain [w0_c05][w0_c06]. Weakest: occupancy_dice (≈56.9-60 skill), d2_shape, and Primitive Streak/SOM neighbourhood composition (errors 0.56) [w0_c06]. Expres
