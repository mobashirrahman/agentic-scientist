"""Continue the forecast's expression program along the vetted late-anchor maturation axis.

The forecast is made of real latest-stage donors, so its pseudobulk is frozen at the latest
observed stage. The parent continues half of the observed interval trend
(0.5 * (pb_latest - pb_earlier)) on genes that are already detected. That direction is a weak
predictor of the NEXT interval (on the released T1 series the two consecutive pseudobulk
differences correlate at only r = 0.12), because one interval of an embryonic series is noisy.

The vetted external late anchor gives a far better estimate of the direction in which the tissue
is maturing. `context['external']` for T1 is a Qiu-2024 subset with an early calibration block
(Theiler stage 12/13, which brackets our inputs) and a late anchor block (Theiler stage 23-25,
E14.5-E16.5). The per-gene pseudobulk difference between the two blocks is a maturation
direction measured within one source and pipeline, so the per-gene platform offset cancels.
On the released T1 series that direction agrees with the true E9.5->E10.5 pseudobulk change at
Pearson 0.45 (top-300 signed agreement 0.92, versus 0.59 for the observed one-interval trend) and
it is stable between the anchor's own late stages (r = 0.97).

We therefore keep the parent's bounded continuation but take most of its DIRECTION from the
anchor: unit(anchor difference) and unit(observed trend) are mixed 3:1, the result is rescaled to
the magnitude of the observed one-interval trend and dosed at the parent's 0.5 damping. This
defines a population-mean step across all nuclei. The step is divided by each gene's detection
prevalence among the selected donors before applying it to detected entries, with a +/-0.35 log
unit cap per entry. The interval-only module remains the fallback when the anchor is unusable.
"""

import numpy as np
from scipy import sparse

from temporal_pseudobulk import LOG_CAP, MIN_DETECTED, STRENGTH, _align, _stage_moments

# Share of the continuation direction taken from the vetted late anchor. The rest keeps the
# parent's accepted observed-trend channel so the emitted change stays inside one observed
# interval rather than being driven by a single source.
ANCHOR_SHARE = 0.75
# A stage block needs enough cells for a pseudobulk to be meaningful.
MIN_GROUP_CELLS = 200


def _stage_coordinate(obs):
    """Numeric developmental coordinate per external cell, from stage_days or a stage label."""
    if 'stage_days' in obs:
        days = np.asarray(obs['stage_days'], dtype=float)
        if np.isfinite(days).all():
            return days
    for key in ('development_stage', 'stage', 'age'):
        if key in obs:
            labels = [str(v) for v in obs[key].to_numpy()]
            values = []
            for text in labels:
                digits = ''.join(ch if ch.isdigit() or ch == '.' else ' ' for ch in text).split()
                values.append(float(digits[-1]) if digits else np.nan)
            values = np.asarray(values, dtype=float)
            if np.isfinite(values).any():
                return values
    return None


def _blocks(coordinate):
    """Boolean (early, late) masks: the two stage blocks separated by the largest gap."""
    finite = np.isfinite(coordinate)
    if finite.sum() < 2 * MIN_GROUP_CELLS:
        return None
    levels = np.unique(coordinate[finite])
    if len(levels) < 2:
        return None
    gaps = np.diff(levels)
    split = int(np.argmax(gaps))
    if gaps[split] <= 0:
        return None
    early = finite & (coordinate <= levels[split])
    late = finite & (coordinate > levels[split])
    if early.sum() < MIN_GROUP_CELLS or late.sum() < MIN_GROUP_CELLS:
        return None
    return early, late


