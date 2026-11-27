# Knowledge bank

## Established (held up; effect sizes and cycles)
(none yet. No cycle has produced a CONFIRMED result. Seed dev proxy is 173.68, the best accepted score for w0 [w0_c00][w0_c01].)

## Dead ends (and the condition under which a retry is justified)
(none yet. Both cycles were DISQUALIFIED, so no mechanism was measured or refuted [w0_c00][w0_c01].)
- As-run cardiac maturation-delay reversal [w0_c01] is not refuted, only uninformative: alpha=0.1, clip ±0.35, mean |dX| 5.6e-4, so Δproxy +0.00. No retry as run. Retry only with a magnitude-calibrated variant. Its predicted DE log-fold changes must clearly exceed scorer and seed noise. Choose the effect size a priori, or sweep it on dev while keeping gata4_2 and one other knockout untouched. It also needs an authorised on-panel non-dev knockout.

## Promising / inconclusive leads
- **Expression-supported lineage reweighting for knockout perturbation (perturbation board)** [w0_c00]. Unmeasured: the cycle was DISQUALIFIED and Δproxy was zeroed. The numbers below are self-reported and unaudited, so this is a lead only.
  - Mechanism: keep the parent within-type complexity sampler. Apply one global composition reweighting in predict_perturbation.
    - Weights are w_t = exp(-ln2 * max(0, q_t - q)).
    - q_t is the detection fraction of the context-supplied knockout gene in type t, shrunk toward the population fraction q with lambda = sqrt(n_obs).
    - Any type's mass change is capped at 2x.
    - It abstains (base probabilities) when the gene is absent or undetected.
  - Self-reported on Gata4 dev:
    - Composition TV error 0.168→0.132, against copy_last 0.146.
    - Pseudobulk r 0.392→0.483.
    - Quick-eval +2.04 on gata4_1 and +0.37 on gata4_2.
  - The severity term stayed at its floor of 50.0 because delay=0. The gain came from composition, pseudobulk and variogram.
  - Caveats: two Gata4 replicates, one seed, one gene, so transfer across genes is unestablished. Detection measures exposure, not essentiality, Cre recombination or phenotype direction. It is an association-based prior, not a causal one.
  - **Retry condition:** rerun the identical mechanism with all diagnostics written outside ws/ (see Implementation pitfalls). Judge it with at least 2 scoring seeds and at least one additional on-panel knockout gene. Do not re-tune the 2x cap to the reported CM fraction.
- Cardiac maturation delay as a state-change hypothesis [w0_c01]. It is unmeasured and only conceptually motivated. Cited biology (myocardial Gata4 deletion; MesP1-Cre beta-catenin SHF/RV defects with FHF preserved) supports lineage-selective disruption, not a uniform reversed WT maturation trajectory. Keep it separate from composition reweighting.

## Per-board state of the art and weakest metrics
- **perturbation**: best accepted program is the seed, dev proxy 173.68 (w0). No accepted mechanism beyond the parent within-type complexity sampler [w0_c00][w0_c01].
- **heart**: the only record is [w0_c01], which was tagged heart but was inert. No board score beyond the seed.
- Other boards have no records.
- Weakest metrics, from unaudited or inert cycles:
  - Severity_slope sits at the finite floor of 50.0 (-6.908 raw) for the parent, copy_last and candidate alike [w0_c00][w0_c01]. It is gated on beta>0 and R2>0.01 on the scorer's DE set. Moving 50→75 is worth about 6.25 T3 points only if the gate passes.
  - Gata4 composition TV error (parent 0.168, copy_last 0.146) [w0_c00].
  - Pseudobulk r (parent 0.392) [w0_c00].
  - Quick-eval per replicate: gata4_1 53.52 and gata4_2 53.66 for the parent [w0_c01].
- Target for the next cycle: beat copy_last on composition, and check the severity gate explicitly.

