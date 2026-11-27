"""Detection-matched, GO-weighted WT-neighbour maturation axis (T3).

Why this module exists
----------------------
The shipped perturbation mechanism (``perturbation_prior_composition.py``)
contains each latest-WT annotation by a min-KL exponential tilt of its REAL
donors along an axis measured as one earlier-minus-later centroid
(``mean(E_prev | t) - mean(E_last | t)``).  That single centroid mixes three
different things: within-state maturation, a change in the MIX of local states,
and (most importantly for log1p single-cell data) a change in detection depth
between the two released stages.  A knockout that keeps a lineage's annotation
but delays selected differentiation programmes inside it is therefore only
partly described by that centroid.

This module re-estimates the earlier-like displacement of a lineage from
matched wild-type neighbourhoods at SHARED detection depths:

  * both released WT stages are aligned on shared symbols and the latest stage
    defines detection-depth quartiles;
  * in each depth bin that is supported in BOTH stages and in BOTH independent
    halves of the WT split, a pooled, standardised PCA of variable NON-GO panel
    genes supplies a local neighbourhood space;
  * every evenly sampled latest-stage anchor is compared with (a) its up-to-15
    nearest earlier neighbours in that bin and (b) its up-to-15 nearest
    leave-self latest neighbours in the same bin;
  * the mean earlier-minus-latest contrast over anchors is the candidate axis of
    that bin.  Only genes whose sign recurs between the two independent
    half-splits with |change| >= 0.02 in BOTH halves and agrees with the
    matched-neighbour contrast are retained, which removes sample noise;
  * genes sharing a vetted GO term with the knocked-out gene (case-insensitive
    symbol lookup, exact terms annotated to 5-500 prior genes) receive DOUBLE
    signed weight -- co-annotation alone carries no direction, it only says
    which measured trends are relevant to this knockout;
  * a lineage needs at least five reliable GO-linked genes, otherwise it falls
    back to the seed's one-centroid axis, so a knockout with thin annotation
    (the Mab21l2 dev case) reproduces the seed.

Realisation is unchanged in kind: the axis is used only to reweight the REAL
latest-WT donors (min-KL exponential tilt inside the annotation), so every
output row remains a resampled real cell and no expression vector is
synthesised here.  Nothing branches on a gene name, a stage value, a coordinate
or a split identity; the GO lookup is the only gene-specific input and it comes
from the supplied prior.
"""
import numpy as np
from scipy import sparse
from scipy.spatial.distance import cdist

# ---- pre-registered constants (fixed a priori, never swept on dev) ----------
MIN_LABEL_CELLS = 30       # cells of the label required at BOTH WT stages
MIN_BIN_CELLS = 5          # cells from each stage per depth bin per half
MIN_SHARED = 20            # shared-symbol support for the contrast
MIN_PCA_GENES = 20         # non-GO variable genes required for the local space
MAX_PCA_GENES = 120        # cap on the variable-gene set (runtime)
MAX_COMPONENTS = 8         # pooled PCA components for the neighbourhood space
MAX_ANCHORS = 128          # evenly sampled latest anchors per bin (runtime)
K_NN = 15                  # earlier / latest neighbours per anchor
MIN_ABS_HALF = 0.02        # |contrast| required in BOTH halves
MIN_GO_RELIABLE = 5        # reliable GO-linked genes required in a lineage
GO_TERM_MIN, GO_TERM_MAX = 5, 500   # vetted term size range (prior genes)
BIN_QUANTILES = (0.25, 0.5, 0.75)
HALF_BIN_MIN_COVER = 0.5   # supported bins must cover half of each WT half
# --- donor-tilt constraints (identical to the parent's maturation tilt) ------
TILT_RATIO_LO, TILT_RATIO_HI = 0.25, 4.0
TILT_ESS_FRAC = 0.5
TILT_LAMBDA_MAX = 60.0
EXPOSURE_REF = 0.10        # same absolute-exposure reference as the parent
RHO_CAP = 0.60             # cap on the interval fraction traversed


