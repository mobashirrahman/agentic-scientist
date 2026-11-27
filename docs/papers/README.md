# Literature and experiments

Run `python scripts/fetch_references.py` to cache the accessible PDFs and write their hashes locally. The cache is for reading. Cite the publisher or proceedings on publication. See [the bibliography](references.bib).

| Method | What the paper demonstrates | Candidate for this study |
|---|---|---|
| [Waddington-OT](https://doi.org/10.1016/j.cell.2019.01.006) | Estimates growth-aware couplings between populations observed at different times. | Match states in consecutive observed stages. Carry intact donor profiles into a separately tested extrapolation model. |
| [moscot](https://doi.org/10.1038/s41586-024-08453-2) | Scalable optimal transport across modalities. Includes a mouse developmental trajectory application. | Compare lineage-restricted population matching against a simple prevalence trend. |
| [DeST-OT](https://doi.org/10.1016/j.cels.2024.12.001) | Jointly registers measured spatial transcriptomics and accommodates changing population mass. | Compare patch matching based on expression and local geometry. Extrapolate the registered changes separately from the coupling. |
| [TIGON](https://doi.org/10.1038/s42256-023-00763-w) and [TrajectoryNet](https://proceedings.mlr.press/v119/tong20a.html) | Learn continuous distributions over time, including growth in TIGON. | Test a small regularized flow after a static transport model has shown a benefit on held-out stages. |
| [scGPT](https://doi.org/10.1038/s41592-024-02201-0) | A pretrained transcriptomic transformer supports downstream single-cell tasks. Its recommended whole-human model was trained on human cells. | Use frozen embeddings as one feature set for donor retrieval and population matching. Keep mouse profiles as the output. |
| [Nicheformer](https://doi.org/10.1038/s41592-025-02814-z) | Learns from mouse and human spatial and dissociated data, with tasks probing neighborhood structure. | Use the architecture as a reference for a modality-aware encoder. Inventory pretraining data before staging any weights. |
| [State](https://pubmed.ncbi.nlm.nih.gov/42673963/) | Predicts response distributions across heterogeneous cell populations. | Test the architectural idea of aggregating a population separately from encoding individual cells. |
| [Independent foundation-model evaluation](https://doi.org/10.1186/s13059-025-03574-x) and [linear benchmark](https://doi.org/10.1038/s41592-025-02772-6) | Simple baselines sometimes exceed pretrained embeddings or deep perturbation predictors on the published benchmarks. | Fix strong PCA, empirical donor, no-change, and linear controls in advance. Measure what a representation adds under identical downstream code. |

The literature motivates these experiments. Performance reported on other organisms or assays does not establish a Virtual Embryo score.
