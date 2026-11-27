# Lab notebook (shared, distilled)

## w0_c00: Heart: separate empirical sampling diversity from spatial deformation [rejected, gain +0.31 <= tau 1.0]
```json
{"lesson": "Replacing the parent's with-replacement latest-stage sampler with duplicate-free (no-replacement / balanced-pass) sampling moved heart by only +0.07 on the 3-draw mean (per-draw range -0.97 to +0.66; aggregate proxy 173.99 vs 173.68, +0.31, below tau 1.0) — removing ~6% duplicate rows from 2.4e4 cells at n=3000 is below this panel's sampling noise. Disabling deformation was strictly harmful (-0.25 to -0.32 heart, 3/3 draws, both splits, coordinates only), while scale 0.5 vs 0 was worth +0.30/+0.31, which traces to a field-of-view artefact in the input-derived growth rate and is the real follow-up signal.",
 "tags": {"boards": ["heart"], "family": ["sampling", "spatial deformation", "growth scaling"]},
 "mechanism": "predict_heart now samples observed latest-stage cells without replacement (balanced permutations when n > n_obs), keeps the parent's centred geometry, strain-bounded deformation (0.25) and bounded scale growth (0.5, growth_rate = clip(log(rb/ra)/interval,-0.15,0.25)), with the LatentFlow fit restricted to the latest-order shared gene panel.",
 "retry_condition": "Retry only if (a) duplicate-driven variance is made to dominate the noise band (larger n relative to n_obs, a smaller/less redundant panel, or many more prediction and scoring draws), or (b) the experiment targets the growth term instead — an FOV-robust growth estimator or horizon-shrunk scale — since scale=0 was +0.30/+0.31 on both splits.",
 "method_lessons": [
  "A single official-dev-seed gain of +0.63 heart (~+0.31 proxy) shrank to +0.07 on the 3-draw mean; single-draw deltas must not be promoted past the aggregation tau.",
  "Pair predictions across configs (same seed) so prediction/expression noise cancels; the unpaired balanced-vs-parent comparison hid per-draw swings of -0.97 to +0.66.",
  "The critic-relevant distinction held: expression stays strictly empirical, so sampling diversity and spatial deformation are separable knobs — and the ablation showed the second knob is load-bearing (+0.32) while the first is null.",
  "Aggregate board score masks metric attribution: deformation moved only scale_log_ratio (+0.35/+0.39) and d2_shape (+0.05/+0.09) with occupancy Dice unchanged, i.e. it expands the cloud toward the larger target rather than improving expression.",
  "A positive but out-of-scope ablation (scale=0, +0.30/+0.31) should be recorded, not tuned in: its gain is exactly the copy_last floor for size and stems from a negative growth rate (earlier-stage RMS radius larger, a field-of-view difference), so it is unlikely to transfer.",
  "A null mechanism is not a licence to change unrelated knobs: the hypothesis proposed deformation=0, and the factorial showed that costs 0.25-0.32, so the parent value was retained and the final candidate differs from the parent only in the sampling rule."
 ],
 "impl_pitfalls": [
  "LatentFlow.__init__ slices earlier[:, latest.var_names], so any latest-stage gene absent from the earlier input raises KeyError; the output-side gene-union logic runs later and can never rescue the fit. Fit on latest-order shared-gene column slices of both stages instead.",
  "Slicing with earlier[:, shared].copy() / latest[:, shared].copy() preserves all cells, obs and obsm['spatial_3D'], so row order and therefore velocity[idx] still align with the empirically sampled rows — do not reindex rows separately.",
  "Guard the degenerate fit: with < max(16, 10% of the smaller panel) shared genes, skip the velocity field, set deformation=0, keep the spatial frame and bounded growth, and record uns['transport_gene_alignment']='insufficient-overlap'.",
  "Earlier-only genes must be appended as observed-zero CSR columns via sparse.hstack; never densify the 3000 x 500 matrix.",
  "Reuse the parent's exact centre, RMS-radius units and clip bounds from geometry()/LatentFlow rather than re-deriving a radius conversion from function names.",
  "Dev heart stages share one 500-gene panel, so the alignment bug was invisible on dev; test with released stage pairs that differ (E7.25 -> E8.75, latest-only Casp4/Pnliprp1) and with the reverse direction."
 ],
 "sources": ["https://pmc.ncbi.nlm.nih.gov/articles/PMC6402800/", "https://pmc.ncbi.nlm.nih.gov/articles/PMC6719697"]}
```
