# TASK: T2 heart extrapolation (Virtual Embryo Challenge, NeurIPS 2026)

You are building a model that predicts the **mouse embryonic heart at E12.5** as a population of single cells, measured
by 3D MERFISH: each cell has expression of 500 genes and a 3D position. The prediction is scored against a hidden real
E12.5 heart by the official challenge scorer. You work fully autonomously; nobody will answer questions.

## Data you can read
`/scratch/user/focused_morphogen_t2_heart/data/train/` (read-only), official training stages:

| file | stage | cells |
|---|---|---|
| E8.25_late.h5ad | E8.25 (slightly later than E8.25) | 58,716 |
| E8.75.h5ad | E8.75 | 24,826 |
| E9.5.h5ad | E9.5 | 53,742 |

AnnData, 500 genes. `.X` = log1p(1e4 * counts / total) per cell (expm1(X) sums to 10,000). `obs['celltype']`
(E8.x: ~33 embryo-region labels; E9.5: 22 heart-region labels; the same string at two stages is not guaranteed to be the
same population; 'Unknown' exists), `obs['cm_celltype']` (second-level labels of heart-lineage cells, 'Unknown' = none),
`obsm['spatial_3D']` (x, y, z; per-embryo local frame, NOT registered across stages; z advances in fixed steps per
section, treat it as a section index), `obsm['spatial_2D']`.

Two more stages exist and are **protected** (you cannot read them; the sandbox denies it): E8.5 and E10.5 (heart,
validation answers). Your program receives them as inputs only inside the evaluation service.

Organiser facts about the samples: E8.25-E10.5 are heart-centred dissections WITH surrounding tissue (pericardium /
body wall, pharyngeal and dorsal tissue next to the heart tube; the younger, the more non-heart tissue). **E12.5 is
dissected as the heart chambers only** (possibly a few cells from the oesophagus-heart junction). "All late-stage heart
tissue comes from previous-stage heart tissue." Each stage is a different embryo (no cell correspondence).

## The program contract
Your workspace must contain `program.py` with

```python
def predict(inputs, times, target_time, context) -> anndata.AnnData
```
- `inputs`: list of AnnData (copies), ascending stage order, all with the same 500 genes in the same order.
- `times`: list of floats, e.g. [8.25, 8.75, 9.5]. `target_time`: float, e.g. 10.5 or 12.5.
- `context`: `seed` (int; your output must be deterministic given it), `dissection` ('heart_with_surroundings' or
  'heart_chambers_only': the dissection protocol of the target), `max_cells`, `min_cells` (1000), `genes`.
- Return 1000..max_cells cells with every panel gene (extra genes / obs columns are ignored), non-negative finite
  log1p-CP10k expression in `.X`, and finite `obsm['spatial_3D']` of shape (n, 3). Cell labels are ignored by the
  scorer (it types cells with its own classifier). Cell count is not scored; it is only a sample size.
- Helper modules and small asset files in your workspace are allowed (they are snapshotted with program.py; no .h5ad,
  files up to 50 MB). Use only packages of the fixed environment (`python` = numpy, scipy, scikit-learn, pandas,
  anndata, scanpy, statsmodels, torch (CPU in evaluation), numba, igraph, pynndescent). Anything you install elsewhere
  is invisible to the evaluator. No network, no file reading outside the snapshot in evaluation.
- Tunable knobs (optional, recommended for continuous choices such as damping strengths, neighbour counts, blend
  weights): declare up to 4 in `knobs.json` next to program.py, e.g.
  `{"trend_damping": {"low": 0.2, "high": 1.0, "default": 0.6}, "k": {"low": 10, "high": 200, "default": 50, "type": "int", "log": true}}`
  and read them as `context['params'].get('trend_damping', 0.6)` (`context['params']` is `{}` unless tuned). After
  your session the harness runs Optuna on these knobs (validation objective, confirmed on a second seed) and the tuned
  version competes for the round checkpoint. Spend your own evaluations on structural ideas, not on fine-tuning numbers.
  Do not write `tuned_params.json` yourself.
- Limits per configuration: 30 min wall time (45 min for the test configuration, whose last input E10.5 has
  ~168k cells), 20 GB memory, 4 CPU threads.

