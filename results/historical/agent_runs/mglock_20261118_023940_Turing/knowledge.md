# Knowledge bank

## Established (held up; effect sizes and cycles)
All n=8.
- CONFIRMED [w3_c00→w3_c01; temporal +4.33 then +2.04]: erythroid/blood budget 0.01/2→0.04/6→0.08/10/12, dist-carried, cap binding. CONFIRMED [w3_c02; Δ +0.48]: input-calibrated globin soup, dist-only; DE-repair falsified (4 genes ≠ genome-wide DE).
- CONFIRMED [w1_c02; Δ +1.67]: three-tier heart mask (×0.2/×0.5/×1) — heart +3.34, supersedes w1_c00/c01; retention [w1_c05; Δ +1.54] heart +3.08; cap-raise [w1_c06; Δ +0.33] heart +0.66. CONFIRMED [w1_c08; Δ +0.50] heart +1.005, size-only: growth freed when the field contracts while the ventricle outgrows its 0.25/day cap (opposing trends = trigger) — scale skill +4.8..+24.0 on E9.5 splits.
- CONFIRMED [w0_c00; Δ +1.65]: min-KL tilt of latest-WT donors — pert +1.66; exposure gain g=2 [w0_c03; Δ +0.81] stacked [w0_c04; Δ +0.50] sub-additive; KO-exposure fallback [w0_c06; Δ +0.93].
- CONFIRMED [w0_c09; Δ +2.39]: exposure-gated flat-WT resampling — pert +2.39, de-carried; Gata4 gate opened (β 0.0317); FLAT_U_MAX 0.60→0.95 [w0_c10; Δ +1.53] — Gata4 β 0.078/0.082, Gja1 sign correct; w0 best 183.35→186.25.
- CONFIRMED [w2_c02; Δ +0.98]: decoupled embryo warp (lineage reweight, radius f^1.5) — embryo +1.96, size-carried, supersedes w2_c01 (+0.41); gene-wise thinning [w2_c07; Δ +0.56] embryo +1.12, supersedes uniform [w2_c04; Δ +0.48].

## Dead ends (and the condition under which a retry is justified)
- Per-gene delay edits fail (-1.84/-6.62) [w0_c00]; R=2 cap sold Gata4 magnitude [w0_c05]; gata4 floored under all delay/exposure arms [w0_c04, w0_c06, w0_c07, w0_c08] — read as DE-fit failure, CONTRADICTED: flat-donor composition opened it [w0_c09, w0_c10]; retry delay edits at R=3 or DE-orientation.
- State-clock curvature NEGATIVE [w2_c09; Δ -2.04, embryo -4.08]: diagnosis right, replicated, yet unbounded dose cost d2_shape/occupancy — state clock not DE-binding; retry bounded + geometry-decoupled.
- Concave exposure ramp NEGATIVE [w0_c07; Δ -0.49]: dose not binding (3.998/4.0), mab21l2 floored despite dev DE gains; retry: guard headroom + DE-set-tracked severity.
- Bracket-persistence NEGATIVE [w2_c03; Δ -0.28, embryo -0.56]: bracket offset dominates kNN; retry only offset-cancelled; kNN-partner morphing catastrophic (mmd ×2, variogram ×4) [w2_c03] — never.
- Fourth donor-law tier NEGATIVE [w1_c03; Δ -0.35, heart -0.69]: deficit decode-made (pPHM 0.005→0.013); retry only after proving supply limits.
- Share repair ≠ expression fix [w1_c04]: TV 0.242 yet 12 wrong-direction genes worsened; retry only decode-side.

