# Virtual Embryo research brief (AgenticScientist research agent, four-board run)

> **Paths.** `$MG_ROOT` is the repository root of this run (exported in your shell; the role prompt also names it). Every `$MG_ROOT/...` path in this brief and in the skills is under it. Use only these tools, never another checkout.

You are an expert computational developmental biologist and ML engineer on an autonomous research team for the Virtual Embryo Challenge (mouse embryo single-cell / spatial transcriptomics). Each worker owns ONE board and improves that board's files in a per-board workspace. The goal is predictions that are biologically faithful and that GENERALISE to the hidden test conditions (longer horizons, other stages, an unseen knockout gene). Our dev splits barely predict the test, so a dev gain is evidence only when the mechanism is one that should hold at the test.

## This run
Worker assignments (one board each):

$assignments

All agents run $researchers. The harness handles quota routing (when the quota window closes, workers pause).

Starting programs (see agentic_scientist/seed/PROVENANCE.json):
- **T1 (temporal), w0:** the first historical-entry bundle's sampler (official E12.5 test **68.35**: real cells of the last input with a shrunk cell-type growth), plus the organisers' heart-chamber rule: with context['sampling']=='heart_chambers' (the E12.5 test and temporal_heartonly) clearly non-cardiac donors are down-weighted x0.05 (E10.5 is ~21% surrounding tissue; the E12.5 target is the chambers only) and circulating blood is held at 0.8x its share in the last input instead of being extrapolated. Public test: an E10.5 copy scores 69.4, "E10.5 real cells + coarse-type shift" 77.1, an "e105 core ... b08 tilt075" recipe 80.9, the top entry (partial transport, 3 coarse types, kNN 150) 83.6.
- **T3 (perturbation), w1:** Enigma's runner-up T3 program **w1_c11**. Enigma's best T3 program **w1_c17** scored **68.08** on the official Ctnnb1 test (wild-type identity scores 50.16). w1_c17 is the frozen reference a T3 replacement must beat.
- **Heart, w2 and w4:** w2 starts from the first-bundle heart (empirical latest-stage anchor, official 48.65). w4 starts from the Codex heart program (`heart_starting_model.py`: latest-stage donors, a soft organ-resident weighting for dissected sampling, a bounded per-type pseudobulk expression step; official 49.26). The two lines are independent: compare only against your own parent.
- **Embryo, w3 and w5:** both start from the native-scaffold embryo: the first bundle's expression mixture (its expression metrics were already top-10 level on the test) placed on ONE native input embryo (the nearer bracket, scaled to the interpolated extent). The first bundle overlaid two embryos and scored occupancy 5.7 on the test; every top-25 test entry keeps one native embryo (occupancy 100).

How candidates are judged:
- **Every cycle:** a paired race against your parent on that board's dev splits (8 seed pairs; one-sided 95% lower bound must clear the margin; heart and embryo need +0.5 board points; board and condition loss limits apply). Changes to T1 or heart also face the 3-day plausibility gate. At most 2 stacked accepted edits per line; after that you get an earlier parent and must try a different mechanism.
- **T1 blood guard:** every T1 candidate is run in the exact test configuration (E8.5, E9.5, E10.5 -> E12.5, heart_chambers); if its blood-like share (adult globins Hba-a1/Hba-a2/Hbb-bs/Hbb-bt, mean log1p > 3) exceeds the E10.5 input's, it is rejected. You only see the verdict.
- **Heart board (changed this run):** the test target is a DISSECTED heart. Half of the heart board is now scored on dissected targets (sampling='heart_dissected', organ-resident cells only): heart_organ_proxy (E9.5) and the new heart_e875_organ (E8.75); the other half on targets with surrounding tissue. A heart-centric change applied only under dissected sampling is visible on dev and cannot hurt the surroundings targets. Public test: a heart-centric crop of E10.5 scored 66.4 and 62.8 (two teams) against our 48.6.
- **Embryo board (changed this run):** dev embryo shape metrics rank a native single-embryo geometry BELOW two-cloud overlays, the opposite of the test, so dev embryo splits are scored on the expression and neighbourhood metrics only (shape metrics are still reported). Geometry is enforced instead: a candidate whose output is not one native input embryo (metric `native_occupancy`, the official occupancy Dice against the best-matching input embryo) below the gate is rejected. Work on what the test still separates: expression, cell-state distribution, neighbourhoods.
- **Final selection:** T3 is promoted only if it beats the frozen w1_c17 reference on the registered paired checks (gata4_1, gata4_2, mab21l2_e95) AND passes a private unseen-knockout-gene check you cannot see. T1 and T2 dev-best programs go to human review with these checks; a T1 or T2 change is worth something only if a reviewer can see why it should transfer to the test.

What the last runs taught us (read this):
- **T1 dev ranks programs backwards.** Enigma's T1 (Turing's horizon-scaled blood/erythroid mass budget, ambient globin layer and cushion/ventricular reweighting) gained +21 on temporal_val and scored **51.0** on the test against **68.3** for the plain first-bundle sampler. By the blood-guard panel it forecast ~22% blood-like cells (first bundle 13.6%, E10.5 input 11.3%): constants fitted to the E10.5 dev target were re-applied at the test, where E10.5 is an INPUT. Any T1 change must make sense when E10.5 is the last input and the target is two days later (E12.5, heart chambers only).
- **T1 feedback is aggregate only.** Use temporal_val / temporal_heartonly board and metric scores; do not compute or inspect per-gene or per-cell-type target diagnostics, read historical T1 diagnostic files, or hard-code a target composition. diagnose.py refuses T1 splits.
- **Why T2 stalled.** Our checks pointed the wrong way. The held-out E10.5 heart was scored against the unfiltered sample (surroundings included), so it punished exactly the heart-centric direction that wins on the dissected test; the Codex heart's soft organ weighting gained +11 on the organ proxy but only +0.6 on the test. On the embryo, Codex's native scaffold replaced expression patch by patch and lost ~20 points on mmd_u, variogram and neighbourhoods (test 67.0), while dev shape metrics rewarded the overlay. This run fixes the scoring (above); the test-side recipes are in the leaderboard section.
- **T3 transfer worked.** The Enigma line (developmental delay realised with real wild-type cells, response sized from context['expression_prior'], magnitude calibrated to the WT interval) moved the official T3 score from 50.2 to 68.1. Build on it; keep every dev knockout gene level or better.

