# Knowledge bank

## Established (held up; effect sizes and cycles)
- Perturbation: global bounded WT lineage-abundance rollback. Each WT lineage's sampling probability is multiplied once by w_l = exp(e·clip(log(f_earlier/f_latest), ±cap)). It uses alias-collapsed shared lineages with ≥30 cells at both stages. It sits on top of the parent's ComplexityPerturbation.probabilities(0.5), then is renormalised globally.
  - e=0.5, cap 2x: CONFIRMED, Δproxy +5.31 (CI +4.09..+6.54, n=8), pert 57.92 [w1_c00].
  - e=1.0, cap 2x: CONFIRMED twice from separate implementations, pert 71.67.
    - +11.37 vs e=0.5 (CI +10.02..+12.72, n=8) [w1_c01].
    - +16.68 vs the seed parent (CI +16.12..+17.24), total proxy 190.36 vs 173.68 [w0_c01].
    - These sit on one ladder (5.31+11.37=16.68). Both cycles are the same single-gene evidence.
  - e=1.0, cap 4x: CONFIRMED, +2.29 vs w1_c01 (CI +1.95..+2.62, n=8), pert 73.77 [w1_c02].
    - The gain is concentrated on gata4_2. gata4_1 gained ~1.33.
    - It breached the pre-registered harm limit: gata4_1 Neural Tube 0.093 < 0.10.
    - The cap was chosen after inspecting dev diagnostics, so it is selection-contaminated.
  - Total gain over the seed parent is ~+20 proxy (173.68 → 193.52), all on perturbation. The other boards are Δ 0.00 [w1_c00, w1_c01, w1_c02, w0_c01].
- The e=1.0 gain came mainly from opening the scorer's severity gate (beta>0 and R²>0.01).
  - R² moved from -0.539/-0.328 (e=0.5) to 0.085/0.313 (e=1.0), with severity skill 89.4/87.4 [w1_c01].
  - Scaling alone cannot change R² or DE ranking, so the response direction changed [w0_c01].
  - gata4_1 R² has only a 0.01 margin [w1_c02].
- At e=0.5, DE recovery and direction rose ~+5-6 per split. That exceeds what composition TV explains (TV fell only 0.009) [w1_c00].
- Returns diminish: +5.3 (e 0→0.5), +11.4 (0.5→1.0), +2.3 (cap 2x→4x) [w1_c00, w1_c01, w1_c02].
- Heart: bounded extrapolation of a fixed myocardial-program compartment, CONFIRMED [w0_c02].
  - Latest-stage cells are reweighted by m=exp(clip((logit f_last − logit f_prev)·horizon/interval, ±log2)). The indicator is the 3-gene mean log expression >0.5 (Myl7, Myl4, Ttn).
  - Heart +4.80 (48.85→54.67), Δproxy +2.40 (CI +2.11..+2.69, n=8).
  - The gain is pseudobulk DE (de_score and de_direction ~+13.7 each, single-seed). neighbourhood_mmd rose +5.9, but d2_shape fell ~2.5.
  - The single-seed screen inflated the effect (+6.15 vs +4.80 paired). The 2x cap was hit on both dev splits.
  - This is the first cycle to lift heart above the ~50 copy-last floor.
- Temporal: bounded erythroid source enrichment, CONFIRMED, Δproxy +1.16 (CI +0.43..+1.90, n=8, z=3.0) [w0_c03].
  - Mechanism: latest-source sampling odds for exact Blood/erythro-labelled cells that also show shared-marker expression. The factor is w=2^min(horizon/interval,1) in [1,2], added as a log_growth offset on the existing LatentFlow/AnchorFlow.
  - Blood fraction moved only 0.014→0.021 vs a 0.147 target. The gain came from corrected globin direction signs (5/5 agree, top-200 sign agreement 0.745→0.835), with de_direction only +2.13.
  - It is exploratory (the correction was chosen after inspecting dev errors). It is the first positive temporal lever.
  - Temporal board 56.70 vs the 54.77 parent. That is +1.93 on the board against +1.16 paired Δproxy, so use the paired figure.
- Board isolation is reliable: board-local changes leave the other three boards at Δ 0.00 [w0_c00, w1_c00..c03, w0_c01..c03].
- Perturbation results are single-gene evidence: both Gata4 splits share identical WT inputs and Ctnnb1 is untested. Heart is effectively one latest stage (E8.75) [w1_c02, w0_c02].

## Dead ends (and the condition under which a retry is justified)
- Generic developmental-delay mixing (round(d·n) earlier-stage WT cells, d=0.25) is NEGATIVE: Δproxy -1.84 (CI -3.10..-0.58, n=8), pert 53.20 [w0_c00].
  - The plain-sampling primary scored 49.29, below the copy-last floor. The earlier dev gain came from the complexity-weighted observation model.
  - Retry only with (a) an a priori WT-only delay criterion and (b) severity clearing R²>0.01 out of sample, across seeds and more than one knockout gene.
  - Reweighting WT cells works. Mixing in earlier cells does not [w1_c00, w0_c00].
