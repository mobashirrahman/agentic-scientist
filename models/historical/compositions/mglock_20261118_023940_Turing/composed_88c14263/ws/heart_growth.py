"""Bounded, horizon-dependent size growth for the heart spatial board.

Why this file exists
--------------------
The parent's size law extrapolates the *whole observed cloud* RMS radius:

    L_parent = 0.5 * h * clip(log(R_field_latest / R_field_earlier) / dt)

That extent mixes real cardiac growth with the observation field: the released
heart stages are embryos whose dissection includes progressively less
surrounding tissue, so R_field can *fall* between two early stages while the
heart itself grows.  Extrapolating that fall predicts a shrinking heart (the
diagnosed parent is far too small on early/long horizons) and even at short
horizons it inherits the contraction.

Biology (Francou 2015; live-imaging reviews; ventricular-wall morphogenesis):
the anatomical cardiac compartment grows through progenitor deployment and
later ventricular expansion, while the extent of the surrounding tissue field
is dominated by how much non-cardiac tissue the section carries.  A short
observed whole-field trend therefore loses credibility as the horizon grows,
whereas the ventricular compartment supplies a stable long-horizon prior.

The frozen rule
---------------
g_field = log(R_field_latest / R_field_earlier) / dt      (same whole-cloud RMS
                                                          as heart_transport)
g_vent  = log(R_vent_latest  / R_vent_earlier)  / dt      (95%-winsorized
                                                          ventricular RMS)
g_vent  = clip(g_vent, -0.15, 0.25)                       (inherited rate cap)
a       = exp(-h / dt)                                    (fixed modelling
                                                          assumption, not a
                                                          fitted constant)
g       = a * g_field + (1 - a) * g_vent
h_eff   = min(h, 2 * dt)                                  (two-interval cap)
L       = clip(0.5 * h_eff * g, -log 1.3, +log 1.3)

So the observed field trend owns the short horizon and the anatomical
compartment owns the long horizon; the half-strength, rate cap, horizon cap
and final size bound keep the forecast conservative.  Only an isotropic
coordinate scale changes: the sampled expression, `source_row`, the RNG draws
and the local topology are untouched, so pairwise-distance shape ratios are
preserved exactly (up to float32 rounding).

No stage, split or target value enters this module: the plan is a function of
the passed coordinates, the passed interval and the positive horizon only.
"""
import numpy as np

from heart_transport import geometry, lineages

# Broad ventricular alias: lineages() maps LV-CM / RV-CM / vCM to V-CM.
VENTRICULAR = 'V-CM'
MIN_VENTRICULAR = 100
WINSOR_QUANTILE = 0.95
RATE_MIN = -0.15
RATE_MAX = 0.25
HALF_STRENGTH = 0.5
HORIZON_CAP_INTERVALS = 2.0
SIZE_BOUND = float(np.log(1.3))


def _coordinates(a):
    """Validated finite 3D (or at least 2D) coordinates, else None."""
    if a is None or 'spatial_3D' not in a.obsm:
        return None
    p = np.asarray(a.obsm['spatial_3D'], dtype=float)
    if p.ndim != 2 or p.shape[0] != a.n_obs or p.shape[1] < 2:
        return None
    if not np.all(np.isfinite(p)):
        return None
    return p


def field_radius(a):
    """Whole-cloud RMS radius, identical to heart_transport.geometry."""
    if _coordinates(a) is None:
        return None
    _, radius = geometry(a)
    radius = float(radius)
    return radius if np.isfinite(radius) and radius > 0 else None


