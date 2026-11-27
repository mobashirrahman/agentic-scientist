# Research notes (round 0)

## Question and setup

Predict E10.5 (validation) and, later, a chamber-dissected later stage (E12.5 target).
The control is the exact seeded empirical donor sampler in the original `program.py`:
sample rows from the latest input stage with weights from observed broad-type growth,
then return them unchanged. All my work keeps that sampler as the row generator and
changes only (a) the expression of already-sampled rows and (b) broad-type sampling
weights, evaluated as separate ablations.

Local data used: `data/train/E8.5_RNA.h5ad` and `E9.5_RNA.h5ad` only. The E10.5 score
comes from `tools/evaluate.py`; I did not access guard data, answers, other runs, or
submission endpoints. All experiments and scripts are in `experiments/`.

Expression is log1p CP10k: expm1 row sums are 1e4 and 86.5% of entries are zero.
Output cells are kept sparse, nonnegative, finite float32, and renormalized to exact
CP10k after the step.

## Hypotheses

- **H1 (maturation).** A bounded within-type displacement along the observed
  E8.5->E9.5 change is a better forecast of the next day than holding donor rows
  fixed, because it moves cell states toward the future while preserving real donor
  profiles and zeros.
- **H2 (transfer).** The direction estimated from one successive pair transfers to the
  next interval, and remains useful when extrapolated over two days.
- **H3 (measurement/batch).** The component shared by all cell types is mostly
  technical (sex, dissociation, ribosomal/mitochondrial), so removing it should help.
- **H4 (composition).** Growth of types that first appear in the later stage is real
  signal at E10.5, but a chamber dissection should never increase surrounding tissue
  or circulating blood.
- **H5 (amplitude).** Gains grow with horizon-scaled amplitude up to a point, and the
  step should be bounded per gene and per day.

## Method implemented (`program.py` + `agentic_scientist.py`)

1. Map labels through `ALIASES` (adds LV-CM/RV-CM -> Ventricular cardiomyocyte; the
   original map only knew V-CM).
2. Composition weights: `w = exp(0.5 * horizon * growth)`, where growth is the clipped
   log ratio of latest/earlier frequencies (clipped at +/-log 2). Types absent from the
   earlier stage get `+log 2` (emerging), except that non-chamber types are capped at
   zero growth. `horizon = clip((target - latest)/(latest - earlier), 0, 2)`.
3. Sample `context['n']` donor rows from the latest stage with those weights
   (with replacement, seeded by `context['seed']`), exactly as the control.
4. Estimate a per-type, per-gene one-day log1p change from the two passed inputs:
   pseudobulk means and variances per matched group, empirical-Bayes posterior
   `d * tau^2/(tau^2 + se^2)` with `tau^2 = var(d) - mean(se^2)`, clipped to
   `+/-0.5` log1p per gene per day. Groups with fewer than 50 cells in either stage
   get no type-specific step; groups present only in the later stage get the
   cell-weighted shared step (fallback).
5. Apply the step multiplicatively on the CP10k scale:
   `x' = log1p(expm1(x) * exp(scale * posterior))`, `scale = horizon` (STEP_SCALE=1).
   Zeros stay exactly zero, and each cell's relative profile is scaled rather than
   rewritten.
6. Renormalize every cell back to expm1 sum 1e4, so output units remain exact
   log1p CP10k.
7. Align the output panel to `context['genes']` (reorder, pad missing genes with zero)
   and enforce `context['min_cells']/['max_cells']`.

Runtime ~6 s for 3000 x 32285 cells; testcheck ~10 s.

## Offline controls (no evaluation budget)

- **Split-half generalization.** Estimate the shift on half the cells of each stage and
  test pseudobulk transfer on the held-out half. Mean absolute pseudobulk error falls
  by 30-60% for every matched type (ratio after/before 0.39-0.90, median ~0.57).
  The direction is not an artifact of the particular cells used.
