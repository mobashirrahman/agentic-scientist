"""Time-damped fetal-heart expression and composition calibration on fixed sites."""

import re

import numpy as np
from scipy import sparse
from scipy.spatial import cKDTree
from scipy.stats import rankdata

BULK_DOSE_CAP = 0.30  # Public KBULKO30 recipe.
BULK_LOG_CAP = 0.35
LOCAL_LOG_CAP = 0.15
N_NEIGHBORS = 15
MIN_SUPPORT = 20
COMPARTMENTS = tuple(re.compile(pattern, re.I) for pattern in (
    r'(?:^|[-_ ])cm(?:$|[-_ ])|cardiomyoc|myocard',
    r'^endo$|chamber.endo|endocard|valvular.endothel|early.vec|endomt',
    r'^bec$|vascular.ec|vascular.endoth|intra.endoth|great artery endoth|lymphatic.endoth',
    r'fibroblast|valvular.interstitial|cush|pericyte|smooth.muscle|epicard|^epi$|pericard|^peri$|^dmp$',
))


def _future_groups(atlas, target_time, section_key):
    obs = getattr(atlas, 'obs', None)
    if obs is None or 'stage_days' not in obs or section_key not in obs:
        return []
    days = np.asarray(obs['stage_days'], dtype=float)
    sections = np.asarray(obs[section_key])
    future = np.isfinite(days) & (days > target_time)
    groups = []
    for section in np.unique(sections[future]):
        rows = np.flatnonzero(future & (sections == section))
        if rows.size:
            groups.append((float(np.min(days[rows])), rows))
    return groups


def maturation_plan(inputs, times, target_time, context):
    """Find later anchor cohorts and scale their influence by elapsed forecast time."""
    latest_time = float(times[-1])
    horizon = float(target_time) - latest_time
    if len(times) != len(inputs) or not np.isfinite(horizon) or horizon <= 0:
        return None
    anchor = context.get('external')
    groups = _future_groups(anchor, target_time, 'stage_days')
    if not groups:
        return None
    spatial = context.get('external_spatial')
    sections = _future_groups(spatial, target_time, 'anchor_source')
    dose = min(BULK_DOSE_CAP, horizon / (min(day for day, _ in groups) - latest_time))
    return anchor, groups, spatial, sections, dose


def _classes(adata, label_key):
    labels = adata.obs[label_key].astype(str)
    unknown = len(COMPARTMENTS)
    classes = np.full(adata.n_obs, unknown, dtype=np.intp)
    for index, pattern in enumerate(COMPARTMENTS):
        keep = labels.str.contains(pattern, regex=True).to_numpy()
        classes[(classes == unknown) & keep] = index
    return classes


def _atlas_mix(atlas, cohorts):
    classes = _classes(atlas, 'cell_type')
    return np.median([
        np.bincount(classes[rows], minlength=len(COMPARTMENTS) + 1) / len(rows)
        for _, rows in cohorts
    ], axis=0)[:len(COMPARTMENTS)]


