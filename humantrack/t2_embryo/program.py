"""Interpolate real expression profiles on one native embryo scaffold."""

import anndata as ad
import numpy as np
import pandas as pd
from scipy import sparse
from scipy.optimize import linear_sum_assignment
from scipy.spatial.distance import cdist
from sklearn.decomposition import TruncatedSVD


MAX_CELLS = 5_000
N_COMPONENTS = 24
SPATIAL_WEIGHT = 0.65
LINEAGE_PENALTY = 0.50
MIN_LANDMARK = 20
DEPTH_JUMP = 2.0
MAX_DEPTH_LOG_RATE = 0.75
RADIUS_CATCHUP_POWER = 4
PATCH_CENTERS = 32
PATCH_RADIUS = 0.25


def stratified_rows(labels, n, rng, priority=None):
    """Use largest-remainder quotas to retain the endpoint's label proportions."""
    if n == 0:
        return np.empty(0, dtype=int)
    _, codes, counts = np.unique(labels, return_inverse=True, return_counts=True)
    expected = counts * (n / len(labels))
    quotas = np.floor(expected).astype(int)
    remainder = n - quotas.sum()
    quotas[np.argsort(-(expected - quotas), kind='stable')[:remainder]] += 1
    draws = []
    for code, quota in enumerate(quotas):
        rows = np.flatnonzero(codes == code)
        if priority is None:
            first = rng.choice(rows, min(quota, len(rows)), replace=False)
        else:
            first = rows[np.argsort(-priority[rows], kind='stable')[:quota]]
        extra = rng.choice(rows, max(quota - len(rows), 0), replace=True)
        draws.append(np.concatenate((first, extra)))
    return rng.permutation(np.concatenate(draws))


def centered(coords):
    shifted = coords - coords.mean(axis=0)
    radius = max(float(np.sqrt(np.mean(np.sum(shifted ** 2, axis=1)))), 1e-6)
    return shifted / radius, radius


def register(left, right, left_labels, right_labels):
    """Use shared lineage landmarks to orient the two donor tissues."""
    left_marks, right_marks = [], []
    for name in np.intersect1d(left_labels, right_labels):
        a, b = left_labels == name, right_labels == name
        if name != 'Unknown' and min(a.sum(), b.sum()) >= MIN_LANDMARK:
            weight = (a.mean() * b.mean()) ** 0.25
            left_marks.append(weight * left[a].mean(axis=0))
            right_marks.append(weight * right[b].mean(axis=0))
    if len(left_marks) < 3:
        return right, 0.0
    covariance = np.asarray(right_marks).T @ np.asarray(left_marks)
    u, _, vt = np.linalg.svd(covariance)
    u[:, -1] *= np.sign(np.linalg.det(u @ vt))
    return right @ (u @ vt), SPATIAL_WEIGHT


def place_donors(left, right, left_labels, right_labels, slots, donors, pa, pb, fit_seed):
    """Match profiles and spatial landmarks with an exact one-to-one assignment."""
    x = sparse.vstack((left.X, right.X), format='csr', dtype=np.float32)
    rank = min(N_COMPONENTS, x.shape[1] - 1, x.shape[0] - 1)
    if rank > 0:
        latent = TruncatedSVD(n_components=rank, random_state=fit_seed).fit_transform(x)
        latent /= np.maximum(latent.std(axis=0), 0.25)
    else:
        latent = x.toarray()
    cost = cdist(latent[slots], latent[left.n_obs + donors], 'sqeuclidean') / latent.shape[1]
    aligned, spatial_weight = register(pa, pb, left_labels, right_labels)
    if spatial_weight:
        cost += spatial_weight * cdist(pa[slots], aligned[donors], 'sqeuclidean')
    shared = np.intersect1d(left_labels, right_labels)
    donor_labels = right_labels[donors]
    cost += LINEAGE_PENALTY * (
        (left_labels[slots, None] != donor_labels[None, :]) & np.isin(donor_labels, shared)[None, :]
    )
    _, order = linear_sum_assignment(cost)
    return donors[order]


def molecule_counts(x):
    """Recover relative integer counts from the lowest detected molecule tier."""
    linear = np.expm1(x.data)
    counts = np.empty(len(x.indices), dtype=np.int64)
    for start, stop in zip(x.indptr[:-1], x.indptr[1:]):
        if stop > start:
            values = linear[start:stop]
            counts[start:stop] = np.rint(values / values.min()).astype(counts.dtype)
    return sparse.csr_matrix((counts, x.indices, x.indptr), shape=x.shape)


