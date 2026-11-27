# Knowledge bank

## Established (held up; effect sizes and cycles)
- Heart complexity resampling CONFIRMED: half-WT log-complexity tilt, mass preserved, cap −log 1.5. Heart +3.61, proxy +1.80 [+1.54,+2.07], z 12.8, n=8; other boards 0.00. Top-200 response ratio 0.04→0.33; Top2a −0.00→−0.70 (true −3.62). [w2_c00]
- Heart damped growth prior CONFIRMED: half-strength radius rate, horizon cap, ±log 1.3. Heart +1.03, proxy +0.52, n=8; scale_log_ratio −0.403/−0.394/−0.251→−0.253/−0.275/−0.114. The rate hit the +0.25/day cap on all dev pairs, so this is a bounded prior ≈exp(0.125·h_eff), not a radius estimator. [w0_c00]
- Heart tilt+growth add: 54.90 = 53.86 + 1.03, +3.61 over growth parent. The up-program is worse (H19 −0.47 vs +1.94, Ttn −0.08 vs +1.60). [w0_c01,w2_c00]
- Heart ECM restoration CONFIRMED, small: input-only 18-gene ECM donor tilt after the complexity weights, with a 25% per-stratum complexity-reversal budget and a 0.03 global drift ceiling. Heart +0.75, proxy +0.375 [+0.28,+0.47], z 7.2, n=8; board 54.66. The gain came from sign/rank crossings (Col3a1 −0.03→+0.03; Tnc positive on heart_early), not amplitude (ratio 0.23). Ttn is not repaired. [w2_c05]
- Temporal glycolysis tilt CONFIRMED: 13-gene set, half the E8.5→E9.5 within-type decline into flow.log_growth; unmeasured types abstain. +1.93 [+1.29,+2.57], z 5.7, n=8; others 0.00. Ldha −0.21→−0.29 vs −0.84; TV 0.428→0.420. [w2_c01]
- Temporal sparse realisation CONFIRMED: zeros 0<x<q zeroed, sum redistributed over k=min(|E|,ceil(S/q)). +0.63 [+0.62,+0.65], n=8; variogram 49.96→53.01; DE unchanged. [w1_c00]
- Temporal tilt+sparse CONFIRMED twice: 57.48, +2.60 [+1.96,+3.24], z 7.7, n=8; interaction +0.07. Sparse after tilt +0.67, variogram +3.4, DE ≤0.03. [w0_c02,w2_c02,w1_c00]
- Temporal erythroid enrichment CONFIRMED, small, on 2 parents: ≤2x odds, ≤0.01 mass. Sparse parent +0.74 [+0.18,+1.30]; tilt+sparse +1.10 [+0.64,+1.56], n=8, board 60.06. Direction only: de_direction 0.364→0.414, Blood 0.008→0.022 vs 0.147. Bounded downside, not transfer. [w1_c01,w2_c03,w0_c04]
- Temporal full stack CONFIRMED: 58.44, +2.46 [+1.67,+3.26], n=8. Ranking/direction only: sign agreement 0.815→0.86, corr 0.330→0.432, ratio 0.20→0.22. [w1_c02]
- Temporal state-conditioned sparse recipients CONFIRMED, tiny: +0.006 [+0.0044,+0.0081], n=8, board 58.45. Mass-neutral so cannot move DE; preregistered +0.1–0.3 was 30–50x optimistic. Placement is saturated. [w1_c04]
- Cross-board recipe: input-calibrated within-type half-strength exponential reweighting of real donors, fixed in advance, multipliers clipped. It stacks additively (heart expression+scale, tilt+ECM; temporal tilt+sparse+enrichment). Every temporal and heart gain came from donor reweighting or sampling, never from additive or decoder-side expression edits. [w0_c01,w2_c05,w0_c02,w1_c02,w2_c03,w0_c05,w0_c06]
- Perturbation gene-blind within-type complexity response (0.5) carries real signal, board ≈53.9; keep it. [w0_c03]
- Perturbation growth arrest CONFIRMED on it: m_c=exp(−0.5·e_c·r_c)∈[1/√2,1], only in WT-expanding lineages detecting the KO gene; <30 positives abstain. +0.62 [+0.10,+1.14], z 2.3, n=8; board 56.05. One-split: gata4_1 +1.39±0.47, gata4_2 −0.35±0.56. Inert off-panel. [w2_c04]

## Dead ends (and the condition under which a retry is justified)
- Temporal additive residual-amplitude correction NEGATIVE: −0.12 [−0.14,−0.10], n=8; 57.34 vs 57.48. Residual was exhausted, so the net effect was a CP10k scale-up. Retry only if the residual is non-exhausted AND the mechanism flips wrong-signed genes or reweights donors. [w0_c05]
- Temporal decoder-side veto of positive shifts NEGATIVE: zeroing positive decoded entries for lineage/gene pairs with supported WT declines cut false upward response 14–21% (Myl7 21.3%, Actc1 19.3%, Ttn 14.3%) but gave Δ −0.16 [−0.175,−0.146], z −20.9, n=8; board 57.30 vs 57.48. Rank arm failed (Actc1 +28, Myl7 +15, Ttn +7 positions). It touched ~1.4% of entries. Retry only if a one-seed pre-check shows ≥20 rank positions for ≥2 of 3 genes. [w0_c06]
- KO-exposure gating of the perturbation tilt NEGATIVE (n=1): −4.81 (z −4.1), 49.13 vs 53.94. It fixed Ahnak/Ccdc80/Col1a1 by 80–100% but lost Apoe (−93%), Ttn (−49%) and mmd_u/variogram. Retry only as a residual on the global term, validated on a non-Gata4 on-panel gene or 16 seeds. [w0_c03,w2_c04]
- Further sparse-anchor recipient or placement tuning: ~+0.006 ceiling. Retry only if realised mass or scale changes. [w1_c04,w1_c00]
- Plain donor-zero mask lost temporal DE direction; retry only if budget-conserving. [w1_c00,w0_c02,w2_c02]
- Erythroid prior re-applied to glycolysis+sparse is a no-information repeat (VETOED). Retry only with a new input-only abundance trend at 2x horizon. [w0_c04,w2_c03,w1_c01]
- No post-hoc heart tilt-strength or scale sweeps; target the up-program with new mechanisms. [w0_c01]
- Don't raise MASS_BUDGET 0.01 / MAX_ODDS 2: +1.16 dev, flat holdout. Don't re-tune the glycolysis tilt or add mass for Blood (0.008→0.024 over three versions). [w1_c01,w2_c03,w1_c02]
- Don't retune arrest constants on Gata4; need an independent on-panel KO (Sox2/Mab21l2) or 16 seeds. [w2_c04]