def refine_composition(out, plan, seed):
    """Swap a small number of profiles across a shared compartment boundary at fixed sites."""
    anchor, groups, spatial, sections, dose = plan
    if (not sections or 'celltype' not in out.obs or 'cell_type' not in anchor.obs
            or 'cell_type' not in spatial.obs):
        return out, 0

    codes = _classes(out, 'celltype')
    counts = np.bincount(codes, minlength=len(COMPARTMENTS) + 1)[:len(COMPARTMENTS)]
    fractions = counts / out.n_obs
    anchor_delta = _atlas_mix(anchor, groups) - fractions
    spatial_delta = _atlas_mix(spatial, sections) - fractions
    # Bead occupancy and dissociated cell abundance differ. Transfer only the common directional mass.
    supported = (counts >= MIN_SUPPORT) & (anchor_delta * spatial_delta > 0)
    shift = np.where(supported, np.sign(anchor_delta) * np.minimum(abs(anchor_delta), abs(spatial_delta)), 0)
    excess = np.maximum(-shift, 0)
    deficit = np.maximum(shift, 0)
    n = int(dose * min(excess.sum(), deficit.sum()) * out.n_obs)
    if n == 0:
        return out, 0

    rng = np.random.default_rng([int(seed), 19])
    removal_weight = np.append(excess / np.maximum(counts, 1), 0.0)[codes]
    replace = rng.choice(out.n_obs, n, replace=False, p=removal_weight / removal_weight.sum())
    destinations = rng.choice(len(COMPARTMENTS), n, p=deficit / deficit.sum())
    xyz = np.asarray(out.obsm['spatial_3D'])
    donors = np.arange(out.n_obs)
    for compartment in np.unique(destinations):
        rows = replace[destinations == compartment]
        sites = np.flatnonzero(codes == compartment)
        neighbors = cKDTree(xyz[sites]).query(xyz[rows], k=1)[1]
        donors[rows] = sites[neighbors]

    remixed = out[donors].copy()
    remixed.obs_names = out.obs_names.copy()
    remixed.obsm['spatial_3D'] = xyz.copy()
    return remixed, n


def _means(matrix):
    return np.asarray(matrix.mean(axis=0), dtype=np.float64).ravel()


def _trend(inputs, times, genes, organ_mask):
    """Use the depth-scaled full input trajectory to temper short-interval section effects."""
    observed_days, observed_means = [], []
    for stage, time in zip(inputs, times):
        keep = organ_mask(stage)
        if keep is None or not genes.isin(stage.var_names).all() or not np.isfinite(time):
            continue
        matrix = sparse.csr_matrix(stage[keep, genes].X)
        depth = float((matrix > 0).sum()) / matrix.shape[0]
        if depth > 0:
            observed_days.append(float(time))
            observed_means.append(_means(matrix) / depth)
            latest_depth = depth
    if len(observed_days) < 2:
        return np.zeros(len(genes))
    time = np.asarray(observed_days)
    centered = time - time.mean()
    sum_squares = centered @ centered
    if sum_squares <= 0:
        return np.zeros(len(genes))
    slope = (centered @ np.asarray(observed_means)) * (latest_depth / sum_squares)
    return slope - np.median(slope)


def _detection_field(detected, coords):
    """Average the 15 nearest *sites*, merging exact spatial repeats from donor oversampling."""
    sites, site_for_row, repeats = np.unique(coords, axis=0, return_inverse=True, return_counts=True)
    k = min(N_NEIGHBORS, len(sites) - 1)
    if k == 0:
        return None
    neighbors = cKDTree(sites).query(sites, k=k + 1)[1][:, 1:]
    n = len(sites)
    graph = sparse.csr_matrix((np.full(neighbors.size, 1.0 / k, dtype=np.float32),
                               (np.repeat(np.arange(n), k), neighbors.ravel())), shape=(n, n))
    if n == detected.shape[0]:
        return (graph @ detected[np.argsort(site_for_row)])[site_for_row]
    aggregate = sparse.csr_matrix((1.0 / repeats[site_for_row], (site_for_row, np.arange(len(site_for_row)))),
                                  shape=(n, len(site_for_row)), dtype=np.float32)
    return (graph @ (aggregate @ detected))[site_for_row]


def _enrichment(detected, field):
    n = detected.shape[0]
    count = np.asarray(detected.sum(axis=0)).ravel()
    prevalence = count / n
    valid = (count >= MIN_SUPPORT) & (n - count >= MIN_SUPPORT)
    covariance = _means(detected.multiply(field)) - prevalence * _means(field)
    lag = covariance / np.maximum(prevalence * (1.0 - prevalence), 1e-8)
    return lag, valid


