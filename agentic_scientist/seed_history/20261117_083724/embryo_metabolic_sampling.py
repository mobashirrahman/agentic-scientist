"""Bounded input-calibrated glycolytic-state resampling of latest-stage donors.

Why: within the heart-region temporal dissection, the supplied wild-type inputs
show a consistent decline of a fixed canonical glycolysis score inside most
cell types between the last two stages (e.g. V-CM 2.06 -> 1.94, SV-CM 1.73 ->
1.43, aSHF 1.58 -> 1.16 in log1p CP10k units).  The parent flow freezes the
latest donor state distribution, so it cannot follow that measured metabolic
shift.  Embryonic cardiac maturation involves a transition toward oxidative
metabolism (immature mitochondria at E9.5, coupled ETC by E11.5), which makes a
*state* axis plausible; RNA abundance is not flux, so the direction and
amplitude are taken only from the passed WT inputs, never from a target.

Mechanism (no target access, no stage-specific branch):
  * fixed 13-gene canonical glycolysis set, arithmetic mean per cell in the
    supplied log1p(CP10k) units; require >= 8 measured genes;
  * supported type = present with >= 50 cells in both last inputs;
  * d_c = mean_latest - mean_earlier per type,
    delta_c = max(-0.25, 0.5 * F * min(d_c, 0)) with F = bounded horizon factor;
  * exponential tilt of the parent donor probabilities inside each type toward
    downward z-scored score, bisected on beta in [0,1] with per-donor
    multipliers clipped to [1/2, 2]; beta saturates at 1 when the requested
    half-trend is unreachable, and is 0 for nondeclining / rare / degenerate
    types;
  * each type's tilted probabilities are renormalised to its *original* parent
    mass, so cell-type composition is unchanged and only the within-type donor
    state distribution moves.

The tilt is injected into the existing flow by an algebraic identity: the
parent draws donors with weights proportional to exp(growth*F*log_growth).
Writing p0 for those normalised probabilities and p1 for the tilted ones,
log_growth + log(p1/p0)/(growth*F) yields exactly p1 at the same draw, leaving
the decoder, anchor drift, RNG stream and everything else untouched.

Interaction guard (w1_c02)
--------------------------
This helper is applied *after* the bounded erythroid source-sampling prior
(temporal_sampling.py) has already modified ``flow.log_growth``.  Two
consequences, both deliberate:

  * ``p0`` is recomputed from that already-enriched flow, so the two
    interventions compose multiplicatively instead of one silently replacing
    the other's weights;
  * every lineage that contains a marker-corroborated erythroid donor is
    excluded from the glycolysis tilt (``excluded_labels``).  The erythroid
    prior is a donor-identity intervention with its own probability budget;
    keeping it on lineages the metabolic tilt never touches means its budget,
    its sampled composition and its already-measured effect are unchanged even
    if an unusual input annotates erythroid cells under a non-Blood label.
    The exclusion is derived from the passed input alone and its mass is
    restored exactly with the other types' masses.
"""

import numpy as np
from scipy import sparse

# Canonical glycolysis / lactate fermentation set, fixed a priori.  These are
# the shared measured genes of the pathway; no gene selection by score.
GLYCOLYSIS = ['Hk1', 'Hk2', 'Gpi1', 'Pfkl', 'Pfkm', 'Aldoa', 'Tpi1',
              'Gapdh', 'Pgk1', 'Pgam1', 'Eno1', 'Pkm', 'Ldha']

MIN_GENES = 8          # require at least 8 of the 13 measured
MIN_CELLS = 50         # per type in BOTH last inputs
DISPLACEMENT_CAP = 0.25  # max |score| change in log1p CP10k units
MAX_FACTOR = 2.0       # horizon bound, same as the parent's min(h/interval, 2)
MULTIPLIER_BOUND = np.log(2.0)  # per-donor weight multiplier in [1/2, 2]
GROWTH = 0.25          # parent donor growth coefficient (unchanged)


