"""Per-lineage calibration of the latent state-shift amplitude (T1 temporal board).

Problem addressed
-----------------
``LatentFlow.predict`` realises a *fixed* fraction of the learned velocity field:
``shift = state * min(horizon/interval, 2) * velocity`` with ``state = 0.35`` and a
hard per-gene clip of +/-0.35 log.  The velocity is a Waddington-OT-style
transport field in the model's own latent space (Schiebinger et al. 2019,
Cell 176:928 use couplings between time points to move whole populations;
Tong et al. 2020, TrajectoryNet, constrains dynamic-OT trajectories to reproduce
the observed marginals; Qiu et al. 2022, Nat Genet 54:328 describe per-lineage
transcriptional velocities across the E8.5-E9.5 bridge).  The seed realises only
a damped, clipped slice of that field, so the generated whole population stays
near the latest input: the recorded pseudobulk magnitude ratio against the
observed interval is only ~0.48-0.54.  MMD and the variogram see the full
distribution, so this residual under-travel is population-wide, not confined to
the lineages tuned by earlier cycles.

Calibration
-----------
The anchor is the *task's own observed interval*: for each lineage shared by the
two latent point clouds we measure how far the latest centroid actually moved
from the earlier centroid, ``d_obs``, and how far the parent's decoded shift
moves it, ``d_pred = state * min(horizon/interval, 2) * ||mean velocity||``.
The per-lineage gain

    kappa = clip(rho * d_obs * h_eff / d_pred, 1, 2.5),
    h_eff = min(horizon / interval, 1.5),

therefore makes the population travel ``rho`` times the *observed* interval
displacement (horizon-damped so that a longer horizon does not compound the
per-day step), never less than the parent (kappa >= 1) and never more than
2.5x.  The gain is multiplicative on the expression matrix
(``x *= exp(shift)``), so donor zeros stay zero, donor profiles stay real and
the RNG stream / donor weights / composition are untouched.  Only the amplitude
of the already-learned direction changes: the velocity *direction* is exactly
the parent's, which is why the change cannot flip a lineage's trajectory.

No-op guards (parent runs unchanged)
------------------------------------
* non-finite or non-positive interval / horizon;
* fewer than two lineages with >= 30 cells in both stages (no stable centroid);
* a lineage with < 30 cells keeps kappa = 1.
``rho`` is the declared knob ``state_gain_rho`` (default 0.8); the caps,
``h_eff`` and the per-lineage minimum are fixed a priori and were not swept.
"""
import numpy as np

# Parent's state coefficient and log-clip, mirrored from LatentFlow.predict.
STATE = 0.35
SHIFT_CLIP = 0.35
# A-priori bounds on the gain and its realised log-clip.
GAIN_MIN, GAIN_MAX = 1.0, 2.5
CLIP_MAX = 0.60
# Horizon damping for the *calibration* target only (per-day travel shrinks
# with the jump length, so a 2-3 day extrapolation cannot compound a 1-day step).
H_EFF_MAX = 1.5
# Statistical guards: a lineage centroid needs enough cells to be meaningful.
MIN_LINEAGE_CELLS = 30
MIN_SHARED = 2