- **Per-gene replication.** Estimating the posterior independently on two disjoint cell
  halves gives median per-gene correlation 0.897 across all 32285 genes, 0.977 on the
  top 1000 genes, sign agreement 1.00, and top-100 overlap 56-88/100 (weakest for Blood,
  n=213). The per-gene direction is reproducible, not only the type pseudobulk.
- **Bounds at the final horizon (2 days).** Composition weights are bounded to
  [0.5, 2.0] for observed growth and <=1.0 for non-chamber types; the per-gene
  multiplicative factor is bounded to exp(+/-1.0) = [0.37, 2.72] before renormalization.
  Amplitudes are therefore finite and tied to the forecast horizon.
- **Gap closure.** Projection of the shifted pseudobulk onto the true E8.5->E9.5 gap:
  median 0.29 at one day, 0.57 at two days; off-axis displacement 0.18 / 0.36. The step
  moves toward the observed direction and remains partial, i.e. conservative.
- **Sparsity/profile.** Zero count unchanged exactly; per-cell cosine to the same donor
  row 0.9987 at one day and 0.9949 at two days.
- **Units.** After shifting, cells are renormalized to expm1 sum 10000.000 (float32
  range 9999.999-10000.002); maximum value 7.27 at one day and 7.60 at two days, below
  log1p(1e4)=9.21.
- **Seed stability.** With n=1000 and 8 seeds, the per-type composition SD is 0.006
  (max 0.013) and the seed-to-seed pseudobulk L2 is 1.90. The same-row step displacement
  is L2=2.07 at both n=1000 and n=3000 (it is a deterministic per-cell transform), so
  the systematic step is ~1.1x sampling noise at n=1000 and ~1.8x at n=3000. At the
  final two-day amplitude it is ~3.5x at n=3000. The step is deliberately modest; the
  evaluation gains come from its consistent direction, not from dominating noise.
- **Runtime.** Max-size final path (n=5118, three inputs, 32285 genes): 8.9 s and
  2.1 GB peak RSS, with exact CP10k and finite values. Validation n=3000 runs in ~6 s.
- **Shared component.** 28.5% of step energy is shared across types; top genes include
  ribosomal, glycolytic, heat-shock and Xist. This is a mixture of real metabolic
  maturation and protocol/sex drift (see H3 result below).

## Evaluation ledger (validation = E8.5+E9.5 -> E10.5, n=3000)

| # | snapshot | score | DE | dir | MMD | vario | change |
|---|----------|-------|----|-----|-----|-------|--------|
| 1 | s001 | 48.85 | 39.8 | 55.4 | 50.8 | 49.1 | control donor sampler |
| 2 | s002 | 50.50 | 43.4 | 56.6 | 52.1 | 49.4 | EB multiplicative step, scale=horizon, alias-aware weights |
| 3 | s003 | 51.19 | 44.6 | 56.5 | 53.6 | 49.3 | 2x amplitude on one-day target |
| 4 | s004 | 49.28 | 40.3 | 56.5 | 50.6 | 49.5 | composition only (alias map), maturation off |
| 5 | s005 | 48.40 | 41.3 | 53.2 | 50.8 | 47.6 | no growth boost for unmatched types |
| 6 | s006 | 51.00 | 44.6 | 57.8 | 52.3 | 48.6 | chamber-aware growth cap |
| 7 | s007 | 51.52 | 45.0 | 57.7 | 53.8 | 48.4 | chamber cap + 2x amplitude |
| 8 | s008 | 49.62 | 40.3 | 57.4 | 51.7 | 48.3 | remove shared across-type component |
| 9 | s009 | 51.22 | 45.1 | 57.8 | 52.6 | 48.5 | shared-step fallback for later-only types |
| 11 | s011 | 50.81 | 44.3 | 57.6 | 53.1 | 47.0 | additive log1p step instead of multiplicative |
| 12 | s012 | 51.62 | 45.2 | 57.6 | 54.3 | 48.2 | fallback + 2x amplitude |
| 13 | s013 | 51.31 | 45.4 | 57.8 | 52.7 | 48.5 | per-gene cap 0.75 |
| 14 | s014 | 51.69 | 45.3 | 57.6 | 54.4 | 48.2 | cap 0.75 + 2x |
| 15 | s015 | 50.31 | 44.0 | 56.2 | 52.3 | 48.0 | composition exponent 0.75 |
| 16 | s016 | 51.01 | 44.6 | 56.8 | 53.0 | 48.9 | composition exponent 0.35 |
| 17 | s017 | 51.22 | 45.1 | 57.8 | 52.6 | 48.5 | nominated pre-renormalization |
| 19 | s019 | 51.60 | 45.6 | 58.2 | 52.9 | 48.9 | + exact CP10k renormalization |
| 20 | s020 | 52.57 | 45.6 | 58.6 | 55.2 | 49.7 | + renormalization at 2x (two-day control) |
| 21 | s021 | 51.60 | 45.6 | 58.2 | 52.9 | 48.9 | final nomination confirmation |
| 23 | s023 | 50.56 | 44.0 | 57.2 | 52.4 | 47.6 | 0.5x targeted down-weight of surrounding tissue (rejected) |

