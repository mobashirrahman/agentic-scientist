# Research notes — round 0: predicting the E7.75 mouse embryo from two bracketing stages

Task: `predict(inputs, times, target_time, context) -> AnnData`. Validation board: inputs E7.25 + E8.0 →
target 7.5 (fraction 1/3), three scoring seeds. Starting program: empirical endpoint mixture on one native
scaffold, validation **70.07** (`native_occupancy` 0.916).

**Final model: validation 73.49** (`native_occupancy` 0.950, test configuration PASS).
Per-metric skills: de_score 60.1, de_direction 67.7, mmd_u 71.4, variogram 79.5, d2_shape 56.4,
occupancy_dice 91.4, scale_log_ratio 99.6, neighborhood_mmd 73.0.

## 1. What the scorer actually measures

Read from the installed `veckit` / `vec_local_score` source (the same panel the board uses). Each stage is
subsampled to 10 %; the target is split in half (half A is scored against, half B is the attainable ceiling); the
floor is the reference stage (E8.0) resubmitted; every raw metric is mapped through
`skill(value, floor, ceiling)` (hyperbolic, floor 0.5, ceiling 1.0). Weights: de_score .125, de_direction .125,
mmd_u .15, variogram .10, d2_shape / occupancy_dice / scale_log_ratio .0833 each, neighborhood_mmd .25, with the
three shape terms gated by `min(1, neighborhood_mmd skill / 50)`.

* `de_score`: the truth fixes how many genes go up/down against E8.0; the prediction is ranked by its own
  `pb(pred) − pb(E8.0)` and matched sign-for-sign, minus a measured expression-magnitude null. **Rank-based and
  invariant to any positive rescaling of the delta** — the mixture weight cannot move it, only the *direction* can.
* `de_direction`: rank-partial correlation of the predicted and observed change, partialling out `pb(E8.0)`.
* `mmd_u`: unbiased multi-kernel RBF-MMD² in the truth's 30-PC expression space, 2000 cells per side.
* `variogram`: mean over 20 000 random gene pairs of (E|xᵢ − xⱼ|^0.5) differences — pure co-expression structure.
* `d2_shape`: 1-D Wasserstein distance between rms-normalised pairwise-distance distributions (alignment-free and
  **scale-free**).
* `occupancy_dice`: Dice of occupied voxel sets on a shared 16³ grid spanning ±3 rms radii after centre/PCA/rms
  canonicalisation, maximised over proper sign flips.
* `scale_log_ratio`: |log| of the rms-radius ratio prediction/truth.
* `neighborhood_mmd`: MMD between the distributions of **15-NN spatial-neighbourhood pseudobulk** (each cell
  replaced by the mean expression of its 15 nearest spatial neighbours, itself included).

This decomposition is the backbone of the whole round: `de_score`, `de_direction`, `mmd_u` and `variogram` depend
only on the *set* of expression profiles; `d2_shape`, `occupancy_dice` and `scale_log_ratio` depend only on the
*coordinates*; `neighborhood_mmd` couples them. Profiles and positions were therefore designed separately, and the
coupling was treated as its own problem.

## 2. Facts established from the two released stages

