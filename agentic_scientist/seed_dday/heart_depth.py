"""Match the detection-depth trend across input heart sections.

Later released sections detect fewer panel genes per cell, including within annotated
ventricular cardiomyocytes. Thinning models the change in measured depth on actual donor
profiles while keeping each cell's spatial location.

The decline decelerates (organ-resident detected genes/cell 79.5 -> 67.6 -> 58.4 -> 41.1 at
E8.25/E8.5/E8.75/E9.5; interval log rates -0.65, -0.59, -0.47 per day), so beyond the observed
input span the dose is continued as a damped approach to the inherited safety bound instead of
stopping at one span. This keeps long-horizon forecasts from emitting cells at the latest
input's too-deep library, while never thinning below the accepted 64% retention floor.
"""
import numpy as np
from scipy import sparse

MAX_LOG_DEPTH_CHANGE = 0.45   # safety bound: retain at least exp(-0.45) of the emitted mean detection depth
MIN_CURVATURE_RATE = 0.05     # only continue a decline the observed span already shows materially


def molecule_counts(expression):
    """Infer integer counts assuming the smallest positive entry per row encodes one molecule."""
    counts = sparse.csr_matrix(expression, dtype=np.float64, copy=True)
    counts.eliminate_zeros()
    np.expm1(counts.data, out=counts.data)
    for start, stop in zip(counts.indptr[:-1], counts.indptr[1:]):
        if start < stop:
            row = counts.data[start:stop]
            row /= row.min()
    rounded = np.rint(counts.data)
    if not counts.nnz or not np.allclose(counts.data, rounded, atol=1e-3, rtol=2e-6):
        return None
    counts.data = rounded.astype(np.int64)
    return counts


def _stage_depth(stage, organ_mask):
    """Mean detected genes per organ-resident cell (all cells if the stage lacks enough organ labels)."""
    if stage.n_obs == 0:
        return None
    keep = organ_mask(stage)
    X = stage.X if keep is None else stage.X[np.flatnonzero(keep)]
    detected = (sparse.csr_matrix(X) > 0).sum(axis=1) if sparse.issparse(X) else (np.asarray(X) > 0).sum(axis=1)
    depth = float(np.asarray(detected).mean())
    return depth if np.isfinite(depth) and depth > 0 else None


def _rate_decay_tau(t, y):
    """Time constant (days) of the decelerating log-depth decline, from the ratio of the last two
    measured interval rates: rate(t) ~ exp(-t/tau). None when <3 stages or no deceleration is seen."""
    if len(t) < 3:
        return None
    rates = np.diff(y) / np.diff(t)
    if not (rates[-2] < 0 and rates[-1] < 0):
        return None
    ratio = rates[-1] / rates[-2]
    if not (0.0 < ratio < 1.0):
        return None
    tau = float((t[-1] - t[-2]) / -np.log(ratio))
    return tau if np.isfinite(tau) and tau > 0 else None


def target_log_depth_change(inputs, times, target_time, organ_mask):
    """Log-linear depth trend over the inputs; beyond their span a damped continuation toward the
    thinning bound. Thinning only, with the accepted one-span linear dose as the h <= span case."""
    pts = [(float(t), np.log(d)) for a, t in zip(inputs, times)
           if np.isfinite(t) and (d := _stage_depth(a, organ_mask)) is not None]
    if len(pts) < 2:
        return 0.0
    t, y = np.array(pts).T
    span = t.max() - t.min()
    horizon = float(target_time) - float(times[-1])
    if span <= 0 or not np.isfinite(horizon) or horizon <= 0:
        return 0.0
    slope = np.polyfit(t, y, 1)[0]
    # Damping: the latest measured interval must also show the decline (a recent change of protocol or batch
    # that stops or reverses it switches thinning off), and the shallower of the two rates is used.
    if t[-1] > t[-2]:
        slope = max(slope, (y[-1] - y[-2]) / (t[-1] - t[-2]))
    if slope >= 0 or -slope * span < MIN_CURVATURE_RATE:
        return 0.0
    dose = slope * min(horizon, span)
    if horizon > span:
        # The measured decline decelerates, so the rate beyond the observed span is damped toward zero. Model the
        # total change as approaching the inherited thinning bound with a time constant fitted from the inputs'
        # own rate decay (rate ratio of the last two intervals); with only two stages, one observed span is the
        # only time unit available. The bound is a safety limit, not a fitted target: the realised dose at the
        # longest dev horizon is about -0.435, still short of it.
        tau = _rate_decay_tau(t, y)
        if tau is None:
            tau = span
        dose = dose + (-MAX_LOG_DEPTH_CHANGE - dose) * (1.0 - np.exp(-(horizon - span) / tau))
    return float(np.clip(dose, -MAX_LOG_DEPTH_CHANGE, 0.0))


def thin_to_depth(out, log_change, rng):
    """Binomially thin every emitted row with one retention probability so mean detected genes scale by
    exp(log_change); renormalise to log1p(CP10k). Returns the retention used (1.0 = unchanged)."""
    if log_change >= 0 or out.n_obs == 0:
        return 1.0
    counts = molecule_counts(out.X)
    if counts is None:
        return 1.0
    depth = counts.nnz / out.n_obs
    target = depth * np.exp(log_change)
    molecules, frequency = np.unique(counts.data, return_counts=True)
    frequency = frequency / out.n_obs

    # A gene with c molecules stays detected if at least one of its c molecules survives.
    low, high = 0.0, 1.0
    for _ in range(30):
        retention = (low + high) / 2.0
        if (1.0 - (1.0 - retention) ** molecules) @ frequency < target:
            low = retention
        else:
            high = retention
    retention = (low + high) / 2.0

    thinned = counts.copy()
    thinned.data = rng.binomial(thinned.data, retention).astype(np.float64)
    total = np.asarray(thinned.sum(axis=1)).ravel()
    empty = total <= 0
    scale = 1e4 / np.maximum(total, 1.0)
    normalized = sparse.csr_matrix(thinned.multiply(scale[:, None]))
    normalized.eliminate_zeros()
    np.log1p(normalized.data, out=normalized.data)
    if empty.any():  # a cell must keep at least one molecule: leave such rows as observed
        original = sparse.csr_matrix(out.X, dtype=np.float64)
        normalized = (sparse.diags((~empty).astype(float)) @ normalized
                      + sparse.diags(empty.astype(float)) @ original).tocsr()
    out.X = normalized.astype(np.float32)
    return retention
