"""Embryo geometry check (no target access): is the prediction ONE coherent embryo with midpoint proportions?

TEST evidence: the embryo board's occupancy_dice is all-or-nothing. A native, unstretched E7.5 scaffold
scored occupancy 3.7 (the floor IS the earlier bracket, and the attainable ceiling lies just above it); public
endpoint-mixture entries score 3-10; public entries that describe "E7.5 skeleton,
midpoint geometry" score 100. The shape metrics rotate every cloud onto its own principal axes, and between the
brackets the embryo's proportions change so much that the ORDER of those axes changes (E7.5: the section-stack axis
is the longest, E8.0: the shortest). The reference geometry is therefore one input embryo whose per-NATIVE-axis
spread is log-linearly interpolated between the brackets at the elapsed-time fraction (all stages share the native
imaging frame). The check is the official occupancy Dice of the prediction against that reference, best bracket.
"""
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'vendor/veckit'))


def midpoint_cloud(k, clouds, fraction):
    """Input embryo k with each native axis rescaled to the brackets' log-interpolated spread at `fraction`."""
    first = np.asarray(clouds[0], dtype=float)
    last = np.asarray(clouds[-1], dtype=float)
    q = np.asarray(clouds[k], dtype=float)
    q = q - q.mean(axis=0)
    wanted = np.exp((1.0 - fraction) * np.log(np.maximum(first.std(axis=0), 1e-9))
                    + fraction * np.log(np.maximum(last.std(axis=0), 1e-9)))
    return q * (wanted / np.maximum(q.std(axis=0), 1e-9))


def _fraction(times, target_time):
    span = float(times[-1]) - float(times[0])
    return float(np.clip((float(target_time) - float(times[0])) / span, 0.0, 1.0)) if span > 0 else 0.0


def native_occupancy(pred, inputs, seed=0, times=None, target_time=None):
    """Best occupancy Dice of the prediction against a bracket embryo in midpoint geometry (native geometry when
    no times are given)."""
    from common.shape_metrics import occupancy_dice
    p = np.asarray(pred.obsm['spatial_3D'], dtype=float)
    clouds = [np.asarray(a.obsm['spatial_3D'], dtype=float) for a in inputs]
    clouds = [q for q in clouds if len(q) and np.isfinite(q).all()]
    if not clouds:
        return 0.0
    if times is None or target_time is None or len(clouds) < 2:
        refs = clouds
    else:
        fraction = _fraction(times, target_time)
        refs = [midpoint_cloud(k, clouds, fraction) for k in (0, len(clouds) - 1)]
    return float(max(occupancy_dice(p, q, seed=seed)[0] for q in refs))
