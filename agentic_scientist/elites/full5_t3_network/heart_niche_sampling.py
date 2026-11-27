"""Bounded cardiac-neighbourhood donor prior for the heart board.

Biology
-------
Cardiac morphogenesis expands an *organised multicellular domain*: myocardium,
endocardium and the adjacent cardiac progenitors move and grow together, and
endothelial / mesenchymal / epicardial populations accompany the myocytes
(Esteban et al. 2022; Li et al. 2016; Savolainen et al. 2009).  The released
heart-region inputs therefore do not just gain isolated myocardial cells; the
local neighbourhoods inside the cardiac territory change.  A donor-level field
that measures, for each cell, what *fraction of its spatial neighbours are
corroborated cardiomyocytes* is a local, multicellular quantity that rises while
the heart tube is being built, and that a purely uniform donor draw ignores.

Mechanism (all constants fixed a priori; no sweeps)
---------------------------------------------------
1. Seed donors: a cell is a corroborated cardiomyocyte when (a) its own input
   label is cardiac-muscle (``CM``, ``vCM`` or any ``*-CM`` subtype) and (b) its
   mean log expression over the *shared* members of a fixed marker panel
   (Myl7, Myl4, Tnnt2, Actc1, Nkx2-5, Myh6, Ttn) exceeds 0.5.  At least two
   shared markers and at least 30 seed donors are required.
2. Field: on each input stage independently, the three ``spatial_3D`` axes are
   standardised by their standard deviation (z is a section *index*, so raw
   units are not comparable), and ``s_i`` is the fraction of the cell's
   ``min(31, N)`` nearest neighbours (including itself) that are seeds.
3. Trend: ``mu_a`` and ``mu_b`` are the mean field on the earlier and the latest
   input.  The logit gain is clipped to ``[0, log 2]`` (one doubling of the odds
   at most) and damped twice: by ``F = horizon/(horizon+interval)`` (a shorter
   observed interval carries less evidence about the future) and by
   ``(1 - mu_b)`` (a territory that is already mostly myocardium has little room
   to expand further).  This is exactly the lesson of the earlier binary
   myocardial-compartment pilot, which gained on dev and lost badly on the
   longer holdout because it compounded an early fraction.
4. Sampling: ``ptilt = softmax(beta * s)``, then the mixed law
   ``p = p0 + lambda * (ptilt - p0)`` with ``p0 = 1/N`` and ``lambda`` chosen so
   the total-variation shift is at most ``0.05 * F``.  Every donor keeps
   positive probability, so the output is still a sample of real latest-stage
   cells; no expression is edited and no cell is invented.
5. Abstention: a flat, falling, saturated (``mu_b > 0.5``), unsupported or
   invalid trend returns ``None`` and the parent path runs bit-identically.
"""
import numpy as np
from sklearn.neighbors import NearestNeighbors

# Fixed cardiac-muscle marker panel (structural / sarcomeric plus Nkx2-5).
CM_MARKERS = ('Myl7', 'Myl4', 'Tnnt2', 'Actc1', 'Nkx2-5', 'Myh6', 'Ttn')
MIN_MARKERS = 2            # need at least this many shared markers
MARKER_THRESHOLD = 0.5     # fixed a priori: mean log expression over shared markers
MIN_SEED_DONORS = 30       # support guard on the seed set, per input
MIN_CELLS = 100            # support guard on the stage size, per input
K_FIELD = 31               # neighbourhood size of the local CM field (self included)
MAX_LOGIT_GAIN = float(np.log(2.0))   # at most a doubling of the CM odds
MAX_TV = 0.05              # hard absolute probability-mass budget (times F)
MAX_CM_SHARE = 0.5         # saturation guard: abstain above this latest-stage share
MAX_CM_SHARE_GAIN = 0.03   # plausibility cap: myocardial share may not rise by more than
                           # three points above the latest input's own share


def _cm_label(label):
    """Cardiac-muscle label test on the input's own label set.

    ``CM``, ``vCM`` and every ``*-CM`` subtype (V-CM, IFT-CM, OFT-CM, SV-CM,
    A-CM, ...) qualify.  Tokenised so that names such as ``OFT/RV-CM`` or
    ``CM_1`` also match, while non-myocyte labels (Endo, Chamber-Endo,
    Endocardium, ...) never do.  No cross-stage ontology is assumed: only the
    label string carried by the stage itself is read.
    """
    low = label.strip().lower()
    if 'non-cm' in low or 'noncm' in low:
        return False
    tokens = [t for t in low.replace('_', '-').replace('/', '-').split('-') if t]
    return any(t.lower() == 'cm' for t in tokens) or low == 'vcm'


def _marker_block(a, markers):
    pos = {g: i for i, g in enumerate(a.var_names)}
    cols = [pos[g] for g in markers if g in pos]
    if not cols:
        return np.zeros((a.n_obs, 0), dtype=np.float32), []
    sub = a.X[:, cols]
    sub = sub.toarray() if hasattr(sub, 'toarray') else np.asarray(sub)
    return np.asarray(sub, dtype=np.float32), cols


def cm_seed_mask(a, markers):
    """Boolean mask of marker-corroborated cardiomyocyte donors (input-only rule)."""
    labels = np.asarray(a.obs['celltype']).astype(str)
    label_ok = np.array([_cm_label(s) for s in labels], dtype=bool)
    x, cols = _marker_block(a, markers)
    if len(cols) < MIN_MARKERS:
        return np.zeros(a.n_obs, dtype=bool), len(cols)
    mean_marker = x.mean(axis=1)
    return (label_ok & (mean_marker > MARKER_THRESHOLD)), len(cols)


