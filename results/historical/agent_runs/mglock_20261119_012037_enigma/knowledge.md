# Knowledge bank

## Established (held up; effect sizes and cycles)
- **WT-donor delay — CONFIRMED twice.** Δpert +0.66 [+0.40,+0.92] (z 4.8, n=8), de_based +0.64, severity +3.0, 5/7 gates [w0_c04,w0_c07].
- **Draw ordering — CONFIRMED on one parent, not portable.** Detection-quartile→maturation +0.80 [+0.58,+1.02] (z 6.9, n=8), de_based +0.21 [w1_c11]; best-of-8 −0.23 [w1_c13]; seed parent −0.03 [w1_c14].
- **Temporal bounded transport — CONFIRMED; cap binds.** κ=clip(0.8·||d_obs||·h/||d_pred||,1,2.5), log clip ≤0.6: +1.76 [+1.33,+2.20] (z 7.7, n=8), 69.11→70.89, mmd_u +2.1/variogram +9.3, de_based −0.71 [w3_c02]; release 4.0 −0.72 [w3_c04].
- **Temporal trend gating — CONFIRMED; temporal SOTA.** Shrink the boost where released and Qiu within-lineage trends disagree in sign: +1.84 [+1.43,+2.25] (z 8.5, n=8), board 70.94, mmd_u +2.4/variogram +8.8, de_score −2.2 (de_based −0.66), others 0.0; paired w3_c02 ablation untested [w3_c05].
- **Calibration is board-dependent.** Temporal +1.76 [w3_c02]; heart 0.25× −0.28 [w2_c01]; perturbation +0.08…−1.45 [w0_c01–c03,c05]; none (0.215×) −6.91 [w1_c07].
- **Source identity beats tilt; gene-blind dose saturates.** Slots +0.09→+0.26→+0.26→+0.52 across 1–12% [w0_c10,w1_c08,w0_c11,w1_c10]; 8–12% costs hand2 −3.03, specificity −0.03 [w1_c10]; routed +0.21 but direction rejected [w1_c03].

## Dead ends (and the condition under which a retry is justified)
- **Resampling/tilt — NEGATIVE.** Temporal donor resample −0.25 [−0.41,−0.10] (n=3) [w3_c03]; Geneformer tilt −0.32, de_direction −0.7 [w0_c08]; WT scoring −0.96 (z −3.6, n=3) [w0_c18]. Retry if per-label gating + residual SD ≫0.06–0.08.
- **Earlier-bracket embryo — NEGATIVE.** −4.01 (embryo −8.02, d2_shape −44.7) [w3_c00]; exact-donor −3.15 (embryo −6.31, d2_shape −53.4, occupancy +2.0) [w3_c01]. Retry if d2_shape cost < occupancy gain.
- **Lineage re-allocation ×4 — NEGATIVE.** −0.12…−1.45 (de_based −0.54…−1.33, 8/8 on two arms) [w0_c02,c03,c05,c16]; blind control recovered Hand2/Mef2c, so weighting is the cost. Retry ablated only: open gate, seed DE, beat blind ≥3/4, no gene >−0.30 [w0_c16].
- **Composition swaps ×5 — NEGATIVE/INCONCLUSIVE.** −0.36…−6.91, de_based −6.67; worst drops calibration (0.215×) [w1_c01,c07,c09,c15,c16]. Retry c01/c07 with calibration; c09 at ≥0.005 TV on 2 genes; c15/c16 after TV/DE moves.
- **Heart edits — NEGATIVE; variants ≤0.** c01–c10 0→−0.87 (c10 −0.19 INCONCLUSIVE) [w2_c01–c10]; c11 low-rank whole-profile −0.03, de_based −0.054, dist +0.019; mechanism fired (+0.26…0.29 sd, 11.1%) but nbr/mmd ~0 [w2_c11]. Retry only after TVD 0.444 falls or an exercising assay validates direction.
- **Temporal cap release — NEGATIVE.** −0.72 (z −7.1, n=3), mmd_u −1.4/variogram −2.8 [w3_c04]. Retry if clip_frac saturates or a covariance map reaches |d_obs|.

