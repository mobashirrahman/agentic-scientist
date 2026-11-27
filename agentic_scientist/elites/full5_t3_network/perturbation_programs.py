"""Program-space knockout response projected onto real latest-stage donors.

Architecture family 2 of the T3 menu ("gene-program model").  A small
non-negative factorization (NMF) is fitted to the passed WT cells of BOTH
supplied stages, in the latest stage's gene order.  The programs are cell
*activities*: the factor H gives each program's gene loading, the activation
Z gives each latest WT cell's usage.  The measured knockout gene loads into a
subset of programs; a fixed HALF-STRENGTH suppression is applied only to the
activities of those programs:

    s_k       = ||H_k||_2                     (removes the NMF scale ambiguity)
    Hunit_k   = H_k / s_k
    A_ik      = Z_ik * s_k                    (absolute activity, NOT a fraction)
    w_k       = Hunit[k,g] / sum_l Hunit[l,g] (the gene's loading share)
    target_ik = Astd_ik * (1 - 0.5 * w_k)

Absolute activities are used deliberately.  Renormalizing activities to
fractions summing to one cancels the suppression in nearly pure-program cells
and the WT probe (analysis/program_probe.json) showed that variant was almost
inert.  This is a dependency prior, not a claim that coexpression proves
regulation.

The weakened activity vectors are then mapped back onto REAL cells of the
latest WT stage: within each original ``obs['celltype']`` annotation the single
nearest latest donor is chosen for every target vector.  A cell's state
probability is moved from the parent donor law p0 to that real donor with
weight equal to the knockout gene's detection fraction q_t in the cell's own
latest WT annotation:

    p1[j] = p0[j] * (1 - q_type(j)) + sum_{i: T(i)=j} p0[i] * q_type(i)

This analytical pushforward (the expectation tested in
analysis/program_absolute_probe.py) is mass-preserving per annotation by
construction: every cell's probability is either kept at its own row or moved
to another row of the SAME annotation.  No synthetic expression is generated,
no smoothing is applied, and the parent annotation masses are untouched.

Fallbacks are input-contract only (symbol absent, too few detecting cells, no
earlier input, zero gene loading, degenerate fit): the parent p0 is returned
unchanged.  There is no outcome-dependent switching.
"""
import numpy as np
from scipy import sparse
from sklearn.decomposition import NMF
from sklearn.neighbors import NearestNeighbors

from perturbation_local_rollback import resolve_symbol, _detection

# Pre-registered constants: one fixed factorization and one fixed half-strength
# suppression.  They are NOT searched on the dev knockout.
N_PROGRAMS = 8
CORESET_PER_STAGE = 1200
SUPPRESSION = 0.5
STD_FLOOR = 1e-6
MAX_ITER = 200


def _aligned(stage, wt_names):
    """Columns of ``stage`` matching each latest-stage gene (first match), -1 if absent."""
    pos = {}
    for j, v in enumerate(stage.var_names):
        pos.setdefault(str(v), j)
    return np.array([pos.get(g, -1) for g in wt_names], dtype=int)


def _fallback(p0, reason, n_prog=0):
    p = np.asarray(p0, dtype=np.float64)
    p = p / max(float(p.sum()), 1e-12)
    n = len(p)
    diag = dict(applied=0.0, reason=str(reason), n_programs=float(n_prog),
                donor_tv=0.0, mean_target_displacement=0.0,
                projected_displacement=0.0,
                achieved_weighted_program_reduction=0.0,
                max_annotation_mass_error=0.0, effective_donor_count=float(1.0 / max(float((p ** 2).sum()), 1e-12)),
                n_detected=0.0, exposure_mass=0.0,
                program_weights=np.zeros(max(n_prog, N_PROGRAMS), dtype=float),
                fit_iterations=0.0, reconstruction_relative_error=0.0)
    return p, diag


