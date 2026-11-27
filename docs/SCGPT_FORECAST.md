# scGPT donor-selection forecast

We tested whether a frozen scGPT representation improves retrospective mouse heart forecasting when the donor forecast is held fixed. This follows the [observed-cell retrieval probe](FIRST_PILOT.md), which measured a different outcome.

## Protocol

For each observed stage, sample 4,096 donor cells from its full observed population. Compare four arms using the same pools:

- **Uniform donor.** Draw observed donor profiles and their coordinates from the latest stage.
- **PCA.** Use the 474 mouse genes mapped to the checkpoint vocabulary, project the expression vectors to 32 components, and use cosine neighbors to estimate changes in cell-state frequencies.
- **Frozen scGPT.** Encode the same matched genes, project the embeddings to 32 components, and use the same cosine-neighbor forecast.
- **Random encoder.** Use the same scGPT architecture with randomly initialized weights, then use the same forecast.

Each arm takes the two most recent observed stages for its fold. Each 64-neighbor density estimate excludes the query cell itself. The forecast damps and clips the observed frequency changes and draws 3,000 real latest-stage profiles and their original positions with two paired prediction seeds. It outputs all 500 genes. The scorer uses three matched draws. The primary endpoint is the two-day E8.5-to-E10.5 chamber replay; the E9.5-to-E10.5 and E8.75-to-E9.5 chamber replays are shorter checks.

The predeclared rule advances scGPT for a gain of at least 0.75 headline points over PCA on the two-day replay, with nonnegative differences for both prediction seeds and no loss greater than 0.50 on either shorter replay. Both E10.5 folds share one target and are retrospective. The experiment isolates this donor-selection method. It does not measure a new chamber-placement or conditional-generation architecture.

## Results

| Chamber replay | Uniform donors | PCA | Frozen scGPT | Random encoder | scGPT − PCA |
|---|---:|---:|---:|---:|---:|
| E8.5 → E10.5 (two days) | 50.87 | 50.64 | 51.04 | 49.81 | +0.40 |
| E9.5 → E10.5 | 49.12 | 48.99 | 49.32 | 49.44 | +0.33 |
| E8.75 → E9.5 | 50.58 | 49.86 | 49.13 | 49.41 | -0.72 |

scGPT gained about 0.40 over PCA on the primary replay. The paired differences were +0.39 and +0.40, while the improvement over uniform donor sampling was only +0.18. The earlier E9.5 replay lost 0.72 against PCA. The method missed both the primary margin and the earlier-stage regression limit. The archived focused model scored 60.65 on the same primary replay and remains a stronger retrospective comparator.

Keep PCA as the representation baseline and leave the frozen scGPT donor selector out of the main heart run. The result applies to this forecast and checkpoint on the three registered retrospective replays. The experiment did not test an E12.5 outcome, condition-specific forecasting, or fine-tuning.

## Reproduce

```sh
OPENBLAS_NUM_THREADS=2 OMP_NUM_THREADS=2 .venv/bin/python experiments/scgpt_heart_forecast.py
```

The report is written to [results/scgpt_heart_forecast.json](../results/scgpt_heart_forecast.json). It includes checkpoint hashes, metrics, and paired differences.