## Promising / inconclusive leads
- **Heart within-type offset — PROMISING, ceiling.** +0.06 (heart +0.11); offset-only de_direction +1.55 [w2_c00]. Extensions ≤0: −0.38/0.00/−0.02 [w2_c07–c09]; −0.19 [w2_c10]; −0.03 [w2_c11].
- **Earlier-WT slots — PROMISING, dose-limited.** +0.26 at ≤10% [w1_c08,w0_c11]; +0.52 at 8–12% but hand2 −3.03 [w1_c10]; 12% +0.13 [w0_c12]; post-cal +0.03 [w0_c14]; anchor +0.02 [w0_c15].
- **Post-hoc delay closure — INCONCLUSIVE, delivery-limited.** +0.13 [−0.05,+0.31] [w1_c04]; −0.05 [−0.23,+0.13], 0.068/0.207 delivered [w0_c17]; −0.12 [w0_c02]. Retry with detection-weighted dosing ≥0.15.
- **Composition/draw-variance — INCONCLUSIVE.** T3 −1.58…+0.10, cross-lineage −0.35, weight cap +0.23, draw levers −0.23…+0.23; CIs span 0 [w1_c00,c02,c05,c06,w0_c06,c13,w1_c13,c14].

## Per-board state of the art and weakest metrics
| Board | Best program | Score | Mechanisms | Weakest metrics |
|---|---|---|---|---|
| temporal | **w3_c05 gating** | **70.94** | κ 2.5 + trend shrink [w3_c02,c05] | mmd_u 65.8/82.6; de_score −2.2; de_direction −0.65 [w3_c02,c05] |
| heart | seed | 53.08 | offset +0.11 [w2_c00]; edits ≤0 [w2_c01–c08] | nbr 41.9/72.5; mmd_u 38.2/71.9; TVD 0.444 [w2_c09,c11] |
| embryo | seed | 56.44 | smoothed transport [w3_c00] | occupancy 5.7/100; variogram 19.5; d2_shape −44.7/−53.4 [w3_c01] |
| perturbation | **w0_c04/w0_c07** | **62.22** | delay; quotas; frozen cal [w0_c04,c07] | de_direction 5.92; severity 11.23 (value edits −1.5 [w0_c17]); Mef2c R² −0.13/−0.03 [w0_c10,w1_c15] |

## Method pitfalls (statistics, evaluation, reasoning traps)
- **Screens overstate; require +0.30.** quick_eval 6× (+11.5 vs +1.76) [w3_c02]; single-seed +1.85 vs paired −0.19 [w2_c07]; +0.09–0.26 below margin [w0_c10,w1_c08,w0_c11]; hand2 −3.03 kills +0.52 [w1_c10]; pooled +0.21 hid Gata4 −1.04 [w1_c12].
- **Power and pre-registration.** n=8 resolves |Δ|≥0.96; +0.5–0.8 needs 12–30 pairs [w1_c14]; n=3 decisive only for tight same-sign diffs [w2_c11]; c15 −0.89 [−2.18,+0.39] INCONCLUSIVE [w1_c15]; +1.84 landed in +1.3–2.2 with 3/3 signature [w3_c05].
- **Direction persistence binds; signature is only a check.** Misdirected shift (cosine −0.32 vs E8.75) paid de_based −0.262/de_direction −1.0, no mmd gain [w2_c07]; 11.23-pt severity gap delivered −1.3 [w0_c11].
- **Probe the realised lever.** rho 0.341 requested vs 0.07–0.14 delivered [w0_c09,c13]; zero-preserving shifts diluted to 0.068/0.207 [w0_c17].
- **Activation ≠ benefit; gene-blind control decides.** 7.2%/4.5% moved at <1% mismatch, 8/8 diffs negative; control recovered Hand2/Mef2c loss [w0_c16]. Quota TV 0.006–0.008 on 2/3 active genes; masked TV 0.175; sub-floor genes are absent activation [w1_c15].
- **Surrogates decouple; unexercised falsifiers vacuous.** Heart −0.16/−0.02 [w2_c02,c03]; 5/7 gates, 0/5 metrics, −1.45 [w1_c09]; active route left TV 0.175 before de_based −0.89 [w1_c15]; c11's Feulner assay never ran the operator (missing spatial_3D), so its pass was uninformative [w2_c11].
- **Paired ablation and exact-seed discipline.** Reserve a quick_eval slot for the paired ablation [w3_c05]; unpaired cross-line references are not evidence and the paired w3_c02 ablation was never run [w3_c05]; label 3-seed metric columns vs scoring seed 101 [w3_c05]; de costs forecast conservatively (−2.25…−3.3 vs 0.9–1.9 predicted, pooled −0.66) [w3_c05].

