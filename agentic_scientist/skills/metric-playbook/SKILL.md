---
name: metric-playbook
description: Exactly how every Virtual Embryo metric is computed, weighted and gated, which ones are cheap to win, and where the headroom is. Read before choosing what to work on.
---

# Metric playbook

## The levers, in order of points per unit of effort (read this first)
1. **T3 `severity_slope` (25% of T3).** It is the OLS slope of the predicted vs observed log-fold-change on the observed DE set, scored as |log β|. It is UNDEFINED (skill 0) unless R² > 0.01 and β > 0. A 2x magnitude error still scores ~91, a 10x error ~75. If a T3 model sits at exactly 50, its response is either absent or uncorrelated. Any weak, correctly signed, generic knockout response (lineage depletion plus maturation delay, magnitude scaled plausibly) unlocks most of ~12 headline points. This is the cheapest term on the board.
2. **T2 gate.** Shape credit (d2_shape, occupancy_dice, scale_log_ratio; 1/12 each) is multiplied by G = min(1, neighborhood_mmd skill / 50). Fix local spatial organisation (neighborhood_mmd, 25% of T2) BEFORE geometry, or geometry gains are discounted.
3. **T2 `scale_log_ratio`.** One scalar: log of the RMS-radius ratio. copy_last misses size by 26-39% in radius. Cell count is not scored, so set the coordinate scale from the extrapolated or interpolated growth.
4. **Embryo `occupancy_dice` is bimodal** (most entries 0-10, some 100). A coherent single anatomy in the rms frame (16³ voxels over ±3 rms radii, best of 4 det=+1 flips) is worth about 8 headline points per board.
5. **DE terms (`de_score`, `de_direction`)** are pseudobulk statements about the target vs the reference stage. Mean shifts must be cell-level and magnitude-calibrated; averaging cells hurts mmd_u and variogram. T1 de_direction is easy (median 77); de_score has the largest gap.
6. `mmd_u` and `variogram` reward realistic single-cell distributions and gene-gene co-variation: sample REAL cells and adjust them, do not generate smoothed means.

## Skill scale
skill = hyperbolic between floor (copy_last, or WT identity for T3) and the split-half ceiling: floor → 50, ceiling → 100, worse than the floor → below 50 toward 0. A missing or NaN metric scores 0. Folded metrics (scale_log_ratio, severity_slope) score |value|, so overshooting is penalised.

## Exact sources (read them for any detail)
- Wrapper, weights, skill: `vendor/vec-community-kit/vec_local_score/local_score.py`
- Metric implementations: `.venv/lib/python3.12/site-packages/T1|T2|T3/metrics_v2.py` and `metrics.py`
- Our dev harness: `shinka_ve/harness.py` (splits) and `agentic_scientist/evaluate.py` (scoring seeds, noise).

## Reference: metric definitions, aggregation, cheap vs expensive, blind spots, levers
(from our competition analysis, docs/analysis/01_competition.md; numbers are from the public test boards)

### 2.1 Preprocessing (applies to every metric)

