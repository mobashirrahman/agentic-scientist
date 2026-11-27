# w1_c04 — state-conditioned recipients for the sparse anchor realisation (temporal only)

Parent: w1_c02 workspace (sparse anchor realisation + erythroid donor prior + input-calibrated
glycolysis state prior). Hypothesis: biasing the *recipients* of the existing sparse anchor
realisation toward donors whose latest-input latent neighbours detect the gene reduces
pair-moment overprediction (variogram), with S, k, q, the seed streams and the source rows
unchanged.

**Result in one line: the mechanism is implemented exactly as pre-registered and every
invariant holds, but the scored effect at n=1 is flat (proxy 57.84 vs parent 57.84).
This is a null/inconclusive result, not a gain.** Details below.

## What changed

- `sparse_anchor.py` — `realise_sparse_anchor(out, latest, seed, embedding=None)`, new
  optional `embedding` argument plus the recipient law:
  - Per operator lineage block (`lineages(latest)[source_row]`, the same grouping the
    realisation already used) with `>= MIN_LINEAGE_CELLS = 50` latest cells: a
    `sklearn.neighbors.NearestNeighbors` index (`k = 31`) on the block's rows of
    `embedding`; for each **distinct sampled donor** of the block the 30 nearest *other*
    lineage cells (self dropped). A sparse (donors x lineage-cells) indicator matrix with
    `1/|neighbours|` averages the binary detection matrix of the latest stage, restricted to
    the genes that actually have eligible entries in the block, in 2048-gene chunks.
  - `pi_g` = detection frequency of `g` over the lineage's latest cells;
    `r_ig` = fraction of donor `i`'s neighbours detecting `g`;
    `w = clip((0.5*pi + 0.5*r)/pi, 0.5, 2)` on the eligible rows, normalised, then
    `chosen = rng_w.choice(elig, k, replace=False, p=w)` on the independent
    `SeedSequence([seed, 23456])` stream.
  - **Parent stream preserved exactly**: for every eligible gene, in the original gene
    order, `chosen_u = rng.choice(elig, k, replace=False)` is *always* drawn on the parent
    `SeedSequence([seed, 12345])` stream first. It is the result when the gene falls back
    (no embedding / unsupported lineage / `pi_g == 0` / constant weights) and is discarded
    when the weighted draw is used. So a full abstention is bit-identical and fallback genes
    inside a mixed run keep the parent's draws for all later genes — this fixes the stream
    claim the critic flagged in the proposal.
  - Assignment (`dens[elig,j]=0; dens[chosen,j]=total/k`), `q`, `S`, `k`, CP10k
    renormalisation of changed rows, and `source_row` are unchanged. No expression mass is
    added.
  - Diagnostics (flat scalars in `out.uns['sparse_anchor']`): `embedding_used`,
    `n_latent_dims`, `n_supported_lineages`, `n_weighted_genes`, `n_fallback_genes`,
    `mean_recipient_r_over_pi`, `mean_uniform_r_over_pi`, `recipient_enrichment_ratio`,
    `max_budget_error`.
- `program.py`, `predict_temporal` only (single changed statement block):
  `zb = flow.zb` (the `LatentFlow`/`AnchorFlow.flow` representation of the latest input),
  validated as 2-D with `shape[0] == latest.n_obs` and all-finite, else `None`; passed as
  `embedding=`. Nothing else in `program.py` changed; heart/embryo/perturbation functions are
  byte-identical (`diff` shows only the one return statement), so those boards cannot change.
- Constants were fixed before any score was seen (pre-registered): 50 cells, k=31 (30
  others), shrink 0.5, clip [0.5, 2], streams 12345/23456, gene-chunk 2048. **No sweep.**

## Implementer validation — invariants (temporal_val, pred seed 101, fit seed 0)

One AnchorFlow prediction was produced in a single process, then three realisations were run
on *identical copies* of the same `out`: (a) candidate code with `embedding=None`,
(b) the parent workspace's `realise_sparse_anchor` (loaded under a separate module name),
(c) candidate code with `embedding=flow.zb`.

| check | value | pre-registered bar |
|---|---|---|
| embedding shape | (17057, 32) == `latest.n_obs` | accepted ✓ |
| (a) vs (b) bit-identical | **True**, max abs diff 0.0 | exact ✓ |
| `source_row` / `var_names` identical (a vs c) | True / True | identical ✓ |
| finite, non-negative | True, min 0.0 | ✓ |
| nonzero fraction parent vs candidate | 0.12289805 vs 0.12289805 | unchanged ✓ |
| median row sum | 3768.92 vs 3769.45 | CP10k restored ✓ |
| supported lineages | 8 | — |
| weighted / fallback genes | 58,907 / 26,332 | — |
| mean recipient `r/pi` (weighted genes) | 1.7685 | — |
| mean uniform `r/pi`, same genes | 0.9808 | — |
| recipient enrichment ratio (chosen vs uniform) | **1.803** | bounded by the [0.5, 2] clip ✓ |
| max pre-normalisation budget error | 2.0e-6 | ~float32 epsilon ✓ |
| entries changed by >1e-9 | 5.4% of the matrix | — |