## What the diagnostics say

- **H1 supported.** The step raises every headline component (s001 -> s002, +1.65).
  Multiplicative scaling beats additive (s009 vs s011, +0.41), mainly on variogram
  (48.5 vs 47.0), consistent with preserving donor co-expression and zeros.
- **H2 supported.** Doubling the one-day step still improves the one-day forecast
  (s019 -> s020, +0.97), with all four components non-decreasing. Median gap closure
  rises from 0.29 to 0.57, so the mechanism is not saturating or overshooting badly at
  the horizon the final task will use (E12.5 from E10.5 = 2 days).
- **H3 refuted.** Removing the shared component costs 1.4 points (s006 -> s008). The
  common metabolic/ribosomal shift is predictive even if it likely contains batch/sex
  drift. I kept it, but this is the main measurement-effect risk.
- **H4 partially supported.** Emerging types matter at E10.5: suppressing their growth
  is much worse (s005, 48.40). But capping non-chamber types at zero growth while
  retaining chamber-type growth improves the score (s006, +0.50) and matches the
  chamber-dissected final protocol. Stronger growth (0.75 exponent, s015) hurts; weaker
  growth (0.35, s016) is slightly worse than 0.5. The 0.5 exponent is a local optimum.
  Blood growth is negative from E8.5 to E9.5 (1.58% -> 1.25%, weight ~0.89) and is never
  increased; it is not in the chamber allow-list. An explicit 0.5x down-weight of
  surrounding (non-cardiac) tissue (s023) cost 1.04 and was rejected: at E10.5 those
  cells are real, and removing them hurt DE and variogram more than the chamber prior
  can justify without chamber-stage truth.
- **H5 supported.** Per-gene cap 0.75 adds only +0.09 at one day (s013) and +0.07 at
  two days (s014), while a higher effective amplitude via horizon scaling adds much
  more. The 0.5 cap plus horizon scaling is the conservative choice. Renormalization is
  not just cosmetic: it adds +0.38 at one day and +0.95 at two days (s017 -> s019,
  s012 -> s020), probably by keeping shifted cells on the CP10k manifold.
- **Panel robustness.** The shift estimator aligns the earlier panel to the latest
  panel gene-by-gene; missing genes get zero step. Reordered/subset panels give nearly
  identical pseudobulk (mean difference ~0.0017 log1p).

## Module-level reading of the estimated direction

Mean posterior over curated modules (matched types only; unmatched types show the shared
fallback by construction):

- **Proliferation (20 genes).** Down in 11/12 matched types: OFT/RV mean -0.181
  (20/20 genes down), IFT-CM -0.134 (18/20), AVC-CM -0.072 (17/20), pSHF -0.044.
  The exception is Ventricular cardiomyocyte (+0.080, 17/20 up).
- **Sarcomere (15 genes).** Up in OFT/RV (+0.118, 11/15) and IFT-CM (+0.319, 12/15);
  mixed/down in V-CM (-0.130) and SV-CM (-0.400).
