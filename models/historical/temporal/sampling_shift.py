"""Helpers for the empirical donor sampler with a bounded within-type step."""
import numpy as np
import scipy.sparse as sp

ALIASES = {
    'vCM': 'Ventricular cardiomyocyte', 'V-CM': 'Ventricular cardiomyocyte',
    'LV-CM': 'Ventricular cardiomyocyte', 'RV-CM': 'Ventricular cardiomyocyte',
    'OFT-CM': 'Outflow/right ventricular cardiomyocyte',
    'OFT/RV-CM': 'Outflow/right ventricular cardiomyocyte',
    'Peri': 'Pericardium', 'Proepi': 'Proepicardium',
    'Hepatocytes': 'Hepatocyte', 'SE': 'Surface Ectoderm',
    'Branch Arch': 'Branchial Arch', 'DMP': 'Dorsal mesenchymal protrusion',
    'DPM': 'Dorsal mesenchymal protrusion',
    'Dorsal-PAM': 'Paraxial Mesoderm', 'Lateral-PAM': 'Paraxial Mesoderm',
    'Chamber-Endo': 'Endocardium', 'Cush-EndoMT-Endo': 'Endocardium',
    'BEC': 'Endothelium', 'Great Artery Endoth': 'Endothelium',
    'early-VEC': 'Endothelium',
}

STEP_SCALE = 1.0          # fraction of the one-day posterior applied per day
EB_CLIP = 0.5             # per-gene bound on the one-day log1p step
FALLBACK_SCALE = 1.0      # shared step for types absent from the earlier stage
COMPOSITION_EXPONENT = 0.5
MIN_CELLS = 50
MAX_LOG1P = float(np.log1p(1e4))

# Groups plausibly retained by a more precise heart-chamber dissection.
CHAMBER_TYPES = {
    'Ventricular cardiomyocyte', 'Outflow/right ventricular cardiomyocyte',
    'AVC-CM', 'IFT-CM', 'SV-CM', 'Endocardium', 'Proepicardium',
    'Pericardium', 'NCC-derived', 'aSHF', 'pSHF', 'aPHM', 'pPHM',
    'Endothelium',
}


def groups(stage):
    return np.asarray([ALIASES.get(label, label) for label in stage.obs['celltype'].astype(str)])


def _mean_var(X):
    if sp.issparse(X):
        mean = np.asarray(X.mean(axis=0)).ravel()
        mean_sq = np.asarray(X.multiply(X).mean(axis=0)).ravel()
    else:
        mean = X.mean(axis=0)
        mean_sq = (X * X).mean(axis=0)
    return mean, np.maximum(mean_sq - mean * mean, 0.0)


def _aligned_stats(stage, rows, target_genes):
    """Mean/variance of `stage` rows on `target_genes`; absent genes flagged."""
    position = {str(g): i for i, g in enumerate(stage.var_names)}
    take = np.array([position.get(str(g), -1) for g in target_genes])
    present = take >= 0
    mean = np.zeros(len(target_genes), dtype=np.float64)
    var = np.zeros(len(target_genes), dtype=np.float64)
    if present.any():
        m, v = _mean_var(stage.X[rows][:, take[present]])
        mean[present] = m
        var[present] = v
    return mean, var, present


def estimate_shift(earlier, latest, group_earlier, group_latest):
    """Shrunk per-type log1p change between the two input stages.

    Groups measured in both stages get an empirical-Bayes per-gene step.
    Groups that only appear in the later stage receive the cell-weighted
    shared step, which keeps unsupported trajectories bounded rather than
    inventing type-specific directions.
    """
    target_genes = [str(g) for g in latest.var_names]
    shift, weights = {}, {}
    for label in np.unique(group_latest):
        i1 = np.flatnonzero(group_earlier == label)
        i2 = np.flatnonzero(group_latest == label)
        if len(i1) < MIN_CELLS or len(i2) < MIN_CELLS:
            continue
        m1, v1, present = _aligned_stats(earlier, i1, target_genes)
        m2, v2 = _mean_var(latest.X[i2])
        se2 = v1 / len(i1) + v2 / len(i2)
        delta = m2 - m1
        delta[~present] = 0.0
        tau2 = max(float(np.var(delta) - np.mean(se2)), 1e-6)
        post = delta * (tau2 / (tau2 + se2 + 1e-12))
        shift[label] = np.clip(post, -EB_CLIP, EB_CLIP).astype(np.float32)
        weights[label] = len(i2)
    if not shift:
        return shift
    total = float(sum(weights.values()))
    shared = sum(shift[k] * (weights[k] / total) for k in shift)
    for label in np.unique(group_latest):
        if label in shift or int(np.sum(group_latest == label)) < MIN_CELLS:
            continue
        shift[label] = np.clip(FALLBACK_SCALE * shared, -EB_CLIP, EB_CLIP).astype(np.float32)
    return shift


def apply_shift(matrix, row_types, shift, scale):
    """Multiplicative step on the log1p CP10k scale, applied to nonzeros.

    Zeros stay exactly zero and each cell's profile is scaled rather than
    rewritten, so donor-specific co-expression is retained.
    """
    if not sp.issparse(matrix):
        matrix = sp.csr_matrix(matrix)
    if scale == 0.0 or not shift:
        return matrix
    matrix = matrix.tocsr()
    indptr, indices, data = matrix.indptr, matrix.indices, matrix.data
    for label in np.unique(row_types):
        vector = shift.get(label)
        if vector is None:
            continue
        for row in np.flatnonzero(row_types == label):
            lo, hi = indptr[row], indptr[row + 1]
            if lo == hi:
                continue
            cols = indices[lo:hi]
            vals = np.log1p(np.expm1(data[lo:hi]) * np.exp(scale * vector[cols]))
            data[lo:hi] = np.clip(vals, 0.0, MAX_LOG1P)
    return matrix


def renormalize(matrix, target=1e4):
    """Return cells to exact log1p CP10k units after the step."""
    if not sp.issparse(matrix):
        matrix = sp.csr_matrix(matrix)
    matrix = matrix.tocsr()
    row = np.repeat(np.arange(matrix.shape[0]), np.diff(matrix.indptr))
    total = np.bincount(row, weights=np.expm1(matrix.data), minlength=matrix.shape[0])
    factor = target / np.maximum(total[row], 1e-12)
    matrix.data = np.log1p(np.expm1(matrix.data) * factor).astype(matrix.data.dtype, copy=False)
    return matrix


def align_panel(adata, genes):
    """Return an AnnData restricted to `genes` in the requested order."""
    genes = [str(g) for g in genes]
    present = [g for g in genes if g in adata.var_names]
    if len(present) == len(genes) and list(adata.var_names) == genes:
        return adata.copy()
    order = {gene: i for i, gene in enumerate(genes)}
    source = adata[:, present].X
    if sp.issparse(source):
        source = source.tocoo()
        column = np.array([order[present[c]] for c in source.col])
        X = sp.csr_matrix((source.data, (source.row, column)),
                          shape=(adata.n_obs, len(genes)), dtype=np.float32)
    else:
        X = np.zeros((adata.n_obs, len(genes)), dtype=np.float32)
        X[:, [order[g] for g in present]] = source
    from anndata import AnnData
    out = AnnData(X=X, obs=adata.obs.copy())
    out.var_names = genes
    return out