def _group_pseudobulk(external, mask, gene_index):
    """Mean log1p(CP10k) and detected-cell count per gene of the latest input."""
    sub = external.X[mask]
    mean = np.asarray(sub.mean(axis=0)).ravel().astype(np.float64)
    if sparse.issparse(sub):
        detected = np.asarray(sub.getnnz(axis=0)).ravel()
    else:
        detected = np.count_nonzero(np.asarray(sub), axis=0)
    out_mean = np.zeros(len(gene_index), dtype=np.float64)
    out_det = np.zeros(len(gene_index), dtype=np.int64)
    present = gene_index >= 0
    out_mean[present] = mean[gene_index[present]]
    out_det[present] = detected[gene_index[present]]
    return out_mean, out_det


def anchor_direction(external, latest):
    """Unit maturation direction per latest-input gene, or None when the anchor is unusable."""
    if external is None or getattr(external, 'n_obs', 0) == 0 or latest.n_vars == 0:
        return None
    coordinate = _stage_coordinate(external.obs)
    if coordinate is None:
        return None
    blocks = _blocks(coordinate)
    if blocks is None:
        return None
    gene_index = external.var_names.get_indexer(latest.var_names)
    if (gene_index >= 0).sum() < 100:
        return None
    early_mean, early_det = _group_pseudobulk(external, blocks[0], gene_index)
    late_mean, late_det = _group_pseudobulk(external, blocks[1], gene_index)
    measured = (gene_index >= 0) & (early_det >= MIN_DETECTED) & (late_det >= MIN_DETECTED)
    if measured.sum() < 100:
        return None
    delta = np.zeros(latest.n_vars, dtype=np.float64)
    delta[measured] = late_mean[measured] - early_mean[measured]
    norm = np.linalg.norm(delta)
    if not np.isfinite(norm) or norm < 1e-8:
        return None
    return delta / norm


def continue_with_anchor(earlier, latest, prediction, relative_horizon, external):
    """Anchor-directed, bounded continuation of the observed interval. None = use the parent term."""
    direction = anchor_direction(external, latest)
    if direction is None or prediction.n_obs == 0:
        return None
    old_mean, old_det = _stage_moments(earlier)
    new_mean, new_det = _stage_moments(latest)
    index = _align(earlier, latest)
    valid = index >= 0
    old_full = np.zeros(latest.n_vars, dtype=np.float64)
    old_det_full = np.zeros(latest.n_vars, dtype=np.int64)
    old_full[valid] = old_mean[index[valid]]
    old_det_full[valid] = old_det[index[valid]]
    supported = valid & (old_det_full >= MIN_DETECTED) & (new_det >= MIN_DETECTED)
    if supported.sum() < 100:
        return None

    observed = np.zeros(latest.n_vars, dtype=np.float64)
    observed[supported] = new_mean[supported] - old_full[supported]
    magnitude = np.linalg.norm(observed)
    if not np.isfinite(magnitude) or magnitude < 1e-8:
        return None
    # Unit directions over their own support; the observed one is zero outside `supported`.
    observed_unit = observed / magnitude
    mixed = ANCHOR_SHARE * direction + (1.0 - ANCHOR_SHARE) * observed_unit

    dose = STRENGTH * min(max(relative_horizon, 0.0), 1.0)
    bulk_step = dose * magnitude * mixed
    x = sparse.csr_matrix(prediction.X, dtype=np.float32, copy=True)
    x.eliminate_zeros()
    prevalence = x.getnnz(axis=0) / prediction.n_obs

    # A shift of s in detected nuclei only changes the population mean by
    # prevalence * s. Let rare transcripts saturate at the existing cap.
    editable = supported & (prevalence > 0)
    shift = np.zeros(latest.n_vars, dtype=np.float32)
    shift[editable] = np.clip(bulk_step[editable] / prevalence[editable], -LOG_CAP, LOG_CAP)
    if not np.any(shift):
        return None

    x.data += shift[x.indices]
    np.maximum(x.data, 0.0, out=x.data)
    x.eliminate_zeros()
    prediction.X = x
    prediction.uns['anchor_trend'] = float(dose)
    prediction.uns['anchor_trend_genes'] = int(np.count_nonzero(shift))
    return prediction