| | E6.75 | E8.0 |
|---|---|---|
| cells | 7 093 | 31 671 |
| genes | 498 (subset of E8.0's 500) | 500 |
| rms radius | 122.7 | 326.6 |
| PC variance fractions | .677 / .181 / .142 | .481 / .383 / .136 |
| pseudobulk mean | .175 | .588 |

* The two clouds differ strongly in form: `d2` 0.065, `occupancy_dice` 0.766, `scale_log_ratio` −0.979.
  Scaffold choice is therefore a real decision (measured below: −6.7 points for the wrong bracket).
* Cell-type centroids are poorly separated in a 30-PC embedding: matched-type centroid distances are 10–20 while
  within-type spread is ≈1.8 per component (≈10 in 30-D norm). Label-level cross-stage type matching is weak, which
  is why the plan for a type-composition model was dropped.
* The board is deterministic: re-running an unchanged program reproduces the score to the last digit (the starting
  program re-ran at exactly 70.073, the final program at exactly 73.493). Changing the program's *internal draw*
  moves the total by ±0.5 but individual metrics by up to ±11 (occupancy_dice), so metric-level readings need care
  and only the total is a reliable signal.

## 3. Final model (`program.py`)

1. **Geometry — one native scaffold, interpolated size.** The scaffold is the bracket nearer in time (the earlier
   one on an exact tie). Output coordinates are a *distinct random subsample* of that embryo's own cloud,
   isotropically rescaled to the interpolated rms radius. `radius = exp((1−f)·log r_L + f·log r_R +
   c·f(1−f))`, with `c = 0.15` a concave-growth correction that vanishes at both brackets and then a
   renormalisation so the radius is exact.
2. **Shape — anisotropy interpolation.** The scaffold's PCA eigenvalue spectrum is blended linearly toward the
   other bracket's spectrum by `f` and the cloud is stretched along its own principal axes to that spectrum
   (scale-free, wipes out nothing else on the board).
3. **Cell states — empirical endpoint mixture of real observed cells.** `n = 5000` cells; a fraction
   `w = f^0.7` are transplants from the other bracket, the rest are scaffold cells. Every cell is a real profile
   (morphing/averaging profiles is much worse, see below).
4. **Coupling — local-field matching.** Each candidate position is described by the pseudobulk of its 300 nearest
   spatial neighbours in the scaffold; each sampled donor profile is matched one-to-one (greedy nearest, unit
   capacity, cosine) onto the position whose *local field* matches it best. The scaffold cells left over keep
   their own profile at their own position, which preserves the native local-composition field exactly.

## 4. Evaluation log

Validation = inputs E7.25+E8.0 → 7.5. `nocc` = native occupancy, `nb` = neighborhood_mmd, `occ` = occupancy_dice.

| # | snapshot | change | validation | nocc | de | de_dir | mmd | vario | d2 | occ | scale | nb |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | s001 | starting program | 70.07 | .916 | 59.5 | 66.4 | 67.8 | 79.9 | 55.5 | 87.4 | 92.2 | 66.4 |
| 2 | s002 | distinct positions, capacity-1 assignment, exact radius | 68.21 | .956 | 59.3 | 66.5 | 67.6 | 80.1 | 55.4 | 74.9 | 94.4 | 62.5 |
| 3 | s003 | same program, different internal seed (noise probe) | 68.23 | .959 | 58.3 | 65.5 | 66.8 | 79.5 | 55.9 | 82.8 | 94.4 | 61.4 |
| 4 | s004 | state weight w = f^0.5 = 0.58 | 67.31 | .959 | 59.7 | 65.0 | 69.5 | 75.1 | 55.9 | 82.8 | 94.4 | 57.5 |
| 5 | s005 | state weight w = f^1.6 = 0.17 | 65.72 | .959 | 56.6 | 65.1 | 59.4 | 75.3 | 55.9 | 82.8 | 94.4 | 58.6 |
| 6 | s006 | n = 5000 cells (was 3000) | 68.93 | .958 | 58.5 | 65.9 | 67.4 | 79.9 | 56.0 | 88.3 | 94.4 | 61.6 |
| 9 | s009 | transplants pick randomly among the 10 nearest free positions | 68.20 | .958 | 59.1 | 66.5 | 65.0 | 79.1 | 56.0 | 88.3 | 94.4 | 59.8 |
| 11 | s011 | transplants blended 50 % toward the host profile | 66.34 | .958 | 58.3 | 65.8 | 56.3 | 78.4 | 56.0 | 88.3 | 94.4 | 58.6 |
| 12 | s012 | cell-centric start-style placement (duplicate positions) | 70.29 | .881 | 58.3 | 66.3 | 67.9 | 80.0 | 56.4 | 81.5 | 94.4 | 68.7 |
| 13 | s013 | + unit capacity over the full scaffold pool | 70.11 | .889 | 58.3 | 66.3 | 67.9 | 80.0 | 56.0 | 83.2 | 94.4 | 67.6 |
| 14 | s014 | transplant candidate pool k = 100 | 69.54 | .889 | 58.3 | 66.3 | 67.9 | 80.0 | 56.3 | 78.1 | 94.4 | 66.9 |
| 15 | s015 | volume-covering native sample + concentrated transplants | 70.11 | .886 | 57.9 | 66.2 | 68.4 | 80.2 | 54.9 | 81.2 | 94.4 | 68.4 |
| 16 | s016 | uniform position set, transplants choose best free position | 69.49 | .958 | 58.3 | 66.0 | 66.2 | 79.7 | 56.0 | 88.3 | 94.4 | 64.6 |
| 18 | s018 | concentrated transplants + 1-NN jitter | 70.07 | .903 | 58.3 | 66.3 | 67.9 | 80.0 | 56.1 | 82.8 | 94.4 | 67.5 |
| 19 | s019 | unit capacity + 2-NN jitter | 69.45 | .899 | 58.3 | 66.3 | 67.9 | 80.0 | 55.6 | 83.4 | 94.4 | 65.0 |
| 20 | s020 | **transplants matched to the scaffold's 15-NN local field** | 70.60 | .958 | 59.5 | 66.6 | 66.6 | 79.8 | 56.0 | 88.3 | 94.4 | 67.9 |
| 21 | s021 | novelty attenuation κ=1.5 (unrepresented donor states → precursor) | 69.48 | .958 | 59.7 | 66.6 | 63.9 | 78.5 | 56.0 | 88.3 | 94.4 | 65.5 |
| 22 | s022 | context-to-context (donor 15-NN field too) | 70.45 | .958 | 58.9 | 66.6 | 66.8 | 79.7 | 56.0 | 88.3 | 94.4 | 67.6 |
| 23 | s023 | field-matching neighbourhood 30 | 70.79 | .958 | 59.3 | 66.9 | 66.9 | 79.8 | 56.0 | 88.3 | 94.4 | 68.5 |
| 24 | s024 | field-matching neighbourhood 60 | 71.03 | .958 | 59.3 | 67.0 | 67.2 | 80.0 | 56.0 | 88.3 | 94.4 | 69.1 |
| 25 | s025 | field-matching neighbourhood 120 | 71.40 | .958 | 59.5 | 67.2 | 68.1 | 80.0 | 56.0 | 88.3 | 94.4 | 69.9 |
| 26 | s026 | field-matching neighbourhood 300 | 71.68 | .958 | 59.7 | 67.3 | 68.7 | 80.2 | 56.0 | 88.3 | 94.4 | 70.4 |
| 27 | s027 | field-matching neighbourhood 1000 | 71.60 | .958 | 59.5 | 66.9 | 68.5 | 80.1 | 56.0 | 88.3 | 94.4 | 70.5 |
| 28 | s028 | + PCA-spectrum anisotropy interpolation (strength 1) | 71.96 | .950 | 59.7 | 67.3 | 68.7 | 80.2 | 56.4 | 91.4 | 94.4 | 70.4 |
| 29 | s029 | anisotropy strength 2 | 71.82 | .934 | 59.7 | 67.3 | 68.7 | 80.2 | 56.6 | 89.4 | 94.4 | 70.4 |
| 30 | s030 | state weight w = f^0.85 = 0.394 | 72.70 | .950 | 59.6 | 67.6 | 70.4 | 80.4 | 56.4 | 91.4 | 94.4 | 72.1 |
| 31 | s031 | state weight w = f^0.7 = 0.463 | **72.96** | .950 | 59.5 | 67.6 | 71.4 | 79.5 | 56.4 | 91.4 | 94.4 | 73.0 |
| 32 | s032 | state weight w = f^0.55 = 0.545 | 72.48 | .950 | 60.0 | 67.8 | 71.0 | 76.9 | 56.4 | 91.4 | 94.4 | 72.0 |
| 33 | s033 | state weight w = f^0.75 | 72.91 | .950 | 59.7 | 67.5 | 71.1 | 79.9 | 56.4 | 91.4 | 94.4 | 72.7 |
| 35 | s035 | field-matching neighbourhood 600 | 72.92 | .950 | 59.7 | 67.3 | 71.3 | 79.5 | 56.4 | 91.4 | 94.4 | 72.9 |
| 36 | s036 | scaffold = later bracket at f = 1/3 | 66.81 | .941 | 57.9 | 62.3 | 70.1 | 75.6 | 50.9 | 46.7 | 94.4 | 70.9 |
| 37 | s037 | anisotropy strength 1.4 | 72.96 | .942 | 59.5 | 67.6 | 71.4 | 79.5 | 56.5 | 91.2 | 94.4 | 73.0 |
| 39 | s039 | + radial-profile interpolation | 72.82 | .950 | 59.5 | 67.6 | 71.4 | 79.5 | 55.8 | 90.2 | 94.4 | 72.9 |
| 40 | s040 | descriptor embedding 60 components | 72.93 | .950 | 59.5 | 67.7 | 71.3 | 79.5 | 56.4 | 91.4 | 94.4 | 72.8 |
| 41 | s041 | w = f but *all* cells placed by field matching | 71.95 | .950 | 59.3 | 66.7 | 67.9 | 79.9 | 56.4 | 91.4 | 94.4 | 71.4 |
| 42 | s042 | best configuration, different internal draw (stability) | 71.97 | .946 | 58.5 | 67.6 | 71.3 | 79.9 | 55.9 | 80.7 | 94.4 | 73.1 |
| 43 | s043 | unbiased native subset, transplants take the leftovers | 70.84 | .950 | 59.5 | 66.4 | 70.1 | 79.0 | 56.4 | 91.4 | 94.4 | 66.1 |
| 44 | s044 | cosine descriptor matching | **73.06** | .950 | 60.1 | 67.7 | 71.4 | 79.5 | 56.4 | 91.4 | 94.4 | 73.0 |
| 45 | s045 | volume-covering position sample | 72.18 | .956 | 59.1 | 67.5 | 71.0 | 79.2 | 55.8 | 85.9 | 94.4 | 72.4 |
| 46 | s046 | volume-covering position sample, second draw | 72.16 | .956 | — | — | — | — | — | — | — | — |
| 48 | s048 | cleaned final code (refactor check) | 73.06 | .950 | 60.1 | 67.7 | 71.4 | 79.5 | 56.4 | 91.4 | 94.4 | 73.0 |
| 49 | s049 | radius × 1.06 (scale-bias probe) | 73.45 | .950 | 60.1 | 67.7 | 71.4 | 79.5 | 56.4 | 91.4 | 99.1 | 73.0 |
| 50 | s050 | **concave radius growth c = 0.15** | **73.49** | .950 | 60.1 | 67.7 | 71.4 | 79.5 | 56.4 | 91.4 | 99.6 | 73.0 |
| 51 | s051 | state weight w = f^0.78 | 73.42 | .950 | 60.1 | 67.5 | 71.1 | 80.1 | 56.4 | 91.4 | 99.6 | 72.7 |
| 52 | s052 | state weight w = f^0.62 | 73.23 | .950 | 59.9 | 67.8 | 71.2 | 78.4 | 56.4 | 91.4 | 99.6 | 72.5 |
| 54 | s054 | radius × 1.03 (bracketing probe) | 73.47 | .950 | 60.1 | 67.7 | 71.4 | 79.5 | 56.4 | 91.4 | 99.3 | 73.0 |
| 55 | s055 | radius × 0.97 (bracketing probe) | 72.61 | .950 | 60.1 | 67.7 | 71.4 | 79.5 | 56.4 | 91.4 | 89.0 | 73.0 |
| 56 | s056 | quadratic state-warp form (same value at f = 1/3) | 73.49 | .950 | 60.1 | 67.7 | 71.4 | 79.5 | 56.4 | 91.4 | 99.6 | 73.0 |
| 57 | s057 | FINAL re-run (identical snapshot) | **73.49** | .950 | 60.1 | 67.7 | 71.4 | 79.5 | 56.4 | 91.4 | 99.6 | 73.0 |

`testcheck.py` (inputs E7.5+E8.0 → 7.75): **PASS** (run twice, on the settled structure and on the final file).

## 5. Hypotheses tested, and the evidence

* **State fraction.** With poor placement the mixture weight looked optimal at w = f; with good placement both
  distribution metrics (`mmd_u`, `neighborhood_mmd`) peak at w ≈ 0.46 when f = 1/3, i.e. the cell states move
  faster than clock time. `variogram` peaks near w = f and is the only term that disagrees; at weight 0.10 it
  loses to the two stronger terms. A quadratic warp `w = f + c·f(1−f)` reproduces the same optimum, so the effect
  is a property of the stage pair's positions on the trajectory, not of the functional form.
* **Real profiles beat averaged profiles.** Blending a transplant 50 % toward the host profile costs 11 points of
  `mmd_u`. Every output cell must be an observed profile.
* **Duplicate positions are expensive.** Placing transplants on the nearest expression-matched cells (the starting
  program's rule, and every capacity-limited variant) buys `neighborhood_mmd` (+4 to +6) but drops
  `native_occupancy` from .958 to .88–.90, below the hard 0.90 gate; jitter repairs the gate only to .90 and costs
  part of the gain. Keeping the *position multiset* a uniform subsample of the native cloud and letting the donor
  choose its best *free* position recovers most of the gain with `native_occupancy` .958.
* **Match against the local field, not the single cell.** Describing a candidate position by its 300-NN
  neighbourhood pseudobulk instead of by the cell's own profile is the largest single improvement of the round:
  +5.8 `neighborhood_mmd` at fixed positions, and it improves monotonically as the descriptor's neighbourhood
  grows (15 → 300) before plateauing (1000 ≈ 300). The metric is defined on exactly that quantity, and the smooth
  descriptor is far more robust to stage offsets and single-cell noise than a raw profile match. Cosine similarity
  between descriptors is a small further gain.
* **The native subset bias is beneficial.** Letting the transplants claim positions first makes the leftover
  "native" cells the ones least resembling advanced states; making that subset unbiased instead costs 2.2 points
  of `neighborhood_mmd`. Transcriptionally distinct states ending up in distinct places is what the truth looks
  like.
* **Composition attenuation is wrong here.** Thinning donor states that the earlier bracket does not represent
  (κ = 1.5, each replaced by its nearest earlier counterpart as a "precursor") costs 1.1 total: the truth keeps
  more of those states than a precursor-substitution model predicts, i.e. the composition moves closer to linear
  than a naive "new types are absent earlier" story suggests.
* **Full re-placement is wrong.** Matching *every* cell (not just transplants) to its best position costs 1.0 —
  scaffold cells are the best possible evidence for their own location.
* **Anisotropy interpolates.** Stretching the scaffold's principal axes toward the interpolated spectrum raises
  `occupancy_dice` 88.3 → 91.4 and `d2_shape` 56.0 → 56.4 for free; strength 2 overshoots. Interpolating the
  *radial* profile on top is slightly negative.
* **Radius is systematically underestimated by log-linear interpolation.** Probing ±3 % around the log-linear
  rule shows the true radius at f = 1/3 is ~4 % larger than the geometric interpolation of the two brackets;
  a concave growth term `exp(c·f(1−f))` with c = 0.15 takes `scale_log_ratio` from 94.4 to 99.6.
* **Scaffold choice matters more than anything else in the shape group.** Using the later bracket's cloud at
  f = 1/3 costs 6.7 points (occupancy_dice collapses to 46.7). The rule therefore prefers the earlier bracket on
  an exact tie, which is also what the test configuration (f = 0.5) hits.

## 6. Open ideas for the next rounds

1. **de_score / de_direction (15.7 of 25 points, weight .25) are the largest untouched block.** The predicted
   direction is locked to `pb(E7.25) − pb(E8.0)` by construction; the truth's partial-interval direction overlaps
   it only about half as well as the truth's own split half does. The candidate mechanism is *non-monotone*
   (transiently peaking) genes, which two bracketing stages cannot identify directly — a prior distilled from the
   released E6.75/E8.0 pair (abundance-driven vs regulatory change, per matched cell type) into a small asset file
   is the obvious next attack. Both metrics are rank-based, so only the *direction* needs improving.
2. **A second coupling pass.** The transplant placement is a one-shot greedy match; a swap-based refinement that
   minimises the output's own 15-NN field misfit (the exact quantity scored) is cheap and untried.
3. **Spatial registration as a competing placement.** The local-field match is a nonparametric registration in
   expression space; a rigid/affine registration of the donor frame onto the scaffold (estimated from matched
   cell-type centroids, which are weak in expression but meaningful in canonical space) would preserve the donor's
   own field structure and could beat it on `neighborhood_mmd`.
4. **Between-stage radii.** The concave growth term is fitted at one fraction; measuring it on the test interval
   (E7.5→E8.0, f = 0.5) is only possible through the hidden runs, so its form (vanishing at both endpoints) is
   deliberately conservative.
5. **Cell count.** The board compares shape at a matched cell count, but the *density* of a prediction still sets
   the 15-NN scale used by `neighborhood_mmd`; outputting a count matched to the expected 10 % sample of the target
   (estimated from the inputs' own cell counts) is untested and may be worth a point.

## 7. Sources

* Harland et al., *A spatiotemporal atlas of mouse gastrulation and early organogenesis* (Cell Reports 2025) —
  https://www.sciencedirect.com/science/article/pii/S2211124725008186 — used for: the E7.25/E7.5 stages are
  consecutive mid-gastrulation time points with substantial cell-state change packed into 0.25 day, which is the
  qualitative basis for the state weight being > the clock fraction.
* *Digital reconstruction of full embryos during early mouse organogenesis* (Cell 2025) —
  https://www.sciencedirect.com/science/article/pii/S0092867425006221 — used for: E7.5–E8.0 is the window in
  which regionalisation (neural, cardiac, foregut) appears, i.e. the two brackets of the test configuration differ
  mainly by the emergence of new regional states.
* UNSW Embryology, *Mouse E8.0* — https://embryology.med.unsw.edu.au/embryology/index.php/Category:Mouse_E8.0 —
  used for: foregut pocket and cardiogenic plate are present only from ~E8.0, so the E8.0-only labels (V-FG, D-FG,
  SHF/FHF, forebrain) are genuinely late-appearing rather than annotation artefacts.
* `veckit` 0.1.1 metric source (`common/core_metrics.py`, `common/shape_metrics.py`, `T2/metrics_v2.py`) and
  `vec_local_score` (local scorer wrapper) as installed in the environment — the definitions in section 1.