def _shared_columns(earlier, wt):
    """Column indices of the shared symbols (first occurrence, wt order)."""
    pos = {}
    for j, g in enumerate(str(v) for v in earlier.var_names):
        pos.setdefault(g, j)
    cw, ce, genes, seen = [], [], [], set()
    for j, g in enumerate(str(v) for v in wt.var_names):
        if g in seen or g not in pos:
            continue
        seen.add(g)
        cw.append(j)
        ce.append(pos[g])
        genes.append(g)
    return (np.asarray(cw, dtype=int), np.asarray(ce, dtype=int), genes)


def _dense(X, cols):
    """Selected columns of ``X`` as float64 ndarray (sparse safe)."""
    if sparse.issparse(X):
        return np.asarray(X.tocsc()[:, cols].toarray(), dtype=np.float64)
    return np.asarray(X[:, cols], dtype=np.float64)


def _detection(X):
    """Per-cell number of detected (non-zero) shared genes."""
    if sparse.issparse(X):
        return np.asarray(X.getnnz(axis=1)).ravel().astype(np.float64)
    return np.count_nonzero(np.asarray(X), axis=1).astype(np.float64)


def go_related(go_prior, knockout, genes):
    """Boolean mask: gene shares a vetted GO term with ``knockout``.

    Case-insensitive symbol lookup and EXACT term identity (no propagation
    through ``term_parents``): terms annotated to 5-500 genes of the supplied
    prior are the ones specific enough to carry a per-knockout prior and broad
    enough not to be a private annotation.  Missing prior / symbol gives an
    all-False mask (the caller then falls back to the seed axis).
    """
    rel = np.zeros(len(genes), dtype=bool)
    if not isinstance(go_prior, dict) or knockout is None:
        return rel
    gt = go_prior.get('gene_terms')
    if not isinstance(gt, dict) or not gt:
        return rel
    cf = {str(g).casefold(): set(str(t) for t in terms)
          for g, terms in gt.items()}
    freq = {}
    for terms in cf.values():
        for t in terms:
            freq[t] = freq.get(t, 0) + 1
    ko_terms = {t for t in cf.get(str(knockout).casefold(), ())
                if GO_TERM_MIN <= freq.get(t, 0) <= GO_TERM_MAX}
    if not ko_terms:
        return rel
    for i, g in enumerate(genes):
        rel[i] = bool(ko_terms & cf.get(str(g).casefold(), set()))
    return rel


def _tilt_weights(s, rho):
    """Min-KL exponential tilt w ~ exp(lam s) with weighted mean ``rho``.

    Same solver and declared ceilings as the parent composition module: the
    lambda is shrunk (never raised) while the effective sample size is below
    TILT_ESS_FRAC of the annotation or the largest per-donor density ratio
    exceeds TILT_RATIO_HI.  Those bounds are what keep every output row a real
    cell instead of overweighting a handful of donors.
    """
    n = float(s.size)

    def w_of(lam):
        z = lam * s
        z = z - z.max()
        w = np.exp(z)
        return w / w.sum()

    if float(w_of(TILT_LAMBDA_MAX) @ s) <= rho:
        lam = TILT_LAMBDA_MAX
    else:
        lo, hi = 0.0, TILT_LAMBDA_MAX
        for _ in range(40):
            mid = 0.5 * (lo + hi)
            if float(w_of(mid) @ s) < rho:
                lo = mid
            else:
                hi = mid
        lam = 0.5 * (lo + hi)
    w = w_of(lam)
    for _ in range(24):
        ess = 1.0 / float(np.sum(w * w))
        if (ess >= TILT_ESS_FRAC * n
                and float(np.max(w) * n) <= TILT_RATIO_HI) or lam <= 1e-6:
            break
        lam *= 0.8
        w = w_of(lam)
    ess = 1.0 / float(np.sum(w * w))
    return w, float(lam), float(w @ s), float(ess), float(np.max(w) * n)


