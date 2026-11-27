# Lab notebook (raw log; the curated synthesis is knowledge/knowledge.md)

## w0_c00: (no hypothesis) [skipped, ideator wrote nothing]
- ideator wrote nothing

## w2_c00: (no hypothesis) [skipped, ideator wrote nothing]
- ideator wrote nothing

## w3_c00: Embryo: single native-scaffold output (earlier bracket coordinates only, fixed 3000 cells) instead of a two-bracket overlay [negative, clear loss on screen: Δ-2.85 (z -15.3) | severity gate (β>0 & R²>0.01): gata4_1 β 0.307 R² 0.15 mag 0.92 OPEN; gata4_2 β 0.328 R² 0.23 mag 0.73 OPEN; hand2_e825 β 0.632 R² 0.14 mag 1.28 OPEN; hand2_e925 β 0.22 R² 0.28 mag 0.58 OPEN; mab21l2_e95 β 0.001 R² -0.06 mag 0.29; mef2c_e85 β 0.342 R² 0.48 mag 0.53 OPEN; mef2c_e90 β 0.001 R² -0.13 mag 0.85]
- Replacing predict_embryo's two-bracket coordinate overlay with a single earlier-bracket native scaffold (3000 distinct cells, donor expression law unchanged) lost Δproxy -2.85 (z -15.3, embryo board -5.7): occupancy_dice gained only +2.9 (predicted +10 to +25, weight 0.083) while neighborhood_mmd fell -7.4 (weight 0.25) because 40% of donors are later-bracket expressions dropped into earlier-stage tissue with no same-lineage neighbours (only 50.75% matched). The overlay's doubled shell is the cheaper error — discarding later-stage coordinates destroys emerging-lineage neighbourhood composition (Primitive Streak 0.63, Caudal Epiblast 0.57, SOM 0.54, Allantois 0.48, PHM/PAM 0.46), which outweighs any single-scaffold geometry gain ~3:1 in metric weights.