def ventricular_radius(a):
    """Winsorized RMS radius of the ventricular compartment about its centre.

    The 95% winsorization stops a handful of extreme section-index or
    dissection-edge cells from setting the compartment's size trend (the
    unwinsorized and in-plane radii show the same positive trend), and the
    >=100-cell guard keeps the rate input-derived rather than degenerate.
    """
    p = _coordinates(a)
    if p is None or 'celltype' not in a.obs:
        return None
    mask = lineages(a) == VENTRICULAR
    if int(mask.sum()) < MIN_VENTRICULAR:
        return None
    q = p[mask]
    q = q - q.mean(0)
    d2 = np.sum(q * q, axis=1)
    d2 = d2[np.isfinite(d2)]
    if d2.size < MIN_VENTRICULAR:
        return None
    d2 = np.minimum(d2, np.quantile(d2, WINSOR_QUANTILE))
    radius = float(np.sqrt(d2.mean()))
    return radius if np.isfinite(radius) and radius > 0 else None


def growth_plan(earlier, latest, dt, h):
    """Bounded horizon-dependent log size multiplier; None-safe diagnostics.

    Returns a flat dict (safe for ``uns``) with ``applied`` 0/1.  ``log_scale``
    is None when any input guard fails, in which case the caller keeps the
    parent scalar law unchanged.
    """
    diag = dict(
        applied=0.0,
        interval=float(dt) if np.isfinite(dt) else 0.0,
        horizon=float(h) if np.isfinite(h) else 0.0,
        field_radius_earlier=0.0, field_radius_latest=0.0,
        ventricular_radius_earlier=0.0, ventricular_radius_latest=0.0,
        field_rate=0.0, ventricular_rate_raw=0.0, ventricular_rate=0.0,
        field_weight=0.0, rate=0.0, horizon_effective=0.0,
        log_scale_raw=0.0, log_scale=0.0, size_multiplier=1.0,
        clipped_rate=0.0, clipped_size=0.0, parent_log_scale=0.0,
    )
    try:
        dt = float(dt)
        h = float(h)
    except (TypeError, ValueError):
        return diag
    if not (np.isfinite(dt) and np.isfinite(h)) or dt <= 0 or h <= 0:
        return diag

    r_field_e, r_field_l = field_radius(earlier), field_radius(latest)
    r_vent_e, r_vent_l = ventricular_radius(earlier), ventricular_radius(latest)
    if None in (r_field_e, r_field_l, r_vent_e, r_vent_l):
        # Keep whatever radii were measurable for diagnosis only.
        diag.update(
            field_radius_earlier=float(r_field_e or 0.0),
            field_radius_latest=float(r_field_l or 0.0),
            ventricular_radius_earlier=float(r_vent_e or 0.0),
            ventricular_radius_latest=float(r_vent_l or 0.0))
        return diag

    g_field = np.log(r_field_l / r_field_e) / dt
    g_vent_raw = np.log(r_vent_l / r_vent_e) / dt
    g_vent = float(np.clip(g_vent_raw, RATE_MIN, RATE_MAX))
    weight = float(np.exp(-h / dt))
    rate = weight * g_field + (1.0 - weight) * g_vent
    h_eff = float(min(h, HORIZON_CAP_INTERVALS * dt))
    L_raw = HALF_STRENGTH * h_eff * rate
    L = float(np.clip(L_raw, -SIZE_BOUND, SIZE_BOUND))
    parent_L = float(HALF_STRENGTH * h * np.clip(g_field, RATE_MIN, RATE_MAX))

    if not np.all(np.isfinite([g_field, g_vent_raw, weight, rate, L, parent_L])):
        return diag
    diag.update(
        applied=1.0,
        field_radius_earlier=float(r_field_e), field_radius_latest=float(r_field_l),
        ventricular_radius_earlier=float(r_vent_e),
        ventricular_radius_latest=float(r_vent_l),
        field_rate=float(g_field), ventricular_rate_raw=float(g_vent_raw),
        ventricular_rate=float(g_vent),
        field_weight=weight, rate=float(rate), horizon_effective=h_eff,
        log_scale_raw=float(L_raw), log_scale=L,
        size_multiplier=float(np.exp(L)),
        clipped_rate=float(abs(g_vent_raw - g_vent) > 1e-12),
        clipped_size=float(abs(L_raw - L) > 1e-12),
        parent_log_scale=parent_L)
    return diag
