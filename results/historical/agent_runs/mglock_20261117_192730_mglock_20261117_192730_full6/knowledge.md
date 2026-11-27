# Knowledge bank

## Established (held up; effect sizes and cycles)
- **Perturbation best, CONFIRMED: w0 maturation + breadth-scaled mass multiplier.** Δproxy +2.68 [+2.31,+3.06], z 13.4, n=8 (54.37→58.18; DE +3.58/dist +0.23/size 0); 5/5 gates (Gata4 .054/.11, .027/.03; Hand2 .16/.16, .098/.46; Mab21l2 .018/.14); specificity −0.00 [w0_c01]. Law: per-type p_delay×mass, d=min(1.5,2.25·frac_all), 0 prior-null.
- **Largest gain, CONFIRMED: two-arm real-cell KO donor.** Δ +7.07 [+6.60,+7.54], z 28.3, n=8 (50.69→57.80; DE +6.32/dist +0.79); 4/5 gates (Hand2 .206/.21, .186/.19; Mab21l2 .043/.05; Gata4_1 .079/.04 from R² −1.09; Gata4_2 .001/.01 shut); no-harm +0.84 [w2_c00]; unmatched sub-state R²<0, matched .04–.21. Different parent: do not compare or sum.
- **Composition overlays: sub-additive, gene-blind.** +4.71 [w0_c00]; exposure +2.92 [w1_c00]; mass×state +2.40 [+2.17,+2.63] to 55.99, DE +1.96 [w1_c01]; breadth mass×frozen w0 +2.685 [w0_c01]. Sum +7.63 vs +5.30 [w1_c01]; never sum arms.
- **Heart, CONFIRMED.** Chamber conditioning q=.05p+.95p(.|cardiac) when sampling=='heart_chambers': Δheart +3.28, Δproxy +1.64 [+1.58,+1.70], z 50.8, n=8 (54.88→71.11, occ 47.7→39.1) [w3_c00]. Frozen 11.3–12.7% mitotic swap at fixed coords: Δheart +1.04, Δproxy +0.52 [+0.49,+0.55], z 29.7, n=8; geometry 0.0; module −0.36 vs −3.62 [w3_c01].
- **Gates are law/gene/stage-specific; never pool.** 5/5 only w0_c01 [w0_c01]; 4/5 w2 [w2_c00]; w1_c01 Hand2 .195/.21, .083/.40, Mab21l2 .020, Gata4 .001 [w1_c01]; w0/w1 ≤.145 [w0_c00][w1_c00]. Gate≠specificity: all laws stay ≤−0.00 [w0_c01][w1_c01][w0_c00][w1_c00].

## Dead ends (and the condition under which a retry is justified)
- **No measured gene specificity.** Composition, maturation, product and multiplier laws leave specificity −0.01..0.00 [w0_c00][w1_c00][w1_c01][w0_c01] (w2 no-harm +0.84 the lone exception [w2_c00]), though w0_c01 opens both Gata4 gates. noharm.py maps only 'external'→identity; use the prior-aware probe [w0_c00][w1_c00][w2_c00]. Retry only with a gene-specific mmd/variogram/de_score arm or scorer null panel, not a retuned multiplier [w0_c01].
- **Native anatomy replacing transport.** −3.42 embryo, −1.71 proxy despite Dice .7882→.8235; d2_shape −30..−45 swamped +5.6; lineage-local maturation +5.6 unpaired [w4_c00]. Retry only on parent transport coords with a net-gain test.
- **Heart donor side-effects.** +3.28 headline but occ 47.7→39.1 [w3_c00]; 12% swap module −0.36 vs −3.62 (10x weak) [w3_c01]. Retry with larger/matched donors, pre-registered nbr gain, domain-restricted reference or >0.5 SD separation.
- **Temporal by side effect: 8 laws give Δ0.00** — maturation, exposure, both composition products, chamber conditioning, frozen swap, KO law, native anatomy [w0_c00][w1_c00][w1_c01][w0_c01][w2_c00][w3_c00][w3_c01][w4_c00]. Retry only with a temporal-targeted dose that moves slope .133 / R² .212 / mag .25 on one split [w4_c01].

