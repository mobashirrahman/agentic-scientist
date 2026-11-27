"""Detection-quartile + WT-maturation ordering of latest-WT donors (T3).

Why this module exists
----------------------
``perturbation_prior_composition.realise`` draws donors with weighted
SYSTEMATIC resampling (one uniform phase per lineage).  A systematic sweep is
sensitive to the *order* of the donors: consecutive entries of the cumulative
donor distribution receive consecutive output slots, so if similar rows sit
next to each other in native input order a shared phase error can duplicate a
whole run of them.  Gerber, Chopin & Whiteley (arXiv:1707.01845) show systematic
resampling can even be inconsistent for some orderings, and Douc, Cappe &
Moulines (arXiv:cs/0507025, sec. 3.4) construct interleaved particles whose
systematic variance stays large -- the input order is the source in both cases.

The perturbation mechanism is unchanged (same lineage quotas, same conditional
donor probabilities, same systematic phase).  Only the finite-sample
realisation is ordered so that CDF neighbours are close on *developmental
state at comparable detection depth*:

  * detection depth = number of detected shared genes, already supplied as the
    masked panel (the knockout gene is masked from the inputs by the evaluator);
  * within each latest-WT lineage, the depth quartiles of the latest stage are
    computed and deduplicated; the SAME cut points are applied to the earlier
    cells so the two stages are compared at like depth;
  * in each (lineage, depth bin) supported by at least ``MIN_BIN_ROWS`` cells
    at BOTH endpoints, the earlier-like direction is the measured WT interval
    contrast

        d = mean(earlier | label, bin) - mean(latest | label, bin)

    and each donor's coordinate is its projection on that direction

        s_i = (x_i - mean(latest | label, bin)) . d / ||d||.

    ``d`` is measured only from the two supplied wild-type stages; no knockout
    outcome, gene name, stage value or split identity enters it.  Where a bin
    has too few cells or a degenerate direction the projection is set to zero
    (so the order falls back to the depth bin).
  * the donor order inside each lineage is the lexicographic sort
    (depth bin, ascending s, original source row).  The original row index is
    the final tie-breaker, so the order is deterministic and independent of
    how the caller happens to list donors.

This is a finite-sample-variance lever: under either ordering a systematic
draw has the same expectation, so the only measurable effect is a smaller
directional sampling error, which can interact with nonlinear DE ranks and
severity scoring.  Nothing here changes the donor law or the output size.
"""
import numpy as np

# ---- pre-registered constants (fixed a priori, never swept on dev) ----------
MIN_BIN_ROWS = 8          # WT rows required at EACH endpoint for a local axis
QUANTILES = (0.25, 0.50, 0.75)
NORM_FLOOR = 1e-8         # degenerate-direction floor


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
    """Selected columns as a float64 ndarray (sparse safe)."""
    if hasattr(X, 'toarray'):
        return np.asarray(X.tocsc()[:, cols].toarray(), dtype=np.float64)
    return np.asarray(np.asarray(X)[:, cols], dtype=np.float64)


def _detection(X):
    """Per-cell number of detected (non-zero) shared genes."""
    if hasattr(X, 'getnnz'):
        return np.asarray(X.getnnz(axis=1)).ravel().astype(np.float64)
    return np.count_nonzero(np.asarray(X), axis=1).astype(np.float64)