def program_probabilities(earlier, wt, knockout, p0, fit_seed):
    """Return (p1, diagnostics) for the program-space knockout projection.

    ``p0`` is the parent donor law (complexity law x local rollback), length
    ``wt.n_obs`` and aligned with the latest WT rows.  All randomness is seeded
    by ``fit_seed``, the parent's factorization seed.
    """
    p0 = np.asarray(p0, dtype=np.float64)
    n = wt.n_obs
    if earlier is None:
        return _fallback(p0, 'no_earlier_input')
    if p0.shape[0] != n or not np.all(np.isfinite(p0)) or p0.sum() <= 0:
        return _fallback(p0, 'invalid_parent_law')

    wt_names = [str(v) for v in wt.var_names]
    cols = _aligned(earlier, wt_names)
    present = cols >= 0
    if int(present.sum()) < 2:
        return _fallback(p0, 'no_shared_genes')
    wcols = np.flatnonzero(present)[:, None]
    ecols = cols[present][:, None]
    # Sparse column selection keeps both stages in the latest gene order.
    ex = earlier.X.tocsc()[:, ecols.ravel()]
    wxx = wt.X.tocsc()[:, wcols.ravel()]
    ex = sparse.csr_matrix(ex)
    wxx = sparse.csr_matrix(wxx)

    labels_e = np.asarray(earlier.obs['celltype'].astype(str)).ravel()
    labels_w = np.asarray(wt.obs['celltype'].astype(str)).ravel()

    # ---- fixed NMF baseline on an annotation-stratified coreset of both stages ----
    rng = np.random.default_rng(fit_seed)
    ie, _ = _coreset(labels_e, CORESET_PER_STAGE, rng)
    iw, _ = _coreset(labels_w, CORESET_PER_STAGE, rng)
    xfit = sparse.vstack([ex[ie], wxx[iw]], format='csr')
    n_vars = int(xfit.shape[1])
    k = int(min(N_PROGRAMS, n_vars - 1, xfit.shape[0] - 1))
    if k < 1 or xfit.nnz == 0:
        return _fallback(p0, 'degenerate_fit')
    model = NMF(n_components=k, init='nndsvda', random_state=fit_seed,
                max_iter=MAX_ITER)
    try:
        model.fit(xfit)
        z = model.transform(wxx)
    except Exception:
        return _fallback(p0, 'fit_failed', k)

    h = np.asarray(model.components_, dtype=np.float64)          # k x n_vars
    s = np.linalg.norm(h, axis=1)
    if not np.all(np.isfinite(h)) or np.any(s <= 0):
        return _fallback(p0, 'degenerate_components', k)
    hunit = h / s[:, None]
    a = np.asarray(z, dtype=np.float64) * s[None, :]              # absolute activity
    if not np.all(np.isfinite(a)):
        return _fallback(p0, 'nonfinite_activity', k)

    # Resolve the knockout symbol against the latest gene list.  ``present_cols``
    # maps fitted-space positions back to the latest stage's own columns.
    present_cols = np.flatnonzero(present)
    sub = resolve_symbol([wt_names[j] for j in present_cols], knockout)
    if sub is None:
        return _fallback(p0, 'uniform_offpanel', k)
    gcol = int(sub)
    gene_col = int(present_cols[sub])
    det = _detection(wt, gene_col)
    n_det = int(det.sum())
    if n_det < int(np.ceil(np.sqrt(n))):
        return _fallback(p0, 'uniform_low_detection', k)

    load = hunit[:, gcol]
    tot = float(load.sum())
    if not np.isfinite(tot) or tot <= 0:
        return _fallback(p0, 'zero_loading', k)
    w = load / tot                                                  # loading shares

    # Standardize activity columns by the LATEST stage's own spread.
    sd = a.std(axis=0)
    astd = a / np.maximum(sd, STD_FLOOR)[None, :]
    target = astd * (1.0 - SUPPRESSION * w[None, :])

    # ---- project each target activity onto a real latest donor of the same annotation ----
    q = np.zeros(n, dtype=np.float64)          # knockout detection fraction per annotation
    donor = np.arange(n, dtype=int)
    for t in np.unique(labels_w):
        rows = np.flatnonzero(labels_w == t)
        q[rows] = float(det[rows].mean())
        nn = NearestNeighbors(n_neighbors=1).fit(astd[rows])
        _, ind = nn.kneighbors(target[rows])
        donor[rows] = rows[np.asarray(ind).ravel()]

    # Analytical pushforward: keep unexposed mass at home, move exposed mass to T(i).
    exposed = p0 * q
    p1 = np.bincount(donor, weights=exposed, minlength=n) + p0 * (1.0 - q)
    total = float(p1.sum())
    if not np.all(np.isfinite(p1)) or total <= 0:
        return _fallback(p0, 'invalid_pushforward', k)
    p1 = p1 / total

    # Mass bookkeeping per original annotation (should be at rounding level).
    err = 0.0
    for t in np.unique(labels_w):
        rows = labels_w == t
        err = max(err, abs(float(p1[rows].sum() - p0[rows].sum())))
    if err > 1e-9:
        return _fallback(p0, 'mass_not_conserved', k)

    moved = exposed
    before = float((moved @ astd) @ w)
    after = float((moved @ astd[donor]) @ w)
    diag = dict(
        applied=1.0, reason='ok', n_programs=float(k),
        donor_tv=float(0.5 * np.abs(p1 - p0).sum()),
        mean_target_displacement=float(np.mean(np.linalg.norm(target - astd, axis=1))),
        projected_displacement=float(np.mean(np.linalg.norm(astd[donor] - astd, axis=1))),
        achieved_weighted_program_reduction=float((before - after) / max(abs(before), 1e-12)),
        max_annotation_mass_error=float(err),
        effective_donor_count=float(1.0 / max(float((p1 ** 2).sum()), 1e-12)),
        n_detected=float(n_det), exposure_mass=float(p0 @ q),
        program_weights=np.asarray(w, dtype=np.float64),
        fit_iterations=float(getattr(model, 'n_iter_', 0)),
        reconstruction_relative_error=float(
            model.reconstruction_err_ / max(float(np.sqrt(xfit.multiply(xfit).sum())), 1e-12)))
    return p1, diag


def _coreset(labels, limit, rng):
    """Local copy of the parent stratified coreset (keeps this module standalone)."""
    from perturbation_transport import coreset
    return coreset(labels, limit, rng)
