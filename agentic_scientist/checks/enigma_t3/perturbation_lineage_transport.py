"""Locally bidirectional WT-interval lineage transport at a matched donor budget (T3).

Why this exists
---------------
The seed realises a knockout response as a *single* backward WT-interval
composition rollback: every supported annotation moves toward its earlier
relative abundance with the same exponent, and a breadth-gated flat component
can add a further gene-blind flattening.  A single time direction forces every
lineage to inherit the same interpretation of one interval.  But within an
interval populations expand, contract or hold their prevalence by different
amounts, and the knocked-out gene's own conditional expression contrast may
contradict the shared backward move for a particular lineage (the diagnostic
case is the native Neural Tube, whose share rises 6.1% -> 15.0% across E8.5 ->
E8.75 while the seed still under-represents the analogous target category).

Mechanism (gene-agnostic, WT-only, no mutant data, no gene names)
---------------------------------------------------------------
Work on the shared measured panel of the two supplied WT stages (the
knock-out symbol itself is dropped from the panel, i.e. the same knockout mask
is applied to both arms).  Let

    r_g = E_{p_mix}[x_g] - mean_wt[x_g]

be the *expected* pseudobulk of the seed's pre-calibration donor law minus the
latest WT pseudobulk.  This is the seed's gene-conditioned response direction,
already available for an off-panel knockout because it is produced from the
whole-transcriptome prior.  Remove the parts of r_g that are not gene-
conditioned: a constant (global level), the latest-WT detection frequency by
gene (depth/complexity), and the earlier->latest WT pseudobulk contrast (the
generic developmental-delay axis), by rank-safe least squares

    r = X b + e,   X = [1, det_g, mean_earlier_g - mean_latest_g].

For a lineage l let mu_l be its p_mix-conditional latest-WT mean, centred on
the global latest-WT mean.  Then

    z_l = (mu_l - mean_wt) . e / |e|

is the signed projection of the seed's residual response onto that lineage:
positive when giving the lineage more mass pushes the pseudobulk along the
seed's gene-conditioned residual.

The blind score is the observed WT share change itself,

    d_l = share_earlier(l) - share_latest(l)   (>= 30 cells at both stages),
    b_l = standardise(d_l)  (over supported labels),

i.e. the plain backward-rollback direction with no gene information.  Both
scores are standardised, clipped to +-2 and combined as

    score_l = b_l + LAMBDA * z_l,        LAMBDA = 0.5 (pre-registered),

so a strong gene-conditioned residual can locally reverse the sign of the
rollback for an individual lineage while the WT share change keeps the
capacity.  LAMBDA = 0 is the matched gene-blind comparator: same donors, same
budget, same seed background, no gene-conditioned term.

Allocation
----------
The integer budget is

    B = floor(N * min(0.02, 0.25 * min(sum(d^+), sum(-d^-)))),

where d is the signed WT share difference on supported labels.  That is a 2%
total mass move, small relative to the observed turnover and independent of
elapsed time (bounded behaviour at long horizons).  Additions come from the
highest scores and removals from the lowest, over DISJOINT lineages, capped
per lineage at floor(N * |d_l|) and never taking a lineage's last parent slot.
Unsupported labels (fewer than 30 cells at either stage) never move.  Ties
resolve by stable (sorted) label order.

Realisation
-----------
The seed's own systematic sampler is reused for every parent slot.  For a
lineage whose integer quota is unchanged, the exact parent draws are kept.
A lineage that gains k slots gets k extra intact latest-WT donors drawn
systematically at that lineage's within-type p_mix weights from an
independent RNG stream; a lineage that loses slots drops the tail of its
parent draw.  Every output row is therefore a real latest-WT cell with its
whole expression vector, source_row provenance and coordinates.  Total cell
count is preserved exactly, both arms move exactly B slots, and the existing
perturbation.py calibration runs unchanged on top.

If the interval/panel is unsupported, the residual is degenerate, either arm
cannot place its full B, or the gate below is closed, the exact seed donor
rows are returned (``applied = 0``): the chain falls back to the parent.
The low-exposure no-harm gate is shared with the parent's flat component
(absolute prior exposure a_all > FLAT_A_FLOOR), so a gene the WT barely
expresses is bit-identical to the seed.
"""
import numpy as np
from scipy import sparse