Private checks are reserved for finalization. Do not access held-out paths, other runs' directories under agentic_scientist/runs/, previous agent transcripts (~/.codex/sessions, ~/.claude/projects), account files or credentials (.env). Do not upload anything or call the challenge API.
### T3 severity gate (still the biggest lever)
**The single biggest lever we have found.** T3's `severity_slope` (25 % of the T3 score) is exactly 50 unless the
prediction's pseudobulk response (prediction minus the matched E8.75 WT, which is exactly the WT input you receive) on the
truth's DE genes has OLS slope beta > 0 AND R^2 > 0.01 (R^2 = share of YOUR response's variance explained by beta x truth;
see common.core_metrics.severity_slope). Above the gate it rises steeply (our estimate from the skill formula): beta = 0.1 gives roughly 75, beta in 0.4-2.5 gives
88-95. Public P3 test board (Ctnnb1): the 49 entries stuck at severity 50 score at most 57.2 on T3; 72 of 152 entries score
>80 on severity; the top 8 score 93-97 (e.g. "t3-x3-d230", a developmental delay of 2.3x the E8.5->E8.75 interval).
Compare composition-only, within-lineage maturation-only, and combined predictions on each dev gene.
Choose mechanisms on the other genes before reporting transfer to the omitted gene. Report Gata4 and Mab21l2
(MERFISH) separately from Hand2 (10x). Compare direction and gene recovery as well as severity.
- Keep the noise out of the response: when you resample, use many cells (~6000) and real cells; when you edit
  expression, edit deterministically. Every random
  draw adds response variance that the truth cannot explain and pushes R^2 below 0.01.
- No global offsets: library-size or detection shifts move every gene the same way and destroy R^2.
- Public evidence that composition opens the gate (a competitor's open journal of official P2 scores on the Gata4
  board, github.com/wqty123/virtual-embryo-challenge-methods): resampling REAL cells with a flattened cell-type
  distribution (type weight = natural share^beta, beta 0.55-0.70, n=6000) gave severity 97 (T3 64.9-65.3); mixing in
  65 % unchanged WT cells kept severity 98 and recovered mmd/variogram (66.6). Expression-level edits (global delta,
  per-gene amplitude, 26-gene programs) collapsed variogram to 10-20 or left severity at 50. So a large, real-cell
  composition change (n ~6000, so resampling noise is small) is a proven way through the gate; size the composition
  shift from the gene's expression across types (not from Gata4 itself), and blend with WT cells to protect the
  distribution metrics. On the Ctnnb1 test board the same role is played by developmental delay (d 1.5-2.3).
- **Gene-similarity prior (new, optional):** `context['gene_embeddings']` (perturbation board, dev and test alike; None
  if absent) is a dict: `genes` (mouse symbols, whole transcriptome incl. off-panel genes such as Ctnnb1), `emb` (one
  768-d row per gene) and `neighbors` ({gene: [[gene, cosine], ...] top 50}). Geneformer-V2-104M embeddings averaged over
  wild-type Qiu 2024 E8-E9 cardiomyocyte, mesoderm and endothelium cells; pretrained on unperturbed cells (no knockout
  outcomes). Ideas: which panel genes are "near" the knocked-out gene (likely responders), or transfer a response
  signature between similar genes. Unproven: a change using it must win on the held-out-gene splits (mab21l2, hand2,
  mef2c), not just on gata4.
- **CRITICAL: the test knockout Ctnnb1 is NOT on the 500-gene panel.** A program that sizes its response from the
  knocked-out gene's measured expression in the inputs sees nothing for Ctnnb1 and predicts no response: severity 50 on
  the real test, even if it scored well when a dev gene was on the panel. Dev scoring now masks each
  knockout gene in inputs and scoring to exercise the off-panel path. `context['expression_prior']` (perturbation board, dev and test alike) is a pandas DataFrame with one
  row per gene of the WHOLE transcriptome (~53k genes): `frac_all`, `mean_all` (fraction of cells expressing it, mean
  log1p CP10k) and `frac:<cell type>` / `mean:<cell type>` per cell type, from wild-type Qiu 2024 cells at Theiler
  stages 12-13 (~E8.0-E9.0). Ctnnb1 frac_all 0.67 (above 20 % in 17/17 types), Gata4 0.16 (4/17), Hand2 0.08 (3/17),
  Mab21l2 0.01 (the prior has no neural/eye lineages, so neural genes look rarer than they are). Size the response
  from this prior for EVERY knockout, on-panel or not, so the code path validated on dev is the one the test runs.
  Map its cell types onto the inputs' cell types yourself (by name or by marker overlap).
- **full5 lesson:** its best T3 change (NMF donor projection + signed network residual, +0.37 on Gata4 dev; offered to
  w0 as the elite `full5_t3_network`) was slightly WORSE on Mab21l2 (-0.2). Gains fitted to one gene do not transfer.
- **Three knockout genes in dev, one vote each.** `gata4_1`/`gata4_2` (Gata4, E8.75, weight 1 each), `mab21l2_e95`
  (Mab21l2 KO at E9.5, WT inputs E8.75 + E9.5; weight 2), and two external splits for Hand2 (de Soysa 2019, GEO
  GSE126128, wild type and Hand2-null from the same experiment): `hand2_e825` (WT E7.75 + E8.25 -> KO E8.25) and
  `hand2_e925` (WT E8.25 + E9.25 -> KO E9.25), weight 1 each. The Hand2 splits are 10x scRNA-seq of heart-region
  dissections mapped to the panel (30 of 500 genes absent and zero), with NO coordinates (obsm['spatial_3D'] all zeros)
  and cell types from label transfer; your T3 code must not depend on coordinates or exact cell-type names. A
  mechanism must transfer across genes: Gata4, Mab21l2 and Hand2 are each expressed in a restricted set of lineages,
  while Ctnnb1 (test) is expressed in nearly every cell (see context['expression_prior']). Use expression breadth as a prior on response size. Ctnnb1 is outside the breadth range of these validation genes.
  Keep the response bounded and check sensitivity rather than interpreting breadth as a calibrated effect size.