def _score(a, genes):
    """Arithmetic mean log1p(CP10k) over the measured genes of `genes`."""
    pos = a.var_names.get_indexer(list(genes))
    ok = pos >= 0
    if int(ok.sum()) < MIN_GENES:
        return None, []
    x = a.X[:, pos[ok]]
    s = np.asarray(x.mean(axis=1)).ravel().astype(float)
    used = [g for g, o in zip(genes, ok) if o]
    return s, used


def plan_tilt(flow, factor, excluded_labels=()):
    """Compute donor log-weight increments for the glycolysis half-trend tilt.

    `flow` is the fitted LatentFlow (parent `AnchorFlow.flow` when external data
    is used), evaluated *after* any prior source-weight intervention, so its
    ``log_growth`` already carries that intervention.  ``excluded_labels`` are
    lineages whose donor probabilities must not move (here: every lineage that
    contains an eligible erythroid donor).  Returns None when nothing should
    move, which lets the caller run the unmodified parent so the null is
    bit-for-bit identical.
    """
    F = float(factor)
    if not np.isfinite(F) or F <= 0:
        return None
    excluded = {str(c) for c in np.asarray(list(excluded_labels)).astype(str)}

    latest = flow.latest
    earlier = flow.earlier  # already restricted to the latest gene order
    s_b, used = _score(latest, GLYCOLYSIS)
    if s_b is None:
        return None
    s_a, _ = _score(earlier, GLYCOLYSIS)
    if s_a is None:
        return None

    labels_b = np.asarray(flow.labels_b).astype(str)
    labels_a = np.asarray(flow.labels_a).astype(str)
    n = latest.n_obs

    # Parent donor probabilities p0 (used only to preserve each type's mass).
    log_growth = np.asarray(flow.log_growth, dtype=float).ravel()
    p0 = np.exp(GROWTH * F * log_growth)
    p0 = p0 / p0.sum()
    p1 = p0.copy()

    rows = {'celltype': [], 'cells_earlier': [], 'cells_latest': [],
            'input_delta': [], 'requested_shift': [], 'achieved_shift': [],
            'beta': [], 'saturated': [], 'ess_fraction': [], 'excluded': []}

    any_moved = False
    for c in np.unique(labels_b):
        ia = np.flatnonzero(labels_a == c)
        ib = np.flatnonzero(labels_b == c)
        n_early, n_late = len(ia), len(ib)
        is_excluded = str(c) in excluded
        d_c, delta, beta, achieved, sat, ess_frac = (0.0, 0.0, 0.0, 0.0, False, 1.0)
        # Excluded lineages keep their enriched donor probabilities exactly:
        # the erythroid budget must be invariant, so no support test is applied.
        if not is_excluded and n_early >= MIN_CELLS and n_late >= MIN_CELLS:
            d_c = float(s_b[ib].mean() - s_a[ia].mean())
            # Half of the observed forward score displacement over the (bounded)
            # horizon; only a decline is acted on and it is capped at 0.25.
            delta = max(-DISPLACEMENT_CAP, 0.5 * F * min(d_c, 0.0))
            if delta < 0.0:
                v = s_b[ib]
                base = p0[ib]
                total = float(base.sum())
                base = base / max(total, 1e-300)
                mean0 = float(base @ v)
                sd = max(float(v.std()), 0.1)
                z = (v - mean0) / sd
                desired = mean0 + delta
                lo, hi = 0.0, 1.0
                for _ in range(40):
                    trial = 0.5 * (lo + hi)
                    w = base * np.exp(np.clip(-trial * z, -MULTIPLIER_BOUND, MULTIPLIER_BOUND))
                    w = w / w.sum()
                    if float(w @ v) > desired:
                        lo = trial
                    else:
                        hi = trial
                beta = 0.5 * (lo + hi)
                w = base * np.exp(np.clip(-beta * z, -MULTIPLIER_BOUND, MULTIPLIER_BOUND))
                w = w / w.sum()
                achieved = float(w @ v - mean0)
                if achieved > delta + 1e-9:
                    # Requested half-trend unreachable with beta <= 1: saturate.
                    beta = 1.0
                    sat = True
                    w = base * np.exp(np.clip(-z, -MULTIPLIER_BOUND, MULTIPLIER_BOUND))
                    w = w / w.sum()
                    achieved = float(w @ v - mean0)
                # Restore exactly the original parent mass of this type.
                p1[ib] = total * w
                ess_frac = float(1.0 / max(float(w @ w), 1e-300)) / n_late
                any_moved = True
        rows['celltype'].append(str(c))
        rows['cells_earlier'].append(int(n_early))
        rows['cells_latest'].append(int(n_late))
        rows['input_delta'].append(float(d_c))
        rows['requested_shift'].append(float(delta))
        rows['achieved_shift'].append(float(achieved))
        rows['beta'].append(float(beta))
        rows['saturated'].append(bool(sat))
        rows['ess_fraction'].append(float(ess_frac))
        rows['excluded'].append(bool(is_excluded))

    if not any_moved:
        return None

    # Re-normalise (should already sum to 1 up to floating error).
    p1 = p1 / p1.sum()
    # Algebraic donor-weight increment for exp(GROWTH*F*log_growth).
    with np.errstate(divide='ignore', invalid='ignore'):
        log_ratio = np.log(p1 / p0)
    log_ratio = np.nan_to_num(log_ratio, nan=0.0, posinf=0.0, neginf=0.0)

    ess_before = float(1.0 / max(float(p0 @ p0), 1e-300))
    ess_after = float(1.0 / max(float(p1 @ p1), 1e-300))
    mass_err = float(max(abs(float(p1[labels_b == c].sum()) - float(p0[labels_b == c].sum()))
                         for c in np.unique(labels_b)))

    return {
        'log_ratio': log_ratio,
        'genes_used': used,
        'factor': F,
        'rows': rows,
        'excluded_labels': sorted(excluded),
        'ess_before': ess_before,
        'ess_after': ess_after,
        'max_type_mass_error': mass_err,
        'global_score_shift': float((p1 - p0) @ s_b),
        'score_before': float(p0 @ s_b),
        'score_after': float(p1 @ s_b),
        'excluded_mass_before': float(p0[np.isin(labels_b, list(excluded))].sum()),
        'excluded_mass_after': float(p1[np.isin(labels_b, list(excluded))].sum()),
    }


