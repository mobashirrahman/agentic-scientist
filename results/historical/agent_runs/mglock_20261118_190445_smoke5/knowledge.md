# Knowledge bank

## Established (held up; effect sizes and cycles)
- **Seed champion; no CONFIRMED gain.** Proxy 185.84; tested changes: w0 +1.97 (Gata4 −0.67), w2 +0.17 (heart lower bound +0.22 <0.5 gate), w3 −3.54 (embryo −7.08); w1 no-op (CI ±2.21) [w0_c00; w2_c00; w3_c00; w1_c00].
- **Only heart (+0.34), embryo (−7.08) and perturbation (+1.97) moved; temporal is Δ0 everywhere.** Heart +0.34 [w2_c00] overturns the earlier Δ0 claim [w3_c00; w0_c00; w1_c00]; temporal 0 in all changes [w3_c00; w0_c00; w1_c00; w2_c00].
- **Embryo expression is donor-carried, not geometry-carried.** Identical rows on re-placed 3,000 donors: expression Δ0, embryo −7.08 (z −5.85) [w3_c00].
- **93% of the heart stage shift is per-gene detection** (R² 0.91–0.96, corr 0.96–0.98); detection −0.023/0.25 d; sparsity is the stage axis (target-DOWN 0.43 log lower; corr −0.13..−0.34); real-donor reweighting preserves zeros [w2_c00].
- **KO signs do not transfer across Gata4/Mab21l2/Hand2.** r≈0, agreement ≤0.52, LOGO −0.63/−0.26/+0.06; 44 genes |lfc|>0.02, 21 >0.05 [w1_c00].

## Dead ends (and the condition under which a retry is justified)
- **Per-cell local-patch re-placement (NEGATIVE)** [w3_c00]: Δproxy −3.54, embryo −7.08, occupancy −0.75 (Dice 0.8286→0.8238 < +0.008), neighborhood −10.05 (≤4), d2_shape −45.38 (100→46.9). Retry rigid whole-patch grafts/earlier-only, >+0.0086 [w3_c00].
- **Composition-coupled placement** [w3_c00]: independent composition −7.32 neighborhood; coupling expression to placement −50.7 D2; hold expression fixed [w3_c00].
- **Per-gene cross-KO shared-sign templates (INCONCLUSIVE proxy; LOGO gate failed decisively)** [w1_c00]: min-KL donor tilt (rho_T 0.05–0.25) failed LOGO 2/3 (−0.63/−0.26/+0.06 vs ≥0.55), proxy 0.00 (CI ±2.21). Retry lineage shares (r −0.17..−0.43) or non-TF LOGO ≥0.60 [w1_c00].
- **Extrapolated heart interval/maturation** [w2_c00]: last-interval E8.75→E9.5 slope −0.05, corr −0.10; E14.5→E18.5 corr −0.04/+0.06/−0.11. Retry held-out within-dev trend [w2_c00].
- **Law-level maximal coupling (23% profile swap)** [w2_c00]: geometry held but dense/sparse mixed, neighborhood −3.3; within-annotation position matching +2.3; retry with matching [w2_c00].
- **Patch-wise donor sampling** [w2_c00]: no locality benefit; 15-NN MMD unchanged (k 6/12/25 −0.4036/−0.4043/−0.4118 vs −0.4030) [w2_c00].

## Promising / inconclusive leads
- **Heart within-type detection-state tilt — best heart mechanism, rejected on an absolute gate** [w2_c00]: 27 annotation types, exponential tilt (tau 0.03–0.40, odds [0.25,4], mass conserved) of real latest donors to each type's horizon-damped detection level; within-annotation matching on frozen coords keeps geometry identical. PROMISING: Δproxy +0.17 [+0.11,+0.23], z +5.2, n=8; heart +0.34 (variogram +4.76, mmd_u +1.99, neighborhood +1.90; de_direction −2.33; scale 0). Rejected: heart lower bound +0.22 <0.5; it reached only ~1/3 of predicted +0.5–1.0, and the top heart family P3R4_HEART_EXTRAP_E125_CXB_BULKO20/KBULKO30 uses per-type state transport (MorphTilt) [w2_c00]. Retry only stacked with a response-amplitude mechanism (de_direction −2.3; 4/5 gates open β 0.22–0.63, mag 0.58–1.28; Mab21l2 shut 0.001/−0.06) or an orthogonal heart move; alone saturates ~+0.3 [w2_c00].
- **Lineage-specific residual donor shift — best perturbation candidate, rejected once** [w0_c00]: zero-preserving latest-WT shifts toward earlier within-lineage states (≥30 cells/stage, exposure-bounded). PROMISING: Δproxy +1.97 [+1.57,+2.37], z +9.4, n=8; severity_slope +3.42 (Mab21l2 +4.36, late Hand2 +4.58), de_direction +0.80, mmd_u +0.65; all 5 gates open (Mab21l2 0.197/0.02/0.39), ratios 0.392/0.757. Rejected: Gata4 −0.67, null amplification +20–100% (median 1.20). Retry with exposure/detection gate → null median ~1.0, Gata4 ≥0 [w0_c00].
- **Earlier-support occupancy** [w3_c00]: +0.0086 raw 16³ Dice (3/5 positive; diagnostic +0.039). INCONCLUSIVE: no bound, sign unstable, too small for the geometry cost [w3_c00].
- **Untested geometry** [w3_c00]: native-footprint matching (stage-mix v6, t2-rpc-footprint-mid) and rigid/earlier-only transport; method evidence only, no local Δ.
- **Composition/lineage-share retry** [w1_c00]: parent shared floor (composition rollback + maturation-delay tilt + 0.65×WT interval) was not improved by per-gene signs; held-out-gene lineage-share version untested [w1_c00].

