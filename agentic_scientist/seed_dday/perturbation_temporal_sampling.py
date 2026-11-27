"""Bounded erythroid source-sampling prior for the temporal (T1) board.

Rationale
---------
Primitive erythroblasts are a small but transcriptionally distinctive population
in the early heart-region dissections (Huang et al. 2017: primitive erythroblasts
mature in the circulation from ~E9.5 to E12.5 with a coordinated globin / heme /
membrane-skeleton programme).  The sparse-anchor parent under-samples them: the
dev diagnosis measured ~1.4% Blood versus ~14.7% in the target, and three
globin genes (Hbb-y, Hba-x, Hbb-bh1) move in the correct direction in the truth
but not in the prediction.

The intervention here is deliberately tiny and *source-mass bounded*: it changes
only the donor-sampling probabilities of the latest input stage, so that
marker-corroborated erythroid donors are up to twice as likely to be drawn, and
it may add at most 0.01 of absolute probability mass.  No expression value is
edited, no pool is resampled, no seed changes.  Sampling real latest-stage cells
keeps stage-appropriate empirical programmes; the parent's anchor drift and
sparse realisation are applied afterwards exactly as before.

Several published observations argue for a *bounded* rather than compounding
prior: fetal liver provides a maturation niche to which primitive erythroid
cells redistribute (Isern et al. 2008), EPO/EpoR regulates their proliferation
and maturation timing (Malik et al. 2013), and the cells later enucleate and are
replaced by definitive erythropoiesis.  The released early Blood fraction also
falls between E8.5 and E9.5, so this is an exploratory sampling prior, not an
extrapolation of an observed rising fraction.  Accordingly the doubling factor
saturates after one observed interval and the absolute mass budget is the hard
constraint.
"""
import numpy as np

# Shared erythroid marker panel: embryonic globins (Hbb-y, Hba-x, Hbb-bh1) plus
# the two adult alpha globins present throughout the erythroid programme.
ERY_MARKERS = ('Hbb-y', 'Hba-x', 'Hbb-bh1', 'Hba-a1', 'Hba-a2')
MIN_ELIGIBLE = 30          # support guard: below this we abstain entirely
MASS_BUDGET = 0.01         # hard absolute probability-mass budget per interval
MAX_ODDS = 2.0             # at most twofold odds multiplier


def _marker_matrix(a, markers):
    """Dense (cells x markers) log-expression block on the markers present."""
    pos = {g: i for i, g in enumerate(a.var_names)}
    cols = [pos[g] for g in markers if g in pos]
    if not cols:
        return np.zeros((a.n_obs, 0), dtype=np.float32), []
    sub = a.X[:, cols]
    sub = sub.toarray() if hasattr(sub, 'toarray') else np.asarray(sub)
    return np.asarray(sub, dtype=np.float32), cols


def erythroid_eligibility(a, markers):
    """Boolean mask of marker-corroborated erythroid donors.

    Requires (i) a Blood / erythroid label (case-insensitive), (ii) mean shared
    marker log expression above 1.0 and (iii) at least two markers detected.
    This is a donor-identity rule from the input alone; no target information
    enters.
    """
    labels = np.asarray(a.obs['celltype']).astype(str)
    low = np.char.lower(labels)
    label_ok = np.array([('blood' in s) or ('erythro' in s) for s in low])
    x, cols = _marker_matrix(a, markers)
    if len(cols) < 2:
        return np.zeros(a.n_obs, dtype=bool)
    mean_marker = x.mean(axis=1)
    detected = (x > 0).sum(axis=1)
    return label_ok & (mean_marker > 1.0) & (detected >= 2)


def plan_enrichment(flow, eligible, horizon, interval):
    """Recover the parent source probabilities and the bounded tilt.

    The parent's sampler uses ``p = normalize(exp(0.25 * F * log_growth))`` with
    ``F = min(horizon/interval, 2)``.  We choose the desired eligible mass ``q``
    under a twofold odds cap ``m0 = 2**s`` (``s`` saturates after one interval)
    and the absolute budget ``q - f <= 0.01 * s``, then invert the tilt so the
    multiplier ``m`` is applied through the existing sampler.  Everything is
    analytic; there are no sweeps or tuned constants.
    """
    if not (np.isfinite(interval) and np.isfinite(horizon)) or interval <= 0 or horizon <= 0:
        return None
    F = float(min(horizon / interval, 2.0))
    s = float(min(horizon / interval, 1.0))
    if eligible.sum() < MIN_ELIGIBLE or F <= 0:
        return None
    w = np.exp(0.25 * F * flow.log_growth)
    total = float(w.sum())
    if not np.isfinite(total) or total <= 0:
        return None
    p = w / total
    f = float(p[eligible].sum())
    if not (0.0 < f < 1.0):
        return None
    m0 = MAX_ODDS ** s
    q0 = m0 * f / (1.0 - f + m0 * f)
    q = float(min(q0, f + MASS_BUDGET * s))
    if not (q > f and q < 1.0):
        return None
    m = q * (1.0 - f) / (f * (1.0 - q))
    if not (np.isfinite(m) and m > 1.0):
        return None
    return dict(F=F, s=s, f=f, q=q, m=float(m), q0=float(q0),
                mass_binding=bool(q0 > f + MASS_BUDGET * s),
                ess_before=float(1.0 / np.sum(p ** 2)),
                ess_after=float(1.0 / np.sum((p * np.where(eligible, m, 1.0) /
                                              (1.0 + (m - 1.0) * f)) ** 2)))