def attach_diagnostics(out, plan, applied):
    """Store diagnostics as flat arrays (h5ad cannot round-trip list-of-dicts)."""
    r = plan['rows']
    out.uns['metabolic_tilt'] = dict(
        applied=bool(applied),
        factor=float(plan['factor']),
        genes_used=np.array(plan['genes_used'], dtype=str),
        genes_used_count=int(len(plan['genes_used'])),
        score_before=float(plan['score_before']),
        score_after=float(plan['score_after']),
        global_score_shift=float(plan['global_score_shift']),
        ess_before=float(plan['ess_before']),
        ess_after=float(plan['ess_after']),
        max_type_mass_error=float(plan['max_type_mass_error']),
        excluded_labels=np.array(plan['excluded_labels'], dtype=str),
        n_excluded_labels=int(len(plan['excluded_labels'])),
        excluded_mass_before=float(plan['excluded_mass_before']),
        excluded_mass_after=float(plan['excluded_mass_after']),
    )
    out.uns['metabolic_tilt_strata'] = dict(
        celltype=np.array(r['celltype'], dtype=str),
        cells_earlier=np.array(r['cells_earlier'], dtype=np.int64),
        cells_latest=np.array(r['cells_latest'], dtype=np.int64),
        input_delta=np.array(r['input_delta'], dtype=float),
        requested_shift=np.array(r['requested_shift'], dtype=float),
        achieved_shift=np.array(r['achieved_shift'], dtype=float),
        beta=np.array(r['beta'], dtype=float),
        saturated=np.array(r['saturated'], dtype=bool),
        ess_fraction=np.array(r['ess_fraction'], dtype=float),
        excluded=np.array(r['excluded'], dtype=bool),
    )
    return out
