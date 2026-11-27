# w3_c02 — Temporal: empirical hurdle amplitudes for the weak anchor-created component

## What changed

Only `temporal_sparse_anchor.py` was edited (verified with `cmp` against
`agentic_scientist/seed` and the parent copy: the parent's `temporal.py` /
`temporal_anchor.py` differences are w3_c01's, everything else is byte-identical).
No `program.py`, no other board, no `src.v2` import.

### Mechanism (shipped ON, no rollback, no gate, no score-dependent arm)

The sparse realisation replaced tiny artificial positives by `k = ceil(S/q)`
carriers at one lineage quantum `q = min(0.5, median donor row-min positive)`,
which conflates the detection probability with the conditional positive
amplitude of an expressed gene. This cycle factorises them (two-part / hurdle
observation law; Finak MAST 2015, scDesign2 2021 treat detection, positive
magnitude and correlation as distinct properties):

```
u[c,g] = mean(log1p(CP10k) | expression > 0, lineage = c)   # ALL latest-stage cells of c
         (supported only if at least MIN_POSITIVE_CELLS = 10 positives)
a[c,g] = max(q, min(u[c,g], AMPLITUDE_CEILING = 2.0))       # supported
       = q                                                   # unsupported (bit-identical parent)
k0     = min(|E|, max(1, ceil(S/q)))                         # parent, untouched
k1     = min(k0, max(1, ceil(S/a)))                          # supported genes only
```

`S` (the per-lineage/gene log-expression budget of the original eligible weak
block) is unchanged; the same budget is emitted over fewer carriers at
`S/k1`. Recipients are the **first `k1` entries of the parent's already drawn
recipient list** — both parent RNG streams (uniform `rng`, state-conditioned
`rng_w`) are still advanced exactly as before, in the same gene order, with the
same `k0` draw. Unsupported genes and every gene after them therefore keep the
parent's draws and values bit-for-bit (verified: with the support rule disabled
the new module reproduces the seed module byte-identically on a synthetic case).

`normalize_log` still runs on the changed rows only; the log budget is exact
before that CP10k restoration and approximate (not guaranteed) after it, as
documented in the module.

### Diagnostics (flat scalars in `uns['sparse_anchor']`, plus
`uns['sparse_anchor_hurdle_lineage']` = emitted/eligible carrier ratio per
lineage; diagnostics only, no control flow)

`n_hurdle_genes`, `n_quantum_genes`, `n_reduced_genes`, `k0_total`, `k1_total`,
`eligible_entries_total`, `emitted_entries_total`, `carrier_reduction`,
`amplitude_q10/q50/q90`, `created_amplitude_mean`.

## quick_eval (seed 101 / fit 0, one run per split — wiring check only)

temporal_val:

| metric | candidate | parent w3_c01 (same harness, same seed) | delta |
|---|---|---|---|
| score | **58.62** | 58.60 | +0.02 |
| de_score | 52.93 | 52.93 | 0.00 |
| de_direction | 64.04 | 64.04 | 0.00 |
| mmd_u | 60.95 | 60.94 | +0.01 |
| variogram | **55.47** | 55.41 | +0.06 |

temporal_heartonly (target-filtered split; no parent single-seed reference was
recorded in this workspace, so only the candidate is reported):

| metric | candidate |
|---|---|
| score | **59.26** |
| de_score | 54.95 |
| de_direction | 65.65 |
| mmd_u | 61.57 |
| variogram | 53.21 |

Both runs completed without error, so the mechanism is wired on both temporal
splits and does not crash. The temporal_val change is small and inside
single-seed noise; it is **not** a score estimate. No crash, finite/non-negative
output, unchanged `source_row` identities. The mechanism activates only through
`context['external'] is not None` (same gate as the parent's sparse realisation)
and reuses the parent's eligibility mask, `q` and recipient law, so nothing
upstream moved.

## Expected/claimed effect not yet measured

- The hypothesis forecasts >=15% fewer weak-created detections in Endocardium
  and Pericardium. The audit's count-only upper bounds were -24.3% and -32.5%
  before the >=10-positive support rule. The realised per-lineage ratio is
  reported in `uns['sparse_anchor_hurdle_lineage']`; the fleet run is the place
  to read it (quick_eval does not expose `uns`).
- Forecast variogram +0.1..+0.5 on both splits: the single temporal_val run
  gives +0.06, well below the forecast, so the gain claim is likely
  inconclusive at n=8 rather than resolved. Reported as such; the harness decides
  retention.

## Deviations / notes

- No functional deviation from the plan. The pre-registered constants
  (`MIN_POSITIVE_CELLS = 10`, `AMPLITUDE_CEILING = 2.0`) were not swept.
- `temporal_heartonly` was run as a second quick_eval split to confirm the
  filtered split also runs; it is not used to tune anything (2 of 3 runs used).
- The standalone `--set sanity` three-day plausibility run was **not** re-run
  locally inside the time budget; the fleet applies the gate. The mechanism
  cannot change the extrapolation magnitude: per-gene/per-lineage log budgets
  are unchanged, the anchor clip (±0.5) and horizon damping are untouched, and
  the only new bound is the a priori per-entry amplitude ceiling of 2.0 log
  units. The parent passed the gate (var_ratio 0.966, gene_blowup_frac 0.0).
- Linear-mass change after CP10k restoration was not measured exactly (it would
  duplicate the `normalize_log` pass); the module documents that concentration
  at fixed log mass can raise linear abundance by convexity.