def harmonize_depth(expression, is_late, duration, fraction, rng):
    """Thin later donors when the observed molecule budget jumps between assays."""
    x = expression.tocsr(copy=True)
    x.eliminate_zeros()
    early, late = ~is_late, is_late
    if not early.any() or not late.any():
        return x
    counts = molecule_counts(x)
    sizes = np.asarray(counts.sum(axis=1)).ravel()
    early_depth, late_depth = np.median(sizes[early]), np.median(sizes[late])
    if early_depth <= 0 or late_depth < DEPTH_JUMP * early_depth:
        return x
    # Use capped temporal depth growth, retaining differences between late cells.
    log_jump = np.log(late_depth / early_depth)
    ratio = np.exp(fraction * min(log_jump, MAX_DEPTH_LOG_RATE * duration) - log_jump)
    for row in np.flatnonzero(late & (sizes > 0)):
        start, stop = counts.indptr[row:row + 2]
        n = max(1, round(sizes[row] * ratio))
        sample = rng.multivariate_hypergeometric(counts.data[start:stop], n, method='marginals')
        x.data[start:stop] = np.log1p(sample * (10000 / n))
    x.eliminate_zeros()
    return x


def predict(board, inputs, times, target_time, context):
    if board != 'embryo':
        raise ValueError(f'Unsupported board: {board}')
    if len(times) < 2 or not times[0] <= target_time <= times[-1]:
        raise ValueError('Interpolation requires two stages bracketing the target')
    before = max(i for i, time in enumerate(times[:-1]) if time <= target_time)
    after = before + 1
    left, right = inputs[before], inputs[after]
    fraction = float(np.clip((target_time - times[before]) / (times[after] - times[before]), 0, 1))
    genes = left.var_names.union(right.var_names, sort=False)
    if not left.var_names.equals(right.var_names):
        aligned = ad.concat([left, right], join='outer', fill_value=0, index_unique='-')
        left, right = aligned[:left.n_obs, genes].copy(), aligned[left.n_obs:, genes].copy()
    left_labels = np.asarray(left.obs['celltype']).astype(str)
    right_labels = np.asarray(right.obs['celltype']).astype(str)
    pa, ra = centered(np.asarray(left.obsm['spatial_3D'], dtype=float))
    pb, rb = centered(np.asarray(right.obsm['spatial_3D'], dtype=float))
    # Early space grows with estimated cell mass. Field widening enters later.
    log_growth = np.log(rb / ra)
    radius = ra * np.exp(fraction * log_growth)
    if log_growth > 0 and right.n_obs > left.n_obs:
        mass_growth = min(log_growth, np.log(right.n_obs / left.n_obs) / 3)
        radius = ra * np.exp(fraction * mass_growth
                              + fraction ** RADIUS_CATCHUP_POWER * (log_growth - mass_growth))
    rng = np.random.default_rng(context['seed'])
    scaffold = stratified_rows(left_labels, MAX_CELLS, rng)
    right_count = round(fraction * len(scaffold))
    # Nearby sites tend to draw from the same endpoint within each type quota.
    patch_rng = np.random.default_rng([context['seed'], 7])
    centers = pa[patch_rng.choice(left.n_obs, min(PATCH_CENTERS, left.n_obs), replace=False)]
    affinity = np.exp(-cdist(pa[scaffold], centers, 'sqeuclidean') / (2 * PATCH_RADIUS ** 2))
    priority = affinity @ patch_rng.normal(size=len(centers)) / np.maximum(affinity.sum(axis=1), 1e-8)
    replace = stratified_rows(left_labels[scaffold], right_count, rng, priority)
    source = scaffold.copy()
    endpoint = np.zeros(len(scaffold), dtype=int)
    if right_count:
        donors = stratified_rows(right_labels, right_count, rng)
        source[replace] = place_donors(left, right, left_labels, right_labels,
                                       scaffold[replace], donors, pa, pb, context['fit_seed'])
        endpoint[replace] = 1
    x = sparse.vstack((left.X, right.X), format='csr')
    expression = harmonize_depth(x[source + endpoint * left.n_obs], endpoint == 1,
                                 times[after] - times[before], fraction, rng)
    celltypes = np.concatenate((left_labels, right_labels))[source + endpoint * left.n_obs]
    obs = pd.DataFrame({'celltype': celltypes, 'source_row': source,
                        'source_endpoint': endpoint, 'scaffold_row': scaffold},
                       index=[f'pred_{i}' for i in range(len(source))])
    out = ad.AnnData(expression, obs=obs, var=pd.DataFrame(index=genes),
                     obsm={'spatial_3D': (pa[scaffold] * radius).astype(np.float32)})
    out.uns['later_donor_fraction'] = float(endpoint.mean())
    out.uns['size_multiplier'] = float(radius / ra)
    return out
