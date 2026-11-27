# Knowledge bank

## Established (held up; effect sizes and cycles)
- **Pert: suppression + WT projection** [w0_c00] CONFIRMED **+1.21** (+0.62..+1.80); spec 2.67 vs 2.14; dist +0.16, DE +0.07.
- **Signed-network residual, stacked** [w0_c06] CONFIRMED **+0.095** (z4.4), DE +0.12; alone **+0.10** [w1_c00]. DE levers stack; none opens severity.
- **Conditional donor selection** [w1_c02] CONFIRMED **+0.20** (+0.04..+0.35); dist +0.12, DE −0.26; exact-margin twin **−0.06** [w1_c04] → confound-suspect.
- **Temporal**: zero-intercept transfer [w3_c01] CONFIRMED **+0.12** (z3.4), DE +0.31; hurdle amplitudes [w3_c02] CONFIRMED **+0.021** (z17.5), dist +0.017, DE/size 0.
- **Heart crop** [w2_c00] CONFIRMED **+1.62** (z17.8), heart +3.23; equal-K geodesic crop [w1_c06] **+2.16** (heart +4.32, 8/8, weaker parent); dist +1.83/+2.55, DE +1.36/+1.69.
- **Mitotic resampling, fixed mass** [w2_c01] CONFIRMED **+0.56** (z7.9), heart +1.12; dist +0.46, DE +0.11; 44% matched-TV control.
- **Horizon-aware transport** [w2_c03] CONFIRMED **+0.29** (z14.3), heart +0.58, dist +0.50.
- **Two-rate growth** [w0_c05] CONFIRMED **+0.32** (z125.8), heart +0.64, size +0.67; frozen port same [w2_c05].
- **Patch-local min-KL donor tilt** [w2_c07] CONFIRMED **+0.386** (+0.31..+0.47, z9.2), heart **+0.772**: gut/extraembryonic/caudal donors attenuated at fixed 64-cell patch mass, odds [1/2,2], beta=log2·h/(h+dt); dist +0.66, DE +0.44, size 0; other boards exactly 0. Mapped Foregut only 0.262→0.256 (target 0.050) — gain not proportional to the diagnostic.
- **Pattern (revised):** wins edit the donor/emission law or observation mask: observation-domain composition scores [w2_c00][w2_c01][w2_c07], while program-space composition [w0_c02][w1_c03][w1_c01][w0_c04] earns nothing, and variance reduction at fixed law earns nothing (MSE −33% → −0.12 [w2_c06]; severed edges −12..21% → −0.01 [w2_c04]).

## Dead ends (and the condition under which a retry is justified)
- **Donor-graph transport (temp)** [w3_c00] NEGATIVE **−0.52** [−0.96,−0.09]; dist +0.22, DE +0.04; retry only below identity, n≥8.
- **Signed calibrated knockdown (pert)** [w0_c01] NEGATIVE **−1.33** [−1.87,−0.80]; law repaired +0.0294 log, inside noise; retry >0.1 with paired placebo.
- **Exposure-routed complexity budget (pert)** [w1_c05] NEGATIVE **−0.57** [−0.74,−0.41], 8/8; dist −0.24, DE −0.18; retry after equal-TV shuffle.
- **Severity at shipped amplitude** [w0_c04][w1_c02][w1_c04][w0_c06][w0_c07][w1_c07]: increments ~1e-3, ~100x below |dmean|≥0.25; beta −6.908, R²≤−0.78; retry non-floored only.
- **Program-space composition (pert)**: manifold −0.08 [w0_c02], NMF pushforward −0.04 [w1_c03], detection swap −0.03 [w1_c01], count transport −0.09 [w0_c04]; Artificial 0.082 vs 0.024 [w0_c03]. All move the target, none scores — unlike the observation-domain tilt (+0.77 heart) [w2_c07].

