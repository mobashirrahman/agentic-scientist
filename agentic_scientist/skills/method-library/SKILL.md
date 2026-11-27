---
name: method-library
description: Tested numpy/sklearn building blocks for predict() — PCA space, kNN label transfer, composition extrapolation and resampling, unbalanced entropic OT and OT drift, response rescaling for severity, spatial growth/rescale, Procrustes, neighbourhood profiles, patch resampling. Copy into your workspace.
---
# Method library

`cp $MG_ROOT/agentic_scientist/skills/method-library/recipes.py <ws>/` then `from recipes import ...`. It passes the static screen and is deterministic given seeds.

| Need | Function |
|---|---|
| shared latent space | `pca_space(arrays) -> (transform, gene_idx)` |
| label predicted cells | `knn_transfer(Z_ref, labels, Z_query)` |
| future composition | `extrapolate_fractions(frac_list, times, t, shrink)` + `resample_to_fractions(labels, frac, n)` |
| transport | `sinkhorn_unbalanced(a, b, C)`, `ot_drift(Z_early, Z_late)` (per-cell displacement) |
| response size (T3 severity) | `rescale_response(X_pred, X_ref, factor)`, `apply_pseudobulk_shift(X, shift)` |
| size growth (scale_log_ratio) | `growth_factor(radii, times, t)`, `rescale_coords(C, factor)`, `rms(C)` |
| alignment | `procrustes_align(A, B)` (det=+1, as the scorer's flips) |
| local structure (neighborhood_mmd, T2 gate) | `neighbourhood_profiles(C, labels, types)`, `patch_resample(C, n)` |

Our existing model code is in `$MG_ROOT/src/v2/` (LatentFlow, AnchorFlow, SpatialInterpolant, ComplexityPerturbation, ...); inspect APIs with the api-docs skill.
POT/moscot are not installed. Use these recipes, or write your own in numpy.