## Promising / inconclusive leads
- **PORTABLE:** detection matching [w2_c00]; sampling conditioning [w3_c00]; bounded donor law [w1_c00]; scalar-moment maturation [w0_c00]; mass×state + zero-state ablation [w1_c01]; frozen-coord swap [w3_c01]; multiplier preserving the conditional law [w0_c01].
- **Untested; do not sum.** w2+w3 ≈+8.7 if independent but sub-additive [w1_c01][w2_c00][w3_c00]; w0_c01×w2, w3_c00×w3_c01 uncombined.
- **Both w2 arms needed.** Delay alone closes Mab21l2, cuts Hand2 e925 ~5; sub-state without matching R²<0 [w2_c00].
- **INCONCLUSIVE, under-dosed: lineage-specific temporal anchor calibration +0.01** (z 1.8, CI −0.0003..+0.0157, n=8; DE +0.006, rest flat). Only 2 lineages cleared the ≥30 late-anchor-cell gate (OFT-CM 40, Pericardium 107); anchor moved 0.021–0.026 log, diagnostic bit-identical; predicted +0.20 vs CI ±0.016 [w4_c01]. Retry with kappa≪1 or wider gate after one split's diagnostic shifts.

## Per-board state of the art and weakest metrics
- **Overall:** w0_c01 184.25; w2 183.88; w1_c01 182.06; w3_c01 179.25; w4 176.76 [w0_c01][w2_c00][w1_c01][w3_c01][w4_c00].
- **Perturbation 58.18** [w0_c01] (parent 54.37; w2 57.80; w1_c01 55.99); maturation + breadth mass [w0_c01]; alt w2 [w2_c00]. Weakest: specificity −0.00, Gata4_1 .054/.11 (mag .17), Gata4_2 .027/.03 (.13), Mab21l2 .018/.14 (.07), Hand2 mags .19–.42 [w0_c01]; alt w2 Gata4_2 .001/.01, de_score 45.1 [w2_c00].
- **Heart 57.33** [w3_c01]; split 71.11 [w3_c00]; two-embryo transport + 12% mitotic swap [w3_c01], chamber-conditioned donors at 5% mass [w3_c00]. Weakest: occ 39.1 (47.7) [w3_c00], TV .455, response .10 [w3_c00][w3_c01].
- **Embryo 81.15** [w4_c00]; two-embryo transport. Weakest: occ 60.53 (55.74), d2_shape −50.7, slope .605 [w4_c00].
- **Temporal 59.32** [w4_c00][w4_c01]; 8 laws Δ0.00, calibration +0.01 inconclusive. Weakest: slope .133, R² .212, mag .25; Ttn/Actc1/Myl7 sign-reversed (+0.03..+0.05 vs −0.61..−0.72) [w4_c01].

## Method pitfalls (statistics, evaluation, reasoning traps)
- **Per-board/gate:** 0.0 elsewhere = attribution but also scope — a temporal-only delta is temporal, not cross-board [w0_c01][w4_c01]; β>0 & R²>0.01 is weak (5/5 at specificity −0.00) [w0_c01]; β .001 + mags .31–.73 = magnitude without direction → underpowered, not failed [w4_c01]; pooled +0.52 is all heart (forecast +0.18..+0.23 vs −0.256) → widen bands [w3_c01].
- **Dose before seeds:** predicted +0.20, realized 0.021–0.026 log → unconfirmable at any n; compare expected shift to SE, require one split to move [w4_c01]; CI crossing zero (z 1.8, n=8) is inconclusive, unshipped dose leaves the claim unsupported not falsified [w4_c01].
- **Decomposition:** report DE/dist/size; direction reliable, magnitudes loose (w3 +4..10 vs +21; w0 +1..3 vs +4.71; w4 +0.20 vs ±0.016) [w0_c00][w1_c00][w2_c00][w3_c00][w3_c01][w4_c01]; halve spatial gains on proxy; budget the dominant term (d2 −30..−45 swamped +5.6); never infer net gain from n=1 (n=8 ±0.47) [w4_c00][w2_c00].
- **Non-detecting = low-depth:** no per-type matching → global offset, R²<0; report β/R²/mag per split (4/5 hid Gata4_2, mags .16–.42) [w2_c00]; negative R² isn't rescue [w0_c00][w1_c00][w2_c00].
- **Diagnostic≠scorer:** Dice .8235 vs .7882, occ 55.74→60.53 [w4_c00]; heart headline↑ but occ↓ [w3_c00]; acceptance = paired test + invariants + pre-registration + zero-state ablation + bit-identical untouched splits [w4_c00][w3_c00][w1_c00][w2_c00][w0_c01].
- **Nulls/review:** prior-null only with expression_prior (else noharm.py fallback, ~0.28 floor); d=0≡m=1 is verification, zero-state ablation needs the same sampler (Mab21l2 β 3.9x, Hand2 1.36x) [w0_c01][w1_c01]; w4_c01: critics disabled, ablation unrun → unreviewed, leakage assumed [w4_c01].

