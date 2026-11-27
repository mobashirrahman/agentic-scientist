# Decoding the strongest public P3 TEST entries (what to REPLICATE first)

Public model names are free text (truncated to 60 characters by the site). Everything below is read from the public
board; all of it, numbers in names included, is fair game. The one rule (live rules, section 10, last
bullet): "Returned scores may be used to choose among predictions, not to compute them": never solve for a hidden
target property by inverting the skill map or differencing scores. Replicating a recipe a name describes is fine.
Workflow per board: (1) replicate the strongest decodable recipe on top of the seed, (2) race it, (3) build on it.
Check the newest board with `leaderboard.py --live top <board>`; `entry <board> <team>` prints one entry in full.

## T1 (E8.5/E9.5/E10.5 -> E12.5 heart chambers; weights DE 25, direction 25, mmd 30, variogram 20)
- Field: plain E10.5 copy ~69.4 ('E105_direct_reference' 69.4, 'DataHead E10.5 RNA anchor' 68.8).
- 77.1 JLShen 'E10.5 real cells (unlocked val answers, 5000, coarse-type sh[ift])': real E10.5 cells, 5000 rows, then a
  COARSE cell-type composition shift. +8 over the copy from composition at a coarse level only.
- 84.2 devmatrix 'P3MIX_T1_E12p5_D50_OT50U_CB_XF': mixture; D50 (50% delay/drift?), OT50U = 50% unbalanced OT step,
  CB (cell-type balance / composition balance), XF (cross-fit/transfer).
- 83.6 devalex 'P3LT_T1_E12p5_CT3_N0f_k150w100_pt_lhs': lineage transport over 3 coarse types (CT3), kNN k=150 with
  window/weight 100, partial transport (pt), Latin-hypercube-searched knobs (lhs). Same author's sibling 79.1
  'P3LT_T1_E12p5_QM3_N0I_k'.
- 82.1 ckpws 'P3SEL2OT_T1_E12p5_D150_TQ100_TL100_OTC050_HBA_CB_XF': selection + 2-step OT, D150, OT cost 0.50, HBA
  (haemoglobin-adult handling = blood control), CB, XF.
- 81.7 wzb / 78.4 cccjh 'Two-skeleton real-cell extrapolation + maturity-tilted selec[tion]': two skeletons (E9.5 and
  E10.5) define a per-lineage mean+covariance step; real cells are SELECTED with a tilt toward maturity.
- 80.9 syouya 'p3_t1_c298_e105_core_r02_cm18_b08_tilt075': E10.5 core (heart-proper) cells, r02, cardiomyocyte share
  18?, blood x0.8 (b08), maturity tilt 0.75.
- 80.8 Jiyang 'J-T1-LineageTransport'; 78.6 makabaka 'Gaussian OT extrapolation' (agent).
- Weaker but informative: 72.9 'E10.5 nuclei with trend edits, heart-proper donors only'; 72.1 'E10.5 cells + Wu E16.5
  anchor 50%'; 67.4 'E10.5 cells+tilt+kNN count edit+E14.5 20%+denoise'. Heavy late-anchor mixing does not pay.
- CORRECTED: our file with a continued E9.5->E10.5 lineage trend (6% cardiomyocytes) scored mmd_u 66.4; 'cm18'
  in the 80.9 recipe is a cardiomyocyte share near E10.5's own chamber share. Do not deplete myocardium.
- Common core of every entry above 80: REAL E10.5 cells (heart-proper donors), blood held down, a coarse-type
  composition step and a maturity tilt in the selection of which real cells are emitted; mmd_u 84-91, variogram 80-86.

## T2 heart (E8.25..E10.5 -> dissected E12.5 heart; nbr 25, mmd 15, DE 12.5, dir 12.5, vario 10, shape/occ/scale 1/12 each)
- Field: whole-section copies ~49 ('E10.5 comp copy, growth x1.48' 48.8).
- 66.6 JC_VEC 'real E10.5 heart cells, affine-rescaled coords (rms 510.5)'; 66.4 JLShen 'Heart-centric crop of E10.5
  heart MERFISH'; 66.2 fish 'p3_t2_heart_m492_armb_rms510p5'; 59.2 egan '...heartward-rms520'.
  => heart-only REAL E10.5 cells, coordinates rescaled so the RMS radius is ~510.5 (three independent names).