def plan_state_gain(flow, horizon, interval, rho=0.8, state=STATE):
    """Per-source-cell multiplicative gain for the latent shift.

    Parameters
    ----------
    flow : LatentFlow (or AnchorFlow.flow)
        Fitted observed-stage transport; ``labels_a``/``labels_b``, ``za``/``zb``
        and ``velocity`` are the parent's own arrays (same latent space).
    horizon, interval : float
        Target jump and observed input interval, in days.
    rho : float
        Declared knob: fraction of the observed interval displacement the
        calibrated population should realise.

    Returns
    -------
    (row_gain, info) : (np.ndarray of shape (n_latest,), float32) or (None, info)
        ``row_gain`` multiplies ``velocity[idx]`` per source row; ``None`` means
        the parent path must run unchanged (kappa = 1 everywhere).
    info : dict
        Flat diagnostics (h5ad-serialisable) for ``uns['state_gain']``.
    """
    info = dict(enabled=0.0, rho=float(rho), factor=0.0, h_eff=0.0,
                n_shared=0.0, n_active=0.0, kappa_max=1.0, kappa_median=1.0,
                shift_clip=SHIFT_CLIP, n_cells=0.0,
                kappa_names=np.array([], dtype=str),
                kappa=np.array([], dtype=np.float64),
                d_obs=np.array([], dtype=np.float64),
                d_pred=np.array([], dtype=np.float64))
    # --- guards: invalid horizon/interval -> exact parent --------------------
    if not (np.isfinite(interval) and np.isfinite(horizon)):
        return None, info
    if interval <= 0 or horizon <= 0:
        return None, info
    if not (np.isfinite(rho) and rho > 0):
        return None, info
    labels_a = getattr(flow, 'labels_a', None)
    labels_b = getattr(flow, 'labels_b', None)
    za = getattr(flow, 'za', None)
    zb = getattr(flow, 'zb', None)
    velocity = getattr(flow, 'velocity', None)
    if any(v is None for v in (labels_a, labels_b, za, zb, velocity)):
        return None, info
    la = np.asarray(labels_a).astype(str)
    lb = np.asarray(labels_b).astype(str)
    za = np.asarray(za, dtype=np.float64)
    zb = np.asarray(zb, dtype=np.float64)
    velocity = np.asarray(velocity, dtype=np.float64)
    if za.ndim != 2 or zb.ndim != 2 or velocity.shape != zb.shape:
        return None, info
    if za.shape[0] != la.size or zb.shape[0] != lb.size:
        return None, info
    if not (np.all(np.isfinite(za)) and np.all(np.isfinite(zb))
            and np.all(np.isfinite(velocity))):
        return None, info

    # The parent's own horizon factor and the damped calibration horizon.  The
    # former is what d_pred must use (same shift the model will apply); the
    # latter keeps the target per-day displacement from growing with the jump.
    factor = min(horizon / interval, 2.0)
    h_eff = min(horizon / interval, H_EFF_MAX)

    # --- per-lineage observed vs predicted displacement ----------------------
    kappa = {}
    d_obs_map, d_pred_map = {}, {}
    for t in np.intersect1d(np.unique(la), np.unique(lb)):
        ma, mb = la == t, lb == t
        if ma.sum() < MIN_LINEAGE_CELLS or mb.sum() < MIN_LINEAGE_CELLS:
            continue
        # Both clouds live in the same whitened SVD latent the velocity uses.
        d_obs = float(np.linalg.norm(zb[mb].mean(0) - za[ma].mean(0)))
        d_pred = float(state * factor
                       * np.linalg.norm(velocity[mb].mean(0)))
        if not (np.isfinite(d_obs) and np.isfinite(d_pred)) or d_pred <= 1e-9:
            continue
        kappa[t] = float(np.clip(rho * d_obs * h_eff / d_pred,
                                 GAIN_MIN, GAIN_MAX))
        d_obs_map[t] = d_obs
        d_pred_map[t] = d_pred

    if len(kappa) < MIN_SHARED:
        return None, info

    names = sorted(kappa)
    kvals = np.array([kappa[t] for t in names], dtype=np.float64)
    row_gain = np.ones(lb.size, dtype=np.float32)
    for t in names:
        row_gain[lb == t] = np.float32(kappa[t])
    kappa_max = float(kvals.max())
    info.update(enabled=1.0, factor=float(factor), h_eff=float(h_eff),
                n_shared=float(len(names)),
                n_active=float(np.sum(kvals > GAIN_MIN + 1e-9)),
                kappa_max=kappa_max,
                kappa_median=float(np.median(kvals)),
                # Same a-priori rule as the plan: clip scales with the largest
                # realised gain, bounded at 0.6 log.
                shift_clip=float(min(SHIFT_CLIP * kappa_max, CLIP_MAX)),
                n_cells=float(lb.size),
                kappa_names=np.array(names, dtype=str),
                kappa=kvals,
                d_obs=np.array([d_obs_map[t] for t in names]),
                d_pred=np.array([d_pred_map[t] for t in names]))
    return row_gain, info
