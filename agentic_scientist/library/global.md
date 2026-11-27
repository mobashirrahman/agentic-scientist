# Knowledge bank

> **READ FIRST.** The previous seed's TEST result contradicts several records below. The section "TEST result
> of the previous seed" in `lessons.md` OVERRIDES them: T1 lineage-trend / cushion-transfer composition growth is
> test-negative (6% cardiomyocytes, mmd_u 66); heart detached-row relocation kept 21% 'Peri' and the organ pattern missed
> the epicardium; the embryo "one native unstretched embryo" geometry scored occupancy 3.7 (use midpoint geometry per
> native axis); the T3 "d230 = 0.23 day" reading scored mmd_u 56.5 (the delay reaches stages earlier than the brackets).


Note: the section list and size limit in the curator prompt arrived as unfilled placeholders, so I chose the sections below. Cycle ids `[wX_cNN]` are from run runA. Ids prefixed `[v2/…]` are from runB. Records are n=8 paired seed pairs unless stated. Smoke no-ops (Δ=0.00, all boards) show the harness is deterministic and adds no spurious variance.

## Evidence rules and how to read records
- Held-out lessons are authoritative. Dev gains that did not transfer (pilot4ab) are overfitting, not established mechanisms. In that run w0_c03 gained +22.6 on dev but scored 159.2 on holdout vs seed 163.7.
- Rejections for veto, misrepresentation or compliance (the code did not do what the hypothesis claimed) are NOT evidence against the mechanism. Many PROMISING records below are mechanisms that work and were rejected for code or rule defects. Fix the defect, don't abandon the idea.
- Dev-proxy gains on label-filtered dissection proxies over-predict the test about 2× [w1_c04]. Single-seed dev gains often flip over repeated seeds [w1_c09 +0.89→−0.15; w3_c14 +2.42→−3.99].
- All of DE ranking (de_score, de_direction) is invariant under per-gene monotone transforms of Δp. Mixture-weight or amplitude changes cannot move it [w2_c08].

## Per-board state of the art

### T1 temporal (accepted stack is real-cell donor selection plus bounded pseudobulk shift)
- Accepted chain: 3-lineage composition and maturity selection [w0_c00 +1.35]. Half-step unbalanced-OT donor reweighting [w0_c02 +0.75]. Bounded myo→endocardial cushion transfer, FILL 0.5, mass-conserving [w0_c03 +1.85; w0_c06 +1.85, cap 4 pts]. CP10k-log trend continuation [w0_c08 +0.91]. Late-anchor Qiu pseudobulk step [w0_c09 +1.49]. Prevalence-calibrated step clip(d/p, ±0.35) [w0_c10 +0.90; realised shift norm 1.54→2.38, now bound by the 0.35 cap].
- Run #2's seed bakes in the Qiu late-anchor continuation (at 5,000 rows).
- Best dev temporal is about 59.3 [w0_c10]. The cushion dose-response is monotone (53.35/54.99/56.11 at FILL 0/0.5/1.0), so the ceiling is the one-interval bounding rule, not saturation [w0_c03].
- Weakest: MMD/variogram attribution is unverified (only aggregate T1 is reported), and DE gain is capped by the 0.35 log cap.
- PROMISING but vetoed:
  - Full-interval cushion transfer [w0_c01 +3.15]. It applied 2× the claimed log change and breached the 10% cap.
  - Maturity tilt plus cushion on the OT parent [w0_c05 +2.39]. An undeclared log(2) clip applied +0.35 instead of +0.84.
  - Both are likely real gains. Re-race them with an honest dose.

### Heart
- Accepted chain, all heart-only:
  - Organ-resident rim [w1_c01 +0.72].
  - Organ-resident labelled population [w1_c04 +1.67; test gain ≈ half the dev proxy].
  - Detection-depth thinning [w1_c10 +2.39; w1_c11 +2.56 on the organ-resident parent].
  - Saturating depth continuation [w1_c14 +1.33].
  - Constant-density growth anchored to organ RMS [w1_c07 +1.24].
  - Radius-capped growth [w1_c15 +0.62].
  - Relocating detached vessel/pericardial rows [w1_c16 +1.04].