def _standardised_coords(a):
    """Axes standardised by their own std, so the kNN is not dominated by one axis.

    ``spatial_3D`` mixes in-plane coordinates with a section index z; dividing
    each axis by its standard deviation makes the 31-NN a neighbourhood in the
    stage's own (unregistered) spatial frame without needing any registration.
    """
    p = np.asarray(a.obsm['spatial_3D'], dtype=np.float64)
    sd = p.std(axis=0)
    sd = np.where(np.isfinite(sd) & (sd > 1e-12), sd, 1.0)
    return p / sd


def cardiac_field(a, markers):
    """Local CM field ``s_i``: seed fraction among each cell's own 31-NN."""
    seeds, n_markers = cm_seed_mask(a, markers)
    p = _standardised_coords(a)
    k = int(min(K_FIELD, a.n_obs))
    nn = NearestNeighbors(n_neighbors=k).fit(p)
    idx = nn.kneighbors(p, return_distance=False)
    s = np.asarray(seeds[idx], dtype=np.float64).mean(axis=1)
    return s, seeds, n_markers


def _logit(x):
    return float(np.log(x / (1.0 - x)))


def plan_cardiac_tilt(earlier, latest, horizon, interval, markers=None):
    """Bounded donor reweighting toward expanding cardiac neighbourhoods.

    Returns ``None`` (exact parent) whenever any support or monotonicity guard
    fails, otherwise a dict with the donor law ``p`` and flat diagnostics.
    """
    if markers is None:
        markers = [g for g in CM_MARKERS
                   if g in earlier.var_names and g in latest.var_names]
    if len(markers) < MIN_MARKERS:
        return None
    if earlier.n_obs < MIN_CELLS or latest.n_obs < MIN_CELLS:
        return None
    if not (np.isfinite(interval) and np.isfinite(horizon)) or interval <= 0 or horizon <= 0:
        return None
    if 'spatial_3D' not in earlier.obsm or 'spatial_3D' not in latest.obsm:
        return None

    s_a, seed_a, n_markers = cardiac_field(earlier, markers)
    s_b, seed_b, _ = cardiac_field(latest, markers)
    if n_markers < MIN_MARKERS:
        return None
    if seed_a.sum() < MIN_SEED_DONORS or seed_b.sum() < MIN_SEED_DONORS:
        return None

    mu_a = float(s_a.mean())
    mu_b = float(s_b.mean())
    # Guards: a valid monotone, non-saturated trend only.
    if not (0.0 < mu_a < 1.0 and 0.0 < mu_b < 1.0):
        return None
    if mu_b <= mu_a or mu_b > MAX_CM_SHARE:
        return None

    F = float(horizon / (horizon + interval))
    gain = float(np.clip(_logit(mu_b) - _logit(mu_a), 0.0, MAX_LOGIT_GAIN))
    # Damping by F (horizon uncertainty) and by (1-mu_b) (saturation guard).
    beta = float(F * (1.0 - mu_b) * gain)
    if not np.isfinite(beta) or beta <= 0.0:
        return None

    logits = beta * s_b
    logits -= logits.max()
    ptilt = np.exp(logits)
    ptilt /= ptilt.sum()
    n = latest.n_obs
    p0 = np.full(n, 1.0 / n, dtype=np.float64)
    tv_tilt = float(0.5 * np.abs(ptilt - p0).sum())
    lam = float(min(1.0, MAX_TV * F / max(tv_tilt, 1e-12)))
    # Additional long-horizon plausibility cap: the induced myocardial share may
    # not exceed the latest input's own share by more than three points.  This
    # can only tighten the TV budget (it never loosens it), and it is the guard
    # that keeps the 3-day forecast from swelling the heart territory.
    cm_gain_full = float(np.sum(ptilt[seed_b] - p0[seed_b]))
    if cm_gain_full > MAX_CM_SHARE_GAIN:
        lam = min(lam, MAX_CM_SHARE_GAIN / max(cm_gain_full, 1e-12))
    p = p0 + lam * (ptilt - p0)
    p = np.clip(p, 0.0, None)
    p /= p.sum()

    tv = float(0.5 * np.abs(p - p0).sum())
    cm_parent = float(p0[seed_b].sum())
    cm_tilt = float(p[seed_b].sum())
    # Local, not cell-intrinsic: mass of non-seed donors weighted by the CM
    # fraction of their own neighbourhood (the accompanying niche).
    noncm = ~seed_b
    noncm_parent = float(np.sum(p0[noncm] * s_b[noncm]))
    noncm_tilt = float(np.sum(p[noncm] * s_b[noncm]))
    return dict(
        p=p, F=F, mu_a=mu_a, mu_b=mu_b, logit_gain=gain, beta=beta,
        tv_tilt=tv_tilt, tv=tv, lam=lam,
        ess=float(1.0 / np.sum(p ** 2)),
        cm_share_parent=cm_parent, cm_share_pred=cm_tilt,
        cm_share_gain=cm_tilt - cm_parent,
        noncm_nb_mass_parent=noncm_parent, noncm_nb_mass_pred=noncm_tilt,
        n_seeds_earlier=float(seed_a.sum()), n_seeds_latest=float(seed_b.sum()),
        n_markers=float(n_markers), k_field=float(min(K_FIELD, latest.n_obs)),
        interval=float(interval), horizon=float(horizon),
    )