def _anchors(idx, cap=MAX_ANCHORS):
    """Evenly sampled anchor positions over a sorted index array (deterministic)."""
    if idx.size <= cap:
        return idx
    pos = np.unique(np.linspace(0, idx.size - 1, cap).round().astype(int))
    return idx[pos]


def _bin_contrast(coord, X, wb, eb):
    """Mean over latest anchors of (mean earlier nbrs - mean latest nbrs)."""
    anchors = _anchors(wb)
    de = cdist(coord[anchors], coord[eb])
    k_e = min(K_NN, len(eb))
    ne = np.argpartition(de, k_e - 1, axis=1)[:, :k_e]
    dw = cdist(coord[anchors], coord[wb])
    # exclude self by pushing its distance to +inf
    dw[np.arange(len(anchors)), np.searchsorted(wb, anchors)] = np.inf
    k_w = min(K_NN, len(wb) - 1)
    if k_w <= 0:
        return None
    nw = np.argpartition(dw, k_w - 1, axis=1)[:, :k_w]
    m_e = X[eb[ne]].mean(1)
    m_w = X[wb[nw]].mean(1)
    return (m_e - m_w).mean(0)


def _rho_targets(types, exposure, q_all, m_all, rho, strength):
    """Per-lineage interval fraction rho_t (bounded, gene-agnostic)."""
    n = len(types)
    a = np.asarray(exposure, dtype=float)
    if a.shape != (n,):
        a = np.zeros(n)
    try:
        q = float(q_all)
        m = float(m_all)
    except Exception:
        q = m = float('nan')
    if not np.isfinite(q) or not np.isfinite(m) or q <= 0:
        a_all = 0.0
    else:
        a_all = float(q * (1.0 - np.exp(-m / q)))
    base = (rho * float(np.clip(a_all / EXPOSURE_REF, 0.0, 1.0))
            * (1.0 + 2.0 * max(0.0, q - 0.30)))
    ratio = np.clip(a / max(a_all, 1e-6), 0.5, 1.5)
    out = np.minimum(RHO_CAP, base * ratio * float(strength))
    return np.clip(np.nan_to_num(out, nan=0.0, posinf=0.0, neginf=0.0), 0.0, RHO_CAP)


def _seed_axis(Xw, Xe, rows, erows):
    """Parent one-centroid axis: (mean earlier - mean latest) inside the label."""
    mu = Xw[rows].mean(0)
    d = (Xe[erows].mean(0) - mu) if erows.size else np.zeros_like(mu)
    dd = float(d @ d)
    if not np.isfinite(dd) or dd <= 1e-8:
        return None
    return d