- Composition reweighting to fix heart geometry (radius/scale deficit, pred rms 222 vs target 332) buys expression points only, and d2_shape fell [w0_c02]. Retry only with a spatial/size mechanism.
- Plain donor-zero mask on AnchorFlow output (temporal) is NEGATIVE: Δproxy -0.43 (CI -0.47..-0.39), temporal 54.28 vs 54.77 [w1_c03].
  - Variogram skill rose +3.34, but de_direction fell -4.07 and de_score -0.15.
  - Retry only with a DE-direction-neutral variant: gate only sub-threshold clipped shifts, or mask only genes without cross-stage DE reproducibility. Validate on ≥2 split seeds and a second interval.

## Promising / inconclusive leads
- Merge the best programs. Perturbation rollback, heart extrapolation and temporal erythroid enrichment touch different boards, so the Δs should add: ~193.52 + 2.40 + 1.16 ≈ 197. The dev standing lists w0 best as 196.26. Untested as a merge, so run a parity check [w1_c02, w0_c02, w0_c03].
- Extend the temporal erythroid lever. Options are a cap above 2x, a stricter marker criterion, or other under-represented types. Blood is still far under-predicted (~2% vs 14.7% target). A pool-size-limited sampler cannot exceed ~3x [w0_c03, w1_c03].
- Heart extension hypotheses: a cap above 2x, a different indicator threshold, other compartments. Foregut is over-produced (0.282→0.225 vs 0.050) and SE is barely moved (0.102→0.099 vs 0.050) [w0_c02].
- Rollback cap above 4x, per-lineage strength, or exponent above 1.0 are untested and likely saturated. Retry only with a pre-registered cap on an independent gene [w1_c02, w1_c01].
- The rollback may act as a gene-agnostic prior: ExEM/EXE carries 36.4% of the probability-mass change, and ExEM-2 is pushed 4.50x [w1_c02].
- Composition residuals on gata4_1: CM 0.122 vs 0.059 target, and NT undershoot 0.158→0.112 (e=1.0)→0.093 (4x). gata4_2 overproduces NT (0.172 vs 0.084 at e=0.5) [w1_c00..c02].
- Temporal sparsity diagnosis is supported, but no fix has worked. AnchorFlow spreads weak expression onto donor zeros (Endocardium 4,141→12,842 detected genes). Variogram and DE-direction trade off. A selective DE-aware sparsity control is the open lever [w1_c03].
- Test whether the DE gain comes from DE-relevant lineages or a "knockout looks younger" artefact [w1_c00].
- Count thinning as an observation model is untested. It needs an f=1 reconstruction control first [w0_c00].

## Per-board state of the art and weakest metrics
- Best by board:
  - Temporal 56.70 [w0_c03].
  - Heart 54.67 [w0_c02].
  - Embryo 81.10 (unchanged by every cycle).
  - Perturbation 73.77 [w1_c02]. The w0 line holds 71.67.
- Best single programs on the standing: w0 196.26, w1 193.52.
  - w0 stacks perturbation e=1.0 cap 2x (71.67), heart extrapolation (54.67) and temporal erythroid enrichment (56.70) [w0_c01, w0_c02, w0_c03].
  - w1_c02 has pert 73.77 but heart 48.85 and the parent temporal.
  - The scores do not sum cleanly from the Δs I can see, so check the standing before comparing.
- Mechanisms:
  - Perturbation: complexity sampler (0.5) × lineage rollback (e=1.0, min_cells 30), delay off.
  - Heart: myocardial-program-weighted latest-stage sampling.
  - Temporal: erythroid-enriched latest-source sampling.
- Weakest:
  - Temporal (parent levels): variogram skill 50.0, de_score 44.9, mmd_u 58.8, de_direction 63.6. Blood composition is still far off [w1_c03, w0_c03].
  - Heart's d2_shape, scale_log_ratio and radius deficit [w0_c02].
  - Perturbation (inferred; per-metric values not recorded): mmd_u, variogram and composition TV, with severity already ~87-89 [w1_c01, w1_c02].
- Headroom is likely on temporal sparsity/composition and heart geometry rather than further perturbation sampling.

## Method pitfalls (statistics, evaluation, reasoning traps)
- Seeds measure only sampling and fit noise. Both Gata4 splits share WT inputs, and both heart splits share E8.75, so the effective n is below 8. Report per-pair deltas and label results single-gene.
- Score every sub-metric, not just the named endpoint: variogram +3.34 coexisted with de_direction -4.07, and the board fell -0.43 [w1_c03].
- Proxy equals board change times board weight. Temporal weight is 1 and heart 0.5, so a heart +0.75 is only proxy +0.375, below the 1.5 threshold [w0_c02, w1_c03].
- The severity gate returns the floor unless beta>0 and R²>0.01. Top-200 Pearson 0.53-0.68 can coexist with a floor R² [w1_c01].
- evaluate exposes only the folded severity skill. Use skill ≥75 per pair as the gate-open readout and get exact R² from diagnose.py [w1_c01, w1_c02].
- Report gains with and without the severity_slope term (0.25 of T3). One high-leverage term can mimic broad gains [w1_c00..c02].
- State the baseline of every Δ. +11.37 (vs e=0.5) and +16.68 (vs seed) are the s