def _local_shift(matrix, out, spatial, sections, dose):
    if len(sections) < 2 or 'spatial' not in spatial.obsm:
        return 0.0
    cols = np.flatnonzero(out.var_names.isin(spatial.var_names))
    if len(cols) == 0:
        return 0.0
    genes = out.var_names[cols]
    atlas_summaries = []
    for _, rows in sections:
        section = spatial[rows, genes]
        xy = np.asarray(section.obsm['spatial'], dtype=float)
        if not np.isfinite(xy).all():
            continue
        detected = sparse.csr_matrix(section.X > 0, dtype=np.float32)
        field = _detection_field(detected, xy)
        if field is not None:
            atlas_summaries.append(_enrichment(detected, field))
    if len(atlas_summaries) < 2:
        return 0.0

    detected = sparse.csr_matrix(matrix[:, cols] > 0, dtype=np.float32)
    field = _detection_field(detected, np.asarray(out.obsm['spatial_3D'], dtype=float))
    if field is None:
        return 0.0
    current, supported = _enrichment(detected, field)
    for _, valid in atlas_summaries:
        supported &= valid
    if supported.sum() < 2:
        return 0.0
    atlas_lags = np.array([lag[supported] for lag, _ in atlas_summaries])
    target_rank = np.median(rankdata(atlas_lags, axis=1), axis=0)
    rank_gap = (target_rank - rankdata(current[supported])) / supported.sum()
    weights = np.zeros(matrix.shape[1])
    weights[cols[supported]] = rank_gap

    # Centre the native local field over detected entries for each gene, so the local
    # contrast changes where a gene is expressed most strongly while retaining its bulk shift.
    field_cols = np.full(matrix.shape[1], -1, dtype=np.intp)
    field_cols[cols] = np.arange(len(cols))
    entry_cols = matrix.indices
    use = weights[entry_cols] != 0
    if not use.any():
        return 0.0
    entry_rows = np.repeat(np.arange(matrix.shape[0]), np.diff(matrix.indptr))[use]
    gene_cols = entry_cols[use]
    local = np.asarray(field[entry_rows, field_cols[gene_cols]]).ravel().astype(np.float64)
    counts = np.bincount(gene_cols, minlength=matrix.shape[1])
    totals = np.bincount(gene_cols, weights=local, minlength=matrix.shape[1])
    local -= (totals / np.maximum(counts, 1))[gene_cols]
    amplitude = np.full(matrix.shape[1], 0.1)
    np.maximum.at(amplitude, gene_cols, np.abs(local))
    shift = np.zeros(matrix.nnz)
    shift[use] = (LOCAL_LOG_CAP * dose / BULK_DOSE_CAP) * weights[gene_cols] * local / amplitude[gene_cols]
    return shift


def calibrate_expression(out, inputs, times, plan, organ_mask):
    """Apply a prevalence-calibrated bulk offset and a local contrast to existing detections."""
    anchor, cohorts, spatial, sections, dose = plan
    matrix = sparse.csr_matrix(out.X, dtype=np.float32, copy=True)
    matrix.eliminate_zeros()
    cols = np.flatnonzero(out.var_names.isin(anchor.var_names))
    step = np.zeros(matrix.shape[1])
    if len(cols) >= 50:
        genes = out.var_names[cols]
        current = _means(matrix)[cols]
        deltas = np.array([_means(anchor[rows, genes].X) - current for _, rows in cohorts])
        deltas -= np.median(deltas, axis=1, keepdims=True)
        weights = [1.0 / (day - float(times[-1])) for day, _ in cohorts]
        delta = np.average(deltas, axis=0, weights=weights)
        trend = _trend(inputs, times, genes, organ_mask)
        reinforcement = np.minimum(np.abs(trend) * (min(day for day, _ in cohorts) - times[-1]),
                                   np.abs(delta))
        delta += 0.20 * np.sign(delta) * reinforcement * (delta * trend > 0)
        prevalence = _means(matrix[:, cols] > 0)
        requested = np.divide(dose * delta, prevalence, out=np.zeros_like(delta), where=prevalence > 0)
        step[cols] = np.clip(requested, -BULK_LOG_CAP, BULK_LOG_CAP)

    local = _local_shift(matrix, out, spatial, sections, dose)
    requested = matrix.data + step[matrix.indices] + local
    matrix.data = np.maximum(requested, np.minimum(matrix.data, 1e-3)).astype(np.float32)
    out.X = matrix