## Per-board state of the art and weakest metrics
- **embryo — seed 56.44** (unchanged donor law; candidate 49.36 after −7.08); proxy 185.84 [w3_c00]. Weakest: occupancy_dice 5.7 vs 100 (7.86 board/3.93 weighted before gate), d2_shape −45.38, neighborhood −10.05 [w3_c00].
- **heart — seed 53.08; best w2 53.17 board (detection-state tilt; paired Δheart +0.34), rejected** [w2_c00]. Weakest TEST: neighborhood 41.9 vs 70.0 (7.02 pts, 0.25), mmd_u 38.2 vs 69.3 (4.67, 0.15), variogram 51.9 vs 77.6 (2.57, 0.10); dev 53.0/53.1/53.4; occupancy gap 0.16 [w2_c00].
- **temporal — seed 69.11**, Δ0 in every change [w3_c00; w0_c00; w1_c00; w2_c00]; no program/profile.
- **perturbation — seed 61.97; best w0 63.92 (lineage residual shifts; +1.97), rejected (Gata4 −0.67, null amp)** [w0_c00]. w0 opens all 5 severity gates (Mab21l2 0.197/0.02/0.39) [w0_c00]; parent 4/5, Mab shut (0.001/−0.06) [w2_c00]. Weakest: severity_slope (11.2 gap), de_direction (5.9), de_score (5.3) [w1_c00; w0_c00].

## Method pitfalls (statistics, evaluation, reasoning traps)
- Aggregate gain hides per-gene loss: +1.97 proxy vs Gata4 −0.67; +0.19 mean specificity hid null amplification (median 1.20); pair aggregate tests with per-gene no-harm deltas and inspect distributions [w0_c00].
- Point predictions ~2× hot (+3.42 observed vs +4–8 predicted, official ~+2.1) [w0_c00].
- Disabled critics' verdicts are not evidence [w0_c00].
- Occupancy: paired scorer only; diagnostic +0.039 vs canonical +0.0086 (3/5) [w3_c00].
- 4/5 signature ≠ win: w3 shape checks hit, gain missed; w2 inverted de_direction (−2.33) [w3_c00; w2_c00].
- A state-distribution fix is not a response-amplitude fix: w2 moved variogram +4.76 but de_direction −2.33 [w2_c00].
- Significance ≠ acceptance: z +5.2, CI [+0.11,+0.23] failed +0.5 gate [w2_c00].
- Single-seed drop inside 8-seed spread (55.8–61.9) proved real (de_based −0.499) [w2_c00].
- n=1 noise understates; Δ0 with CI ±2.21 is a no-op [w3_c00; w1_c00].
- Preregister bounds (16³ +0.008; neighborhood ≤4); wide d2 pays 30–50+ (53.1) [w3_c00].
- No strength parameter/mechanical LOGO; derive tilt from held-out r; external delta 40.98 falsified, platform breaks signs, so use matched-WT pseudobulk [w3_c00; w1_c00].
- Diagnose stage carrier: 93% detection; reweight real donors [w2_c00].
- Dev–test gap can be state not shape (53.0/53.1/53.4 vs 41.9/38.2/51.9; occupancy 0.16) [w2_c00].
- Don't add board scores to paired Δ: heart seed 53.08 + paired Δ +0.34 ≠ w2 board 53.17; report both [w2_c00].

## Implementation pitfalls (crashes, helper quirks, contract)
- calibrate_response early return at kappa==1 skips residual; restructure [w0_c00].
- Pass split to quick_eval; default gata4_1 burns 1 of 3 runs [w0_c00].
- min(1,a/0.005) underdamps; RESID_EXPOSURE_FLOOR; null amp at doses 0.094/0.047 [w0_c00].
- Keep diagnostics under uns['response_calibration'] [w0_c00].
- n from context['n'] (3000 fallback); deformation=0.5 for donor parity [w3_c00].
- Embryo-only placement module; dispatch-check 4 boards [w3_c00].
- predict() no file access; frozen template constant + analysis/template_logo.json [w1_c00].
- "Three genes" = five KO conditions; pool Gata4_1/_2, Hand2_e8.25/e9.25; skip absent [w1_c00].
- Mab21l2 judgable (w0 gate 0.197/0.02/0.39) but shut in parent (0.001/−0.06) [w0_c00; w2_c00].
- No-op smoke test: gata4_1 60.77; β 0.307/R² 0.15/mag 0.92 [w1_c00].
- No p×odds draw(): resamples coords, occupancy 53.77→49.97, d2 48.51→50.33; compose on frozen coords + within-annotation matching [w2_c00].
- Position matching +2.3 after maximal coupling −3.3; skip patch sampling (MMD unchanged); clipped odds close 2/3 gap (43.2 vs 39.1) [w2_c00].

## Open questions
- Can an exposure/detection gate keep Δproxy +1.97, all five gates open, null median ~1.0 and Gata4 ≥0? [w0_c00]
- Can the heart tilt (+0.34; de_direction −2.33) stack with a response-amplitude mechanism to clear +0.5? [w2_c00]
- What moves temporal, which only ever scores Δ0? [w3_c00; w0_c00; w1_c00; w2_c00]
- Why do heart dev metrics stay 53.0/53.1/53.4 while test is 41.9/38.2/51.9? [w2_c00]
- Can rigid grafts or native-footprint matching beat +0.0086 embryo occupancy without losing d2_shape/neighborhood (patch matching collapsed d2 100→46.9) and preserve 91.5% later-to-later/32.9% native edges; is +0.008 at 16³ the right bar? [w3_c00]
- Does a held-out lineage-share tilt beat the seed, given the maturation-delay prior (r −0.17..−0.43)? [w1_c00]
- Would a larger platform-matched KO set including a non-TF reach LOGO ≥0.60? [w1_c00]