## Configurations your program is run on
1. **Validation (scored for you via `python tools/evaluate.py`)**: inputs E8.25, E8.75, E9.5 -> target_time 10.5,
   max_cells 25,179, run twice:
   - `val_all`: dissection 'heart_with_surroundings', target = the full E10.5 sample (the official
     T2:heart:val_extrap board).
   - `val_heart`: dissection 'heart_chambers_only', target = E10.5 cells whose celltype matches
     `CM$|^Chamber-Endo$|EndoMT|^Epi$|^Proepi$|^DMP$` (cardiomyocytes of every chamber, endocardium, cushion/valve
     EndoMT, (pro)epicardium, dorsal mesenchymal protrusion), a stand-in for the E12.5 chambers-only dissection.
     The real E12.5 dissection may differ somewhat from this rule; do not overfit the rule.
   - validation score = mean of the two.
2. **Final test (the submission)**: inputs E8.25, E8.5, E8.75, E9.5, E10.5 -> target_time 12.5, dissection
   'heart_chambers_only', max_cells 34,641. Check that your program runs there with `python tools/testcheck.py`
   (pass/fail only).
3. **Hidden held-out check (decides the final pick)**: a different configuration (other stages and target time,
   possibly an input stage you have never seen, both dissection modes). Its data and scores are never shown to you. At
   the end of the run the checkpoint of every round (round 0 builder and the improvement rounds) is scored on it and
   the best one is submitted. A program that fails to run there is ineligible.

Therefore: write **general** code. Handle 2-5 inputs and any target time; handle unseen cell-type labels; derive every
quantity (rates, proportions, scales, cell-type roles) from the inputs given at call time. Do not hardcode numbers,
fractions, gene or cell-type lists that you read off a particular stage or that only make sense for one stage pair.
Changes that help validation only through stage-specific constants will lose on the held-out check.

## Scoring (official scorer: veckit metrics via vec_local_score)
Each split is scored with 3 scoring seeds. The scorer subsamples each stage to 10% (reference capped near 4,000 cells,
target near 8,000) and splits the target in halves (one half scored against, one to estimate the ceiling). Each metric
is calibrated so that a copy of the reference stage (the last input: E9.5 in validation) scores about 50 and the
target's own split-half about 100. Points are weighted: de_score 0.125, de_direction 0.125 (pseudobulk expression
change versus the reference: which genes, which direction), mmd_u 0.15 (cell-state distribution, PCA space),
variogram 0.10 (gene-gene co-variation), d2_shape, occupancy_dice, scale_log_ratio 0.0833 each (3D shape, occupancy,
physical size), neighborhood_mmd 0.25 (spatial neighbourhood composition). Structure gate: the three shape terms are
multiplied by min(1, neighborhood_mmd skill / 50). The copy-last template in your first workspace scores about 50.

## Tools and budget
- `python tools/evaluate.py --note "..."`: snapshot + validation score (about 1-10 min, queued, one at a time).
  Budget: 60 evaluations this round. `python tools/evaluate.py --history`: free.
- `python tools/testcheck.py`: test-configuration run check, 12 per round.
- Time budget this round: 4 hours of active work; the evaluation tool prints the time left. When the
  budget ends your session is stopped. Your round's result is the best-validated program snapshot that also runs in
  the test and held-out configurations, so evaluate every version you want to count.
- Do not modify `tools/`. Do not read or try to read anything outside your workspace and the training data (the
  sandbox denies it and attempts are recorded in the transcript that is published as evidence).

## Prior knowledge and research
- `prior_knowledge/` holds everything the team learned in earlier runs (knowledge bank, run digests, reports, public
  leaderboard, earlier heart programs). Read `prior_knowledge/README.md` first and build on it.
- Web search and web fetch are ON. Research the literature (heart development E9.5-E12.5: chamber growth, trabeculation
  and compaction, septation, cushion/valve EndoMT, epicardium, coronary vessels, cell-type proportions and sizes),
  public method write-ups of this challenge, and modelling methods (optimal transport, trajectory inference, spatial
  generative models). Cite every source you use in NOTES.md (URL + what you took from it).

## Rules
- Challenge external-data rules (organisers): you may NOT use measured data (files, tables, or gene-level results read
  from papers) from mouse stages after E9.5 up to and including E13.5, nor from between E8.25 and E8.75 (heart) -
  E10.5 and E12.5 are excluded absolutely. Data after E13.5 is allowed if its source and stage are disclosed. General
  biological knowledge (what forms when, qualitative trends) is fine. Every external source must be listed in NOTES.md.
- Programs run offline in evaluation: any external data you are allowed to use must be distilled into small files or
  constants in your workspace, with its source documented.
- `tools/evaluate.py` is the official scored signal. Your own analyses of the training data are encouraged.
- Keep `NOTES.md` current: hypotheses, what you changed, each evaluation's result, what you concluded, and at the end a
  short summary of the final model. It is published with the run.
- Keep the code clean and documented; the final program is published as the method.
