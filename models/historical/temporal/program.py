"""Empirical T1 sampler: fixed donor rows plus a bounded within-type step."""
import numpy as np

from sampling_shift import (CHAMBER_TYPES, COMPOSITION_EXPONENT, STEP_SCALE,
                       align_panel, apply_shift, estimate_shift, groups,
                       renormalize)


def _in_memory(stage):
    return stage.to_memory() if getattr(stage, 'isbacked', False) else stage


def predict(inputs, times, target_time, context):
    inputs = [_in_memory(stage) for stage in inputs]
    latest = inputs[-1]
    group_latest = groups(latest)
    types, inverse, counts = np.unique(group_latest, return_inverse=True, return_counts=True)

    # Composition weighting: extrapolate observed growth, but never increase
    # tissue that a heart-chamber dissection would remove.
    if len(inputs) >= 2:
        earlier = inputs[-2]
        group_earlier = groups(earlier)
        growth = np.zeros(len(types), dtype=np.float64)
        for k, label in enumerate(types):
            seen = int(np.sum(group_earlier == label))
            if seen < 25:
                growth[k] = np.log(2)
            else:
                growth[k] = np.clip(np.log((counts[k] / latest.n_obs) / (seen / earlier.n_obs)),
                                    -np.log(2), np.log(2))
            if label not in CHAMBER_TYPES:
                growth[k] = min(growth[k], 0.0)
        span = float(times[-1] - times[-2]) if len(times) >= 2 else 1.0
        horizon = min((float(target_time) - float(times[-1])) / max(span, 1.0), 2.0)
        horizon = max(horizon, 0.0)
        weights = np.exp(COMPOSITION_EXPONENT * horizon * growth[inverse])
    else:
        horizon = 0.0
        weights = np.ones(latest.n_obs)

    n = int(context.get('n', 3000))
    if context.get('min_cells') is not None:
        n = max(n, int(context['min_cells']))
    if context.get('max_cells') is not None:
        n = min(n, int(context['max_cells']))
    rng = np.random.default_rng(context.get('seed', 0))
    rows = rng.choice(latest.n_obs, n, replace=True, p=weights / weights.sum())
    out = latest[rows].copy()

    if len(inputs) >= 2:
        shift = estimate_shift(earlier, latest, group_earlier, group_latest)
        out.X = apply_shift(out.X, group_latest[rows], shift,
                            STEP_SCALE * horizon)
        out.X = renormalize(out.X)

    out.obs_names = [f'pred_{i}' for i in range(out.n_obs)]
    if context.get('genes') is not None:
        out = align_panel(out, context['genes'])
    return out
