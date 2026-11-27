# Held-out lessons (from final holdout checks; added deliberately by the team)

## pilot4ab: dev gains did not transfer
Holdout = heart E10.5, embryo E7.5, T3 Mab21l2 knockout at E9.5 (a non-cardiac gene), mean of 3 seed pairs.
- Seed: holdout 163.7 (heart 52.6, T3 46.8).
- w0_c03 (dev +22.6): holdout 159.2. Heart 45.3 (−7.3) and T3 45.6 (−1.2).
- **Heart, "bounded extrapolation of the cardiomyocyte-program compartment" (w0_c02).** Dev heart +4.8, but holdout heart E10.5 −7.3. Trend extrapolation of a cell-type program overshoots at a longer horizon or a later stage. Damp it, and validate on heart_long.
- **T3, "lineage rollback" with exponent 1.0 and widened bounds (w0_c01, w1_c01, w1_c02).** Gata4 +11 to +17, but Mab21l2 −1.2. Gata4 is a cardiac lineage gene whose knockout shifts proportions; the rollback strength is Gata4-specific. Treat these as Gata4 overfitting, not established mechanisms. Any T3 change must be gene-agnostic.
- Embryo and temporal were unchanged on the holdout.

## Run #1 (runA): cross-run transfer lessons (no private scores)
- **T1 (`temporal`):** Real-cell coarse 3-lineage cardiac growth + maturity selection (`w0_c00`) and especially **prevalence-calibrated Qiu 2024 late-anchor pseudobulk continuation** (`w0_c09` + `w0_c10`: `clip(d/p, -0.35, 0.35)` on detected entries) delivered the strongest generalizable DE/variogram gains and are baked into Run #2's seed (at 5,000 rows). Caution: shifting donor mass *out* of myocardium into endocardium (`w0_c06`) fits E10.5 cushions but moves opposite to later fetal heart myocardium growth.
- **Heart (`heart`):** Dissected organ-resident real-cell selection (`w1_c04`) + saturating binomial detection-depth thinning (`w1_c14`) + bounded organ growth (`w1_c15`) + relocating detached vessel/pericardial rows onto nearest attached same-type sites (`w1_c16`, fixing `d2_shape`) all transfer cleanly and are baked into Run #2's seed (now at `N_CELLS = 25,179`). Major untouched headroom: bounded pseudobulk expression extrapolation (`BULKO20/KBULKO30`) using `context['external']` (Feulner E14.5/E16.5) and spatial neighborhood refinement using `context['external_spatial']` (Slide-seq E14.5/E15.5).
- **Embryo (`embryo`):** Run #1's embryo chain overfitted `embryo_early` (E6.75+E8.0 -> E7.25) because E6.75 is 4.6× shallower in detection depth than E8.0 and shape metrics were turned off (`no_shape`). Constant-density radius collapse (`w2_c06+`) and aggressive donor thinning (`w2_c02+`) hurt later depth-matched stages, so Run #2 restores the clean native unstretched scaffold (`seed_final/embryo.py`, occupancy ~100) and puts `guard_embryo_e80` (E7.25+E8.25_late -> E8.0) directly in Dev alongside `native_occupancy >= 0.97`. Note: calibrated CP10k-log midpoint pseudobulk adjustment (`w2_c13`) and complementary donor selection (`w2_c24`) showed promise when not paired with radius collapse or E6.75-specific over-thinning.
- **T3 (`perturbation`):** The GO-weighted real-cell `d230` developmental-delay mixer (`w3_c09`/`w3_c11`) cleanly fires on broad signalling regulators (like off-panel `Ctnnb1`) and narrow GO modules (`Mab21l2`) while leaving DNA-binding TFs (`Gata4`/`Hand2`/`Mef2c`) intact, and is baked into Run #2's seed. Major untouched headroom: `context['gene_embeddings']` (Geneformer-V2-104M) and `context['coexpr_prior']` (WT Qiu 2024 <=E9.0 signed gene-to-panel correlation) to predict gene-specific signed DE directions for off-panel knockouts. Note: Run #1's `mef2c_e85` split passed backwards `[E8.5, E9.0] -> E8.5` (now fixed to forward-time `[E7.75, E8.5] -> E8.5` in Run #2).

## TEST result of the previous seed: corrections that OVERRIDE older records in this library
Total 206.9 (T1 71.1, heart 65.2, embryo 68.4, T3 69.0). Per-metric numbers are in `data/our_test_history.json` (entries D-*).
- **T1: lineage-trend continuation is wrong on the test.** The file had 6% cardiomyocytes and 54% endocardium (E10.5 chamber
  tissues: ~19% cardiomyocytes) and scored mmd_u 66.4. The records "3-lineage composition growth [w0_c00]", "myo->endocardial
  cushion transfer [w0_c03, w0_c06]" and "full-interval cushion transfer (PROMISING)" gained on Dev because the Dev target
  (E10.5) contains the same one-interval sampling shift; they are test-negative. Keep latest-stage lineage masses; the
  composition veto now enforces a cardiomyocyte floor. The late-anchor pseudobulk continuation and the maturity tilt stay.
- **Heart: detached residents and the missing epicardium.** Relocating detached 'Peri'/vessel rows onto the organ [w1_c16]
  fixed d2_shape but kept 21% 'Peri' expression rows; the E10.5 epicardium label 'Epi' was not matched by the organ
  pattern. mmd_u 59.5 and neighbourhood 64.0 on the test (cardiomyocyte-rich public crops: 68-75 and 66-78). The seed now
  draws attached cells only and includes 'Epi'. An RMS of 551 scored scale 87.2; the public 510.5 radius scores 100.
- **Embryo: "one native unstretched embryo" is the FLOOR, not the recipe.** Occupancy 3.7 with the native E7.5 scaffold
  (older records and prompts that say "occupancy ~100 on test" were a prediction, and it was wrong). The floor is the
  earlier bracket itself and the attainable ceiling lies just above it, so occupancy is all-or-nothing: 100 for public
  midpoint-geometry entries, 3-10 for native scaffolds, overlays and sorted-PCA stretches alike. Use midpoint geometry
  per native axis. Embryo Dev shape terms do not reproduce this; the E7.5 holdout fold partly does (d2_shape 49 -> 81).
- **T3: the public "d230" delay is not 0.23 day.** Our 0.23-day real-cell mixture of the two brackets scored mmd_u 56.5 and
  variogram 56.9, the same as every public within-bracket mixture (50-56), while the public d150 -> d170 -> d200 -> d230
  entries rise from mmd_u 63 to 74 and reach 78.3 in total. The delay reaches stages earlier than the brackets; the seed
  reads it as 2.3 sampling intervals and emits real cells of the earlier released WT stages.
- **Selection:** in the previous run every accepted embryo change lost 1.3-8.7 on the E7.5 holdout, and the heart
  changes that raised the dissected E10.5 holdout were rejected for review defects (a missing size cap), not for their mechanism.