# ---- pre-registered constants (fixed a priori, never swept on dev) ----------
MIN_CELLS = 30          # label support required at BOTH WT stages
LAMBDA = 0.5            # pre-registered weight of the gene-conditioned score
BUDGET_CAP = 0.02       # hard cap on the transported share of N
BUDGET_FRAC = 0.25      # fraction of the smaller observed one-sided capacity
CLIP_STD = 2.0          # clip on both standardised scores
STD_FLOOR = 1e-9
MIN_PANEL = 50          # shared measured genes required
EXTRA_SEED = 0x5EEDBEEF  # independent stream for additions (parent draws kept)


def _dense_cols(X, cols):
    """Dense float64 copy of the selected columns (sparse or dense safe)."""
    if sparse.issparse(X):
        return np.asarray(X.tocsc()[:, cols].todense(), dtype=np.float64)
    return np.asarray(X[:, cols], dtype=np.float64)


def _detection(X, cols):
    """Fraction of cells with a positive value, per selected column."""
    n = max(float(X.shape[0]), 1.0)
    if sparse.issparse(X):
        sub = X.tocsc()[:, cols]
        return np.asarray((sub > 0).sum(0)).ravel().astype(np.float64) / n
    return (np.asarray(X[:, cols]) > 0).mean(0).astype(np.float64)


def _panel(wt, earlier, knockout):
    """Shared measured panel, first occurrence, knockout symbol masked out."""
    pos = {}
    for j, g in enumerate(str(v) for v in earlier.var_names):
        pos.setdefault(g, j)
    ko = None if knockout is None else str(knockout).lower()
    cw, ce, genes, seen = [], [], [], set()
    for j, g in enumerate(str(v) for v in wt.var_names):
        if g in seen or g not in pos:
            continue
        seen.add(g)
        if ko is not None and g.lower() == ko:
            continue
        cw.append(j)
        ce.append(pos[g])
        genes.append(g)
    return (np.asarray(cw, dtype=int), np.asarray(ce, dtype=int), genes)


def _standardise(x, supported):
    """Centre/scale over supported labels only; zeros elsewhere."""
    out = np.zeros(x.size, dtype=np.float64)
    if not np.any(supported):
        return out
    v = np.asarray(x[supported], dtype=np.float64)
    sd = float(v.std())
    if not np.isfinite(sd) or sd <= STD_FLOOR:
        return out
    out[supported] = (v - float(v.mean())) / sd
    return np.clip(out, -CLIP_STD, CLIP_STD)


def _allocate(score, cap, counts, supported, budget):
    """Add from the highest scores, remove from the lowest, over disjoint labels."""
    n_types = score.size
    add = np.zeros(n_types, dtype=int)
    rem = np.zeros(n_types, dtype=int)
    if budget <= 0 or not np.any(supported):
        return add, rem, 0
    idx = np.flatnonzero(supported)
    order_add = idx[np.argsort(-score[idx], kind='stable')]
    order_rem = idx[np.argsort(score[idx], kind='stable')]
    left = int(budget)
    used_add = set()
    for l in order_add:
        take = int(min(int(cap[l]), left))
        if take > 0:
            add[l] = take
            used_add.add(int(l))
            left -= take
        if left <= 0:
            break
    if left > 0:
        return add, rem, 0            # infeasible additions
    left = int(budget)
    for l in order_rem:
        if int(l) in used_add:
            continue
        room = int(counts[l]) - 1     # never take a lineage's last parent slot
        take = int(min(int(cap[l]), room, left))
        if take > 0:
            rem[l] = take
            left -= take
        if left <= 0:
            break
    if left > 0:
        return add, rem, 0            # infeasible removals
    return add, rem, int(budget)


def _flat_diag(reason):
    """Flat diagnostics record for every abstaining path."""
    return dict(applied=0.0, reason=reason, lam=LAMBDA, budget=0.0,
                n_supported=0.0, n_add=0.0, n_rem=0.0,
                residual_norm=0.0, n_panel_genes=0.0, a_all=0.0,
                tv_candidate_vs_parent=0.0, tv_blind_vs_parent=0.0,
                tv_candidate_vs_blind=0.0, n_sign_reversals=0.0,
                quotas=np.zeros(0), add=np.zeros(0), rem=np.zeros(0),
                scores=np.zeros(0), blind=np.zeros(0),
                types=np.asarray([], dtype=str))


