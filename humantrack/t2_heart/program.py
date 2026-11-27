"""Forecast a dissected or surrounding-tissue heart from real latest-stage cells."""

import anndata as ad
import numpy as np
from scipy import sparse
from scipy.spatial import cKDTree


MAX_CELLS = 25_179
KNOBS = dict(k=24, bulk_weight=0.20, clip=0.60, jitter=0.15)
MIN_SUPPORT = 40
SUPPORT_PRIOR = 120
MIN_CORE = 100
ORGAN_BLEND = 0.45
SURROUND_BLEND = 0.40
SURROUND_TIMESCALE = 0.75
COMPOSITION_WEIGHT = 0.85
STAGE_DECAY = 0.75
FIELD_TIMESCALE = 0.35
MAX_GROWTH_RATE = 0.40
MIN_FIELD_RATE = -1.0
MIN_SIZE_MULTIPLIER = 0.80
MAX_SIZE_MULTIPLIER = 1.80


def labels(stage):
    return np.asarray(stage.obs['celltype']).astype(str)


def families(celltypes):
    """Pool stage-specific chamber labels only for estimating trends."""
    result = []
    for name in celltypes:
        key = name.lower().replace('/', '-').replace('_', '-')
        tokens = set(key.split('-'))
        if ('cm' in tokens and 'non' not in tokens) or key == 'vcm':
            group = 'ventricular muscle' if (tokens & {'lv', 'rv', 'v'} or key == 'vcm') else 'other muscle'
        elif tokens & {'endo', 'endocardium', 'endocardial', 'endomt', 'cush'}:
            group = 'endocardium'
        elif tokens & {'epi', 'epicardium', 'epicardial', 'proepi', 'proepicardium'}:
            group = 'epicardium'
        elif key in {'peri', 'pericardium'}:
            group = 'pericardium'
        elif 'endoth' in key or 'vec' in tokens or key == 'bec':
            group = 'vascular endothelium'
        else:
            group = name
        result.append(group)
    return np.asarray(result)


def grouped_bulk(stage, keys, genes):
    """Mean log expression and detection frequency of each observed population."""
    index = stage.var_names.get_indexer(genes)
    present = index >= 0
    x = sparse.csr_matrix(stage[:, index[present]].X, dtype=np.float32, copy=True)
    x.eliminate_zeros()
    result = {}
    for key in np.unique(keys):
        block = x[keys == key]
        if block.shape[0] >= MIN_SUPPORT:
            mean = np.full(len(genes), np.nan, dtype=np.float32)
            detection = np.full(len(genes), np.nan, dtype=np.float32)
            mean[present] = np.asarray(block.mean(axis=0)).ravel()
            detection[present] = np.asarray(block.getnnz(axis=0), dtype=np.float32) / block.shape[0]
            result[key] = (mean, detection, block.shape[0])
    return result


def recent_trend(key, summaries, elapsed, interval):
    """Estimate one interval's change, anchored to the latest group mean."""
    latest = summaries[-1].get(key)
    if latest is None:
        return None, 0.0
    shifts = np.zeros((2, len(latest[0])), dtype=np.float32)
    scales = np.zeros(len(latest[0]))
    supports = 0.0
    for stage, age in zip(summaries[:-1], elapsed):
        past = stage.get(key)
        if past is None:
            continue
        support = min(past[2], latest[2])
        time_weight = np.exp(-(age - interval) / STAGE_DECAY)
        weight = time_weight * support / (support + SUPPORT_PRIOR)
        present = np.isfinite(past[0])
        shifts[:, present] += weight * interval / age * (
            np.stack(latest[:2])[:, present] - np.stack(past[:2])[:, present]
        )
        scales[present] += weight
        supports += time_weight * support
    if not np.any(scales):
        return None, 0.0
    average = np.divide(shifts, scales, out=np.zeros_like(shifts), where=scales > 0)
    return average, supports / (supports + SUPPORT_PRIOR)


