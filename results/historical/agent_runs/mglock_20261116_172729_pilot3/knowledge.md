# Knowledge bank

## Established (held up; effect sizes and cycles)
(none yet. No cycle has reached CONFIRMED. Dev proxy 173.68 is the baseline. The T3 empirical sampler with ComplexityPerturbation sampling is the parent for all comparisons [w0_c00][w0_c01].)

## Dead ends (and the condition under which a retry is justified)
(none yet. No NEGATIVE result exists. Both cycles so far are INCONCLUSIVE, so they are not dead ends. See leads.)

## Promising / inconclusive leads
- Both T3 tweaks tried so far are INCONCLUSIVE. Each moved only perturbation, by less than 0.1 proxy. Temporal, heart and embryo stayed exactly 0.0 in both, as expected for T3-only edits [w0_c00][w0_c01].
- Knockout-gene detection reweighting of the T3 empirical sampler: INCONCLUSIVE [w0_c00].
  - Method: in predict_perturbation only, multiply the parent ComplexityPerturbation sampling probabilities (strength 0.5, delay 0) by exp(-0.5*e_t).
  - e_t is a shrunken, clipped enrichment of the knockout gene's detection rate in a celltype relative to the stage-global rate. It must agree across the last two WT inputs (factors ~0.61-1). It abstains to the exact parent prediction when the gene is missing, duplicated or undetected.
  - Measured: Δproxy -0.10 (95% CI -0.70..+0.50, z -0.3, n=8 seed pairs). Perturbation -0.10.
  - Per-seed differences ran -1.20..+1.41 against ~1.0 single-seed parent noise. There is no evidence of gain or harm. The claimed effect (~+1) is below the resolution of n=8 (SE 0.316).
  - Retry only if (a) the knockout gene exists in the target panel and (b) a paired design with >=16 seeds or variance reduction is affordable.
  - Caveat: the real T3 knockout gene Ctnnb1 is absent from the 500-gene T2 panel. On the real T3 test the candidate abstains and returns the parent prediction exactly, so dev (Gata4) signal cannot transfer [w0_c00].
- Cardiac lineage delay: a fixed 0.1-day backward shift along the input-derived WT transport direction, masked to cardiac cells, strength 0.5 kept [w0_c01].
  - Measured: Δproxy +0.07 (95% CI -0.09..+0.23, z +0.79, n=8 seed pairs, SE 0.086). Perturbation 54.03 versus the parent.
  - Per-seed diffs ran -0.34..+0.40, so the sign flips across seeds. The small positive mean is not a trend.
  - A single-seed quick-eval gave -0.52 on perturbation with de_score down on both splits. It did not predict the fleet mean. Severity_slope stayed floored at 50.0, so there was no gate signal.
  - Resolution at n=8 is ~0.1-0.2 proxy, so an effect of order +1 is effectively excluded for this exact shift, and a smaller effect is unresolved. The prior is unsupported at 0.1 day.
  - Retry only with (a) evidence that the fitted velocity encodes maturation state rather than sampling/complexity or cross-lineage artefacts, (b) a variant that moves de_score and de_direction rather than only marker magnitudes, and (c) a powered design that can resolve ~0.1 units.

## Per-board state of the art and weakest metrics
- Dev proxy 173.68 is the best accepted score, held by w0 [w0_c00 pilot parent, seed 101]. Nothing has been accepted since.
- Rejected candidates, for reference:
  - w0_c00: temporal 54.77, heart 48.85, embryo 81.10, perturbation 54.77 (Δ -0.10 on perturbation) [w0_c00].
  - w0_c01: temporal 54.77, heart 48.85, embryo 81.10, perturbation 54.03 (Δ +0.07 relative to the parent) [w0_c01].
- Mechanism behind the current best: the T3 empirical sampler with ComplexityPerturbation sampling (strength 0.5, delay 0). The parent program id is not recorded in the records so far.
- Weakest boards: heart (48.85), then temporal and perturbation (~54). Per-metric breakdowns are mostly unrecorded. The only metric signals so far are de_score and de_direction on perturbation, and severity_slope floored at 50.0 [w0_c01].
- Known composition error: gata4_2 has a Neural Tube CM-fraction error of +0.095 in both parent and candidate. Composition TV is diagnostic only and not scored [w0_c00].