## Implementation pitfalls (crashes, helper quirks, contract)
- quick_eval.py cap .quick_eval_runs 3; then diagnose.py --score (1 seed) or run_split→predict→contract [w1_c01][w0_c01]; screen rejects literal `harness` [w3_c00].
- noharm.py only 'external'→identity; supply expression_prior, keep prior-aware checks external [w1_c00][w2_c00][w1_c01][w0_c01].
- Alignment: intersect symbols, ≥20 columns; array_equal on whole var_names breaks across panels [w0_c01].
- Mass multiplier: clip ratio [0.25,4], exponentiate, clip mass [0.25,4], cap d 1.5, d=0 prior-null, else broad genes run away [w0_c01]; w2 delay uses frac_all, min(1.5,2.25*frac_all) after the product [w2_c00].
- Resampling: largest-remainder counts, one inverse-CDF draw/type; donor sort (detected,row), u=(arange(k)+rng(seed).random())/k; obs_names pred_<i>; 6000 cells not 3000 (0.2763 floor) [w1_c01][w2_c00][w0_c01].
- Off-panel KO (Ctnnb1, frac_all .666) → uniform_offpanel sub-state, delay only d=1.5 [w2_c00].
- New uns must survive h5ad read-back; per-type LS+bisection 1.3–6.9 s/split [w1_c01].
- Frozen swap: coord_max_abs_diff 0.0; expression verbatim; annotation/patch 0.0, mass tol 7e-18; replacement .113–.127 vs TV .119–.136 [w3_c01].
- 64-cell patches straddle 15-NN niches (.43–.49 SD); 25–30 s/heart split [w3_c01].
- Ridge: λ[g]=kappa·mean_t C², kappa=1 pulls G_local≈G_pooled (near-off hidden by clip [0.25,4]); dose stacks with horizon fraction and ±0.5 clip — measure post-clip; ≥30 late-anchor filter silently drops 6/8 lineages; one quick_eval (369 s CPU) + one diagnose ≠ go/no-go [w4_c01].

## Open questions
- **Temporal 59.32:** what moves it? 8 laws Δ0.00; calibration +0.01 (CI ~0), 2/8 lineages ≥30 cells [w1_c00][w2_c00][w3_c00][w3_c01][w1_c01][w4_c01]. Retry with kappa≪1 or wider gate, diagnostic shift first.
- **Specificity/composition:** any law above +0.00 holding 5/5 gates (needs scorer null panel)? Do w0_c01 and w2_c00 compose? [w0_c01][w2_c00][w1_c01]
- Do w3_c00+w3_c01 compose, survive w2's KO law, localise finer than 64-cell patches with >0.5 SD separation? [w3_c00][w3_c01][w2_c00]
- Why late-Hand2 R² .40 vs early .21, yet w0 peaked E9.25 and w1 E8.25? [w0_c00][w1_c00][w1_c01]
- Can heart-style conditioning recover embryo composition (TV .276; missing Caudal Epiblast, Primitive Streak, SOM)? [w4_c00][w3_c00]