- **Glycolysis (8 genes).** Down in cardiomyocytes and most other types (V-CM -0.132,
  OFT/RV -0.093, Pericardium -0.148), consistent with a switch toward oxidation.
- **OXPHOS (8 genes).** Up in OFT/RV (+0.196), AVC-CM (+0.188), IFT-CM (+0.264),
  V-CM (+0.048), most other types small positive.
- **Fetal markers.** Nppa/Nppb down in V-CM (-0.303) and OFT/RV (-0.269).
- **Stress module.** Down in most matched types (OFT/RV -0.047, SV-CM -0.102,
  Foregut -0.125, Blood -0.130).

This is why the shared component is predictive (H3): the common direction carries
coherent metabolic maturation (glycolysis down, OXPHOS up), proliferation down, and
fetal-marker down. The V-CM exception is likely the validation-only merge of E8.5
LV-CM/RV-CM into V-CM, which changes the subtype mixture inside the group; E9.5 and
E10.5 both use V-CM, so the final pair should suffer less from this artifact. If the
final annotations differ, use a stricter label map for shift estimation than for
composition weighting.

## Nominated candidate

`program.py` + `agentic_scientist.py` as left in the workspace:

- Empirical donor rows, fixed after sampling.
- Multiplicative empirical-Bayes within-type step, clipped at 0.5 log1p/gene/day,
  scaled by `horizon = clip((target-latest)/(latest-earlier), 0, 2)`.
- Cell-weighted shared-step fallback for types absent from the earlier input.
- Exact log1p CP10k renormalization after the step.
- Chamber-aware composition: allow observed growth for heart-resident types, never
  increase surrounding tissue; zero growth for unmatched non-chamber types.
- Panel alignment to `context['genes']`, n respected within min/max, sparse float32.

One-day validation: **51.600** (de 45.6, direction 58.2, MMD 52.9, variogram 48.9).
Effective final-horizon (2-day) control on the one-day target: **52.570**
(de 45.6, direction 58.6, MMD 55.2, variogram 49.7).
`tools/testcheck.py`: PASS on the final files.

Final status: the workspace code is the s021 candidate (eval #21, 51.600, plus a final
testcheck PASS after restoring it). The last experiment, s023 (0.5x surrounding-tissue
down-weight), was rejected and fully reverted. The evaluation budget is exhausted
(0 left); 1 format check remains.

Note on the service's "previous best": s020 (52.570) is not a different candidate. It is
the same code with STEP_SCALE=2 evaluated against a one-day target, i.e. the two-day
amplitude control. The nominated code keeps STEP_SCALE=1, so at the final E12.5 horizon
(2 days) it applies the same effective two-day amplitude that s020 measured. Its
one-day validation score is 51.600; the final score will differ because the target and
dissection protocol differ.

Inference-contract hardening (post-score, behavior-preserving): the scored path used
in-memory sparse inputs. I added guards for backed AnnData (`to_memory()` at entry) and
dense matrices (CSR conversion in the step and renormalization); neither changes the
in-memory sparse computation or the RNG stream. `experiments/edge_cases.py` passes:
backed inputs, single input, n above max_cells (clamped), backward target (horizon 0),
unseen label vocabulary, reordered panel with a missing gene (zero-padded).
`tools/testcheck.py` PASS after the change.

## Transfer rationale and risks

- The maturation mechanism is the part I trust most: it is derived only from passed
  inputs, passes split-half transfer, preserves zeros/profiles/units, and improves all
  four components at both one- and two-day amplitude.
- The chamber-aware composition cap is a protocol prior, not a fitted parameter. It
  improved E10.5 and should be safer for a chamber dissection than boosting every
  emerging type. The main residual risk is that the final target's true composition
  differs (e.g. more epicardium/endocardium, less pericardium/endothelium); the cap
  only prevents increases, so it cannot inflate surrounding tissue.
- The retained shared component may encode protocol/sex drift specific to the released
  stages. If the final inputs have a different batch structure, this is the most likely
  source of regression. I did not find a way to separate biological from technical
  parts with only two stages without losing accuracy (H3).