def plan(wt, earlier, types, p_mix, counts, n, context, active, a_all):
    """Score lineages and return the transported integer quotas (or abstain).

    Returns a dict with ``applied`` (1.0/0.0) and, when applied, the new
    integer ``counts`` plus the per-lineage ``add``/``rem`` moves and the
    diagnostics recorded in ``uns['donor_transport']``.
    """
    diag = _flat_diag('inactive')
    diag['a_all'] = float(a_all) if np.isfinite(a_all) else 0.0
    if not active:
        diag['reason'] = 'low_exposure_gate'
        return diag
    if earlier is None:
        diag['reason'] = 'no_earlier_input'
        return diag
    try:
        cw, ce, genes = _panel(wt, earlier, context.get('knockout'))
    except Exception:
        diag['reason'] = 'panel_failed'
        return diag
    diag['n_panel_genes'] = float(len(genes))
    if len(genes) < MIN_PANEL:
        diag['reason'] = 'unsupported_panel'
        return diag
    try:
        Xw = _dense_cols(wt.X, cw)
        Xe = _dense_cols(earlier.X, ce)
        det = _detection(wt.X, cw)
    except Exception:
        diag['reason'] = 'panel_materialise_failed'
        return diag
    if (not np.all(np.isfinite(Xw)) or not np.all(np.isfinite(Xe))
            or not np.all(np.isfinite(det))):
        diag['reason'] = 'non_finite_panel'
        return diag

    wlab = np.asarray(wt.obs['celltype'].astype(str)).ravel()
    alab = np.asarray(earlier.obs['celltype'].astype(str)).ravel()
    n_types = len(types)

    mu_w = Xw.mean(0)
    mu_e = Xe.mean(0)
    p = np.asarray(p_mix, dtype=np.float64)
    p = np.where(np.isfinite(p) & (p > 0), p, 0.0)
    if p.size != wt.n_obs or float(p.sum()) <= 0:
        diag['reason'] = 'invalid_parent_law'
        return diag
    p = p / float(p.sum())

    # Gene-conditioned seed response direction, then remove global level,
    # detection and the generic WT interval axis (rank-safe least squares).
    r = p @ Xw - mu_w
    design = np.column_stack([np.ones_like(det), det, mu_e - mu_w])
    try:
        coef, _res, _rank, _sv = np.linalg.lstsq(design, r, rcond=None)
        e = r - design @ coef
    except Exception:
        diag['reason'] = 'residual_regression_failed'
        return diag
    e_norm = float(np.linalg.norm(e))
    diag['residual_norm'] = e_norm
    if not np.isfinite(e_norm) or e_norm <= 1e-9:
        diag['reason'] = 'degenerate_residual'
        return diag
    e_hat = e / e_norm

    # Per-lineage conditional latest-WT means (centred on the global mean).
    n_l = np.zeros(n_types, dtype=float)
    n_e = np.zeros(n_types, dtype=float)
    z = np.zeros(n_types, dtype=float)
    for i, t in enumerate(types):
        rows = np.flatnonzero(wlab == t)
        n_l[i] = float(rows.size)
        n_e[i] = float(np.count_nonzero(alab == t))
        if rows.size == 0:
            continue
        w = p[rows]
        sw = float(w.sum())
        if sw <= 0:
            continue
        z[i] = float((w @ Xw[rows] / sw - mu_w) @ e_hat)
    supported = (n_l >= MIN_CELLS) & (n_e >= MIN_CELLS)
    if int(supported.sum()) < 3:
        diag['reason'] = 'too_few_supported_labels'
        return diag

    f = n_l / max(float(wt.n_obs), 1.0)
    f_e = n_e / max(float(earlier.n_obs), 1.0)
    d = np.zeros(n_types, dtype=float)
    d[supported] = (f_e - f)[supported]

    zs = _standardise(z, supported)
    bs = _standardise(d, supported)
    score = bs + LAMBDA * zs
    blind = bs

    pos_cap = float(np.sum(np.maximum(d[supported], 0.0)))
    neg_cap = float(np.sum(np.maximum(-d[supported], 0.0)))
    if not (np.isfinite(pos_cap) and np.isfinite(neg_cap)) or min(pos_cap, neg_cap) <= 0:
        diag['reason'] = 'no_two_sided_capacity'
        return diag
    budget = int(np.floor(float(n) * min(BUDGET_CAP, BUDGET_FRAC * min(pos_cap, neg_cap))))
    diag['budget'] = float(budget)
    if budget <= 0:
        diag['reason'] = 'zero_budget'
        return diag

    counts = np.asarray(counts, dtype=float)
    if counts.size != n_types:
        diag['reason'] = 'quota_mismatch'
        return diag
    # Capacities are the observed |share change| in slots, as pre-registered.
    cap = np.floor(float(n) * np.abs(d)).astype(int)
    cap[~supported] = 0
    add, rem, placed = _allocate(score, cap, counts, supported, budget)
    if placed != budget:
        diag['reason'] = 'budget_infeasible'
        return diag

    # Blind arm: identical machinery, gene-blind score (same donors, budget).
    add_b, rem_b, placed_b = _allocate(blind, cap, counts, supported, budget)
    # Disjointness / quota bookkeeping is validated by the caller on the real
    # parent quotas; here we only need the arm-level direction comparison.
    if placed_b == budget:
        shared_flip = ((add > 0) & (rem_b > 0)) | ((add_b > 0) & (rem > 0))
        diag['n_sign_reversals'] = float(np.count_nonzero(shared_flip))
        q_c = (add - rem).astype(float) / float(budget)
        q_b = (add_b - rem_b).astype(float) / float(budget)
        diag['tv_candidate_vs_blind'] = float(0.5 * np.abs(q_c - q_b).sum())

    diag.update(applied=1.0, reason='ok', n_supported=float(supported.sum()),
                n_add=float(add.sum()), n_rem=float(rem.sum()),
                add=add, rem=rem, quotas=(add - rem).astype(float),
                scores=score, blind=blind, types=np.asarray([str(t) for t in types]),
                tv_candidate_vs_parent=float(0.5 * np.abs(add - rem).sum() / max(n, 1)),
                tv_blind_vs_parent=float(0.5 * np.abs(add_b - rem_b).sum() / max(n, 1)))
    return diag