- 77.1 PeacyBlose25 'P3R4_HEART_EXTRAP_E125_CXB_KBULKO30D2XJ15PK1_N25179_R5105' and 73.7 devalex
  'P3R4_HEART_EXTRAP_E125_CXB_BULKO20_N11547_R5105': CXB (crop x blood?), BULKO20/KBULKO30 = a pseudobulk offset of
  strength 0.2/0.3 (shift expression toward the extrapolated pseudobulk), D2, XJ15 (jitter 15?), PK1, N25179 = the
  maximum allowed rows, R5105 = RMS radius 510.5. The 77.1 vs 73.7 difference: more rows (25179 vs 11547) and K-scaled
  bulk offset 0.3 with D2/XJ15/PK1.
- 72.5 makabaka 'T2 heart extrapolation, T family alpha=0.50 coordinate-only ...' (agent).
- Every entry >= 72: neighborhood_mmd 72-78, mmd_u 70-75, scale 89-100, occupancy ~50 (occupancy is hard for all).

## T2 embryo (E7.5 + E8.0 -> E7.75; same weights as heart)
- Field: endpoint mixtures with two overlaid clouds ~66-71 with occupancy 3-10 (public endpoint-mixture entries).
- 76.9 makabaka 'T2 embryo agent run 2026-11-23 (E7.5 skeleton, midpoint geom...)': E7.5 skeleton, midpoint geometry.
- 78.8 WeiQA 'p3_e775_m369_nystrom_neighborhood_embedding_n5000_v1': 5000 rows, Nystrom neighbourhood embedding.
- 73.6 JLShen 'Slot-1 expression population (E7.5 val-answer cells, half gi[ven]...)'.
- Top 10 (80-81, codenames): d2_shape 93-100, occupancy 100, scale 98-100, nbr 79-80, mmd_u 77-81, DE 64-67.
  => CORRECTED by our own test file: ONE native embryo's UNSTRETCHED coordinates score occupancy 3.7 (that
  geometry is the floor; the ceiling lies just above it, so the term is all-or-nothing). The entries at 100 use MIDPOINT
  geometry (makabaka: "E7.5 skeleton, midpoint geom"): one bracket's cells and positions with the proportions
  interpolated between the brackets. Interpolate each NATIVE axis (the principal-axis ORDER changes between E7.5 and
  E8.0, so sorted PCA spectra pair the wrong axes). Entries that resubmit the reference geometry exactly sit at
  48.9-50. Then the remaining points are expression (DE, variogram) and neighbourhoods.

## T3 (Ctnnb1 KO at E8.75 from WT E8.5/E8.75; DE 30, dir 25, severity 25, mmd 12, vario 8)
- Ours (previous seed, 0.23-day delay): 69.0 (severity 88.7, DE 61.7, dir 68.0, mmd 56.5, vario 56.9); a matched WT is the floor (50).
- 78.3 olivevector70 't3-x3-d230', 75.6 harbor5071 't3-r2-d230', 72.6 't3-oat-d170' (mmd 68), 72.5 't3-oat-donoronly-d200'
  (mmd 66), 71.7 't3-oat-d150' (mmd 63): the score and mmd_u rise with the delay. CORRECTED: the delay is NOT
  0.23 day. Our 0.23-day mixture of the E8.5/E8.75 brackets scored mmd_u 56.5 / variogram 56.9, like every public
  within-bracket mixture ('E8.5 reference donors' mmd 50, '50% WT' mmd 55, 'D0188' mmd 54). mmd_u 63-74 needs cells from
  stages EARLIER than E8.5: the delay is read as 2.3 WT sampling intervals (0.575 day -> E8.175, real E8.0/E8.25 cells).
- 73.4 'WT delay composite, Gata4-derived response direction on both...'; 70.1 'real-cell portfolio: E8.5 65% +
  Gata4-KO E8.75 20% + WT E8.7[5]'; 68.4 JLShen 'beta-catenin KO as a developmentally delayed embryo: 50% WT ...';
  67.0 'P3-T3-AR-DELAY-LOGLIN-D0188-DSF025-TKO'.
  => mixing real cells of an EARLIER WT stage (E8.5) into the E8.75 WT (developmental delay) is the shared core;
  the strongest add a response direction learned from the released Gata4 KO and a sizeable delay.
- Top 10: severity 92-97, DE 67-72, direction 73-78, mmd 67-77, variogram 67-75.