- The final task's latest pair will be E9.5->E10.5 (if E10.5 is supplied), which is a
  more relevant direction than the validated E8.5->E9.5 pair. No averaging across both
  pairs was implemented because it could not be validated here; it is a reasonable
  next experiment.
- I tested an explicit chamber-priority treatment: a 0.5x down-weight of surrounding
  (non-cardiac) tissue (Foregut, Hepatocyte, ST, Epithelium, Surface Ectoderm, neural
  tube, paraxial mesoderm, etc.) on top of the nominated config (s023). It reduced the
  E10.5 score to 50.56 (DE 44.0, direction 57.2, MMD 52.4, variogram 47.6), costing
  1.04 with every component lower. I reverted it. The loss in DE and variogram, not
  just MMD, says that dropping real donor cells is a larger distortion than the
  chamber-composition prior justifies without chamber-stage truth. The chamber cap
  (never increase surrounding tissue) remains the conservative protocol treatment; a
  future round with a chamber control could calibrate a milder down-weight.
- I did not increase circulating blood, and did not chase the E10.5 score with larger
  composition growth (which hurt anyway).

## What could carry over to the final task

1. The horizon-scaled, clipped, multiplicative within-type step with CP10k
   renormalization and exact zero preservation.
2. The shared-step fallback for newly annotated cell types.
3. Alias-aware, chamber-capped composition, especially the "never increase surrounding
   tissue" rule.
4. The offline controls (split-half pseudobulk transfer, gap projection, sparsity/
   units checks) as cheap regression tests for later rounds.
5. Avoid removing the shared component and avoid additive shifts; both were measured
   regressions.
6. A chamber-priority down-weight of surrounding tissue is plausible but cost 1.04 at
   E10.5 without chamber truth (s023); calibrate it only with a chamber-stage control.

## Literature

- Cao J et al. The single-cell transcriptional landscape of mammalian organogenesis.
  Nature 2019;566:496-502. (mouse embryonic cell-state manifolds and staged atlases)
- de Soysa TY et al. Single-cell analysis of cardiogenesis reveals basis for organ-level
  developmental defects. Nature 2019. (staged mouse heart single-cell atlas; chamber and
  progenitor composition)
- Asp M et al. A spatiotemporal organ-wide gene expression and cell atlas of the
  developing human heart. Cell 2019;179:1647-1660. (chamber, endocardium, epicardium
  and valve populations across development)
- Moorman AF, Christoffels VM. Cardiac chamber formation: development, genes, and
  evolution. Physiol Rev 2003;83:1223-1267. (chamber identity and ballooning model)
- Guo Y, Pu WT. Cardiomyocyte maturation: new phase in development. Circ Res
  2020;126:1086-1106. (sarcomere/metabolic maturation program used to interpret the
  ventricular shift)
- Tyser RCV et al. Characterization of a common progenitor pool of the epicardium and
  myocardium. Science 2021;371:eabb2986. (proepicardium/epicardium and myocardial
  progenitors)
- Efron B, Morris C. Data analysis using Stein's estimator and its generalizations.
  JASA 1975;70:311-319. (empirical-Bayes shrinkage used for per-gene steps)
- Aitchison J. The statistical analysis of compositional data. J R Stat Soc B
  1982;44:139-177. (why composition is analyzed on log-ratio scale and separately)
- Haghverdi L et al. Batch effects in single-cell RNA-sequencing data are corrected by
  matching mutual nearest neighbors. Nat Biotechnol 2018;36:421-426. (motivation for
  treating the shared cross-stage component cautiously)
- Gretton A et al. A kernel two-sample test. JMLR 2012;13:723-773. (MMD-like
  distribution comparison)
- Cressie N. Statistics for Spatial Data. Wiley 1993. (variogram-based structure)
- Wolf FA, Angerer P, Theis FJ. SCANPY: large-scale single-cell gene expression data
  analysis. Genome Biol 2018;19:15. (log1p CP10k conventions and AnnData tooling)