def retarget(wt, idx, counts, types, p_mix, diag, seed):
    """Apply the planned quota moves to the parent draw, keeping parent rows.

    Unchanged lineages keep their exact parent index list; a lineage that loses
    slots drops the tail of its list; a lineage that gains slots gets extra
    intact donors drawn systematically from that lineage's p_mix weights with
    an independent RNG stream (so the parent stream is untouched).
    Returns ``(idx, counts)`` or ``(None, None)`` if the result fails its
    totals check.
    """
    add = np.asarray(diag.get('add', []), dtype=int)
    rem = np.asarray(diag.get('rem', []), dtype=int)
    n_types = len(types)
    if add.size != n_types or rem.size != n_types:
        return None, None
    wlab = np.asarray(wt.obs['celltype'].astype(str)).ravel()
    new_counts = np.asarray(counts, dtype=int) + add - rem
    base_total = int(np.sum(counts))
    if int(np.sum(new_counts)) != base_total or np.any(new_counts < 1):
        return None, None
    p = np.asarray(p_mix, dtype=np.float64)
    p = np.where(np.isfinite(p) & (p > 0), p, 0.0)
    if p.size != wt.n_obs or float(p.sum()) <= 0:
        return None, None
    p = p / float(p.sum())
    rng = np.random.default_rng(int(seed) ^ EXTRA_SEED)
    idx = np.asarray(idx, dtype=int)
    chosen = []
    offset = 0
    for i, t in enumerate(types):
        k_old = int(counts[i])
        k_new = int(new_counts[i])
        block = idx[offset:offset + k_old]
        offset += k_old
        if k_new <= k_old:
            chosen.append(block[:k_new])
            continue
        chosen.append(block)
        donors = np.flatnonzero(wlab == t)
        need = k_new - k_old
        if donors.size == 0:
            return None, None
        q = p[donors]
        if float(q.sum()) <= 0:
            q = np.ones(donors.size, dtype=float)
        q = q / float(q.sum())
        # Systematic (low-variance) resampling, same convention as the seed
        # sampler: counts differ from need*q by less than one.
        c = np.cumsum(q) * need
        u = np.arange(need, dtype=float) + rng.random()
        pos = np.searchsorted(c, u, side='left')
        chosen.append(donors[np.minimum(pos, donors.size - 1)])
    if offset != idx.size:
        return None, None
    out = np.concatenate([b for b in chosen if b.size]) if chosen else np.zeros(0, int)
    if int(out.size) != base_total:
        return None, None
    return out, new_counts