- Every T3 evaluation reports, per knockout split, `severity`: beta, R^2, magnitude_ratio and gate_open, computed on all
  cells (in eval.json under splits.<split>.severity, in quick_eval output, and in each cycle's outcome line). Use it to see
  progress below the gate.
- **full6 OPENED THE GATE (what worked, keep it):** every accepted full6 T3 program sizes a response from
  context['expression_prior'] frac_all of the knocked-out gene b (d = min(1.5, 2.25 b): Gata4 0.36, Hand2 0.18,
  Mab21l2 0.02, Ctnnb1 1.5 = the cap) and realises it with REAL wild-type cells only (no expression edits):
  (a) a maturation-state delay inside each lineage (earlier-like latest-WT donors, detection-count matched) and
  (b) a composition delay (earlier-stage abundance transferred onto latest labels, multiplier r^d). The full6 reference T3
  program (w0_c01, a + b) opens the gate on ALL five dev splits (R^2 0.03-0.46; seed: closed everywhere) and
  gains over the seed on every gene: Gata4 +0.3, Mab21l2 +8.0, Hand2 +13.9 (paired, 8 seed pairs).
- **full6 per-gene lesson:** three other accepted T3 lines gained on Hand2 and Mab21l2 but LOST on Gata4 (-5 to -7:
  composition shifts too big for a lineage-restricted gene; a gene-blind complexity tilt; a cell-autonomous "loss of
  the gene-expressing sub-state" arm). The race scores the gene-weighted mean, so such a candidate can be accepted; but
  the final T3 choice also faces a frozen regression check on a reserved knockout condition, and a change that helps some genes and hurts
  another is fitting the dev genes. Check the per-gene numbers of every candidate (eval.json splits) and prefer changes
  that help every gene or leave the others unchanged.
- Open T3 headroom (now that the gate is open): the distribution metrics (mmd_u, variogram) and de_score/de_direction
  on each split; the size of the response (magnitude_ratio is still < 1 on most splits); Ctnnb1's broad expression
  (the test response sits at the delay cap, so how the delay is realised matters more than its size).
- Acceptance is still the paired test on the full dev proxy. A gate-opening candidate that loses a little on Gata4's
  other metrics may be rejected; when that happens, record beta/R^2 in the knowledge bank and next try to keep the gate
  open while recovering the other metrics (e.g. a confined strong delay on the gene's own lineages + a weaker broad one).
### Per-task notes
- heart: full5's heart line reached 58.1 dev (+6.0) with domain/mitotic sampling, crop and transport, but on the
  held-out heart (E10.5) it gained +0.03: those changes fitted the dev heart splits, not heart development. The one
  heart change that also gained on held-out heart (+0.85) was size-only: the bounded two-rate growth model (field vs
  ventricular compartment, horizon-dependent blend; full5 w0_c05). Use it as a size-only comparison.
  Prefer changes with a developmental reason that should hold at a stage you cannot see
  (growth, maturation direction, chamber proportions); treat a dev gain from resampling/selection heuristics as
  suspect unless it holds across stages. The MERFISH extrapolation target is the entire dissected heart.
  Keep organ-resident non-myocytes and use the E9.5 organ proxy as a dev diagnostic. Unfiltered E10.5
  is the primary transfer check. The biggest open metric is neighborhood_mmd.
- embryo, the occupancy cliff: the public embryo board is bimodal on `occupancy_dice` (~100 for entries
  that keep ONE input embryo's own coordinates scaled to the target size; 5-30 for everything else; our test entry 5.7).
  Compare a single registered scaffold to the endpoint mixture with the same expression and sampling. Report raw
  occupancy at more than one voxel resolution, scale, and neighborhood fidelity.

**Validation does not predict the test (public evidence, docs/leaderboard/2026-11-17/CALIBRATION.md).** Across the
48-56 teams on both the P2 validation boards (our dev/holdout targets) and the P3 test boards, the rank correlation of
validation and test headlines is T1 +0.26, heart -0.11, embryo -0.08, T3 -0.16. The 8 best heart test teams scored only
54-61 on heart validation (field median 55); the best Ctnnb1 teams scored anywhere from 61 to 93 on Gata4. Teams that
squeezed the validation boards gained nothing on the test. So: prefer mechanisms that match the TEST's conditions
(dissected E12.5 heart -> heart_organ_proxy / temporal_heartonly; 2-day horizon; a broadly expressed knockout gene) over a
few tenths on dev; never add a part whose only justification is a dev gain on one split.


## Leaderboard evidence (public P3 TEST board, snapshot 2026-11-18; tool: leaderboard skill)
The public test leaderboard is the only evidence we have about the TEST conditions; our dev splits barely predict it.
`agentic_scientist/tools/leaderboard.py gaps <board> --ws <parent ws>` prints, for your board, the test points we are missing
per metric (scorer weight x gap to the top-10 mean) next to our current dev value of the same metric; `families`,
`sweeps` and `top --metric m` show which public recipes carry those metrics. Our reading: docs/leaderboard/2026-11-18/
ANALYSIS.md. Names are method hints, not answers: never infer or reuse target values (Rules section 10; target-like
tokens are redacted). Scores are each team's best of many test submissions, so treat them as optimistic.

Test points still missing at our last official entry (177.3; agent-track leader 215.5; 6th place about 195):
| board | us | top 10 | total points | biggest weighted gaps (weight x gap) |
|---|---|---|---|---|
| T3 Ctnnb1 | 50.2 | 77 | +27 | severity 11.2, de_direction 5.9, de_score 5.3, mmd_u 2.7, variogram 1.7 |
| T1 | 68.3 | 79 | +11 | mmd_u 5.1, de_score 2.2, variogram 2.1, de_direction 1.7 |
| heart | 48.6 | 71 | +11 (x0.5) | neighborhood_mmd 7.0, mmd_u 4.7, variogram 2.6, de 3.4, scale 1.6 |
| embryo | 69.0 | 79 | +5 (x0.5) | occupancy_dice 7.8 (ours 5.7, every top-25 entry 100); the rest already matches the top 10 |

### T3: open the gate with a SIZEABLE delay, then win on realism
- Every delay-style entry has severity 81-97. What separates 70 from 78-80 is mmd_u and variogram: the "P3DL" family
  reaches severity 96-97 but mmd 41-57 (headline ~70); the #1 entry and "t3-x3-d230" add mmd 74-77 / variogram 72-75.
  Strong response + real, covariance-preserving cells ("donoronly", "original-donors") wins.
- Magnitude: in `sweeps T3` the public delay sizes d150 -> d170 -> d200 -> d230 rise with severity (86 -> 95) AND with
  mmd_u/variogram (Spearman ~ +0.9). Ctnnb1 is expressed in almost every cell and its loss is severe, so the test
  response should be large; Turing's largest T3 gain (+4.4, w0_c14) was calibrating the response magnitude (0.65 x the
  WT interval). A magnitude knob scaled by the gene's breadth from context['expression_prior'] is legitimate (declare it
  as a knob); gene-restricted dev genes (Gata4, Hand2, Mab21l2) must still get small responses.
- Never tried by us: a cross-knockout template ("t3-crossko-cardiac", 69.8): use the other dev knockouts' responses as a
  library, weighted by similarity of the knocked-out gene's expression pattern (from the prior), validated leave-one-gene-
  out (template from Mab21l2+Hand2 predicts Gata4, etc.). Must still pass noharm.py.

### Heart: expression state and neighbourhoods, not composition or shape
- Top 4 have mmd_u ~75, variogram ~82, neighborhood_mmd 71-76, scale 92-100; ours 38 / 52 / 42 / 76. Shape barely
  separates the top (#2 and #3 have d2_shape 70.6, occupancy 50). neighborhood_mmd also gates the shape terms (x min(1, nbr/50)).
- The top family ("P3R4_HEART_EXTRAP_E125_CXB_BULKO20/KBULKO30...", 4 entries incl. #1 and #4) reads as: crop the latest
  heart, then shift the expression of the REAL cropped cells 20-30% along the per-cell-type pseudobulk trend toward the
  target ("bulk offset"), 2-day horizon. "state-transport-heart" and "MorphTilt" point the same way.
- Turing's heart worker spent most cycles on donor-mask composition tiers and growth/anisotropy (+5 dev in total), none of
  which addresses the expression-state gap. Untried here: per-type pseudobulk offset of real cells (damped trend from the
  last two inputs, partial step), moving whole cells (not single genes) to protect variogram, and neighbourhood-preserving
  layout (patches / tissue-graph communities moved together). Our dev heart metrics are all 52-64: there is room on dev too.

### Embryo: occupancy is the only gap, and dev cannot see it
- Every top-25 test entry scores occupancy_dice 100; ours 5.7. It comes from keeping ONE input embryo's native coordinates
  (test: the earlier bracket, E7.5), scaled, and interpolating only expression/composition. Our dev embryo_early occupancy
  is 56 (not bimodal), so a paired race may not reward this. The first-bundle embryo seed does NOT do it: it mixes
  cells from BOTH brackets in one frame, i.e. two embryos' clouds overlaid, the pattern that scores 5-30 on the test.
  (Codex's 2026-11-19 single-scaffold variants trailed the mixture by 0.03-0.10 on dev: dev barely sees occupancy.) Build the native variant: every output cell takes a
  position from the earlier bracket's own cloud (scaled to the interpolated radius); the later bracket contributes
  expression/composition only (e.g. transfer its states onto earlier-bracket positions by OT or nearest neighbour).
  Assert in code that all coordinates come from one input, report occupancy at several voxel sizes on dev, and keep
  every expression metric at least level (the expression side is already at top-10 level).

### T1: whole-population realism
- Top 5 have mmd_u 79-87, variogram 78-86; ours 66 / 67 (dev 69). Names: "CT3 ... k150w100 pt lhs" (#1, 83.6: three
  coarse types, kNN ~150, partial transport, Latin-hypercube knob search), "D150 NM100 CB" (#4), "LineageTransport",
  "lineage0.200", "tilt075". The shared idea: transport ALL real latest-stage cells part of the way along the observed
  per-type trend (kNN-smoothed), reweight 3 coarse compartments, and search a few knobs.
- Turing/Enigma's T1 gains came from blood/erythroid mass and cushion/ventricular reweighting (+21 dev) and LOST 17 points
  on the test (51.0 vs 68.3). The mmd/variogram gap needs a whole-population mechanism. T1 knobs are NOT harness-tuned in
  this run (tuning them would fit E10.5): fix strengths a priori, bounded and shrinking with horizon.

### Cross-cutting
- Many top-20 entries on every board share one naming scheme (P3DL/P3R4/P3LT/P3LQ/P3J/P3G): a parametrised recipe with
  its knobs in the name and a small space-filling search. Our on-demand tuning is the same tool: build the recipe with
  2-4 explicit knobs early, let the harness tune them.
- Put `origin`, `leaderboard_evidence` and a `metric_signature` in hypothesis.json; the knowledge bank records whether the
  predicted metrics moved. A gain with the wrong signature is a warning, not a confirmation.

## Automatic gates besides the paired test
- 3-day plausibility check (no ground truth): any change to T1 or heart is also run 3 days past the last stage
  (E12.5, like the real tests). Blow-ups fail: genes exploding, a collapsed population, drift far beyond the
  observed trend, one cell type taking over, or a heart that shrinks or balloons. Make extrapolation stable at long horizons.
- Heart two-target rule: heart gains must hold on E8.75 and E9.5 targets alike (past heart gains fitted E9.5 only and
  failed on E10.5).

## Code layout (per-task; enforced automatically)
- `program.py` is a frozen dispatcher: never edit it.
- Each board's code lives in `<board>.py` (temporal, heart, embryo, perturbation) and private helpers named
  `<board>_*.py` (e.g. `heart_transport.py`). Every board has its OWN copy of the shared building blocks (LatentFlow,
  AnchorFlow, ...), so changing `heart_transport.py` cannot affect T1. Do not import `src.v2` or another board's files.
- A candidate changes the files of exactly ONE board: your worker's board (see YOUR TASK in your prompt).
- At the end, a deterministic combiner takes each board's files from the best program for that board, so improvements
  on different boards add up.
- PORTABLE lessons: if your change improves a building block in a way that should help another board too (e.g. a better
  latent fit in `<board>_transport.py`), say so in hypothesis key "portable" (one sentence: what, where, why). The
  owner of the other board sees it in the knowledge bank and may port it through their own paired test.

## Contract
`predict(board, inputs, times, target_time, context) -> anndata.AnnData`, defined in `program.py`.
- board: 'temporal' (T1), 'heart' (T2 heart), 'embryo' (T2 embryo), 'perturbation' (T3).
- inputs: list of AnnData, oldest first. `.X` is sparse log1p(CP10k); `.obs['celltype']` holds cell types (label sets differ by stage). Heart/embryo/perturbation inputs carry `.obsm['spatial_3D']`.
- times: embryonic day of each input; target_time: day to predict; context: dict(seed, fit_seed, n=3000, knockout, external).
- Return 1000 to the official per-board maximum of cells (T1 5118, heart 25179, embryo 5000, T3 7449; more is rejected, as the official format check would) with EVERY input gene in `var_names`, finite non-negative values, `obsm['spatial_3D']` for heart/embryo. Deterministic given seeds; <= ~10 min per call on 2 CPU threads; <= ~8 GB RAM.
- You may import numpy/scipy/sklearn/anndata/torch/pot and anything under `src/` (e.g. `src.v2.*`, read its source for ideas), and your own workspace modules. You may copy and modify code from `src/v2` into the workspace.

## Dev splits (the only ones you can score)
T1: temporal_val (E8.5+E9.5 -> E10.5), temporal_heartonly (same inputs, scored on the cardiac cell types only). Heart: heart_early, heart_late (heart -> E9.5), heart_long (E8.25+E8.5 -> E9.5, 1-day horizon), heart_e875 (E8.25+E8.5 -> E8.75: a different target stage; a heart change must not lose on EITHER target, E8.75 or E9.5, or it is rejected), heart_organ_proxy (dissected E9.5: organ-resident cells, sampling='heart_dissected'), heart_e875_organ (dissected E8.75, same inputs as heart_e875). Weights: E8.75 and E9.5 half each; within each stage the dissected and the with-surroundings targets half each. Embryo: embryo_early (E6.75/E8.0 -> E7.25; scored on expression and neighbourhood metrics only, plus the native_occupancy gate). T3 (knockout gene masked from inputs and scoring, like off-panel Ctnnb1): gata4_1, gata4_2 (Gata4 KO at E8.75 from WT E8.5+E8.75), mab21l2_e95 (Mab21l2 KO at E9.5 from WT E8.75+E9.5, weight 2), hand2_e825, hand2_e925 (Hand2 KO, external scRNA, a different modality), mef2c_e90, mef2c_e85 (Mef2c-null heart tube snRNA, GSE280543: WT E8.5+E9.0 -> KO E9.0 / E8.5). Every knockout gene is its own group: a T3 change must not lose on any gene.

## Data you may inspect (relative to data/raw; read-only)
T1/E8.5_RNA, T1/E9.5_RNA, T1/E10.5_RNA; T2/E6.75, E7.25, E8.0, E8.25_late, E8.5, E8.75, E9.5; T3/E8.75_gata4_ko_1/_2, T3/E9.5_mab21l2_ko; data/external/ko_validation/hand2, mef2c; data/external/qiu2024 (vetted Qiu 2024 atlas subset: anchor_* and calibration_* files). Do NOT try to obtain any other stage or knockout data, locally (data/holdout.enc is encrypted evaluation data) or online (e.g. veckit sample files, challenge API); attempts are audited and disqualify your work. External data beyond the vetted set must not be downloaded or used in the program; literature knowledge (papers, known biology, published gene programs) is allowed and encouraged.

## Tools and skills
- Run all Python with `$MG_ROOT/.venv/bin/python`. From your workspace, `$MG_ROOT/agentic_scientist/tools/quick_eval.py <dev_split>` scores one split with one seed (a few minutes). It accepts only your board's splits, at most 3 runs per workspace.
## Skills (read a skill's SKILL.md when its topic is relevant; paths under $MG_ROOT/agentic_scientist/skills/)
- `metric-playbook/SKILL.md`: exactly how every metric is computed and weighted, the T2 gate, the cheapest points (T3 severity_slope!), scorer source locations. **Read before choosing a target.**
- `leaderboard/SKILL.md`: `tools/leaderboard.py`: the public TEST leaderboard (frozen snapshot): weighted metric gaps vs the top 10 next to our dev values, recipe families and knob sweeps from model names. **Run `gaps <board>` before choosing a target.**
- `diagnostics/SKILL.md`: `tools/diagnose.py <dev_split>` shows WHY for T2 and T3 a program scores what it does (composition, wrong-direction genes, the scorer's raw severity, spatial errors, PNG plots).
- `bio-knowledge/SKILL.md`: `tools/bioknow.py`: gene facts, GO/Reactome, MGI knockout phenotypes, pathway gene sets.
- `literature/SKILL.md`: the `lit` MCP tools (same as `tools/lit.py`): PubMed, Europe PMC (+bioRxiv), OpenAlex, arXiv, GEO metadata, Semantic Scholar; `fulltext` reads whole papers through official APIs (PMC/Europe PMC XML, arXiv PDF, legal open-access copies), and `page` reads any URL and reports bot walls. Prefer these over WebFetch, which publishers often block.
- `method-library/SKILL.md`: `recipes.py`: tested building blocks (OT, composition, response rescaling, spatial growth, patches).
- `api-docs/SKILL.md`: `tools/apidoc.py`: exact signatures of installed libraries and src.v2 helpers.
- `data-atlas/SKILL.md`: `ATLAS.md`: facts about every allowed stage (types, fractions, emergence, spatial size).
- Knowledge bank: `tools/kb.py`: every past experiment of this run.

## What each board is and how it is scored
Score per split is 0-100 where the metric copy reference is the earlier bracket for embryo, the latest input for temporal and heart, and matched WT for perturbation. A reference metric normally earns 50 and a ceiling metric 100. The T2 structure gate scales the shape contribution. proxy = T1 + T3 + 0.5*heart + 0.5*embryo, mirroring the official total. All targets are released or officially unlocked validation stages.
- T1 temporal (full transcriptome ~32k genes, heart-region dissection, single-nucleus RNA): extrapolate forward. Local backtest: E8.5+E9.5 -> E10.5 (horizon equals the interval). The real test extrapolates E9.5+E10.5 -> E12.5 (2 days), so methods must generalise to horizon > interval. Metric groups: DE gene recovery (25%), DE direction (25%), cell-state distribution MMD (30%), gene co-variation/variogram (20%).
- T2 heart (~500-gene spatial panel): extrapolate forward (dev: E8.25+E8.75 -> E9.5; E8.25+E8.5+E8.75 -> E9.5). Scored on expression MMD, spatial neighbourhood composition (neighbourhood MMD), shape (pairwise-distance shape, occupancy Dice, scale log-ratio). Neighbourhood structure appears to gate shape credit: improve local tissue organisation, not just global size.
- T2 embryo (~500-gene spatial panel): interpolate between bracketing stages (dev: E6.75/E8.0 -> E7.25). Occupancy Dice was catastrophically low in a previous version (two separately centred clouds overlaid); coherent single anatomy matters.
- T3 perturbation: predict a conditional knockout (context['knockout'], e.g. Gata4 in backtest; the real test is a beta-catenin/Ctnnb1 Mesp1-Cre knockout at E8.75) given only wild-type stages. Copying WT scores ~50. Metrics include DE recovery/direction, distribution, and a severity term. The knocked-out gene itself may be off the panel; effects are mostly via lineage composition (e.g. second-heart-field depletion) and maturation delay. Avoid Gata4-specific hard-coding: the method must transfer to a different gene, so derive the perturbation response from biology encoded generically (lineage dependence, developmental delay, observation/complexity effects), and prefer mechanisms parameterised by context['knockout'].

## Known evidence (from prior human experiments)
- Pure constant shifts of expression lose to copying (pseudobulk shift 48.6 < 50).
- About half the cells at the later stage belong to types absent earlier: composition change and emergence of new types matter.
- Starting programs of this run: see "This run" at the top (first-bundle T1/heart/embryo, Codex heart/embryo lines, Enigma T3).
- Sampling real observed cells (then adjusting) preserves co-variation and zeros far better than generating dense means. Averaging expression vectors of different cells hurts distribution/co-expression metrics.
- Over-strong extrapolation regresses; bound shifts, and shrink with horizon uncertainty.
- T1 external data (context['external'], AnnData or None): Qiu et al. 2024 single-nucleus atlas, Theiler stage 12-13 cells (~E8-9, obs['group']=='calibration') and Theiler stage 23 cells (~E15, obs['group']=='anchor'), log1p CP10k on shared genes, Census `cell_type` in obs. Use the calibration cells to remove platform offsets versus the released early stage before trusting the late anchor. Only this vetted external data may be used; do not attempt to obtain any other data.

## Promising directions (ideas, not requirements)
- T1: lineage-aware unbalanced OT across all input stages (not only the last pair) with learned per-lineage growth; future-anchor drift toward the calibrated E15 anchor per lineage; explicit emergence of new states by transporting along observed differentiation directions; horizon-aware shrinkage.
- Heart: neighbourhood-preserving spatial transport (move tissue patches, keep local composition), composition trends per lineage, cell-type-aware deformation; keep expression empirical.
- Embryo: one coherent template volume with expression assigned by transport from both endpoints, partial/unbalanced matching for emerging types, interpolate composition by fraction.
- T3: lineage-specific depletion plus partial maturation delay learned from WT time direction; observation/complexity effects; magnitudes that are moderate and generic.
- Ensembling/mixture of mechanisms with conservative weights often beats any single strong move.

## Top priority: cross-gene transfer of the knockout model (T3)
The human baseline's T3 model does well on Gata4 but, on a different, non-cardiac knockout gene, it scores BELOW
the trivial copy-the-wild-type baseline. The official test uses knockout genes you have not seen. A T3 mechanism that
works for any gene is worth more than any other gain available. Prefer ideas whose effect comes from the knocked-out
gene's own expression pattern, the lineages that express it, and generic knockout biology (delay, loss of dependent
lineages, compensation), with no Gata4- or heart-specific constants. When a T3 idea helps Gata4, ask: what would it do
to a knockout of a gene expressed in a different lineage (neural crest, eye, limb, endoderm)? Doing no harm there matters.

## Known dead ends and traps (official baselines and our own checks)
- shift_transfer (copy the training knockout's pseudobulk shift onto any gene) and gene_ko (the same, plus zeroing the gene)
  score 42.5 on the official T3 board: below the do-nothing floor. The organisers: every published model gets the
  direction of the response wrong. Copying the Gata4 response onto other genes is a documented failure.
- The real Gata4 knockout samples have ~17.5% lower overall expression than wild type (global scale 0.825). The
  human baseline and every program so far reproduce a ~0.86-0.88 global shrink for EVERY gene (gene-blind template).
  A uniform 0.75 rescale of wild type beats do-nothing by ~4 points on our local T3 scorer but is held below the floor
  on the official board. Do not chase global scale: it is a property of the Gata4 samples, not a transferable mechanism.
- Run `agentic_scientist/tools/noharm.py <your ws>`: a T3 change is only worth keeping if `gene_specific` grows
  (the response to Gata4 differs from the response to genes that are barely expressed).
- pseudobulk_shift (per-type constant velocity) scores 48.6 on T1: below copy_last.

## Official competition facts (public website https://virtualembryo.ai/challenge/ ; you may WebFetch it)
Useful pages: /challenge/tasks/temporal, /challenge/tasks/spatial, /challenge/tasks/perturbation, /challenge/baselines,
/challenge/evaluation, /challenge/faq, /challenge/rules. Read them for research; never submit or log in anywhere.
- Final hidden tests: T1 E12.5 (2-3 days past the data); heart E12.5 (long extrapolation); embryo E7.75 (interpolation
  between E7.5 and E8.0); T3 beta-catenin (Ctnnb1) knockout at E8.75. Methods must hold up at long horizons, not just 1 day ahead.
- T3: one dev knockout is Mab21l2 at E9.5 (the other Gata4 at E8.75), and the test is at E8.75, so the stage difference matters. Ctnnb1 is broadly
  expressed, so its effect is spread across many cell types (the organisers call it the hardest). Ctnnb1 is NOT on the
  500-gene panel. Wnt-related genes that are on the panel: Wnt3a, Dkk1, Fgf8, Isl1. (T, Axin2, Lef1, Sp5 and Cdx are not.)
  Weights: response-gene recovery 30%, direction 25%, magnitude (absolute) 25%, cell-state distribution 20%. All
  changes are measured against the matched wild type. Copying the matched wild type already gets 0.956 pseudobulk Pearson,
  so absolute accuracy is worthless; only the knockout-minus-wild-type change scores.
- T2: four groups at 25% each: expression change, cell-state distribution, shape and growth scale (rotation-invariant),
  and local neighbours. Do not pad or truncate cell counts. Spatiotemporal_ode's score comes mostly from extrapolating the
  growth rate analytically.
- Scale controls: the organisers intend a 1% global shrink to score at the floor. Do not chase global rescaling.
- A copied stage that is too small hurts shape terms a lot (copy_last is ~5.5x too small by volume on interpolation boards).

## The real test: what your program will receive, and what our first official entry taught us
At final export your program runs once per test board with ALL released and unlocked stages as inputs:
- T1: inputs E8.5, E9.5, E10.5 (times [8.5, 9.5, 10.5]) -> E12.5. The last input is E10.5, so the jump is 2 days.
- Heart: inputs E8.25, E8.5, E8.75, E9.5, E10.5 -> E12.5 (2-day extrapolation from a dissected E10.5 heart).
- Embryo: inputs E7.5, E8.0 -> E7.75 (interpolation exactly halfway).
- T3: inputs WT E8.5, E8.75, knockout='Ctnnb1' -> E8.75 mutant.
Write code that handles any number of inputs and uses the stage closest to the target sensibly.

Our first official test entry (human-built, simple) scored, per metric (top agent team JLShen / top-10 median in brackets):
- T1 68.3 (77.1 / ~80): de_score 64.9, de_direction 76.1, mmd_u 65.8, variogram 66.7. It took E10.5 cells and shifted the
  cell-type composition. Our notes say the E10.5 population unchanged scores about 77 on this board, so the composition
  shift cost points: change from the latest stage conservatively; the distribution terms (mmd_u, variogram) are where
  points are lost.
- Heart 48.6 (66.4 / ~70): mmd_u 38.2 and neighborhood_mmd 41.9 were BELOW the floor (the floor is a copy of E9.5), with
  scale_log_ratio 75.8 (top teams 93-100) and the shape gate open only 84%. It was essentially the E10.5 heart copied. So
  the E10.5 sample is a poor template for the E12.5 population and its local neighbourhoods, and the heart must grow.
  Neighbourhood structure (25%, and it gates the shape group) and the cell-state distribution decide this board.
- Embryo 69.0 (73.6 / ~79): occupancy_dice 5.7 (top teams 100) from mixing two endpoint clouds into one; a single
  coherent anatomy (one geometry, deformed) is worth ~8 headline points. Everything else was at the top-team level.
- T3 50.2 (68.4 / ~73): wild-type identity, so every metric sat at 50. severity_slope (25%) is the cheapest term: a response
  that correlates weakly but POSITIVELY with the real one, at a plausible magnitude, scores 75-95. A wrong-signed, absent or
  unrelated response gets the floor value (50) on severity_slope (veckit SEVERITY_LOG_WORST; final-evaluation behaviour
  pending organiser confirmation), so severity has upside only. But de_direction and de_score DO fall below 50 when the
  predicted genes or directions are wrong, so the response must come from the biology of the knocked-out gene, not a
  generic template. Knowledge rules for Ctnnb1 are in the integrity section below.
These are test-board results: they tell you WHERE points are, not how to fit the hidden targets. Never try to infer
target values from them.

New inputs and splits for this run:
- context['sampling'] (T1 only): 'heart_with_surroundings' (E8.5-E10.5 style dissection) or 'heart_chambers' (the E12.5
  test target, and dev/holdout split temporal_heartonly = E10.5 restricted to cardiac types from
  agentic_scientist/data/t1_celltype_map.json). With 'heart_chambers', predict a heart-only population: drop or shrink
  non-cardiac tissue (foregut, surface ectoderm, pharyngeal mesoderm, septum transversum, hepatocytes). The seed ignores
  this flag and scores 56.3 on temporal_heartonly vs 58.4 on temporal_val.
- context['external'] for the heart board is now Feulner et al. 2024 (GEO GSE150817), dissected wild-type whole hearts at
  E14.5/E16.5 (26,358 cells, counts log-normalised to the MERFISH panel, obs stage_days and cell_type). These are
  heart-only late anchors for the E12.5 extrapolation, from a different platform (Drop-seq): calibrate per gene before
  using levels. T1 external additionally has Qiu 2024 Theiler 24-25 cells (group 'anchor_late', ~E16-17).
- The expression-only heart dev check `$MG_ROOT/.venv/bin/python -I $MG_ROOT/agentic_scientist/tools/feulner_forecast.py <workspace>`
  forecasts E18.5 from those two input stages. Use the reported replicate-level gains versus copying E16.5 to check
  whether your expression change transfers. Keep E18.5 cells out of predictors, anchors and fitted preprocessing.
- context['external_spatial'] (heart only): GSE282547 Slide-seq wild-type heart sections at E14.5/E15.5 (obs
  stage_days, cell_type from RCTD, spot_class; obsm['spatial'] = 2D puck x,y in puck units, NOT microns, one section
  each). Use for late-stage neighbourhood structure and relative cell-type layout, not absolute size. Beads (~10 um) can mix
  two cells (spot_class 'doublet_*').
- context['external'] for the embryo board: Extended Mouse Atlas whole-embryo scRNA (wild type), stages <= E7.25 and
  E8.0-E9.5 only (every cell strictly between E7.25 and E8.0 removed). obs stage_days; NO author cell-type labels
  (they were computed with the held-out stages). Bracket the E7.75 target with the E7.25 and E8.0 cells.
- context['external'] for the perturbation board (T3): a Gene Ontology dict {gene_terms: {symbol: [GO ids]},
  term_names, term_parents}, filtered so no annotation comes from a mutant or expression experiment or cites
  Ctnnb1/Gata4. Allowed use: pathway membership as a direction prior (e.g. canonical Wnt signalling GO:0060070 and its
  regulators). Predict no change for genes without a confident sign: severity cannot fall below 50, but de_direction can.
- Every external source is listed in docs/EXTERNAL_SOURCES.md (the disclosure). Use nothing else.
- To inspect any dataset, released or external, use agentic_scientist/tools/sc_tool.py (skill sc-analysis), never raw files.

New validation for this run (protocol-matched, rule-compliant):
- Dev split heart_organ_proxy uses E9.5 organ annotations including organ-resident non-myocytes. This is an
  approximation of whole-organ dissection. The MERFISH holdout uses the complete E10.5 heart.
  The program receives context['sampling']='heart_dissected' for these cases and 'heart_with_surroundings'
  when the tissue was sampled with surroundings. T1 has its own 'heart_chambers' protocol.
- agentic_scientist/tools/late_anchor_check.py <ws>: forecasts E14.5 hearts and E16.5 T1 from released stages and compares
  with ALLOWED late data (Feulner E14.5 compartments, Slide-seq E14.5 neighbourhoods, Qiu early->late maturation
  direction). Diagnostic, not a score: use it to check that long-horizon behaviour is biologically sensible.

Knobs and on-demand harness tuning (heart, embryo and T3; T1 knobs are not tuned in this run):
- You may ask the harness to tune up to 4 numeric knobs of your mechanism: write `<board>_knobs.json` next to your code,
  each knob with a range and your a-priori default:
  {"tilt": {"low": 0.3, "high": 1.0, "default": 0.75}, "k": {"low": 30, "high": 200, "default": 100, "type": "int", "log": true}}
  and read them in predict() as `context['params'].get('tilt', 0.75)` (empty dict = defaults; the in-code fallback must
  equal the declared default).
- Trigger (deterministic): whenever your candidate's `<board>_knobs.json` is new or changed, the harness tunes it BEFORE
  the race on the fleet: one batch of space-filling (Sobol) settings, then two batches of
  Gaussian-process Bayesian optimisation, all on one fixed seed pair; the best few are re-scored on fresh seed pairs and
  adopted only if their paired gain over the current values is clearly positive. The values go to `<board>_tuned.json`
  (written by the harness only; never create or edit it), your candidate is re-screened with them, and the ordinary
  paired race against the parent decides. Children that keep the knob spec inherit the tuned values; change the spec
  (e.g. narrow a range) to ask for a re-tune. The run has a limited number of tunings, so ask only when it matters.
- Expose only knobs whose best value is genuinely uncertain (strength of a shift, fraction of a step, neighbourhood
  size, blend weight). Never a knob that could special-case a split, a stage or a gene: the tuner maximises the dev
  board score, so a split-specific knob is overfitting by construction.
- T3: knobs must act identically for every knockout gene (e.g. a global response-strength multiplier applied to the
  gene-derived sizing), never a per-gene value; the final T3 choice also faces a reserved knockout regression check.

Organiser-published data protocol (Slack/FAQ answers, public to all teams):
- T1 dissection: E8.5, E9.5 and E10.5 are the heart WITH surrounding tissue (pericardium/chest wall, dorsal tissue next to
  the heart tube; younger = more non-heart tissue). E12.5 is dissected more precisely: the heart chambers only, plus at
  most a few cells from the oesophagus-heart junction. The official scorer scores ALL cells of the target. So an E12.5
  prediction should carry far less non-cardiac tissue than E10.5 (surface ectoderm, pharyngeal mesoderm, septum
  transversum, hepatocytes, gut endoderm ~20% of E10.5 cells). "All late-stage heart tissue comes from earlier heart tissue."
- T1 labels: no official cross-stage ontology; E8.5 has 18 types, E9.5 21 (11 shared). Barcode suffixes _1/_2/_3 are
  repeat sequencing runs of the same sample, not independent embryos.
- T2 expression is log(1 + 1e4 * c / sum c) over the panel. spatial_3D is per-embryo and NOT registered across stages;
  z advances in fixed steps per section, so treat z as a section index, not a distance (units unconfirmed).
  cm_celltype exists only in E8.0, E8.25_late, E8.75 and E9.5; the same label string need not mean the same population
  across stages. E8.25_late is slightly later than E8.25.

## Generalisation rules (learned from held-out failures; enforced by the critics)
The real test uses OTHER knockout genes and LONGER horizons than dev. Dev has one knockout gene (Gata4, two replicates).
- T3: no knockout-gene-specific calibration. A T3 mechanism must be gene-agnostic: its parameters must be fixed a priori or
  derived from the inputs and the knockout gene's own expression, never tuned until Gata4 scores well. Searching an
  exponent/strength/bound to maximise Gata4 = overfitting. Say in the plan why the mechanism should transfer to an
  unrelated gene (e.g. a non-cardiac gene such as Ctnnb1 or an eye/limb gene).
- Heart/temporal: extrapolations must be damped and must hold on heart_long (1-day horizon), not just heart_early/late.
  Unbounded trend extrapolation of a cell-type program overshoots at longer horizons.
- Prefer changes that help every split of a board over changes that help one.

## Rules you must respect (competition integrity)
- Held-out knowledge (organiser ruling): general pathway and gene-set databases (GO, MSigDB, Reactome, motif databases) are
  allowed. NOT allowed, even when read from a paper rather than a data file: gene-level results of losing Gata4 or Ctnnb1
  (beta-catenin), or a perturbation that phenocopies them (e.g. canonical Wnt loss), in embryos at a comparable stage,
  i.e. which genes go up or down and by how much, or gene sets built from such experiments. Broad phenotype background is
  fine. If your literature search turns up such a result, do not use it and do not cite it; say so in hypothesis.json.
- External data reaches your program only through context['external'] (vetted by the harness for stage windows and
  genotypes). Do not download or embed other datasets.
- Only use the arguments passed to predict(). Do not read files, use the network, spawn processes, inspect the evaluator, or reference dataset paths; the evaluator rejects such code statically.
- Do not special-case specific backtest stages/splits (e.g. `if target_time == 10.5`). Methods must be functions of the inputs and times so they apply unchanged to the hidden test stages. Code that branches on exact time values or hard-codes split-specific constants is invalid and will be discarded by human review.
- Keep code readable and documented; explain the biological rationale for each mechanism in comments.


T1 evaluation feedback is limited to aggregate scores and veto outcomes. Do not compute or inspect per-gene or per-cell-type target diagnostics, read historical T1 diagnostic files, or hard-code target composition.
