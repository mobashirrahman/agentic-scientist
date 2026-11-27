"""Select native donor cells using regularized Gaussian lineage transport."""

import numpy as np
from scipy import sparse
from sklearn.decomposition import PCA

FIT_CELLS_PER_STAGE = 1500
FEATURES = 2048
COMPONENTS = 12
TRANSPORTED_MASS = 0.5
LOG_LIKELIHOOD_CAP = np.log(4.0)


def _variance(x):
    squared = x.multiply(x) if sparse.issparse(x) else np.square(x)
    return np.asarray(squared.mean(axis=0)).ravel() - np.square(np.asarray(x.mean(axis=0)).ravel())


def _project(early, late, fit_seed):
    """Use a common PCA space with approximately equal representation of both stages."""
    rng = np.random.default_rng(fit_seed)
    sample_size = min(FIT_CELLS_PER_STAGE, early.shape[0], late.shape[0])
    old_sample = early[np.sort(rng.choice(early.shape[0], sample_size, replace=False))]
    new_sample = late[np.sort(rng.choice(late.shape[0], sample_size, replace=False))]
    variance = _variance(old_sample) + _variance(new_sample)
    features = np.argsort(variance, kind='stable')[-FEATURES:]
    basis_data = [x[:, features] for x in (old_sample, new_sample)]
    fit_data = np.vstack([x.toarray() if sparse.issparse(x) else x for x in basis_data])
    if not (variance[features] > 0).any():
        return None
    pca = PCA(n_components=min(COMPONENTS, len(features), fit_data.shape[0] - 1),
              svd_solver='randomized', random_state=fit_seed).fit(fit_data)
    center = pca.mean_ @ pca.components_.T
    return tuple(x[:, features] @ pca.components_.T - center for x in (early, late))


def _gaussian_tilt(early, late, step):
    """Continue the Gaussian map in latest-whitened coordinates."""
    center = late.mean(axis=0, dtype=np.float64)
    old = early - early.mean(axis=0, dtype=np.float64)
    new = late - center
    cov_late = new.T @ new / len(new)
    ridge = 0.05 * np.trace(cov_late) / cov_late.shape[0] + 1e-6
    eigenvalues, axes = np.linalg.eigh(cov_late)
    whiten = axes / np.sqrt(np.maximum(eigenvalues, 0.0) + ridge)

    # With regularized latest covariance equal to I, the quadratic Gaussian
    # transport map scales each early covariance axis by its inverse SD.
    cov_early = old.T @ old / len(old)
    cov_early.flat[::cov_early.shape[0] + 1] += ridge
    values, directions = np.linalg.eigh(whiten.T @ cov_early @ whiten)
    slope = np.clip(1.0 / np.sqrt(np.maximum(values, 1e-8)), 0.75, 4.0 / 3.0)
    forecast_sd = 1.0 + step * (slope - 1.0)
    late_scores = new @ whiten @ directions
    mean_drift = (center - early.mean(axis=0, dtype=np.float64)) @ whiten @ directions
    mean_drift /= max(1.0, np.linalg.norm(mean_drift) / 2.0)

    # Select measured cells near the forward state while preserving an
    # empirical component for cells outside the well-supported transport.
    residual = (late_scores - step * mean_drift) / forecast_sd
    log_ratio = 0.5 * np.sum(late_scores**2 - residual**2, axis=1) - np.log(forecast_sd).sum()
    ratio = np.exp(np.clip(log_ratio, -LOG_LIKELIHOOD_CAP, LOG_LIKELIHOOD_CAP))
    return (1.0 - TRANSPORTED_MASS) + TRANSPORTED_MASS * ratio / ratio.mean()


def maturity_weights(earlier, latest, old_lineages, new_lineages, n_lineages, step, fit_seed):
    """Return a mean-one donor tilt in each supported cardiac lineage."""
    old_core = old_lineages[old_lineages < n_lineages]
    new_core = new_lineages[new_lineages < n_lineages]
    tilt = np.ones(len(new_core))
    genes = latest.var_names[latest.var_names.isin(earlier.var_names)]
    if min(len(old_core), len(new_core)) < 2 or len(genes) == 0:
        return tilt
    old = earlier[old_lineages < n_lineages, genes].X
    new = latest[new_lineages < n_lineages, genes].X
    projected = _project(old, new, fit_seed)
    if projected is None:
        return tilt
    early_scores, late_scores = projected
    minimum = 3 * early_scores.shape[1]
    for lineage in range(n_lineages):
        was, now = old_core == lineage, new_core == lineage
        if min(was.sum(), now.sum()) >= minimum:
            tilt[now] = _gaussian_tilt(early_scores[was], late_scores[now], step)
    return tilt