def expression_forecast(inputs, times, horizon, source, celltypes, groups, knobs, rng):
    latest = inputs[-1]
    x = sparse.csr_matrix(latest.X, dtype=np.float32)[source].toarray()
    interval = times[-1] - times[-2]
    if interval <= 0 or horizon <= 0 or knobs['bulk_weight'] == 0:
        return sparse.csr_matrix(x)

    exact, broad = [], []
    for stage in inputs:
        stage_labels = labels(stage)
        exact.append(grouped_bulk(stage, stage_labels, latest.var_names))
        broad.append(grouped_bulk(stage, families(stage_labels), latest.var_names))
    elapsed = times[-1] - np.asarray(times[:-1])
    # A two-interval saturation timescale limits extrapolation of past changes.
    strength = knobs['bulk_weight'] * horizon / (interval + 0.5 * horizon)
    donor_labels = celltypes[source]
    for name in np.unique(donor_labels):
        rows = np.flatnonzero(donor_labels == name)
        group = groups[source[rows[0]]]
        base = exact[-1].get(name, broad[-1].get(group))
        if base is None:
            continue
        within, reliability = recent_trend(name, exact, elapsed, interval)
        pooled, pool_reliability = recent_trend(group, broad, elapsed, interval)
        shift = np.zeros((2, latest.n_vars), dtype=np.float32)
        if within is not None:
            shift += reliability * within
        if pooled is not None:
            shift += (1 - reliability) * pool_reliability * pooled
        shift *= strength
        x[rows] = shift_profiles(x[rows], base, shift, knobs['clip'], rng)
    return sparse.csr_matrix(x)


def shift_profiles(x, base, shift, clip, rng):
    """Realise a bounded pseudobulk offset through detection and amplitude."""
    mean, detected, _ = base
    bulk_delta, detection_delta = shift
    frequency = np.clip(detected + detection_delta, 0.0, 1.0)
    drop = np.clip((detected - frequency) / np.maximum(detected, 1e-6), 0.0, clip)
    gain = np.clip((frequency - detected) / np.maximum(1 - detected, 1e-6), 0.0, clip)
    conditional = np.divide(mean, detected, out=np.zeros_like(mean), where=detected > 0)
    median = np.median(conditional[conditional > 0]) if np.any(conditional > 0) else 5.0
    conditional = np.where(conditional > 0, conditional, median)
    realised_frequency = detected * (1 - drop) + (1 - detected) * gain
    value_delta = np.clip(
        (bulk_delta - (realised_frequency - detected) * conditional) / np.maximum(realised_frequency, 0.05),
        -clip, clip,
    )
    detected_here = x > 0
    draws = rng.random(x.shape, dtype=np.float32)
    removed = detected_here & (draws < drop)
    added = ~detected_here & (draws < gain)
    shifted = np.where(detected_here, np.maximum(x + value_delta, 0), 0)
    shifted[removed] = 0
    np.copyto(shifted, conditional + value_delta, where=added)
    # Keep the original molecule budget of each row, including empty profiles.
    library = np.expm1(x).sum(axis=1, keepdims=True)
    np.expm1(shifted, out=shifted)
    total = shifted.sum(axis=1, keepdims=True)
    changed = (total[:, 0] > 0) & (library[:, 0] > 0)
    shifted[changed] *= library[changed] / total[changed]
    np.log1p(shifted, out=shifted)
    shifted[~changed] = x[~changed]
    return shifted


def rms(coords, robust=False):
    distances = np.sum((coords - coords.mean(axis=0)) ** 2, axis=1)
    if robust:
        distances = np.minimum(distances, np.quantile(distances, 0.95))
    return max(float(np.sqrt(distances.mean())), 1e-6)


def geometry_growth(inputs, times, horizon, groups, dissected):
    if horizon <= 0 or times[-1] <= times[-2]:
        return 1.0
    earlier, latest = inputs[-2:]
    a, b = (np.asarray(s.obsm['spatial_3D'], dtype=float) for s in (earlier, latest))
    interval = times[-1] - times[-2]
    field_rate = np.clip(np.log(rms(b) / rms(a)) / interval, MIN_FIELD_RATE, MAX_GROWTH_RATE)
    va, vb = families(labels(earlier)) == 'ventricular muscle', groups == 'ventricular muscle'
    core_rate = max(0, field_rate)
    if min(va.sum(), vb.sum()) >= MIN_CORE:
        core_rate = np.clip(np.log(rms(b[vb], True) / rms(a[va], True)) / interval, 0, MAX_GROWTH_RATE)
    field_weight = np.exp(-(horizon / FIELD_TIMESCALE) ** 2)
    if dissected:
        field_weight *= 0.5
    rate = field_weight * field_rate + (1 - field_weight) * core_rate
    return float(np.exp(np.clip(horizon * rate, np.log(MIN_SIZE_MULTIPLIER), np.log(MAX_SIZE_MULTIPLIER))))


