# AgenticScientist heart extrapolation

Build a model of the E12.5 mouse heart chambers from observed earlier-stage populations. Predict 3D coordinates and 500-gene MERFISH expression jointly. Read the research brief in `prior_knowledge/README.md`. Use official released inputs and approved assets staged before the lock. For this run, use literature for ideas and the staged official files for fitting.

You may read the official training stages from `{{TRAIN}}`. The scoring service keeps the E8.5 and E10.5 validation files private. Each prediction receives only the observed stages for that replay. Each age samples a different biological preparation. Alignment estimates correspondences between distributions.

Implement `predict(inputs, times, target_time, context)` in `program.py`. Return an AnnData with 1,000–3,000 finite, nonnegative log1p-normalized rows in `.X`, all 500 genes in the published panel, and finite `obsm['spatial_3D']` coordinates. Use `context['seed']` for reproducibility and `context['dissection']` for sample scope. Use 3,000 rows when feasible. Scale and shape are evaluated separately.

Use `python tools/evaluate.py --note "hypothesis and change"` to score a copy of the current workspace. The chamber-filtered E10.5 replay is the development objective. The full-sample score is a diagnostic. The finalizer evaluates frozen checkpoints and fixed controls on registered longer replay and sensitivity checks. It runs format and export checks itself. It never reveals protected scores during the search.

Record each hypothesis, control, method, expected metric changes, and observed outcome in `NOTES.md`. Start from realistic local cell neighborhoods. Try changing chamber volumes, cell composition, or their placement one at a time. Favor transferable improvements in distribution and neighborhoods. Keep shape and expression controls in view. Your budget is {{BUDGET_H}} hours and {{MAX_EVALS}} development evaluations. The finalizer owns the export.