## Implementation pitfalls (crashes, helper quirks, contract)
- **predict co-locates donor with position; realise() latest-WT only.** Post-hoc repair breaks co-adaptation [w2_c05]; earlier states need concat + obs/source_row/spatial_3D [w0_c11].
- **noharm abstain ≠ empty.** a_all<0.015 or <40 earlier cells → s_l=0 [w1_c01,c06]; pin a_all<FLAT_A_FLOOR [w0_c13]; nulls <0.025 pass trivially; require ≥30 WT cells + L_l>0 [w0_c16].
- **Caps bind.** Clip 0.35κ_max; κ=1 on bad interval/<30 cells [w3_c02]; KAPPA_MAX 6 [w0_c08,c09]; KAPPA_MAX=4 leaves capped genes bit-identical [w0_c15]; freeze rho .3451, gata4 .980, response .65×, blind_fill [w0_c04,c07,w1_c10].
- **Whole-profile replacement and stage drift.** p95 ≤0.15 zeroes dose (native depth spread ~0.47 log units); use mean signed log-depth change ≤0.10 [w2_c11]. Stage labels drift: use class-level fallback [w2_c11]. plan_local_state silently returns parent without obsm['spatial_3D']; assert the mechanism fired [w2_c11].
- **Eval harness/budget.** 3 quick_eval runs shared: reserve one for the paired ablation; killed run plus confirmations exhausted the budget [w3_c05]. Same-seed parent first; an unrun control left the falsifier unevaluable [w0_c17]. 1 prediction/call [w1_c05,w2_c04,w1_c07,w3_c03]; critics disabled → vacuous 'go'/'pass' [w0_c15,w2_c10].
- **Temporal AnchorFlow.** Drop the temporary ext copy (181k atlas cells) after group slices, or mask exceeds memory [w3_c05]; discord_masks shipped once per group, not per label [w3_c05]; plausibility held by construction (S0 ±0.35, S1 ±0.60) [w3_c05].
- **Labels/contract.** Class-level CM/Endo pseudobulk; feulner_forecast expression-only [w2_c10]. 7449 rows + spatial_3D; <50 symbols identity; only perturbation reads WT-neighbour [w1_c05]; earlier rows real, unmeasured zeroed [w1_c10]; plan_shift None at h=0/dt=0/<30 cells; per-entry clip [w2_c07]; heart via predict_heart/uns; abstain on degenerate geometry [w2_c10].

## Open questions
- **Perturbation:** close the 11.23-pt severity gap [w0_c11–c17]? Does c11 ordering stack with +0.52 fill [w1_c10]?
- **Temporal:** recover de_score/de_direction (−2.2/−0.65) without losing mmd/var [w3_c02,c03]? Does gating retain the w3_c02 benchmark in a paired ablation [w3_c05]? Reach |d_obs| without cap release [w3_c04]?
- **Heart:** is +0.11 the ceiling [w2_c00]? Would held-out direction + realised dose rescue it [w2_c07]?
- **Embryo/composition:** occupancy worth d2_shape (5.7 vs 100) [w3_c00,c01]? Additive post-calibration [w1_c01,c07,c09]?