## Method pitfalls (statistics, evaluation, reasoning traps)
- Judge effects against seed noise. Single-seed parent jitter is ~1.0 proxy. SE was 0.316 for n=8 in [w0_c00] and 0.086 in [w0_c01], because the noise depends on the candidate. A ~1-point gain needs >=16 paired seeds or variance reduction [w0_c00][w0_c01].
- Quick or single-seed screens do not rank changes at this effect size. The screen proxy (174.51) missed the eval proxy (173.58) [w0_c00]. A quick-eval of -0.52 missed a fleet mean of +0.07 [w0_c01]. Do not accept or reject on a screen alone.
- A small positive mean with a CI spanning zero is not a trend. Average the two splits within each seed configuration before computing the mean and CI. Pre-declare the bar (mean >= +1.0, CI excluding zero, de_score up on both splits) so a null cannot be re-read as a win [w0_c00][w0_c01].
- Marker-magnitude improvement does not imply gains in de_score (signed gene ranking) or de_direction (genome-wide rank correlation after baseline control). Check them separately [w0_c01].
- Severity is a through-origin regression on truth DE pseudobulk. The gate needs beta>0 and R^2>0.01. Parent R^2 does not guarantee the modified response stays unfloored, so measure it. The score is floored, not undefined, when the gate fails, so larger shifts do not guarantee improvement [w0_c00][w0_c01].
- Transcript detection is confounded by observation complexity. It does not identify pathway activity, lineage dependence or the recombined compartment. Cross-stage agreement reduces instability but is not causal evidence [w0_c00].
- Run a zero-shift control. It must return exact identity, which rules out a library-size artefact [w0_c01].
- Scope claims honestly: T3-only changes can only move perturbation, so the other boards should read exactly 0.0 [w0_c00][w0_c01].
- Pre-specify strength and forbid calibrating toward the observed dev CM fraction [w0_c00].
- Two small T3 tweaks, a sampling reweight and a lineage delay, each landed within noise (|Δ| <= 0.1). Expect further small-shift T3 edits to be unresolvable. Prefer larger-headroom changes, or invest in variance reduction first [w0_c00][w0_c01].

## Implementation pitfalls (crashes, helper quirks, contract)
- Resolve gene names only on exactly one exact match and one case-insensitive match. Otherwise return None and fall back to the parent. `names.index(gene)` silently takes the first duplicate and skips the ambiguity abstention [w0_c00].
- Check that the real test knockout gene exists in the target panel before developing on a dev gene. Ctnnb1 is absent from the T2 500-gene var_names [w0_c00].
- ComplexityPerturbation.__init__ hard-codes LatentFlow(interval=0.25). Override model.flow.interval from times[-1]-times[-2], or a "0.1 day" delay has no physical meaning [w0_c01].
- The decoder helper multiplies log-expression by exp(clipped shift) and then renormalizes through expm1/log1p. The ±0.35 clip does not bound the final change (per-element Δlog -4.26..+2.95, 5.6% of shifts clipped) [w0_c01].
- Rescale each affected cell to its own original sum(expm1(X)), not a fixed 10000. Leave zero-total rows at zero and unaffected rows bit-identical [w0_c01].
- Import LineageDelay explicitly. Fall back to the exact delay=0 parent for invalid or non-positive intervals or when no cardiac cells are sampled [w0_c01].
- Quick_eval allows only one split, one seed and 3 runs. Plan paired multi-seed evaluation separately. Parent numbers come from the stored seed-101 pilot3/seed_dev.json [w0_c00].
- Write diagnostics outside the submitted workspace (../diag_*) and outside predict(). Preserve pred_i obs_names, source_row, all genes and spatial coordinates. Keep delay=0 when resampling empirical cells [w0_c00][w0_c01].

## Open questions
- Can any T3 change produce a gain on the real knockout (Ctnnb1), given that it is absent from the T2 panel? Possible routes are composition-level priors or knowledge from other stages [w0_c00].
- Do temporal, heart or embryo changes offer larger headroom than perturbation? Heart is the lowest board (48.85), and no cycle has targeted it yet [w0_c00][w0_c01].
- Which per-metric terms are weakest on each board? Record per-metric breakdowns in the next cycles [w0_c00][w0_c01].
- Can paired variance reduction (shared seeds, control variates) bring the proxy SE below ~0.1-0.3 at an affordable cost [w0_c00][w0_c01]?
- Does the fitted transport velocity carry maturation information at all? A direct check, such as correlation with known cardiac maturation markers, would settle the lineage-delay lead before any retry [w0_c01].