- final_v2 added bounded fetal maturation: cube-root count growth plus a damped Feulner offset plus compartment transfer, heart dev 67.64→68.51 [v2/w1_c02, +0.86 board]. 73% of that gain is size. The Slide-seq local-contrast edit added 0.00.
- Weakest: expression metrics (mmd_u, variogram, de_score). The pseudobulk offset gives only a small gain, almost all on heart_long_organ [v2/w1_c00 +0.21 board, PROMISING; w1_c00 +0.10 INCONCLUSIVE].
- Cautions:
  - Holdout showed that trend extrapolation of a cell-type program overshoots at later stages or longer horizons (heart E10.5 −7.3 on holdout). Keep growth and extrapolation damped, input-derived and capped, and validate on heart_long.
  - Growth bounds fitted to the dev target (MAX_INTERVALS=3, 0.55/day) overshoot on the real test [w1_c13, w1_c02]. Derive them from the inputs.
  - Components do not always compose on a combined parent [w1_c09 −0.15].
  - Input-derived organ-share growth fails when the last input is already a dissected heart (share saturates at ~1) [w1_c05].

### Embryo (T2)
- Accepted chain on the native scaffold:
  - Time-weighted real-cell mixing [w2_c00 +2.56 board]. In final_v2 the elapsed-time weight STATE_WARP 0.7→1.0 alone gave +3.58 [v2/w2_c00, dev board 70.36→74.11]. Always measure the donor share from the scaffold side and mirror it when the later bracket is the scaffold [w2_c05 veto, w2_c08, w2_c11].
  - Binomial depth thinning of deep donors to the interpolated depth, with exact passthrough when inactive [w2_c02 +7.73; w2_c06 +5.47].
  - Constant-packing-density radius law, rms ∝ n^(1/3) from the nearer bracket (scale skill 40.8→~100) [w2_c08 +2.16; w2_c11 +2.48]. Nearer-bracket-anchored, damped, capped size [v2/w2_c02, +4.09 board, but ~3.75 of it is the bundled mixing; the size law alone is ≈+0.3–0.7].
  - CP10k-log median-centred midpoint pseudobulk calibration [w2_c12 +0.75; w2_c13 +2.58; w2_c21 +2.95; w2_c16 +3.35]. The mean correction carries the gain and the spread warp is near-neutral (+0.02).
  - Complementary donor selection [w2_c24 +0.84].
- Best dev embryo is about 74.8 [v2/w2_c02].
- Run #1's embryo chain overfitted embryo_early: E6.75 is 4.6× shallower than E8.0, shape metrics were turned off, and the radius-collapse and aggressive-thinning steps hurt later depth-matched stages. Run #2 restored the clean native scaffold and added guard_embryo_e80. Treat gains from that chain with caution.
- Weakest: de_score and de_direction (gastrulation-midpoint sign reversals are weight-invariant), neighborhood_mmd, and variogram on embryo_early.
- PROMISING but not promoted:
  - Depth-damped gene-specific pseudobulk calibration [v2/w2_c03 +0.72; vetoed because it broke its strict no-op at bracket endpoints].
  - Maturity tilt of donors [w2_c19 +0.9; the sign was float noise, so anchor the orientation by construction].
  - Gene-specific retention [w2_c18, w2_c20 +0.35 board; the lower bound is below the +0.5 bar].

### T3 perturbation
- Core confirmed mechanism: model a broad, non-DNA-binding signalling knockout as the WT ~0.23 d earlier, mixing in real earlier-stage WT cells, gated by GO breadth from context['external']. It was reproduced four or more times [w3_c00 and w3_c04 +2.11, w3_c06 and w3_c07 +2.13 CONFIRMED]. Mef2c E8.5 gained ~+16. On a diverse parent the gain is +3.8 to +4.5 [w3_c11 CONFIRMED, w3_c08].
- The single-normalised GO-module mixer for narrow modules opens the Mab21l2 severity fit [w3_c09 +1.65 CONFIRMED; w3_c11; w3_c16, w3_c17, w3_c22 ≈ +2.4 PROMISING]. It fires on Ctnnb1 and Mab21l2 and leaves Gata4, Hand2 and Mef2c untouched.
- Weakest: Mab21l2 E9.5 severity (β≈0.001, R²<0) and de_based. Severity is direction-limited, not amplitude-limited once the magnitude ratio is ≥~0.7 [w3_c15].
- Run #1 gains came from Gata4 and Mef2c dev splits. Per the holdout, the lineage-rollback gains were Gata4-specific overfitting and any T3 change must be gene-agnostic.
- Repeated rejections of the otherwise-good delay mixer were compliance or defect failures (the identical +2.11/+2.13 delta reproduced across them):
  - breadth read from expression_prior rather than external [w3_c00, w3_c04, w3_c12, w3_c16, w3_c17];
  - a dev-calibrated 0.65 interval ratio;
  - a TypeError fallback [w3_c06];
  - double normalisation that inflated the Ctnnb1 weight 6.2× [w3_c08];
  - gene-blind responses that broke the gata4 guard [w3_c02, w3_c22].
