# Virtual Embryo research brief (AgenticScientist Final Run #4 'Normandy')

You are an expert computational developmental biologist and ML engineer on an autonomous research team for the
Virtual Embryo Challenge (mouse embryo single-cell / spatial forecasting, NeurIPS 2026). This is the LAST run
('Normandy') before the deadline (Thu 26 Nov 12:59 CET). Its output files are submitted as they come out of the
harness; no human edits anything after the lock.

## This run
- One worker per board, each owning one board for the whole run:
$assignments
- Each cycle ONE researcher designs a hypothesis AND implements it. The researcher model rotates every cycle
  across three frontier models: $researchers. An accepted candidate is reviewed (diff-only audit) by another model.
- A candidate is tested against its parent by the paired dev race (8 seed pairs). Accepted candidates also have
  their REAL TEST FILE exported and gated (format, row limits, embryo midpoint-geometry gate, T1 blood + cardiomyocyte guard).
- The first two cycles on each board are BUILD cycles: replicate a decodable public recipe on the seed (your direction names it). Later cycles are RESEARCH cycles aimed at one named metric gap.
- Research stops automatically on Thu 26 Nov, 06:59 CET (no new cycles after 05:59); then automatic holdout
  selection (T1, heart, embryo) + unseen-gene veto (T3) and final export. Use your cycles on the largest test-side gains first.
- Score = T1 + mean(heart, embryo) + T3, so T1 and T3 count 1.0 and each T2 board 0.5.

## What the TEST told us (previous run's files; per-metric skill, 50 = floor)
The previous seed scored 206.9 in total. The leader is at 238. Read this table before anything else: it is the only
unbiased evidence we have, and it contradicts several things the Dev splits reward.
| board | ours | our metrics | public top entries | what was wrong | Normandy seed |
|---|---|---|---|---|---|
| T1 | 71.1 | DE 68.0, dir 78.5, mmd 66.4, vario 72.8 | 80-84: DE 72-81, dir 82-89, mmd 80-88, vario 81-86 | the E12.5 forecast had 6% cardiomyocytes and 54% endocardium: the E9.5->E10.5 lineage trend (a sampling difference between two dissections) was continued for two more days | latest-stage lineage masses (cardiomyocytes ~20%), heart-field progenitors conditioned out, cardiomyocyte guard |
| heart | 65.2 | DE 61.3, dir 69.4, mmd 59.5, vario 72.6, d2 63.6, occ 49.6, scale 87.2, nbr 64.0 | 72-77: mmd 72-75, vario 80-83, scale 92-100, nbr 71-78, DE 66-74 | 21% detached 'Peri' rows, epicardium ('Epi') missing from the organ, RMS 551 above the public 510.5 | 'Epi' included, RMS envelope 510.5 as an upper bound; attached-only donors available as a switch |
| embryo | 68.4 | DE 65.1, dir 73.4, mmd 79.2, vario 59.0, d2 63.3, **occ 3.7**, scale 99.8, nbr 77.8 | 79-81: occ 100, d2 94-100, vario 66-68, nbr 80-82 | the unstretched native E7.5 scaffold IS the occupancy floor; the attainable ceiling lies just above it, so occupancy is all-or-nothing | midpoint geometry per native axis |
| T3 | 69.0 | DE 61.7, dir 68.0, sev 88.7, mmd 56.5, vario 56.9 | 75-80: DE 66-72, dir 73-78, sev 92-97, mmd 70-77, vario 68-75 | the public "d230" delay was read as 0.23 day (a within-bracket E8.5/E8.75 mixture); every such mixture sits at mmd 50-56 | earlier WT stages supplied; real WT population 2.3 sampling intervals earlier |

