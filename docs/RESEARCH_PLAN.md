# Registered research plan

## Goal and comparison set

Build and publish a model for advancing measured developmental cell populations in time, predicting their spatial organization, and estimating held-out perturbation responses. Freeze the task protocol before comparing candidates. Measure leaderboard scores and scientific transfer separately.

| Board | Incumbent | Fifth Agent score to beat | Fifth Human score for context |
|---|---:|---:|---:|
| T1 temporal | 68.47 | 77.07 | 81.50 |
| T2 heart | 49.15 | 63.50 | 74.25 |
| T2 embryo | 69.14 | 71.16 | 80.12 |
| T3 | 68.08 | 68.93 | 76.69 |

The exact numbers and timestamp are in [the leaderboard snapshot](../results/top5_targets.json). These are goals for official hidden outputs. A higher retrospective replay score measures that replay.

## Four linked experiments

1. **Establish a fair heart comparison.** Run copy-last, cell-type crop, crop with bounded scale, and the archived focused model at a matched cell count. Run the latest-stage E10.5 replay and a two-day E10.5 forecast. Keep the E9.5 replay as a sensitivity check. Record the complete skill vector and paired differences. Run an offline E10.5 oracle diagnostic separately by substituting measured composition or measured geometry to quantify each component's potential contribution.
2. **Forecast heart chambers with a structured model.** Start with observed donor profiles paired to their local neighborhoods. Estimate chamber proportions separately from chamber geometry and size. Compare a fixed crop, cell-composition adjustment, local spatial adjustment, and their combination. Run a second arm with growth-aware state matching. Use the same loss, data, forecast horizon, candidate count, and compute budget for the direct comparison. Require incremental evidence before adding a neural flow.
3. **Compare specialists on the other boards and test a shared representation.** For T1, compare real-donor reweighting, within-lineage expression change, and covariance-aware transport. For T2 embryo, compare the two endpoint scaffolds and modest deformation with fixed expression; use the released E7.25 and E7.5 targets as retrospective tests on opposite sides of the bracket. For T3, compare the existing method with measured wild-type and simple response baselines on admissible held-out conditions. Score each condition independently. Compare PCA, an optional audited scGPT encoder, and a small native encoder with downstream models and training data held fixed.
4. **Freeze and test transfer.** Freeze candidate code and selection rules before reading the new target scores. Prefer different specimens of matched stage, dissection, species and assay. Where these are unavailable, report cross-study or cross-assay tests under their exact domain shift. The staged later Slide-seq samples are 2D section data and can test local programs and transfer of regions. The older whole-heart expression atlas is an expression-only cross-assay test. Check their prior use before assigning either to selection. Report each independent specimen as one unit. Prediction and scoring seeds measure technical variation.

The heart protocol is executable now through the AgenticScientist heart lane. The other experiments are research plans and imported components. The final publication analysis should report failures and leave-one-study-out or leave-one-stage-out results alongside the best scores.

## Shared model hypothesis

A shared model is worth testing. T1 and T2 both need an estimate of which expression states are present and how their frequencies change. T2 adds spatial placement. T3 adds a condition-specific response and should be allowed to fall back to a simple baseline. A common model can share:

- A gene-panel-aware encoder with missing-feature masks and assay indicators.
- An operator for changing the composition of a population with age or condition.
- A decoder that samples intact observed profiles, optionally adding a small learned residual.
- A coordinate and patch-placement head for spatial observations.

Test the same shared weights versus separately trained copies with comparable training resources, then remove each shared component in turn. Report changes on every task, including tasks harmed by sharing. A common repository or prompt alone gives no evidence about weight sharing.

## scGPT experiment

The [public vocabulary audit](../results/scgpt_public_vocab.json) maps 15,843/32,285 T1 genes, 475/500 T2 heart genes, 474/497 T2 embryo genes, and 475/500 T3 genes through strict one-to-one Mouse Genome Informatics homology classes. The public software vocabulary is a proxy. The [actual checkpoint audit](../results/scgpt_checkpoint_vocab.json) maps 15,807, 474, 473, and 474 genes respectively. Preserve the full mouse panel for outputs and scoring.

The [completed representation test](FIRST_PILOT.md) compared raw log expression and 32-component PCA with frozen scGPT for cell-type retrieval from E9.5 to observed E10.5, using identical matched genes and neighbors. Its endpoint is label retrieval on already measured expression. PCA beat frozen scGPT in retrieval. Keep that result as the baseline for deciding how much compute to spend on the foundation-model arm. The first forecasting test uses embeddings only to select donor states, while predictions and scoring continue in mouse gene space. Compare with PCA on the same matched genes, PCA on the full panel, and an untrained encoder of the same capacity. Use shared donor sampling, splits, seeds, and downstream code. The [matched-gene donor forecast](SCGPT_FORECAST.md) has completed. Frozen scGPT gained 0.40 points on the primary two-day replay and lost 0.72 on the earlier replay. It failed the registered advancement rule. The main heart run retains its existing representation. See [the model paper](https://doi.org/10.1038/s41592-024-02201-0) and [the original repository](https://github.com/bowang-lab/scGPT).

## Run sequencing

- **Completed:** paired heart control pilot, scGPT retrieval probe, isolated launch preflight and local export rehearsal.
- **First locked launch:** run the focused heart agent against the three controls. Reserve the last hour for selection and export. Review after it finishes.
- **Next locked launches:** stage candidate families and isolated evaluators for temporal, embryo, perturbation, and the shared representation. Keep stage, assay and eligibility inventories with the run. Use the public protocol's local check before handling any official file.
- **Before the article:** archive code and input hashes, split identities, training and prediction seeds, exact comparator definitions, complete metrics, and independent biological results. Use stage and sample holdouts to support transfer claims. Use the annotated bibliography for background and methods comparisons.

Apply the [official data and Agent Track rules](https://virtualembryo.ai/challenge/rules) to every eligible entry. Verify the checkpoint corpus before using learned weights. Final submissions and experimental work have separate timelines.
