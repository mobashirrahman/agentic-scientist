# Focused AgenticScientist T1 research brief

Predict a population of cells from the E12.5 mouse heart chambers using the released earlier stages and the officially unlocked E10.5 stage as a final inference input. Produce finite nonnegative log1p CP10k gene expression over the official ordered panel. Final files have 638 to 5118 cells and need no coordinates or cell-type labels.

Your working directory contains a runnable empirical donor sampler. Read prior_knowledge/README.md before random experimentation. Keep program.py and companion source files in the workspace. The entry point is predict(inputs, times, target_time, context), returning an AnnData. The context contains seed, n, min_cells, max_cells, genes, sampling and params. Inputs are chronological AnnData objects with obs['celltype']. Respect context['genes']; valid input panels and annotations may vary between datasets. The harness clears output annotations. Code executes offline and receives only supplied inputs.

You may examine the two training stages in ../../../../data/train or at /scratch/user/focused_morphogen_t1/data/train. Treat access to released stage files as research only. The inference program must use its arguments. Keep experiment output and logs in the workspace. Cite literature in NOTES.md. Restrict measured model data to the stages supplied by the harness so that all model inputs are reproducible.

- python tools/evaluate.py --note "one change" scores E8.5 and E9.5 forecasting E10.5. The four headline components are DE recovery (25%), DE direction (25%), cell-state MMD (30%) and variogram (20%).
- python tools/evaluate.py --history lists this round's diagnostics.
- python tools/testcheck.py runs a two-day format rehearsal with the public training stages and chamber sampling. It checks the inference interface and file format.
- The final evaluation uses a separate later-stage dataset and the exact unscored test configuration, including E10.5 as an input. Do not access or seek guard data, official answers, other runs, account settings, or challenge submission endpoints.

The E10.5 score reflects a one-day forecast collected with surrounding tissue. A better number there can misrank later chamber predictions. Use its metrics to spot regressions and test the direction of a mechanism. Nominate one working checkpoint based on how the change transfers across stages and sampling protocols. Use NOTES.md to explain that decision.

Budget {{BUDGET_H}} hours, {{MAX_EVALS}} diagnostic evaluations, {{MAX_TESTCHECKS}} format rehearsals.
