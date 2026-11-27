# First AgenticScientist pilot

These are [paired local runs](../results/heart_control_pilot.json), using two prediction seeds, three scorer draws and a fixed 3,000-cell cap.

| Model | E9.5 to E10.5 chamber | E8.5 to E10.5 chamber | E8.75 to E9.5 chamber |
|---|---:|---:|---:|
| Copy last | 49.65 | 49.81 | 48.13 |
| Chamber-label crop | 40.76 | 40.77 | 57.89 |
| Crop with scale | 40.80 | 40.77 | 58.70 |
| Archived focused model | 62.52 | 60.65 | 68.81 |

This crop is one reproducible implementation. It uses the same fixed label rule at each stage. The leaderboard model with a crop description has an unverified crop and post-processing pipeline. Our crop gain on E9.5 reversed on E10.5, despite identical scoring budgets. Treat crop behavior as a hypothesis about dissection and annotation transfer. A distinct biological specimen would help distinguish transfer failure from peculiarities of one target.

The archived focused model led every local comparison. The 47.77 P3 outcome and the matching local subset illustrate the gap between retrospective and official results. The exact submitted SHA-256 remains unverified. Use this model as a demanding retrospective comparator with the caveats in the historical archive.

## scGPT checkpoint result

The [checkpoint vocabulary audit](../results/scgpt_checkpoint_vocab.json) found 474 of 500 heart genes and 15,807 of 32,285 T1 genes with strict one-to-one mouse-to-human mappings.

The [frozen checkpoint probe](../results/scgpt_heart_checkpoint_probe.json) compared four representations on the same 474 genes, 16 shared labels, 1,600 E9.5 reference cells and 1,600 observed E10.5 query cells. The model uses the official whole-human weights and pinned upstream Transformer and collation code, with native Torch attention. All 153 required encoder tensors were loaded and checked against the checkpoint.

| Representation | Macro-F1 | Balanced accuracy |
|---|---:|---:|
| 32-component PCA | 0.624 | 0.631 |
| Raw log expression | 0.614 | 0.631 |
| Frozen scGPT | 0.446 | 0.443 |
| Same scGPT architecture, random weights | 0.258 | 0.273 |

Pretraining improved retrieval relative to the random encoder, and PCA was stronger on this mouse MERFISH dataset. This result concerns same-label retrieval on observed expression. Forecasting would require a separate comparison with the same donor model, data and output genes.