def donor_probabilities(inputs, times, horizon, coords, groups, celltypes, dissected, k):
    n = len(coords)
    p = np.full(n, 1 / n)
    interval = times[-1] - times[-2]
    if interval > 0 and horizon > 0:
        group_names, inverse, counts = np.unique(groups, return_inverse=True, return_counts=True)
        latest_share = counts / n
        weighted_rates = np.zeros(len(counts))
        support = 0.0
        for stage, time in zip(inputs[:-1], times[:-1]):
            old_groups, old_counts = np.unique(families(labels(stage)), return_counts=True)
            old = dict(zip(old_groups, old_counts))
            old_counts = np.array([old.get(g, 0) for g in group_names])
            old_share = old_counts / stage.n_obs
            overlap = np.minimum(old_counts, counts)
            elapsed = times[-1] - time
            confidence = overlap / (overlap + SUPPORT_PRIOR)
            weight = np.exp(-(elapsed - interval) / STAGE_DECAY)
            fold = np.log((latest_share + 0.001) / (old_share + 0.001))
            weighted_rates += weight * confidence * np.clip(fold, -1.2, 1.2) * interval / elapsed
            support += weight
        shift = COMPOSITION_WEIGHT * horizon / (interval + 0.5 * horizon) * weighted_rates / support
        p *= np.exp(shift[inverse])
        p /= p.sum()
    # With surrounding tissue, a growing heart occupies more of the sample.
    # Keep this long-horizon prior weaker than the explicit dissection blend.
    blend = ORGAN_BLEND if dissected else SURROUND_BLEND * horizon / (SURROUND_TIMESCALE + horizon)
    if blend:
        resident = np.isin(groups, ('ventricular muscle', 'other muscle', 'endocardium',
                                    'epicardium', 'pericardium', 'vascular endothelium'))
        resident |= np.isin(celltypes, ('JCF', 'DMP'))
        if resident.sum() >= MIN_CORE:
            nearby = cKDTree(coords).query(coords, k=min(k, n))[1]
            local = resident[nearby].reshape(n, -1).mean(axis=1)
            score = p * (0.5 * resident + 0.5 * local)
            p = (1 - blend) * p + blend * score / score.sum()
    return p


def draw_donors(p, count, rng):
    # Systematic draws preserve the fitted donor masses with little draw noise.
    order = rng.permutation(len(p))
    cdf = np.cumsum(p[order])
    cdf[-1] = 1.0
    quantiles = (np.arange(count) + rng.random()) / count
    return rng.permutation(order[np.searchsorted(cdf, quantiles)])


def predict(board, inputs, times, target_time, context):
    if board != 'heart':
        raise ValueError(f'Unsupported board: {board}')
    latest = inputs[-1]
    knobs = KNOBS | context.get('params', {})
    horizon = max(0.0, target_time - times[-1])
    celltypes = labels(latest)
    groups = families(celltypes)
    coords = np.asarray(latest.obsm['spatial_3D'], dtype=float)
    dissected = context.get('sampling') in ('heart_dissected', 'heart_chambers')
    k = max(2, int(knobs['k']))
    rng_donors, rng_expr, rng_jitter = [
        np.random.default_rng(s) for s in np.random.SeedSequence(context['seed']).spawn(3)
    ]
    probabilities = donor_probabilities(inputs, times, horizon, coords, groups, celltypes, dissected, k)
    source = draw_donors(probabilities, MAX_CELLS, rng_donors)
    position = coords[source].copy()
    copied = np.ones(len(source), dtype=bool)
    copied[np.unique(source, return_index=True)[1]] = False
    if np.any(copied) and knobs['jitter'] > 0 and len(coords) > 1:
        distance = cKDTree(coords).query(position[copied], k=min(k, len(coords)))[0][:, -1]
        noise = rng_jitter.uniform(-1, 1, (copied.sum(), 3))
        position[copied] += knobs['jitter'] * distance[:, None] * noise
    multiplier = geometry_growth(inputs, times, horizon, groups, dissected)
    center = position.mean(axis=0)
    position = (position - center) * (multiplier * rms(coords) / rms(position)) + center
    expression = expression_forecast(inputs, times, horizon, source, celltypes, groups, knobs, rng_expr)
    obs = latest.obs.iloc[source][['celltype']].copy()
    obs.index = [f'pred_{i}' for i in range(len(source))]
    obs['source_row'] = source
    out = ad.AnnData(expression, obs=obs, var=latest.var.copy(),
                     obsm={'spatial_3D': position.astype(np.float32)})
    out.uns['size_multiplier'] = multiplier
    return out