def neighbour_tilt(earlier, wt, exposure, q_all, m_all, rho, go_prior,
                   knockout, strength=1.0, seed=101):
    """Detection-matched GO-weighted donor tilt along WT neighbour directions.

    Returns ``(weights, diag, axis)`` exactly like the parent's
    ``maturation_tilt``: per-donor weights aligned to ``wt`` (None when the
    mechanism abstains for every lineage), flat diagnostics and the global
    axis record used for the realised-response diagnostics.
    """
    diag = dict(applied=False, reason='', rho_target=float(rho),
                rho_realised=0.0, n_shared_genes=0, n_tilted=0,
                tilted_mass=0.0, ess_frac_min=1.0, max_weight_ratio=1.0,
                d_norm=0.0, pseudo_rho=0.0, pseudo_corr_d=0.0,
                tilted_types=np.array([], dtype=str),
                mean_s=np.zeros(0), type_mass=np.zeros(0),
                fallback_to_seed_axis=0.0, n_go_genes=0.0,
                median_go_reliable=0.0, median_cos_to_seed=0.0,
                n_bins_used=0.0, target_frac_mean=0.0, achieved_frac_mean=0.0)
    axis = dict(d=np.zeros(0), cols=np.zeros(0, dtype=int))
    if earlier is None or wt is None:
        diag['reason'] = 'no_earlier_input'
        return None, diag, axis
    if not np.isfinite(rho) or rho <= 0 or not np.isfinite(strength) or strength <= 0:
        diag['reason'] = 'zero_rho'
        return None, diag, axis

    wlab = np.asarray(wt.obs['celltype'].astype(str)).ravel()
    alab = np.asarray(earlier.obs['celltype'].astype(str)).ravel()
    types = np.unique(wlab)
    cw, ce, genes = _shared_columns(earlier, wt)
    diag['n_shared_genes'] = len(genes)
    if len(genes) < MIN_SHARED or types.size == 0:
        diag['reason'] = 'too_few_shared_genes'
        return None, diag, axis

    Xw = _dense(wt.X, cw)
    Xe = _dense(earlier.X, ce)
    if not (np.all(np.isfinite(Xw)) and np.all(np.isfinite(Xe))):
        diag['reason'] = 'non_finite_expression'
        return None, diag, axis
    dw = _detection(wt.X[:, cw])
    de = _detection(earlier.X[:, ce])
    related = go_related(go_prior, knockout, genes)
    diag['n_go_genes'] = float(related.sum())
    rho_t = _rho_targets(types, exposure, q_all, m_all, rho, strength)
    d_global = _seed_axis(Xw, Xe, np.arange(wt.n_obs), np.arange(earlier.n_obs))
    if d_global is None:
        diag['reason'] = 'degenerate_axis'
        return None, diag, axis
    diag['d_norm'] = float(np.sqrt(max(float(d_global @ d_global), 0.0)))
    axis = dict(d=d_global, cols=cw)

    rng = np.random.default_rng(seed)
    W = np.ones(wt.n_obs, dtype=np.float64)
    mass, mean_s, tilted, cosines, go_counts, bins_used = [], [], [], [], [], []
    ess_min, ratio_max = 1.0, 1.0
    real_weighted = achieved = 0.0
    n_any = n_axis_used = 0
    for i, t in enumerate(types):
        rows = np.flatnonzero(wlab == t)
        erows = np.flatnonzero(alab == t)
        if rows.size < MIN_LABEL_CELLS or erows.size < MIN_LABEL_CELLS:
            continue
        n_any += 1
        res = _lineage_projection(Xw, Xe, dw, de, rows, erows, related, rng)
        seed_d = _seed_axis(Xw, Xe, rows, erows)
        cos = 0.0
        if seed_d is not None and res is not None:
            av = res['axis']
            den = np.linalg.norm(av) * np.linalg.norm(seed_d)
            if den > 0:
                cos = float(av @ seed_d / den)
            cosines.append(cos)
        if res is not None and rho_t[i] > 0:
            s = res['s']
            n_axis_used += 1
            w, _lam, ms, ess, rmax = _tilt_weights(s, float(rho_t[i]))
            wl = w * float(rows.size)
            # Preserve the seed's aggregate donor probability per depth bin:
            # renormalise the tilted weights inside every bin to mean one, so
            # only the WITHIN-bin mix of states moves.
            for b in np.unique(res['bins']):
                rb = rows[res['bins'] == b]
                tot = float(wl[res['bins'] == b].sum())
                if rb.size and tot > 0:
                    wl[res['bins'] == b] *= float(rb.size) / tot
            W[rows] = wl
            mass.append(float(rows.size))
            mean_s.append(ms)
            tilted.append(str(t))
            go_counts.append(float(res['n_go_reliable']))
            bins_used.append(float(res['n_bins']))
            ess_min = min(ess_min, ess / float(rows.size))
            ratio_max = max(ratio_max, rmax)
            real_weighted += float(rho_t[i]) * float(rows.size)
            achieved += float(s @ w) * float(rows.size)
        else:
            # Per-lineage fallback to the seed's one-centroid axis (thin GO
            # support or too few depth-matched neighbours).
            if seed_d is None:
                continue
            d = seed_d
            dd = float(d @ d)
            rows_mu = Xw[rows].mean(0)
            s = (Xw[rows] - rows_mu) @ d / dd
            if not np.all(np.isfinite(s)) or float(s.std()) <= 1e-9:
                continue
            r = float(rho_t[i])
            if r <= 0:
                continue
            w, _lam, ms, ess, rmax = _tilt_weights(s, r)
            W[rows] = w * float(rows.size)
            mass.append(float(rows.size))
            mean_s.append(ms)
            tilted.append(str(t))
            go_counts.append(0.0)
            bins_used.append(0.0)
            ess_min = min(ess_min, ess / float(rows.size))
            ratio_max = max(ratio_max, rmax)
            real_weighted += r * float(rows.size)
            achieved += ms * float(rows.size)
    if n_axis_used == 0:
        # No lineage had enough depth-matched GO support: whole-split
        # abstention, so the caller runs the seed's ``maturation_tilt`` with its
        # original rho*scale and the donor rows stay bit-identical to the seed
        # (Mab21l2 E9.5 is the dev case with only ~3 panel GO neighbours).
        diag['reason'] = 'no_go_support'
        return None, diag, axis
    if not tilted:
        diag['reason'] = ('no_supported_annotation' if n_any else
                          'no_label_support')
        return None, diag, axis
    mass = np.asarray(mass, dtype=float)
    mean_s = np.asarray(mean_s, dtype=float)
    tot = max(float(mass.sum()), 1e-12)
    diag.update(applied=True, reason='ok', n_tilted=int(len(tilted)),
                tilted_mass=float(mass.sum() / max(float(wt.n_obs), 1.0)),
                ess_frac_min=float(ess_min), max_weight_ratio=float(ratio_max),
                rho_realised=float(mass @ mean_s / tot),
                tilted_types=np.asarray(tilted, dtype=str),
                mean_s=mean_s, type_mass=mass,
                fallback_to_seed_axis=float(
                    sum(1.0 for g in go_counts if g < MIN_GO_RELIABLE)
                    / max(len(go_counts), 1)),
                median_go_reliable=float(np.median(go_counts)),
                median_cos_to_seed=float(np.median(cosines)) if cosines else 0.0,
                n_bins_used=float(np.median(bins_used)),
                target_frac_mean=float(real_weighted / tot),
                achieved_frac_mean=float(achieved / tot))
    diag['rho_target'] = float(real_weighted / tot)
    return W, diag, axis