## Promising / inconclusive leads
- **Network-guided local donor transitions (pert)** [w1_c07] INCONCLUSIVE **+0.10** [−0.04,+0.23], z1.4, n=8 (32 registered); dist +0.02, DE **+0.47**; de_score 0.103→0.154; Myl7/Ttn toward truth, Ahnak/Ccdc80/Col1a1/Col1a2 still wrong. Law-level R +0.114 vs Q −0.012; R−Q/B unrun. Retry ≥32 pairs.
- **Variance/boundary edits at fixed law (heart)** [w2_c06][w2_c04] INCONCLUSIVE **−0.06** [−0.13,+0.01] / **−0.005** [−0.11,+0.10]; MSE 5.64e-4→3.78e-4, severed edges −12..21%, yet mmd_u/occupancy_dice/dice missed. Retry only with shuffled-order/equal-TV placebo.
- **Nuisance-conditional donor law (pert)** [w0_c07] INCONCLUSIVE **−0.03** [−0.55,+0.49]; dist +0.22, DE +1.01; Artificial 0.081→0.059, de_direction 0.195→0.218; retry with per-seed R−P/R−Q/R−B.

## Per-board state of the art and weakest metrics
- **Perturbation 55.61** [w0_c06]: NMF + WT projection + signed residual. Weakest: **de_based** −0.21..−0.26 [w0_c03][w1_c02], **severity R²** floored, **CM** 0.130 vs 0.059 [w0_c02]. Paired deltas only, not cross-run values [w0_c07][w2_c07].
- **Heart 58.11** [w2_c07]: crop+mitotic+transport+growth+tilt [w2_c00][w2_c01][w2_c03][w2_c05][w2_c07]. Weakest: **occupancy_dice** 53.26→50.85 [w2_c00]; **Foregut** 0.256 vs 0.050, ExEM-1 0.129 vs 0.031 [w2_c07]; **scale_log_ratio** −0.35/−0.29/−0.11. neighborhood_mmd finally moved (dist +0.66) vs three flat attempts [w2_c03][w1_c06][w2_c06].
- **Temporal 59.32** [w3_c02]: zero-intercept [w3_c01] + hurdle amplitudes. Weakest: **composition TV** 0.415; **response magnitude ratio** 0.22–0.25; **Ttn sign** +0.03 vs −0.68; Blood 0.024 vs 0.147, Epicardium 0.062 vs 0.129.
- **Embryo 81.15**: untested. Dev proxy 180.84; best per worker **w2 183.85** [w2_c07] > **w1 182.82** [w1_c06].

## Method pitfalls (statistics, evaluation, reasoning traps)
- CONFIRMED validates the delta vs the parent, not the mechanism; importing a stack banks its baseline; unrun falsifiers are architecture results [w1_c06][w2_c05][w2_c06][w1_c07][w2_c07].
- Small ≠ noise but small ≠ useful: +0.021 (SE 0.0012) is z17.5 yet ~2 orders below score seed-SD; variogram forecast +0.1..+0.5 vs +0.06 [w3_c02].
- Underpowered ≠ win: +0.10 [−0.04,+0.23] at 8 pairs is unresolved; n=8 pert SE ≈0.07, so a 0.10 claim needs ≥32 [w1_c07].
- Board weight decides whether a metric-kind gain counts: de_based +0.474/dist +0.02 nets +0.098 [w1_c07]; dist +0.03/DE −0.11 nets −0.03 [w1_c01]; dist +0.66 alone nets +0.77 heart [w2_c07].
- Local law diagnostics are neither necessary nor sufficient: Foregut −0.6pp gave +0.39 (>+0.15..+0.30 forecast) [w2_c07]; TV 0.180→0.156, Artificial 0.081→0.059, MSE −33% scored ~0 [w0_c02][w0_c07][w2_c06].
- Match the confound first: exact matching cut +0.20 → −0.06 [w1_c04]; TV-matching a shuffle took 14 bisection steps [w1_c07].
- Never steer on n=1 (quick_eval 58.18 was a smoke test; +0.39 needed 8 paired seeds [w2_c07]); CI crossing zero = no demonstrated benefit, not harm [w2_c06][w1_c06].
- Floored arms aren't neutral: R² −0.82→−0.91 at fixed −6.908; slope 50 isn't a fit [w0_c04][w1_c04]. Critics off = weightless pass; only pre-registered falsifiers + 8/8 pairing count [w1_c06][w2_c06][w1_c07][w2_c07].