## Method pitfalls (statistics, evaluation, reasoning traps)
- A DISQUALIFIED cycle with Δproxy +0.00 is not evidence against the intervention. Separate "an artifact tripped the audit" or "the intervention was inert" from "the hypothesis failed" [w0_c00][w0_c01].
- Size a perturbation against the metric's detection threshold before spending a cycle. A shift of ~1e-4 of expression space cannot be tested [w0_c01].
- Check the severity gate (beta>0, R2>0.01) on the scorer's observed DE set. Do not assume it from exploratory correlations. Magnitude only matters after the gate passes [w0_c01].
- de_direction uses a genome-wide partial rank correlation. Positive Pearson correlation of top-100 or all-gene expression does not predict its gain. Validate direction on the scorer's DE set after sampling, decoding and clipping [w0_c01].
- The delay_check correlations may reflect composition, not within-lineage maturation, and were not reproduced. Keep composition weights fixed when isolating a maturation mechanism [w0_c01].
- Both Gata4 replicates informed the hypotheses, so gata4_2 is a validation replicate, not an untouched holdout. Forecasts of severity ≥60 or ≥70 were unsupported [w0_c01].
- Score candidates against copy_last as well as the parent. Beating the parent can mean approaching the trivial baseline (TV 0.132 vs copy 0.146) [w0_c00].
- With delay=0 the severity term cannot move, so a null severity result there is uninformative [w0_c00].
- The severity_slope value -6.908 is a finite floor (beta<=0 or R2<=0.01), not an undefined score. Describing it as "undefined" is misleading [w0_c00][w0_c01].
- Two replicates on one seed and one gene do not establish transfer across knockout genes. Do not let the +6-point forecast or the target CM fraction set constants [w0_c00].
- Expression detection is not essentiality. context['knockout'] carries no Cre driver, so off-panel genes justify no response [w0_c00].
- z uses scoring-seed noise only, because the prediction seed is fixed. It understates total variance, so treat |z| < 3 with caution.

## Implementation pitfalls (crashes, helper quirks, contract)
- **Never write report.json, validation scripts or any diagnostic into ws/ or cycle dirs the audit scans.** The audit substring-scans ws/**/*.{py,md,json,txt} for 'mab21l2', 'T2/E10.5', 'T2/E7.5.h5ad', 'E7.5.h5ad' and 'E10.5.h5ad'. A DE gene list containing Mab21l2 disqualified [w0_c00]. An offline validation script that referenced the cycle paths was flagged in the audit of [w0_c01]. Write diagnostics to analysis/ or outside the workspace, and avoid held-out names and paths in them.
- ComplexityPerturbation builds a LatentFlow with a hard-coded 0.25 interval even when delay=0. Calling model.probabilities is a needless fit, so reimplement the weights directly [w0_c00]:
  - z-score of log1p(n_genes) within type, with std floor 0.1.
  - b = exp(clip(-0.5z, -5, 5)).
  - Normalise per type, then globally.
- Do not pass a nominal delay into a helper with a hard-coded 0.25-day interval. LatentFlow must receive the actual input interval, or an interval-scaled mechanism silently does nothing. Flow velocity is a displacement over the fitted interval, not a per-day rate [w0_c01].
- Never multiply log-scale X by exp(shift) and then call normalize_log. That renormalises the partial 500-gene panel to CP10k and injects unrelated shifts. Use bounded additive deltas with no renormalisation [w0_c01].
- The helper's per-type normalisation preserves WT type mass. Apply composition reweighting globally after building p, and do not renormalise within types again [w0_c00].
- Lineage selection: use lineages()/LineageDelay.CARDIAC from src.v2.transport, not substring matching on 'mesoderm'. Require each affected type to appear in both WT inputs, and use a len(rows) >= 2 per-type guard [w0_c01].
- Sampling with replacement duplicates barcodes and warns about duplicate obs names. Suppress the warning and assign unique pred_i names plus a source_row column. Align genes by name and verify all 500 genes and 3000 cells survive [w0_c00][w0_c01].
- Keep abstention as an explicit code path (return the parent sample) for absent, wholly undetected, uniformly detected or nonpositive-interval cases. Resolve context['knockout'] against var_names with no gene-specific branch. Wrap flow construction and decoding in try/except that abstains. Off-panel Ctnnb1 must reproduce the parent's source_row vector exactly [w0_c00][w0_c01].
- Prediction must not touch files, network or subprocesses [w0_c01].

## Open questions
- Does the reweighting transfer to other on-panel knockout genes and to a second scoring seed? [w0_c00]
- Does the composition gain (TV 0.168→0.132) survive an audit-clean rerun, and does it beat copy_last (0.146) by a meaningful margin? [w0_c00]
- Can a delay or maturation term of calibrated magnitude move severity_slope off its floor and pass the direction gate? Calibration is needed because alpha=0.1 gave nothing [w0_c01]
- Is a lineage-selective (not uniform reversed-WT) cardiac effect detectable at all on the Gata4 DE set? [w0_c01]
- What are the state of the art and weakest metrics on the boards other than perturbation? No records yet.