def _lineage_projection(Xw, Xe, dw, de, rows, erows, related, rng):
    """Depth-stratified matched-neighbour axis and donor projections for a label.

    Returns ``None`` when the lineage does not have enough depth-matched
    support or fewer than MIN_GO_RELIABLE reliable GO-linked genes.
    """
    # ---- pooled PCA space on variable NON-GO genes (direction-free) ---------
    pooled = np.vstack([Xe[erows], Xw[rows]])
    var = pooled.var(0)
    cand = np.flatnonzero((~related) & np.isfinite(var) & (var > 1e-10))
    if cand.size < MIN_PCA_GENES:
        return None
    take = cand[np.argsort(-var[cand], kind='stable')[:MAX_PCA_GENES]]
    mu = pooled[:, take].mean(0)
    sd = pooled[:, take].std(0)
    sd = np.where(sd > 1e-8, sd, 1.0)
    Z = (pooled[:, take] - mu) / sd
    try:
        U, S, _Vt = np.linalg.svd(Z, full_matrices=False)
    except np.linalg.LinAlgError:
        return None
    k = int(min(MAX_COMPONENTS, S.size))
    coord = U[:, :k] * S[:k]
    n_e = erows.size
    c_e = coord[:n_e]
    c_w = coord[n_e:]

    # ---- shared detection depths and the two independent WT halves ----------
    edges = np.unique(np.quantile(dw[rows], BIN_QUANTILES))
    bins_e = np.searchsorted(edges, de[erows], side='right')
    bins_w = np.searchsorted(edges, dw[rows], side='right')
    n_bins = len(edges) + 1
    perm_e = rng.permutation(n_e)
    perm_w = rng.permutation(rows.size)
    half_e = np.zeros(n_e, dtype=int)
    half_w = np.zeros(rows.size, dtype=int)
    half_e[perm_e[n_e // 2:]] = 1
    half_w[perm_w[rows.size // 2:]] = 1

    contrasts, weights_bins, cont_h1, cont_h2, w_h1, w_h2 = [], [], [], [], [], []
    used = 0
    for b in range(n_bins):
        wb = np.flatnonzero(bins_w == b)
        eb = np.flatnonzero(bins_e == b)
        if wb.size < MIN_BIN_CELLS or eb.size < MIN_BIN_CELLS:
            continue
        c = _bin_contrast(coord, np.vstack([Xe[erows], Xw[rows]]),
                          wb + n_e, eb)
        if c is None or not np.all(np.isfinite(c)):
            continue
        # half-split contrasts for the sign-recurrence filter
        ch = []
        cnt = []
        for h in (0, 1):
            wbh = wb[half_w[wb] == h]
            ebh = eb[half_e[eb] == h]
            if wbh.size < MIN_BIN_CELLS or ebh.size < MIN_BIN_CELLS:
                ch = []
                break
            chh = _bin_contrast(coord, np.vstack([Xe[erows], Xw[rows]]),
                                wbh + n_e, ebh)
            if chh is None or not np.all(np.isfinite(chh)):
                ch = []
                break
            ch.append(chh)
            cnt.append(wbh.size)
        if len(ch) != 2:
            continue
        contrasts.append(c)
        weights_bins.append(float(wb.size))
        cont_h1.append(ch[0])
        cont_h2.append(ch[1])
        w_h1.append(float(cnt[0]))
        w_h2.append(float(cnt[1]))
        used += 1
    if used == 0 or not contrasts:
        return None
    # Require the supported bins to cover at least half of each WT half (the
    # depth-matched comparison must not live on a small corner of the data).
    if (sum(w_h1) < HALF_BIN_MIN_COVER * (rows.size / 2.0)
            or sum(w_h2) < HALF_BIN_MIN_COVER * (rows.size / 2.0)):
        return None
    wb = np.asarray(weights_bins, dtype=float)
    full = np.average(np.vstack(contrasts), axis=0, weights=wb)
    h1 = np.average(np.vstack(cont_h1), axis=0, weights=np.asarray(w_h1))
    h2 = np.average(np.vstack(cont_h2), axis=0, weights=np.asarray(w_h2))
    reliable = ((h1 * h2 > 0) & (np.minimum(np.abs(h1), np.abs(h2))
                                >= MIN_ABS_HALF)
                & (full * (h1 + h2) > 0))
    n_go = int(np.count_nonzero(reliable & related))
    if n_go < MIN_GO_RELIABLE:
        return None
    # GO-linked genes get double the signed contrast weight (relevance prior,
    # direction still comes from the measured WT trend).
    axis = full * reliable.astype(float) * (1.0 + related.astype(float))
    dd = float(axis @ axis)
    if not np.isfinite(dd) or dd <= 1e-10:
        return None
    # ---- donor projections, centred inside each depth bin -------------------
    s = np.zeros(rows.size, dtype=np.float64)
    for b in range(n_bins):
        rb = bins_w == b
        if not rb.any():
            continue
        mu_b = Xw[rows][rb].mean(0)
        s[rb] = (Xw[rows][rb] - mu_b) @ axis / dd
    if not np.all(np.isfinite(s)) or float(s.std()) <= 1e-9:
        return None
    return dict(axis=axis, s=s, bins=bins_w, n_bins=float(used),
                n_go_reliable=float(n_go))
