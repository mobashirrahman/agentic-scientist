"""Select real latest-stage cells by kNN lineage transport toward the two-stage mean+covariance step.

Inside one cardiac lineage maturation is not a single Gaussian mode: the myocardium holds atrial,
ventricular, outflow-tract and atrioventricular-canal cardiomyocytes, the endocardial lineage holds
chamber endocardium and cushion mesenchyme. A parametric Gaussian density ratio tilts every cell
along one global direction of the lineage, whichever sub-state it belongs to. Here the same
two-skeleton step (the regularised Gaussian mean+covariance map between the two latest stages of
a lineage, continued by `step`) is applied to every measured cell as a POINT map, and each stepped
cell hands its mass to its k nearest measured cells of the same lineage. Mass therefore moves
locally along the lineage manifold: each sub-state feeds its own more mature neighbours, and a
cell stepped beyond the measured support lands on the leading edge of real cells.

The donor weight is the ratio of a cell's kNN in-degree from the stepped cloud to its in-degree
from the unstepped cloud. This is a local density ratio (forecast density / latest density), so a
zero step is an exact no-op and the hubness of kNN graphs in a multi-dimensional space cancels.
Only part of the mass is transported (partial transport), the ratio is bounded, and the caller
renormalises per lineage: lineage masses, and with them the cardiomyocyte share, never change.
"""

import numpy as np
from sklearn.neighbors import NearestNeighbors

from temporal_maturity import LOG_LIKELIHOOD_CAP, _project

# Neighbourhood that receives the mass of one stepped cell. Large enough that the in-degree ratio
# is a smooth density estimate, capped to a quarter of the lineage for small lineages.
NEIGHBOURS = 150
MAX_NEIGHBOUR_SHARE = 0.25
# Share of each lineage's mass that follows the stepped state; the rest keeps the measured
# latest-stage distribution. The transport stays partial even at 1: the density ratio is bounded
# to [1/4, 4] and damped by a pseudo-count, so no measured cell is ever removed. On the released
# series (E8.5, E9.5 skeletons -> E10.5) full mass moves each lineage as far toward its measured
# next-stage mean as the parametric tilt does, in a better aligned direction (cosine 0.38-0.39
# against 0.14-0.37) and with less donor concentration (effective sample 0.89-0.94 vs 0.80-0.84).
TRANSPORTED_MASS = 1.0


def _stepped_states(early, late, step):
    """Late cells moved by `step` of the lineage's regularised Gaussian early->late map."""
    center = late.mean(axis=0, dtype=np.float64)
    old = early - early.mean(axis=0, dtype=np.float64)
    new = late - center
    cov_late = new.T @ new / len(new)
    ridge = 0.05 * np.trace(cov_late) / cov_late.shape[0] + 1e-6
    eigenvalues, axes = np.linalg.eigh(cov_late)
    scale = np.sqrt(np.maximum(eigenvalues, 0.0) + ridge)
    whiten = axes / scale

    # In latest-whitened coordinates the Gaussian transport map scales each early covariance
    # axis by its inverse SD; the same bounded slopes and drift cap as the parametric tilt.
    cov_early = old.T @ old / len(old)
    cov_early.flat[::cov_early.shape[0] + 1] += ridge
    values, directions = np.linalg.eigh(whiten.T @ cov_early @ whiten)
    slope = np.clip(1.0 / np.sqrt(np.maximum(values, 1e-8)), 0.75, 4.0 / 3.0)
    to_axes = whiten @ directions
    mean_drift = (center - early.mean(axis=0, dtype=np.float64)) @ to_axes
    mean_drift /= max(1.0, np.linalg.norm(mean_drift) / 2.0)
    stepped = (new @ to_axes) * (1.0 + step * (slope - 1.0)) + step * mean_drift
    # Back to the shared expression space, where neighbours are measured.
    from_axes = directions.T @ (axes * scale).T
    return stepped @ from_axes + center


def _lineage_transport(early, late, step, neighbours, mass):
    """Mean-one donor weights of one lineage: stepped / unstepped kNN in-degree, partial."""
    k = int(min(neighbours, max(1, MAX_NEIGHBOUR_SHARE * len(late))))
    index = NearestNeighbors(n_neighbors=k).fit(late)
    received = np.bincount(index.kneighbors(_stepped_states(early, late, step),
                                            return_distance=False).ravel(), minlength=len(late))
    resident = np.bincount(index.kneighbors(late, return_distance=False).ravel(),
                           minlength=len(late))
    # One pseudo-count neighbourhood share keeps rarely visited cells finite and damped.
    log_ratio = np.log((received + 1.0) / (resident + 1.0))
    ratio = np.exp(np.clip(log_ratio, -LOG_LIKELIHOOD_CAP, LOG_LIKELIHOOD_CAP))
    return (1.0 - mass) + mass * ratio / ratio.mean()


def transport_weights(earlier, latest, old_lineages, new_lineages, n_lineages, step, fit_seed,
                      neighbours=NEIGHBOURS, mass=TRANSPORTED_MASS):
    """Return a mean-one kNN-transport donor tilt in each supported cardiac lineage."""
    old_core = old_lineages[old_lineages < n_lineages]
    new_core = new_lineages[new_lineages < n_lineages]
    tilt = np.ones(len(new_core))
    genes = latest.var_names[latest.var_names.isin(earlier.var_names)]
    if min(len(old_core), len(new_core)) < 2 or len(genes) == 0 or step <= 0:
        return tilt
    old = earlier[old_lineages < n_lineages, genes].X
    new = latest[new_lineages < n_lineages, genes].X
    projected = _project(old, new, fit_seed)
    if projected is None:
        return tilt
    early_scores, late_scores = (np.asarray(scores, dtype=np.float64) for scores in projected)
    minimum = 3 * early_scores.shape[1]
    for lineage in range(n_lineages):
        was, now = old_core == lineage, new_core == lineage
        if min(was.sum(), now.sum()) >= minimum:
            tilt[now] = _lineage_transport(early_scores[was], late_scores[now], step,
                                           neighbours, float(np.clip(mass, 0.0, 1.0)))
    return tilt