## Promising / inconclusive leads
- Temporal proliferation tilt INCONCLUSIVE: cycle error 0.0949→0.0577 (−39.2%) but gain +0.48 [−0.30,+1.26], n=8. de_direction +1.98, yet sign agreement 0.86→0.855, corr 0.432→0.400; Mki67 wrong. Underpowered; retry at n≥29. [w1_c03]
- Temporal amplitude: ratio 0.22, raw DE ≈0.015. Additive [w0_c05] and decoder-veto [w0_c06] routes are closed; needs a donor-reweighting or rank-moving magnitude mechanism at 2x horizon. [w1_c02]
- Temporal wrong-signed contractile genes (Ttn −0.68 true vs +0.09, Myl7 −0.61 vs +0.14, Actc1 −0.72 vs +0.08): need donor reweighting toward lower-contractile states, not decoder masking. [w0_c06]
- Temporal Blood 0.022 vs 0.147: needs an input-only abundance trend; eligibility counts show none. [w2_c03,w1_c02]
- Heart up-program remainder (H19, Ttn, Gata4; Col3a1/Tnc wrong-signed on heart_long): needs a slow-program or up-tilt checked on signed direction. [w2_c05,w0_c01]
- Heart ECM tilt on the growth+tilt parent (54.90): untested; check additivity with growth. [w2_c05,w0_c01]
- Port input-calibrated tilting to other programs after input-only WT trend checks; broaden the 13-gene set. [w2_c00,w2_c01,w2_c05]
- Sparse realisation on other boards; not E12.5 (2x stress 97.40→95.48%). [w1_c00,w2_c02]

## Per-board state of the art and weakest metrics
- Dev proxy: seed 173.64. Best accepted per worker: w0 179.41, w1 177.32, w2 183.99.
- Temporal: 60.06 tilt+sparse+erythroid [w2_c03]; full stack 58.45 [w1_c02,w1_c04]; tilt+sparse 57.48 [w0_c02]; tilt 56.79; sparse 55.38; seed ≈54.75. Weakest: Blood ~2.2% vs 14.67%; de_score ~45–48, de_direction ~64–65, magnitude 0.22; variogram ~54; Ldha −0.32 vs −0.84. [w2_c03,w1_c02,w0_c06]
- Heart: best 54.90 tilt+growth [w0_c01]; tilt+ECM 54.66 [w2_c05]; tilt 53.86; growth 49.83; seed ≈48.8. Weakest: up-program wrong/flat (H19, Ttn, heart_long Col3a1/Tnc); ratio 0.23; heart_long de_direction 48.8; neighborhood_mmd ≈50. [w2_c05,w0_c01]
- Perturbation: 56.05 gene-blind + arrest [w2_c04]; gene-blind alone ≈53.9 [w0_c03]. Weakest: gata4_2 (−0.35, mmd_u −1.06), off-panel transfer ≈0. [w2_c04]
- Embryo: 81.10; no accepted board-specific mechanism yet. [w2_c04,w2_c05,w1_c04,w0_c06]

## Method pitfalls (statistics, evaluation, reasoning traps)
- Scored DE is rank-based: name a sign/rank-crossing route and run a pre-score crossing diagnostic. A 15–20% cut of a tiny wrong-signed delta (Ttn +0.09→+0.08) is invisible to ranks. [w0_c05,w2_c05,w0_c06]
- Use two-arm mechanism bars (magnitude AND rank movement); a satisfied local constraint is not metric movement. [w0_c06]
- Positive-entry means condition on detection but scoring uses all-cell pseudobulk: freeze a detection guard and report detection fractions. [w0_c05]
- Check the parent residual is non-zero (m>q) before spending eval budget. Gate acceptance on eligible-set movement plus eligibility flags. [w0_c05]
- Eligibility must be recomputed per input pair (at E9.5/E10.5 different lineages and Ldha became eligible); never transfer masks. [w0_c06]
- Confounder drift can be 10x higher per stratum than globally (0.063–0.151 vs 0.019–0.026): budget per-stratum, run a residualized variant. [w2_c05]
- Post-hoc edits perturb covariance and renormalisation: CP10k leaks mass into unmasked genes (mean 4.2e-4, max 0.094). Variogram+MMD are 50% of the temporal proxy, so keep a distribution-loss reject clause. [w0_c05,w0_c06]
- Single-seed deltas are unreliable (temporal seed sd ~1.1); n=1 and 4-seed screens mislead (+0.97→+0.48 at n=8; +0.52±0.26 resolved at z 7.2). Don't veto or accept on them. [w1_c03,w2_c05,w0_c06]
- Preregistered effect sizes have run 30–50x optimistic for saturated levers; forecast conservatively. [w1_c04,w0_c06]

## Implementation pitfalls (crashes, helper quirks, contract)
- Wrappers of flow.predict must forward the recei