So the placement law really moved (chosen recipients are 1.8x more likely to sit in
state-compatible, gene-detecting neighbourhoods) and the budget is conserved as designed.

## Quick-eval (single seed, `temporal_val`, pred seed 101, fit seed 0)

| metric | parent (w1_c02) | candidate | delta |
|---|---|---|---|
| score | 57.84 | **57.84** | **0.00** |
| de_score | 48.01 | 48.01 | 0.00 |
| de_direction | 65.91 | 65.90 | −0.01 |
| mmd_u | 60.31 | 60.34 | +0.03 |
| variogram | 56.31 | 56.31 | 0.00 |

This reproduces the parent's numbers to 2 dp. That is expected from the design as much as
from noise: per-lineage/gene budget conservation means the pseudobulk gene means (DE score,
DE direction) are essentially untouched by construction, so the only scoreable channel is
co-detection/co-variation (variogram) and cell-state distribution (MMD). Neither moved
beyond 0.03.

## Independent pair-moment diagnostic (not the scorer)

Top-300-variance reference genes, off-diagonal Pearson correlation MSE against the E10.5
target (lower is better):

| realisation | pair-moment MSE | vs parent |
|---|---|---|
| parent operator | 1.692404e-3 | — |
| embedding-conditioned (candidate) | 1.691370e-3 | −6.1e-7 (−0.06%) |

The targeted error moved in the pre-registered direction, but by ~0.06% — two orders of
magnitude short of what a +0.5–1.5 variogram gain would need. The mechanism is real and
correct; its effect on the scored pair moments is below the resolution of the metric.

## Diagnostics (`tools/diagnose.py temporal_val`, report kept outside the workspace)

Same seeds as the parent's `diag_w1c02/report.json`, so the columns are comparable:

| quantity | parent (w1_c02) | candidate |
|---|---|---|
| composition TV (copy-reference 0.428) | 0.415 | 0.413 |
| Blood fraction (kNN) | 0.024 | 0.024 |
| top-200 sign agreement | 0.86 | 0.86 |
| top-200 correlation | 0.432 | 0.432 |
| DE slope β (R²) | 0.113 (0.186) | 0.113 (0.186) |
| severity log β (R²) | −1.819 (0.140) | −1.819 (0.140) |
| response-magnitude ratio | 0.22 | 0.22 |

Exactly the expected signature of a mass-conserving placement change: the pseudobulk/DE
axis is unmoved (per-lineage/gene budget is identical), composition TV improves by 0.002
through CP10k renormalisation only, and the under-predicted globins (Hbb-y +2.28 true vs
+0.06 predicted) and Ldha (−0.84 vs −0.32) are the unchanged parent residuals. The targeted
error (pair-moment MSE) moved by −0.06%, i.e. directionally correct but negligible.

## Verdict

- No DE loss (0.00 ≤ 0.1) and no MMD loss (+0.03, well inside 0.2), i.e. the change is
  **harmless**, but the paired proxy delta is 0.00 with no evidence of a positive effect.
- Pre-registered acceptance rule required a paired proxy CI > 0 with DE loss ≤ 0.1 and MMD
  loss ≤ 0.2. At n=1 we have a point delta of 0.00 and no CI; the honest label is
  **inconclusive / neutral → do not promote on this evidence**. Per the pre-registration
  there was **no escalation with 16 seeds and no sweeps** of 50/0.5/[0.5,2]/q.
- Interpretation for the fleet: the recipient law is a correct but very weak lever because
  the reallocated entries carry only ~0.4% of the expression mass; it changes *which* cell
  holds a small nonzero without changing any gene's mass, so only higher-order co-detection
  terms can respond. A future attempt that wants a scoring effect here would have to change
  the *amount* or *scale* of the realised component, which is outside this hypothesis (and
  was explicitly excluded: "no expression mass added").

## Deviations / scope

- The pre-registered 8 paired seeds were **not** run inside the worker budget (one
  prediction is ~150 s and the workspace's quick-eval counter was at 2/3 on entry; the one
  remaining run was used on `temporal_val`). Only one paired point exists; the fleet's n=8
  paired evaluation is the decisive test. Note the mechanism is structurally near-zero on
  DE metrics, so a paired test would mostly measure variogram/MMD noise around 0.
- Diagnosis tool: `tools/diagnose.py temporal_val --workspace .` was run with the report
  written **outside** the workspace (`/scratch/user/tmp/opencode/w1c04/diag`); numbers
  are in the diagnostics table above. It confirms the mechanism is mass-neutral by design
  (identical DE/severity/pseudobulk axis) and that the only movement is a 0.002 composition
  TV plus the −0.06% pair-moment MSE.
- All validation scripts and the parent-code snapshot were kept outside the workspace
  (`/scratch/user/tmp/opencode/w1c04/`). The workspace contains only `program.py`,
  `sparse_anchor.py`, `temporal_sampling.py`, `metabolic_sampling.py` (the last two
  untouched) plus the inherited `diag_*` directories and this file.
- Not smoke-tested board-by-board: only `predict_temporal` changed. Other boards are
  reached through the same unchanged `predict()` dispatch and their functions are
  byte-identical, so they run the parent code exactly (the module imports successfully, as
  the temporal run proves).