def donor_rank(earlier, wt):
    """Per-row sort rank for the systematic donor sweep, aligned to ``wt`` rows.

    Returns ``(rank, diag)``.  ``rank`` is an int array of length ``wt.n_obs``:
    inside each latest-WT lineage, row i's rank is its position under the
    ordering (detection bin, ascending WT-interval projection, source row).
    ``rank`` is unique inside a lineage, so ``np.argsort(rank[donors])`` is the
    permutation of that lineage's donor list.  ``diag`` holds flat scalars for
    ``uns`` (how much of the pool was ordered, how many bins had a measured
    axis).  A missing earlier stage, too few shared genes or a degenerate
    embedding gives the identity rank (native order).
    """
    n = int(wt.n_obs)
    rank = np.arange(n, dtype=np.int64)
    diag = dict(applied=0.0, reason='ok', n_shared_genes=0.0, n_labels=0.0,
                n_ranked_rows=0.0, n_axis_rows=0.0, n_axis_labels=0.0,
                mean_abs_rank_shift=0.0, max_abs_rank_shift=0.0,
                n_duplicate_cut_sets=0.0)
    if earlier is None:
        diag['reason'] = 'no_earlier_input'
        return rank, diag
    cw, ce, genes = _shared_columns(earlier, wt)
    diag['n_shared_genes'] = float(len(genes))
    if len(genes) < 2:
        diag['reason'] = 'too_few_shared_genes'
        return rank, diag
    wlab = np.asarray(wt.obs['celltype'].astype(str)).ravel()
    alab = np.asarray(earlier.obs['celltype'].astype(str)).ravel()
    Xw = _dense(wt.X, cw)
    Xe = _dense(earlier.X, ce)
    dw = _detection(wt.X[:, cw])
    de = _detection(earlier.X[:, ce])
    labels = np.unique(wlab)
    n_axis_labels = 0
    n_axis_rows = 0
    n_dup = 0
    n_moved = 0
    shift_sum = 0.0
    shift_max = 0.0
    for label in labels:
        rows = np.flatnonzero(wlab == label)
        if rows.size == 0:
            continue
        cuts = np.unique(np.quantile(dw[rows], QUANTILES))
        if cuts.size < len(QUANTILES):
            n_dup += 1
        wb = np.searchsorted(cuts, dw[rows], side='right')
        score = np.zeros(rows.size, dtype=np.float64)
        erows = np.flatnonzero(alab == label)
        if erows.size:
            eb = np.searchsorted(cuts, de[erows], side='right')
            got_axis = False
            for b in np.unique(wb):
                w = np.flatnonzero(wb == b)
                e = np.flatnonzero(eb == b)
                if w.size < MIN_BIN_ROWS or e.size < MIN_BIN_ROWS:
                    continue
                mu = Xw[rows[w]].mean(0)
                d = Xe[erows[e]].mean(0) - mu
                norm = float(np.sqrt(float(d @ d)))
                if not np.isfinite(norm) or norm <= NORM_FLOOR:
                    continue
                score[w] = (Xw[rows[w]] @ d - float(mu @ d)) / norm
                got_axis = True
                n_axis_rows += int(w.size)
            if got_axis:
                n_axis_labels += 1
        # Lexicographic order inside the lineage: depth bin, maturation score,
        # original source row.  np.lexsort uses the LAST key as primary.
        perm = np.lexsort((rows, score, wb))
        local = np.empty(rows.size, dtype=np.int64)
        local[perm] = np.arange(rows.size, dtype=np.int64)
        rank[rows] = local
        # Diagnostic relative to the native order inside the SAME lineage
        # (rows are ascending, so the native local rank is 0..size-1).
        diff = np.abs(local - np.arange(rows.size, dtype=np.int64))
        n_moved += int(np.count_nonzero(diff))
        shift_sum += float(diff.sum())
        shift_max = max(shift_max, float(diff.max()) if diff.size else 0.0)
    diag.update(applied=1.0,
                n_labels=float(len(labels)),
                n_ranked_rows=float(n),
                n_axis_rows=float(n_axis_rows),
                n_axis_labels=float(n_axis_labels),
                n_duplicate_cut_sets=float(n_dup),
                n_moved_rows=float(n_moved),
                frac_moved_rows=float(n_moved / max(n, 1)),
                mean_abs_rank_shift=float(shift_sum / max(n, 1)),
                max_abs_rank_shift=float(shift_max))
    return rank, diag
