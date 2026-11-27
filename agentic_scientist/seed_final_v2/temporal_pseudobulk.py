"""Bounded continuation of the observed pseudobulk interval trend on detected genes.

The forecast is made of real latest-stage donors, so every gene's level is frozen at the
latest observed stage. Development continues between stages: on the median-centred
log1p(CP10k) scale, the average detected transcript level of a gene moves by the difference
between consecutive pseudobulks (this net change contains both maturation of each lineage
and the shift of donor mass between lineages). We continue half of the last measured
interval, the same 0.5 damping the parent applies to its composition step, and cap each
gene at +/-0.35 log units so no single gene can double at any horizon.

Only entries that are already detected are shifted: the detection pattern (which genes a
cell expresses at all) carries a large part of the cell-state distribution that mmd_u and
the variogram reward, and the failed per-gene mean-tiling experiment showed that rewriting
the detection structure costs far more than the marginal fit it buys. Genes without
enough positive cells in both inputs get no shift at all.
"""

import numpy as np
from scipy import sparse

# Half of one observed interval: the parent's own composition damping.
STRENGTH = 0.5
# Per-gene bound: one gene may move at most +/-0.35 log units (a factor exp(0.35)=1.42).
LOG_CAP = 0.35
# A pseudobulk mean is only meaningful when the gene is actually measured in both inputs.
MIN_DETECTED = 30


def _stage_moments(stage):
    """Per-gene mean log1p(CP10k) and number of positive cells (sparse-safe)."""
    x = stage.X
    if sparse.issparse(x):
        mean = np.asarray(x.mean(axis=0)).ravel().astype(np.float64)
        detected = np.asarray(x.getnnz(axis=0)).ravel()
    else:
        dense = np.asarray(x)
        mean = dense.mean(axis=0, dtype=np.float64)
        detected = np.count_nonzero(dense > 0, axis=0)
    return mean, detected


def _align(earlier, latest):
    """Per-latest-gene index into the earlier stage's gene order, -1 when absent."""
    return earlier.var_names.get_indexer(latest.var_names)


def continue_pseudobulk_trend(earlier, latest, prediction, relative_horizon):
    """Add a bounded half-interval pseudobulk trend to detected entries of the forecast."""
    if prediction.n_obs == 0 or latest.n_vars == 0:
        return prediction
    old_mean, old_det = _stage_moments(earlier)
    new_mean, new_det = _stage_moments(latest)
    index = _align(earlier, latest)
    valid = index >= 0

    old_mean_full = np.zeros(latest.n_vars, dtype=np.float64)
    old_det_full = np.zeros(latest.n_vars, dtype=np.int64)
    old_mean_full[valid] = old_mean[index[valid]]
    old_det_full[valid] = old_det[index[valid]]

    supported = valid & (old_det_full >= MIN_DETECTED) & (new_det >= MIN_DETECTED)
    delta = new_mean - old_mean_full
    dose = STRENGTH * min(max(relative_horizon, 0.0), 1.0)
    shift = np.zeros(latest.n_vars, dtype=np.float32)
    shift[supported] = np.clip(dose * delta[supported], -LOG_CAP, LOG_CAP)
    if not np.any(shift):
        return prediction

    x = prediction.X.tocsr(copy=True)
    # Shift detected entries only; a zero stays zero, so the detection pattern is untouched.
    x.data = np.maximum(x.data + shift[x.indices], 0.0).astype(np.float32)
    prediction.X = x
    prediction.uns['pseudobulk_trend'] = float(dose)
    prediction.uns['pseudobulk_trend_genes'] = int(np.count_nonzero(shift))
    return prediction