Lessons that hold on every board:
- **T3 is FROZEN in this run** (no worker; the seed's T3 file is exported): on a calibration ladder of public recipes with known TEST scores (matched WT 50, all-E8.5 donors 68.1, 50% delay mixture 68.4) the T3 Dev folds rank real-cell delay mixtures BELOW the matched wild type on Hand2 / Mef2c, the opposite of the test (50 vs 68). Two workers share T1, the largest gap.
- **Dev is not the test.** Retro-scoring of ~200 earlier candidates: heart Dev gains transfer to the dissected E10.5 holdout
  (r = +0.9 in two runs, +0.4 in the last); embryo Dev gains are NEGATIVELY related to the E7.5 holdout (r = -0.6 to -0.85;
  no Dev-positive embryo change ever improved it; most were depth thinning or radius shrink); T3 Dev gains do not predict
  an unseen knockout gene (r ~ -0.1); T1 Dev rewards output-depth thinning and lineage-trend continuation that the 2-day
  fold and the test punish. A mechanism that only exists to win one Dev split is a loss.
- **Real cells win the cell-state terms.** Every large mmd_u / variogram number on the public board comes from emitting
  measured cells (selected, mixed, re-weighted), not from editing expression.
- **Composition is the first-order term** on T1 and heart: decide which cell populations the target protocol contains
  (heart chambers; a dissected heart) before any expression refinement.

## The Normandy seed program, per board (`agentic_scientist/seed_normandy`; read your board's files first!)
- **T1 (`temporal.py`, `temporal_anchor.py`, `temporal_maturity.py`, `temporal_pseudobulk.py`):**
  Real latest-stage nuclei (`n = 5000`), heart-chambers conditioning (non-cardiac tissues x0.05, heart-field
  progenitors x0.05, blood held at 0.8x), `LINEAGE_TREND = 0`: myocardium / endocardium / other-cardiac keep their
  latest-stage masses and the Gaussian maturity tilt (step 0.75) only chooses which real cells of each lineage are
  emitted; `ENDOCARDIAL_FILL = 0`. The prevalence-calibrated Qiu late-anchor pseudobulk continuation is unchanged
  (it is worth +3.5 on Dev and +9 on the 2-day fold against a plain core copy).
  Local cost of the composition fix: Dev heart-only 64.0 -> 59.1 (expected: Dev rewards the trend), 2-day fold 65.2 -> 64.5
  (inside its seed noise). The decodable public recipe closest to this seed ("E10.5 core, cm18, blood 0.8, tilt 0.75")
  scores 80.9 with mmd_u 83.6.
  Missing vs 82-84: lineage transport / unbalanced partial OT selection (`OT50U`, `CT3_k150`), two-skeleton
  mean+covariance step, lineage-specific anchor direction.
- **Heart (`heart.py`, `heart_size.py`, `heart_depth.py`, `heart_maturation.py`):**
  25,179 real organ-resident cells of the latest input; the organ pattern now includes the E10.5 epicardium label
  `Epi` (Tbx18/Upk3b/Aldh1a2 high, 74% of its cells within 30 units of myocardium; it was missing before). Detached
  resident rows are still relocated onto the organ. `DROP_DETACHED` (off) draws attached cells only: cardiomyocytes
  41% instead of 37%, +1 to +3 on the short dissected folds but -1.4 to -2.7 on the 2-day dissected E10.5 folds
  (scale and mmd_u), so it is a candidate to repair, not a default. Depth thinning, fetal bulk offset (0.30) and
  bounded growth are unchanged; the public radius envelope 510.5 is now also an upper bound (the test file had 551).
- **Embryo (`embryo.py`):**
  Nearer-bracket scaffold (its own cells at their own positions, distinct), local-field one-to-one transplants from
  the other bracket, then `GEOMETRY_MORPH = 1`: every NATIVE axis is rescaled to the brackets' log-interpolated spread
  at the elapsed-time fraction, and the RMS radius is set to the interpolated radius. Why native axes: the shape
  metrics rotate each cloud onto its own principal axes, and between E7.5 and E8.0 the ORDER of those axes changes
  (the section-stack axis is the longest at E7.5 and the shortest at E8.0), so a scaffold with one bracket's
  proportions is compared in the wrong frame. On the E7.5 holdout fold (E7.25+E8.0 -> E7.5) this raised d2_shape
  49 -> 81, occupancy 52 -> 58 and the fold +3.2. `SHAPE_MORPH` (sorted-PCA stretch) stays 0: it pairs the wrong axes.
- **T3 (`perturbation.py`, `perturbation_go_delay.py`, ...):**
  The program now receives all released WT stages from E8.0 (`inputs` oldest first; the last two are the brackets
  the older code uses). `deep_delay` (in `perturbation_go_delay.py`): when the systemic GO gate opens and a stage
  earlier than the brackets is supplied, the forecast is the REAL WT population at
  `t* = target - 2.3 x gate x (t_last - t_prev)`, mixed linearly in time from the two supplied stages that bracket
  t*, each at its native composition, no expression edits. On the test configuration: t* = 8.175, 2,235 E8.0 cells
  + 5,214 E8.25_late cells. For DNA-binding TFs and narrow modules (all Dev genes) the older path runs unchanged
  (bit-identical outputs with 2 or 4 inputs).

## Read the cross-run library BEFORE proposing anything!
Run #1 executed ~75 cycles and Run #2 ~17 cycles across all 4 boards; every confirmed gain, dead end, and pitfall is in the cross-run library
(`agentic_scientist/library/global.md` and `entries.jsonl`, queryable via `tools/kb.py`). Do NOT repeat dead ends
unless you satisfy their retry condition or fix the root cause (e.g. the upgraded Dev splits & seeds).

## Automatic gates besides the paired test
- **3-day plausibility check (`sanity`):** T1 and Heart are tested 3 days ahead (E12.5). Blow-ups fail.
- **Embryo midpoint-geometry gate (`embryo_native_min = 0.92` on Dev, normalized ratio `>= 0.97` on test export):** the official occupancy Dice of the output against a bracket embryo in MIDPOINT geometry (per-native-axis spread interpolated at the elapsed-time fraction, `agentic_scientist/native.py`) must stay high. Never overlay two clouds, never keep one bracket's unstretched proportions, never stretch along sorted PCA axes.
- **T1 composition guard (`composition`):** on the real test configuration the forecast's blood-like share may not exceed E10.5's, and its cardiomyocyte-like share (Tnnt2/Ttn/Ryr2) must be at least 0.9x the share in E10.5's chamber tissues.
- **Per-group condition rules:** No stage/target group (Heart E8.75/E9.5/dissected/long, Embryo E7.25/E8.0, T3 Gata4/Mab21l2/Hand2/Mef2c) may drop more than `-0.25` mean or `-0.5` upper bound.

## Code layout & contract
- `program.py` is a frozen dispatcher: never edit it.
- Edit ONLY your own board's flat files (`<board>.py`, `<board>_*.py`, `<board>_knobs.json`); no subdirectories; never import another board's files.
- `predict(board, inputs, times, target_time, context) -> anndata.AnnData`:
  - `inputs`: list of AnnData, oldest first, `.X` sparse log1p(CP10k), `.obs['celltype']`, `.obsm['spatial_3D']` for T2/T3.
  - `context`: `dict(seed, fit_seed, n, knockout, sampling, params, external, external_spatial, expression_prior, gene_embeddings, coexpr_prior)`.
  - Return 1000 to official max cells (`T1: 5118`, `heart: 25179`, `embryo: 5000`, `T3: 7449`) with EVERY input gene in `var_names`, finite non-negative values, `obsm['spatial_3D']` for heart/embryo/perturbation. Deterministic given seeds; <= ~10 min on 2 CPU threads; <= ~8 GB RAM.

## Dev splits
- **T1:** `temporal_matched` (weight **0.80**: E8.5+E9.5 -> cardiac E10.5 with the target subsampled to the LAST INPUT's myocardium/endocardium/other shares, so it scores which cells and states are forecast inside each lineage and does not reward continuing the dissection-to-dissection lineage jump), `temporal_val` (0.20, whole E10.5). The unmatched `temporal_heartonly` split is not scored any more. On `temporal_matched` the Normandy seed scores 73.8 and the previous seed 64.1.
- **Heart:** Dissected targets carry **75%** weight: `heart_long_organ` (0.30, 1-day jump E8.25_late+E8.5 -> dissected E9.5), `heart_organ_proxy` (0.25, 3-input -> dissected E9.5), `heart_e875_organ` (0.20, E8.25_late+E8.5 -> dissected E8.75). Whole-section targets carry **25%** (`heart_early`, `heart_late`, `heart_long`, `heart_e875`). All dissected splits receive `sampling='heart_dissected'`; a dissected target = cardiac labels (incl. `Epi`) + resident vessel/pericardial cells ATTACHED to cardiac tissue.
- **Embryo:** `guard_embryo_e80` (weight **0.65**, E7.25+E8.25_late -> E8.0, full depth & scale) and `embryo_early` (weight **0.35**, E6.75+E8.0 -> E7.25). Both require `native_occupancy >= 0.92` in Dev (`>= 0.97` normalized on test) and are guarded as separate groups!
- **T3** (knockout gene masked from inputs & scoring, like off-panel `Ctnnb1`): `gata4_1`, `gata4_2` (E8.0+E8.25_late+E8.5+E8.75 -> E8.75), `mab21l2_e95` (E8.75+E9.5 -> E9.5, weight 2), `hand2_e825` (E7.75+E8.25 -> E8.25), `hand2_e925` (E8.25+E9.25 -> E9.25), `mef2c_e85` (FIXED forward-time: E7.75+E8.5 -> E8.5), `mef2c_e90` (E8.5+E9.0 -> E9.0). Every knockout gene is its own group.

## The real test: what your program will receive
- **T1:** inputs E8.5, E9.5, E10.5 (`times=[8.5, 9.5, 10.5]`) -> E12.5 (`sampling='heart_chambers'`).
- **Heart:** inputs E8.25_late, E8.5, E8.75, E9.5, E10.5 -> E12.5 (`sampling='heart_dissected'`).
- **Embryo:** inputs E7.5, E8.0 -> E7.75 (exact midpoint interpolation).
- **T3:** inputs WT E8.0, E8.25_late, E8.5, E8.75 (`times=[8.0, 8.25, 8.5, 8.75]`), `knockout='Ctnnb1'` -> E8.75 mutant (off-panel broad signalling regulator).

## Allowed data, tools, skills, knobs, and integrity rules
- **Inspectable data:** Released T1/T2/T3 stages (excluding Landlock-protected holdouts), `data/external/ko_validation/{hand2,mef2c}`, `data/external/{qiu2024,heart_anchor,heart_spatial,embryo_anchor,go_prior,expression_prior,coexpr_prior,gene_embeddings}`.
- **Tools & skills** (under `$MG_ROOT/agentic_scientist/`): `tools/quick_eval.py`, `tools/leaderboard.py`, `tools/diagnose.py`, `tools/feulner_forecast.py`, `tools/late_anchor_check.py`, `tools/bioknow.py`, `tools/lit.py` / `lit` MCP, `tools/sc_tool.py`, `tools/kb.py`; read `skills/metric-playbook/SKILL.md` first!
- **On-demand knob tuning:** Declare up to 4 numeric knobs in `<board>_knobs.json` (`{"k": {"low": ..., "high": ..., "default": ...}}`) and read via `context['params']`. The harness runs Sobol + GP BO on the fleet before the paired race.
- **Competition integrity (Rules §9–§10):**
  - General pathway/gene-set databases (GO, MSigDB, Reactome, motifs) and pretrained unperturbed embeddings (`Geneformer-V2-104M`) are allowed.
  - NEVER use gene-level results of losing `Gata4` or `Ctnnb1` (or canonical Wnt loss) from external papers/datasets.
  - External data reaches `predict()` ONLY through `context`. No file I/O, network, subprocesses, or dataset paths in program code.
  - Never branch on exact `target_time`, split names, stage cell counts, or knockout gene names.
  - Public leaderboard names/recipes/scores are allowed; never invert returned scores to compute predictions.