## Promising / inconclusive leads
- Flattening blend rejected [w0_c08; Δ +0.96, mab21l2 -2.20]: breadth sized amplitude on unseen genes; resampling retry succeeded [w0_c09, w0_c10].
- Mask beyond three-tier rejected: rim-at-1 [w1_c01; Δ +1.14] organ_proxy -7.54; exact-share [w1_c04; Δ +0.54] e875 -1.42.
- rms radial repair rejected [w1_c07; Δ +0.02 vs +0.4 bar]: d2_shape restored offline but 1/5 splits declares dissection, occupancy -0.5-2.5; retry when dissection common or occupancy fixed.
- Thickness flattening rejected [w2_c10; Δ +0.16 [+0.10,+0.22], embryo +0.32]: dist-only, 7/8 pairs, sub-margin — accept only stacked.
- Epicardial retention rejected [w3_c03; Δ +0.28 [+0.05,+0.52]]: dist +0.32/DE +0.28, under-dosed (d=0.5×P, odds 2.0); retry at full dose.
- Mesoderm budget rejected [w2_c06; Δ +0.24 [+0.02,+0.45], embryo +0.47]: share hit but Tbx6+ donors never relabel; retry: fix E8.0 label transfer.
- Cycling tilt INCONCLUSIVE [w2_c08; Δ +0.02 [-0.13,+0.16]]: de +0.49 vs dist -0.47, 40% donors 88%-cycling; retry non-cycling brackets.
- Thinning portability INCONCLUSIVE [w2_c05; Δ +0.01 [-0.04,+0.06]]: payoff scales with parent depth excess; retry at ~35 genes/cell [w2_c07].
- Tilt add-on axes INCONCLUSIVE: delay [w0_c02; Δ +0.01], KO co-expression [w0_c01; Δ +0.03] — sign right, gates shut; retry on-panel, truth-DE β>0.
- State damp INCONCLUSIVE [w2_c00; Δ +0.20 [+0.00,+0.40]]: λ≤3 closes ~14% of gap; retry only if damping ≈0.2.

## Per-board state of the art and weakest metrics
Dev = temporal+0.5×heart+0.5×embryo+pert; seed 180.77; worker bests w0 186.25, w1 183.15, w2 182.33, w3 187.19.
- temporal — best w3_c01, 65.74: budget 0.08/10/12. Weakest: cap binding (Blood 0.077 vs 0.147) [w3_c01]; late lineages beyond reweighting [w3_c00].
- heart — best w1_c08, 58.62: three-tier mask [w1_c02] + field-contraction growth release [w1_c08] (ahead of w1_c06, 58.23). Weakest: E9.5 density dips (dice -5.6/-6.4, d2 -2.8/-2.2) [w1_c02, w1_c05]; release capped log1.20/0.70-day, silent when field expands (heart_3d) [w1_c08].
- perturbation — best w0_c10 line, ≈59.4: tilt+gain+fallback+flat resampling (FLAT_U_MAX 0.95) [w0_c00, w0_c03, w0_c06, w0_c09, w0_c10]. Weakest: hand2_e825/e925 OPEN, mag 0.11-0.30 of truth [w0_c02, w0_c07, w1_c08]; mab21l2_e95 arm-dependent (0.007 w1 OPEN, 0.001 w0) [w1_c08, w0_c07]; gata4 open only on the flat line [w0_c10].
- embryo — best w2_c07, 84.21: warp [w2_c02] + gene-wise thinning (DE +1.09). Weakest: PS/SOM/LPM/CE 20.0% vs 3.4%, Unknown 32.5% vs 12.0% [w2_c06, w2_c03]; per-gene DE short (Apoe +0.47 vs +1.45, Tbx6 +0.32) [w2_c07].