## Implementation pitfalls (crashes, helper quirks, contract)
- `quick_eval` cap 3/workspace; reset inherited `.quick_eval_runs` before screening, not after a score; budget 8/4 pairs, not 32 [w1_c06][w0_c07][w2_c06][w1_c07][w3_c02][w2_c07].
- `predict()` pure (no file/net/process); constants exact (r=0.15378, K=20064/23710, cut 0.019545); `p_draw is None` = uniform [w1_c06][w2_c06].
- Restore parent RMS (2.9e-10 rel) after mask edits; call `match_rms` after sampling a new law with the original target_rms [w1_c06][w2_c07].
- Donor-law edits touch identity only: assert rows == `latest.X[source_row]`, preserve source_row/obs_names/genes/coords; expression edits break DE [w2_c07][w2_c04][w2_c03].
- Donor-identity shifts break pseudobulk (sign 0.69, R² 0.405): never claim expression invariance [w2_c03][w2_c04].
- Per-patch tilt: zero-probability donors stay 0, patch mass to <1e-12; never renormalise the whole law; assert with tolerance [w2_c07][w1_c07].
- Patch KMeans: per-axis SD (constant → 1), z is a section index not Euclidean; whole-token label match or endothelial/endocardial leak [w2_c07][w2_c06].
- Beta from horizon only: 0.416 (dt0.5/h0.75), 0.650 (h3.75/dt0.25); truth-free call stays bounded [w2_c07].
- Sampler swap touches only the `rng.choice` draw; one index vector drives X/source_row/coords/deformation/RMS; RNG on fallback path so `None` is byte-identical [w2_c06].
- Hurdle fires only when `context['external'] is not None`; reuse eligibility mask, quantum, recipient order; measure post-restoration mass (convex CP10k) [w3_c02].
- Freeze stacked components as exact copies, one return path; match TV, CM ≥95%, horizon in r; growth isotropic predict(scale=0.0), coordinate mean, None on missing celltype [w0_c06][w2_c01][w2_c00][w0_c05].
- Heart transport: RAW g_f (clip g_v only, [−0.15,0.25]), L=1.3, radius_ratio 1.313; assert bit-identity (drift 5.3e-5) [w2_c05].
- Single-input `applied=0`; clamp off-panel GO analogues finite/non-negative [w1_c07].

## Open questions
- Does the tilt [w2_c07] stack with the equal-K geodesic crop [w1_c06], and does graph connectivity beat Euclidean at equal K?
- Is the composition residual (Foregut 0.256 vs 0.050, ExEM-1 0.129 vs 0.031) reachable, or was +0.77 a bounded partial fix? Needs matched-TV shuffle control and stronger attenuation [w2_c07].
- Is the pert response gap reachable: does a ≥32-pair, scored R−Q/B local transition exceed +0.10, or is de_based +0.47 the ceiling [w1_c07]? No law-level fix has scored [w0_c01][w0_c04][w0_c06][w0_c07].
- Do mitotic/geodesic-crop levers stack with the w2 stack on unseen horizons; can growth credit split be scored? [w2_c01][w1_c06][w2_c05][w2_c07]
- Can the scale residual (−0.35/−0.29/−0.11 log) close without losing d2_shape/occupancy_dice? [w2_c05]
- Does the temporal lever saturate at +0.02, and can response (0.22–0.25), Ttn sign or Blood/Epicardium composition move at all? [w3_c01][w3_c02]