- Every stage is subsampled to 10% of cells before comparison. The reference stage is the 10% subsample of the preceding stage (T1 val: 1,706 cells from E9.5's 17,057).
- The target is subsampled to 10% and split into two disjoint halves at a fixed seed. One half is the truth; the other half, submitted as a prediction, gives the ceiling.
- Floor: `copy_last` (reproduces the preceding stage verbatim) for T1 and T2; `wt_identity` (matched WT) for T3.
- Pseudobulk = mean of log-normalised expression over cells, per gene.
- DE truth: two-sided Mann-Whitney U of cells in X_true vs X_ref per gene, Benjamini-Hochberg FDR 0.05, minimum |mean log-expression difference| 0.25.
- Spatial metrics: each cloud is canonicalised (centre, rotate to principal axes, divide by RMS radius), which removes translation, rotation and scale. Reflection is not removed (see 2.6).
- Subsampling caps as in section 1 (MMD 2,000; energy distance and variogram 1,500).

### 2.2 Metric definitions

Lower/higher is better as noted. Anchors are from data/panels/index.json for the validation boards; test anchors are not published in the dump.

| Metric | Used by | What it measures | Computation | Better | Anchors (floor / ceiling) on validation |
|---|---|---|---|---|---|
| `de_score` | T1, T2 (x0.5), T3 | Did you call the right up and down genes? Chance-corrected | Predicted reports n_up = \|U_true\| top genes by Δp = pred - ref and n_down = \|D_true\| bottom genes (set sizes fixed by truth, so no free parameter). ov = fraction of calls that match truth. chance = max(ov with Δp = +ref, ov with Δp = -ref), i.e. the overlap a baseline-expression-only ranking gets. de_score = (ov - chance) / (1 - chance). Only the ordering of Δp matters. | higher | T1 0 / 0.846; embryo 0 / 0.841; heart extrap 0 / 0.942; heart interp 0 / 0.818; T3 0 / 0.870 |
| `de_direction` | T1, T2 (x0.5), T3 | Genome-wide agreement of the direction of change, after removing baseline-level dependence | Rank-transform Δp, Δt = true - ref and ref across all panel genes; partial correlation C = (C_pt - C_pr C_tr) / sqrt((1 - C_pr^2)(1 - C_tr^2)). | higher | T1 0 / 0.790; embryo 0 / 0.919; heart extrap 0 / 0.992; heart interp 0 / 0.955; T3 0 / 0.925 |
| `severity_slope` | T3 (x0.25, scored as abs) | Is the predicted response the right size? | OLS slope β of predicted on observed log fold change, restricted to the observed DE set; R^2 of that fit. Value = log β if β > 0 and R^2 > 0.01, else undefined (skill 0). Normalised on \|value\|. | toward 0 | floor -6.908, ceiling -0.0088 |
| `mmd_u` | T1 (0.30), T2 (0.25 x 0.6), T3 (0.20 x 0.6) | Cell-population distribution (cell states and proportions) | Subsample 2,000 cells. Project both onto 30 PCs fitted on the target only. RBF kernels exp(-γ_s \|x-y\|^2), γ_s = s γ0, s in {0.25, 0.5, 1, 2, 4}, γ0 = median heuristic on target. Unbiased MMD^2 per kernel; mmd_u = (1/5) sum_s MMD^2_s. | lower | T1 0.0836 / 0.00406; embryo 0.0857 / 0.00307; heart extrap 0.0246 / 0.00011; heart interp 0.0207 / 0.00087; T3 0.0314 / 0.00039 |
| `variogram` | T1 (0.20), T2 (0.25 x 0.4), T3 (0.20 x 0.4) | Gene-gene covariance structure, which marginals cannot see | 20,000 random gene pairs (i,j); v(i,j) = mean over cells of \|x_i - x_j\|^0.5 (1,500-cell subsample); metric = mean over pairs of (v_pred - v_true)^2. | lower | T1 0.00522 / 0.000158; embryo 0.0535 / 0.00126; heart extrap 0.0317 / 0.00070; heart interp 0.0238 / 0.00102; T3 0.0322 / 0.00074 |
| `d2_shape` | T2 (1/12 each, gated) | Shape: distribution of within-cloud pairwise distances, rms-normalised | D2 = pairwise distances / rms, 2 x 10^5 within-cloud pairs; d2_shape = Wasserstein-1(D2 pred, D2 true). | lower | embryo 0.0531 / 0.00268; heart extrap 0.00933 / 0.00342; heart interp 0.0308 / 0.00412 |
| `occupancy_dice` | T2 (1/12 each, gated) | Does the predicted tissue sit in the right region of the rms frame? | Shared 16^3 voxel grid over [-3, 3] rms radii; Dice of occupied voxel sets; max over the four sign flips with det = +1. | higher | embryo 0.705 / 0.766; heart extrap 0.775 / 0.947; heart interp 0.675 / 0.880 |
| `scale_log_ratio` | T2 (1/12 each, gated) | Growth in physical size | log(rms(pred) / rms(true)); normalised on \|value\| (optimum 0). | toward 0 | embryo -0.306 / 0.0053; heart extrap -0.268 / 0.0074; heart interp 0.328 / -0.0119 |
| `neighborhood_mmd` | T2 (0.25), ungated | Joint expression and position: each cell's expression averaged over its 15 nearest spatial neighbours, then mmd_u between the two sets | nb_i = mean of the 15 nearest-neighbour expression profiles; mmd_u on {nb_i(pred)} vs {nb_i(true)}. No cell correspondence needed. | lower | embryo 0.211 / 0.0113; heart extrap 0.0718 / 0.0004; heart interp 0.0573 / 0.00432 |

Note that `severity_slope` is scored on \|value\| and is undefined (skill 0, not 50) when R^2 <= 0.01. No row on the dumped boards hits exactly 0.

### 2.3 Normalisation and scale

Per metric (proposal eq. 9):

skill(m) = min( d_base / (d_base + d(m)), 1 ), with d_base = |m_ub - m_base| and d(m) = distance of the metric from the ceiling, oriented so larger is worse. Score = 100 x skill.

- Ceiling maps to 100 (scores above it are clipped at 100). Floor maps to 50. Worse than floor goes below 50 and approaches 0 asymptotically, with no truncation.
- Undefined metric = skill 0 (not omitted).
- Worked example (T1 val mmd_u): floor 0.0836, ceiling 0.00406, so d_base = 0.0795. A prediction at 0.0418 (half the floor) has d = 0.0377 and skill 0.68, i.e. score 68.
- Worked example (severity_slope): floor |log β| = 6.908, ceiling 0.0088, d_base = 6.899. A 2x magnitude error (|log 2| = 0.69) scores 91; a 10x error (2.30) scores 75. Magnitude is forgiving.
- Worked example (T2 scale_log_ratio, embryo val): a 10% radius error (|log 1.1| = 0.095) scores about 77 on this term, which is about 2 headline points on T2 (weight 1/12).

Test-board anchors are not in the dump, so test raw metrics cannot be re-derived from it.

### 2.4 Headline aggregation (verified)

Per board (weights from proposal Table 1; the T2 gate is inferred):

- T1 = 0.25 de_score + 0.25 de_direction + 0.30 mmd_u + 0.20 variogram.
- T2 = 0.125 de_score + 0.125 de_direction + 0.15 mmd_u + 0.10 variogram + G x (1/12) x (d2_shape + occupancy_dice + scale_log_ratio) + 0.25 neighborhood_mmd, with gate G = min(1, neighborhood_mmd / 50).
- T3 = 0.30 de_score + 0.25 de_direction + 0.25 |severity_slope| + 0.12 mmd_u + 0.08 variogram.

Checks against the dump:
- T1 and T3 reproduce every row (max error 0.00006 on all 123 + 200 + 142 + 200 rows of the T1/T3 boards).
- T2 without the gate fails on 74 of 122 heart-test rows (up to 7.8 points off). With G = min(1, nbr/50) every T2 row on all five T2 boards reproduces (max error 0.00008, 0 exceptions). The displayed shape metrics are ungated; only the headline is gated.
- Gate consequence: a structureless cloud that scores 0 on neighbourhood structure gets zero shape credit; the 25% shape group only pays once neighbourhood skill is at least the floor. This is the control `ctrl_random_cube` mentioned on the baselines page.
- Overall = T1 + mean over that task's boards + T3, with a missing board counted as 0. Verified on every row of both overall files (0 exceptions). Validation has 5 boards (T2 averaged over 3); test has 4 (T2 averaged over 2). The total is 300 at ceiling on both.

### 2.5 Cheap to win vs expensive (test-board numbers, all test rows)

| Metric (board) | Test median | Test best | Assessment |
|---|---|---|---|
| `severity_slope` (T3, 25%) | 74.6 | 97.2 | Cheapest term. A defined response with R^2 > 0.01 and beta > 0 gets most of it; the only real requirement is a weak positive correlation with the observed response, then scale to a plausible beta. Validation median on Gata4 is 95. |
| `scale_log_ratio` (T2, 1/12 of T2 when gate open) | 78.3 (heart), 93.8 (embryo) | 100 | One scalar. copy_last misses size by 26% to 39% in radius on the validation boards. Setting the coordinate scale from the interpolated or extrapolated size gets most of it. Cell count is not scored, so size can be fixed independently. |
| `de_direction` (T1, 25%) | 77.0 | 84.8 | Mostly banked: every T1 test row is >= 51 and most are 70 to 85. Spread is about 8 points. |
| `d2_shape`, `occupancy_dice` (T2, gated) | 62 to 72 (d2); 4.7 embryo / 46 heart (occupancy) | 100 / 61 | Shape only pays when neighbourhood skill is >= 50. Embryo `occupancy_dice` is bimodal: 24 of 132 rows at 100, most of the rest at 0 to 10. That mode worth about 8 headline points per board is a large, poorly understood swing. |
| `de_score` (all) | 51.7 to 67.4 | 66.9 to 76.9 | Requires ranking genes correctly. The ref x 2 control scores exactly the chance level (50), so anything at 50 has no information. |
| `variogram` (T3, 20%) | 50.0 | 74.9 | Hard. Median at the floor. |
| `neighborhood_mmd` (T2, 25%) | 46.9 (heart), 76.7 (embryo) | 75.2 / 81.1 | Heart test is hard: a quarter of the T2 headline and it gates the shape group. |
| `occupancy_dice` (heart test) | 46.3 | 60.9 | Largest single-metric gap to ceiling on any board (39 points). |

Largest gap to ceiling per board (best test value vs 100): T1 DE-score 23; T2 embryo DE-score 33 and variogram 31; T2 heart occupancy 39; T3 DE-score 28.

### 2.6 Scorer properties and blind spots (know them; do not treat as a target)

- Reflection: PCA sign assignments use det = +1, so a mirrored embryo scores identically. The organisers call this a known limitation.
- Translation, rotation and scale are removed from the shape metrics, but size is scored separately through scale_log_ratio. Cell count is not scored.
- mmd_u is computed in the top 30 PCs of the target only. Differences outside those directions are invisible to mmd_u (the variogram and DE terms see them instead).
- de_score ignores the magnitude of Δp; only the ranking and the fixed set sizes matter.
- Scaling the reference is a DE null. ref x 2 gives Δp = +ref; ref x 0.99 gives Δp = -0.01 ref, which ranks genes exactly as -ref. Both reduce to the chance term, so de_score = 0 and the score is 50 (the floor value).
- Scores above the ceiling clip at 100, so there is nothing to gain past 100 on any metric.
- Ties: broken by hidden test performance, then DE group, then distribution group (proposal section 1.5).

---


## 5. Scoring levers that are legitimate within the rules

These are modelling choices the panel rewards. They use released data, do not solve for held-out values, and do not use score feedback to build predictions.

1. Separate the pseudobulk-level and distribution-level terms. The weight split:
   - T1: 50% pseudobulk-level (de_score, de_direction), 50% distribution-level (mmd_u, variogram).
   - T2: 25% pseudobulk (DE) and 75% distribution or geometry (mmd, variogram, shape group, neighbourhood).
   - T3: 80% pseudobulk response (de_score, de_direction, severity), 20% distribution.
   A pseudobulk shift (`pseudobulk_shift`) alone is below the floor on T1 val (48.6) and on heart extrap (47.8). A mean-tiled cell (`ctrl_one_cell`) does well on means and near zero on distributions. Both need to be addressed.
2. Magnitude is cheap once direction is right. For T3, set the response scale from the knockout's expected effect size (calibrate on the Gata4 validation answers or on the Mab21l2 training knockout). Any response with R^2 > 0.01 can be scaled to a plausible beta.
3. Size is one scalar on T2. Set the coordinate scale from the interpolated or extrapolated rms radius; cell count is free.
4. Neighbourhood first. The gate means shape credit is worth nothing until neighbourhood_mmd reaches the floor. Model local spatial structure before geometry.
5. Use the dissection. The data protocol says E10.5 and E12.5 hearts were dissected with most surrounding tissue removed, and E8.5 retained more non-cardiac tissue (Neural Tube 4.6% at E8.5, 0% at E9.5). Targets carry this sampling, and the scorer does not ask you to reproduce it. A composition prior that shifts toward cardiac types can be checked on the E10.5 validation answers after opt-in.
6. Nearest-stage priors are a strong baseline on test. A real E10.5 population used as the E12.5 prediction scores 77.1 on T1 test (rank 8 of 123), about 6 points below the best human entry. The equivalent E7.5 and E10.5 copies appear in embryo and heart test entries. These use released validation data, which the rules permit for P3 preparation (Rules section 10). Whether to rely on them is a strategy choice; note that opting in ends P2 eligibility.
7. Use the sample size the scorer uses. Submit about 2,000 to 5,000 cells: MMD and the energy and variogram terms subsample to 2,000 and 1,500 anyway, and the count is free.
8. Calibrate on validation, not on test. Validation boards are for choosing among predictions; the P2 cross-board correlation above shows how little P2 standing carries forward.

Things the panel does not reward, so do not chase them: a scaled copy of the reference (ctrl_scale_ref lands at chance level for DE), reflection (not penalised), and anything above the 100 ceiling.

---


## Which gains transfer to the hidden target (metric kinds)
Every metric is one of three kinds (after vecbench's metric map). Your knowledge-bank lines show each accepted change's
gain split this way ("gain kinds: dist / DE / size", weighted board points), and the final holdout table shows it on dev and holdout.
- **Distribution** (`mmd_u`, `variogram`, `d2_shape`, `occupancy_dice`, `neighborhood_mmd`): compare your cells with the
  target's cells directly. A dev gain here is real evidence for the hidden target.
- **DE-based** (`de_score`, `de_direction`, `severity_slope`): computed on the genes that differ in THAT target. A
  different target has a different gene set, so a dev gain here is weak evidence. This matters most for T3: dev is
  Gata4, the test is Ctnnb1, and DE-based metrics are 80% of T3. Earn T3 DE points from mechanism and biology (which
  genes a Wnt/beta-catenin loss should move, and in which direction), not by tuning to the Gata4 gene list.
- **Size** (`scale_log_ratio`): one unknown number about the target. A local test cannot rank it; only avoid being
  obviously wrong (the sanity check does that).
Caveat from our own runs: distribution gains can still fail to transfer when the dev inputs differ from the test's
(full2's heart candidate gained +3.8 distribution points on dev and lost on holdout, likely because dev heart inputs end
at E8.75 and the test starts from E10.5). Prefer changes whose gain is mostly distribution AND does not depend on the
input regime.
