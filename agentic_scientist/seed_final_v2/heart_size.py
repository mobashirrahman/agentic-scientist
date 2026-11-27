"""Bound the count-derived growth of a dissected heart using observed organ radii."""

import numpy as np


def _organ_radius(stage, keep):
    if keep is None or 'spatial_3D' not in stage.obsm:
        return None
    xyz = np.asarray(stage.obsm['spatial_3D'][keep], dtype=float)
    centered = xyz - xyz.mean(axis=0)
    radius = float(np.sqrt(np.mean(np.sum(centered ** 2, axis=1))))
    return radius if np.isfinite(radius) and radius > 0 else None


def grow_organ(out, inputs, times, target_time, organ_mask, latest_keep):
    """Isotropically scale the sampled cloud; return the factor applied."""
    if latest_keep is None or len(inputs) < 2 or len(times) != len(inputs):
        return 1.0
    interval = float(times[-1]) - float(times[-2])
    horizon = float(target_time) - float(times[-1])
    if not (np.isfinite(interval) and np.isfinite(horizon) and interval > 0 and horizon > 0):
        return 1.0

    previous_keep = organ_mask(inputs[-2])
    previous_rms = _organ_radius(inputs[-2], previous_keep)
    latest_rms = _organ_radius(inputs[-1], latest_keep)
    if previous_rms is None or latest_rms is None:
        return 1.0

    # At constant packing density, an organ's linear extent grows with the cube root of cell number.
    log_step = np.log(latest_keep.sum() / previous_keep.sum()) / 3.0
    if log_step <= 0:
        return 1.0

    radii = [previous_rms, latest_rms]
    for stage in inputs[:-2]:
        radius = _organ_radius(stage, organ_mask(stage))
        if radius is not None:
            radii.append(radius)
    lower, upper = min(radii), max(radii)
    # Earlier specimens bound the size already seen. Beyond that size, allow at most one
    # count-derived radial step, limited by the measured variation in organ radius.
    ceiling = upper + min(latest_rms * np.expm1(log_step), upper - lower)
    log_growth = min(log_step * (horizon / interval), np.log(ceiling / latest_rms))
    factor = float(np.exp(log_growth))
    if factor > 1.0:
        xyz = np.asarray(out.obsm['spatial_3D'], dtype=float)
        center = xyz.mean(axis=0)
        out.obsm['spatial_3D'] = center + (xyz - center) * factor
    return factor
