# TASK: T2 embryo interpolation (Virtual Embryo Challenge, NeurIPS 2026)

You are building a model that predicts the **mouse embryo at E7.75** as a population of single cells measured by 3D
MERFISH: each cell has expression of 497 panel genes and a 3D position. The prediction is scored against a hidden real
E7.75 embryo by the official challenge scorer. You work fully autonomously; nobody will answer questions.

## Data you can read
`/scratch/user/focused_morphogen_t2_embryo/data/train/` (read-only), official training stages:

| file | stage |
|---|---|
| E6.75.h5ad | E6.75 |
| E8.0.h5ad | E8.0 |

AnnData, 497 genes. `.X` = log1p(1e4 * counts / total) per cell. `obs['celltype']` (embryo-region labels; 'Unknown'
exists), `obsm['spatial_3D']` (x, y, z; per-embryo local frame, **not registered across stages**), `obsm['spatial_2D']`.

Two more stages exist and are **protected** (you cannot read them; the sandbox denies it): E7.25 and E7.5. Your
program receives them as inputs only inside the evaluation service. E7.5 is the official validation answer; E7.25 is
the guard answer.

Organiser facts: each stage is a different embryo (no cell correspondence). The test target is an interpolated stage
between the two inputs. Spatial coordinates are in each embryo's own local frame, so the output must be one coherent
anatomy, not an overlay of two independently centred clouds.

## The program contract
Your workspace must contain `program.py` with

```python
def predict(inputs, times, target_time, context) -> anndata.AnnData
```
- `inputs`: list of AnnData (copies), ascending stage order, all with the same 497 genes in the same order.
- `times`: list of floats, e.g. [7.25, 8.0]. `target_time`: float, e.g. 7.5 or 7.75.
- `context`: `seed` (int; your output must be deterministic given it), `n` (requested cell count, 3000), `max_cells`
  (5000), `min_cells` (1000), `genes`, `params` (tuned knobs, `{}` unless tuned), `dissection` (None here).
- Return 1000..5000 cells with every panel gene (extra genes / obs columns are ignored), non-negative finite
  log1p-CP10k expression in `.X`, and finite `obsm['spatial_3D']` of shape (n, 3). Cell labels are ignored by the
  scorer. Cell count is not scored; it is only a sample size.
- Helper modules and small asset files in your workspace are allowed (they are snapshotted with program.py; no .h5ad,
  files up to 50 MB). Use only packages of the fixed environment (numpy, scipy, scikit-learn, pandas, anndata, scanpy,
  statsmodels, torch (CPU in evaluation), numba, igraph, pynndescent). No network, no file reading outside the snapshot
  in evaluation.
- Tunable knobs (optional): declare up to 4 in `knobs.json` next to program.py and read them as
  `context['params'].get(name, default)`. Do not write `tuned_params.json` yourself.
- Limits per configuration: 30 min wall time (45 min for the test configuration), 20 GB memory, 4 CPU threads.

## Configurations your program is run on
1. **Validation (scored for you via `python tools/evaluate.py`)**: inputs E7.25 + E8.0 -> target_time 7.5, max_cells
   5000. This is the official T2:embryo:val_interp board, scored with 3 scoring seeds. The harness also reports
   `native_occupancy`: the official occupancy Dice of your prediction against the best input stage (1 = one native
   cloud). A two-cloud overlay scores far lower.
2. **Final test (the submission)**: inputs E7.5 + E8.0 -> target_time 7.75, max_cells 5000. Check that your program
   runs there with `python tools/testcheck.py` (pass/fail only).
3. **Hidden guard check (a veto at final selection)**: a different configuration with a stage you have never seen. Its
   data and scores are never shown to you. A checkpoint that loses more than 1.0 point to the starting model there is
   ineligible. Write general code; do not hardcode stage-specific constants.

## Scoring (official scorer: veckit metrics via vec_local_score)
Each split is scored with 3 scoring seeds. The scorer subsamples each stage to 10% and splits the target in halves.
Each metric is calibrated so that a copy of the reference stage (the last input, E8.0) scores about 50 and the
target's own split-half about 100. Points are weighted: de_score 0.125, de_direction 0.125, mmd_u 0.15, variogram
0.10, d2_shape / occupancy_dice / scale_log_ratio 0.0833 each, neighborhood_mmd 0.25. Structure gate: the three shape
terms are multiplied by min(1, neighborhood_mmd skill / 50).

**Geometry is the known failure mode.** The official test occupancy is bimodal: predictions that keep one input
embryo's own coordinate cloud (scaled) score about 100; overlays of two clouds score near 5-30. The starting program
already keeps one native scaffold. Do not break that: the harness rejects any checkpoint whose native occupancy is
below 0.90, and the final selection only considers checkpoints that pass it. Isotropic scaling does not change
d2_shape (it is rms-normalised), so the meaningful geometry controls are occupancy and scale.

## Tools and budget
- `python tools/evaluate.py --note "..."`: snapshot + validation score (queued, one at a time). Budget:
  80 evaluations this round. `python tools/evaluate.py --history`: free.
- `python tools/testcheck.py`: test-configuration run check, 12 per round.
- Time budget this round: 3 hours of active work. Your round's result is the best-validated program
  snapshot that also runs in the test and guard configurations and passes the native-occupancy gate.
- Do not modify `tools/`. Do not read or try to read anything outside your workspace and the training data.

## Prior knowledge and research
- `prior_knowledge/README.md` contains the small amount of starting context provided for this run. Read it first.
- Web search and web fetch are ON. Research embryo development around E7.5-E8.0, MERFISH spatial reconstruction, and
  interpolation/optimal-transport methods. Cite every source you use in NOTES.md (URL + what you took from it).

## Rules
- Challenge external-data rules (organisers): do not use measured data (files, tables, or gene-level results read from
  papers) from mouse embryo stages after E8.0 up to and including E13.5. Never attempt to access the protected stages.
  General biological knowledge (what forms when, qualitative trends) is fine. Every external source must be listed in
  NOTES.md.
- Programs run offline: any permitted external information must be distilled into small files or constants in your
  workspace, with its source documented.
- `tools/evaluate.py` is the official scored signal. Your own analyses of the training data are encouraged.
- Keep `NOTES.md` current: hypotheses, what you changed, each evaluation's result, what you concluded, and a final
  summary. It is published with the run.
- Keep the code clean and documented; the final program is published as the method.
