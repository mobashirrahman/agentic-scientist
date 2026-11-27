---
name: diagnostics
description: Find out WHY a program scores what it does on a dev split — composition errors, wrong-direction genes, the scorer's raw DE/severity values, spatial size/occupancy/neighbourhood errors, plus PNG plots. Use before proposing a fix and after implementing one.
---
# Diagnostics

`$MG_ROOT/.venv/bin/python $MG_ROOT/agentic_scientist/tools/diagnose.py <dev_split> --workspace <ws> [--score] [--out dir]`
`agentic_scientist/tools/noharm.py <workspace>`: gene-specificity of your T3 model. It knocks out genes that are barely expressed and compares the response with Gata4 (ratio ~1 = gene-blind template; report gene_specific and global_scale).
(dev splits: temporal_val heart_early heart_late heart_long embryo_early gata4_1 gata4_2; holdout splits are refused.)

Prints, in order:
1. **Composition**: predicted vs target vs reference cell-type fractions (prediction labelled by kNN on target types) and total-variation distance vs copying the reference.
2. **Pseudobulk change** on the target's most-changed genes: sign agreement, correlation, wrong-direction and most under-predicted genes. Then the **scorer's own definitions**: the truth's DE set (|Δmean| ≥ 0.25), de_score, de_direction, and severity log β with R². Severity = worst (−6.91) when the response is absent or unrelated on the truth's DE genes; 0 is ideal.
3. **Spatial**: rms size vs target (scale_log_ratio), occupancy Dice in the rms frame vs the reference, neighbourhood-composition error per cell type (drives neighborhood_mmd and the T2 gate).
4. `--score`: per-metric skills from the real scorer (one seed).

Plots (`pca.png`, `spatial.png`, `composition.png`) and `report.json` go to `<ws>/../diag_<split>/` by default (outside the workspace). Open them with your Read tool to look at them.

Workflow: diagnose the parent → state the specific error you will fix in the hypothesis claim → diagnose the candidate to confirm the error moved. Quote numbers from the diagnostic as evidence ("data:" sources).
Runtime: about 1–3 min per split (T1 is the slowest: ~32k genes).