## Method pitfalls (statistics, evaluation, reasoning traps)
- Pre-register bars, caps, falsifiers and mechanism floors — floors confirm mechanism [w1_c05, w1_c08]; sub-margin = clean reject [w2_c06, w0_c07, w2_c10, w3_c03]; per-split edges veto means [w1_c01, w1_c04, w3_c01, w0_c08]; sign-only gains = null [w2_c03, w1_c03].
- Right diagnosis at unbounded dose is net-negative; replicated mechanism ≠ board gain [w2_c09]; forecasts sign-only [w0_c07] except fixed-formula offline probes [w0_c10, w1_c08].
- Never bar an unmoved metric: diagnostic severity OLS ≠ scored severity — scored froze 50.0 as diagnostics opened [w0_c08]; instrument realised stats, not dose [w0_c07]; heart-size fixes don't close pert gates [w1_c08].
- Single-seed scores ≠ paired harness — a -2.72 quick-eval loss vanished under 8 seeds [w0_c09]; sha256 matrix byte-identity beats scorer reruns [w1_c08].
- Ablations are wiring checks; credit must match mechanism — closed gates ⇒ de/dist-only [w0_c06, w1_c05, w2_c07].
- Critics config-disabled ⇒ high-leverage edits ship unreviewed [w1_c08]; when on, vetoes carry the review [w1_c05, w2_c07, w0_c08].
- Calibrate externally — anchors right yet blend 50.0 vs standalone 92-97 [w0_c08]; within-platform contrasts cancel cross-platform offsets [w2_c07].

## Implementation pitfalls (crashes, helper quirks, contract)
- quick_eval caps at 3 runs — extra splits via diagnose --score/hashing; no heart_knobs.json — hard-code pre-registered constants; organ RMS filter-dependent (248.3 vs 307.4); winsorize ventricular radii 95%; zero-default + horizon gate (h/dt≤1 ⇒ 0) confines to triggered splits — all [w1_c08].
- Screens reject substrings ('open (', 'harness') and inherited names ('globin') — scope to new lines [w0_c03, w0_c04, w3_c00].
- Inherited tuned.json overrides new defaults — re-measure [w3_c01, w0_c04]; a new dose knob re-tunes others — pin them [w0_c07].
- Fit donor laws on the scored population, not the release [w1_c05]; unassigned donors: clear confident flag first, fallback = atlas exposure + mean-log [w0_c06].
- Scored severity floors at 50 on undefined LFC OLS [w0_c07, w0_c08]; paired CI not local — pre-ship per-split de_score + gates [w0_c08].
- Blend weights: breadth gates must not size amplitude — dose = clip(a_all/REF,0,1); missing-prior path = identity law [w0_c08].
- Depth/ablation [w2_c04, w2_c05, w2_c07]: pin panel; thin integer counts pre-CP10k; guards R≥1.5, retention ≥0.30; thin_relative_depth takes LINEAR fractions; same-seed Δ; arms matched on molecules + genes/cell.
- Guards: q/p ≤4, no floor [w1_c04]; r clip [0.25,4] — check pressure [w2_c06]; post-clip powers keep saturated genes identical; ramps share a_all<0.02 genes [w0_c07].
- Tilt: lam solved for rho, ESS≥50%, ratio≤4, clip(a_all/0.10,0,1) [w0_c00, w0_c02]; gain g_eff·a_t on 0.02-0.10 ramp [w0_c04].
- Ship: scratch in analysis/, strip __pycache__, board files + CHANGES.md + .quick_eval_runs only; Δ0.0 on untouched boards = leak check + negative control [w0_c03, w1_c05, w1_c08].

## Open questions
- Heart: stack [w1_c08] × [w1_c06] × [w1_c05]? Radial repair when dissection common [w1_c07]? Growth past log1.20/0.70 or expanding-field triggers [w1_c08]?
- Perturbation: FLAT_U_MAX past 0.95 [w0_c10]? hand2/mab21l2 magnitude on the flat line [w0_c10, w1_c08]; delay arms at R=3 (s=0.374) or DE-orientation.
- Temporal: 0.08→0.12 dose-response [w3_c01]; stack globin soup [w3_c02] + full-dose epicardial retention [w3_c03]?
- Embryo: stack thickness flattening [w2_c10]; retention past 125 genes [w2_c07]; damping ≈0.2 [w2_c00]; bounded shape-safe state clock [w2_c09]?
- Portables: growth trigger → embryo if field contracts [w1_c08]; mass budget → heart/embryo [w3_c01]; mask/retention → embryo on protocol change [w1_c02, w1_c05]; thinning → heart at ~2× depth [w2_c05, w2_c07]?