- Headroom: context['gene_embeddings'] and context['coexpr_prior'] for signed DE direction on off-panel knockouts. Holdout gene Mab21l2 and test gene Ctnnb1 are non-cardiac.

## What worked (mechanism classes, CONFIRMED)
- Real-cell selection or mixing beats synthetic blending. Pseudobulk edits go only on detected entries, scaled by 1/prevalence and clipped.
- Detection-depth harmonisation by binomial thinning toward the measured trend is the largest cross-board lever. It gave embryo +5.5 to +7.7 [w2_c02, w2_c06] and heart +2.4 to +2.6 [w1_c10, w1_c11]. It is bounded and input-derived, with byte-exact passthrough when no correction is needed.
- Size laws are clean, board-isolated gains: constant packing density, nearer-bracket anchoring, radius caps.

## Negative and dead ends
- Neighbourhood or focal-identity transplant matching on embryo: Nyström [w2_c00 aborted run −1.65 board; v2/w2_c01 −0.34] and focal-identity matching [w2_c04 −2.83]. Both lowered neighborhood_mmd. Local donor re-permutation also gave ~0 [w2_c23 +0.06].
- Embryo expression: per-cell linear interpolation (depth inflates 19→37 genes, mmd_u worse) [w2_c07]. Local-field depth completion [w2_c09]. Detected-abundance gene-wise calibration [w2_c14 −1.32]. Upper-tail molecule thinning [w2_c10 −0.57]. Convex depth interpolation [w2_c03 local optimum]. Type-conditioned midpoint [w2_c15 ≈ +0.1]. The Extended Mouse Atlas as a DE source scored worse than the released mixture (Spearman +0.31 vs +0.41) [w2_c09].
- T1: chamber-residence donor conditioning [v2/w0_c00 −1.28; a verified composition change is not a forecast gain]. OT50U on top of the maturity+cushion parent duplicates the density channel [w0_c07, negative at 2/2 seeds]. Per-lineage anchors replacing the global Qiu axis were harmful offline [v2/w0_c01]. Knob exposure was a bit-for-bit no-op [w0_c04].
- T3: DNA-binding TFs must stay excluded from the delay mixer [w3_c18]. Interval-scaled delay plus a GO routing tilt [w3_c14 −3.99]. WT-only exposure and amplitude substitution [w3_c13 −0.83; w3_c21 hand2_e925 −6.93]. Raising the amplitude caps [w3_c15]. Thinning delay donors [w3_c19]. GO-module direction term [w3_c10]. WT-stage module orientation [v2/w3_c00 ≈ 0].
- Heart: daughter-cell densification [w1_c03 ≈ 0]. Per-gene depth calibration [w1_c12]. Dropping, rather than relocating, detached rows lost de_score −3.6.

## Pitfalls (actionable)
- Promised no-op branches must be byte-exact. Test every branch (zero-draw, retention=1, endpoint share=0, unusable priors) before submitting.
- State the real caps. Apply the cap after any renormalisation, and don't add undeclared clips or doubled rates.
- Don't hard-code split-specific constants. Express doses in WT-interval units and derive growth bounds from inputs only.
- Any data-derived sign or orientation must be anchored by construction, not by comparing float residues.
- Perturbation gates read context['external'] only, never expression_prior. Unbounded gates (n_support) will fire on unseen broad modules.
- Require the paired n≥3 repeat and the guard-gene check (gata4 ≥ −0.25) before claiming a T3 gain. Single-seed dev screens flip.
- Always validate heart on heart_long and embryo on both embryo_early and guard_embryo_e80.

## Next to try
- Re-race the vetoed high-yield items with their defects fixed: T1 full-interval cushion transfer at an honest dose [w0_c01, w0_c05]. Embryo midpoint-share-correct mixing plus depth thinning plus the cube-root size law [w2_c05]. Heart input-derived organ growth with a true cap [w1_c06, w1_c08].
- Heart: bounded pseudobulk extrapolation using context['external'] (Feulner E14.5/E16.5) at weight beyond heart_long, and Slide-seq neighbourhood refinement (the local-contrast edit gave 0 in [v2/w1_c02], so test it separately).
- T3: signed off-panel DE direction from gene_embeddings and coexpr_prior, kept gene-agnostic and guarded on Gata4.
- Port the depth-trend thinning to T1 and to heart/embryo at horizons beyond the bracket span [w1_c10, w1_c14].
