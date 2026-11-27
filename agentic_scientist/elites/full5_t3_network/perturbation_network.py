"""T3 architecture family 3: WT-calibrated signed-network propagation.

Why this mechanism exists
-------------------------
The parent sampler re-draws real WT donors within each annotation.  It is
*structurally* gene-aware only through the donor law, so the transcript-level
response of a knockout is at best a small composition change.  The official
diagnostic on the Gata4 backtests showed exactly that: a nonzero but very
poorly calibrated response (through-origin severity fit log beta = -6.908 on
both replicates, i.e. the predicted change is far too small and its direction
barely correlates with the observed one).

A regulator-dependent program can change *within* a lineage even when the
regulator's abundance is conserved.  This module adds one bounded, signed
downstream response to the real donor profiles of the unchanged parent:

1. A local signed association graph is inferred from the passed WT stages only
   (no knockout data).  Each gene is regressed, within its own original
   annotation, on an intercept and log1p(detected-gene count) to remove the
   annotation mean and the detection-complexity effect; the residuals of the
   two WT stages are correlated independently and an edge is retained only if
   its sign agrees at both stages and its weaker absolute residual correlation
   is at least 0.05.  A sign that replicates across two independent wild-type
   samples is a much weaker claim than a causal sign, so the operator is
   deliberately sub-stochastic and damped.
2. The supplied filtered GO dictionary (context['external']) supplies
   *functional similarity*, never an up/down label: shared informative terms
   (5-50 panel genes after ancestor expansion) boost the magnitude of an
   already-signed edge by (1 + Jaccard).  GO membership alone can never create
   or flip a sign.
3. A negative source is placed on the knocked-out gene (or, for a symbol that
   is not on the panel, on its GO-functional analogues -- GEARS-style
   inductance, not an assertion that analogue expression measures the missing
   gene).  The signed response is propagated for three damped steps,
   v = sum_l 0.5**l * s @ A**l, which approximately converges for a
   row-sub-stochastic A.
4. The amplitude is calibrated from WT data alone: one half of the median
   within-type WT stage-contrast L2 norm, multiplied by the knockout's own
   detection fraction inside the recipient annotation.  This separates a
   biological effect-size prior from the arbitrarily small products of
   residual correlation coefficients.  Off-panel analogues get a fixed 0.25
   reliability multiplier.

Everything is added *additively* to the parent's real donor log-expression on
donor-positive entries only (zeros stay zero), clipped to [-0.35, 0.35] and
re-normalised once to CP10k.  Parent composition, donor indices and RNG draws
are untouched.  A low-detection measured gene, an unsupported off-panel symbol
or a degenerate graph adds nothing, so the parent's null path is preserved
exactly (see agentic_scientist/tools/noharm.py).

No gene name, pathway name, stage value or dataset constant is hard-coded: the
only gene-specific input is the passed ``context['knockout']`` symbol.
"""
import numpy as np
from scipy import sparse

from perturbation_transport import normalize_log
from perturbation_local_rollback import resolve_symbol

# Pre-registered constants (fixed before any score was seen; never swept).
MIN_RESIDUAL = 0.05        # replicated |residual correlation| floor for an edge
MIN_TERM_PANEL = 5         # informative GO term: at least this many panel genes
MAX_TERM_PANEL = 50        # ... and at most this many (specific, not the root)
TOP_EDGES = 10             # strongest outgoing edges kept per source gene
TOP_ANALOGUES = 10         # maximal number of functional analogues for a source
DAMPING = 0.5              # per-step decay of the random-walk propagation
N_STEPS = 3                # three iterations approximately converge (CellOracle)
CLIP = 0.35                # per-gene log-expression bound on the increment
HALF_CONTRAST = 0.5        # use one half of the observed WT stage contrast
OFFPANEL_RELIABILITY = 0.25  # fixed uncertainty damping for GO analogues
MIN_TYPE_CELLS = 30        # both WT stages need this support to set the scale


def _ancestor_closure(parents):
    """Memoised transitive GO ancestor closure (iterative, cycle-safe)."""
    memo = {}

    def closure(term):
        if term in memo:
            return memo[term]
        out, stack = set(), [term]
        while stack:
            t = stack.pop()
            if t in out:
                continue
            out.add(t)
            for p in parents.get(t, ()) or ():
                if p not in out:
                    stack.append(p)
        result = frozenset(out)
        memo[term] = result
        return result

    return closure


def _gene_term_set(gene, gene_terms, closure):
    """All GO terms annotating ``gene``, expanded through the supplied parents."""
    out = set()
    for t in gene_terms.get(gene, ()) or ():
        out |= closure(t)
    return out


def _dense_x(a):
    x = a.X
    return np.asarray(x.toarray() if sparse.issparse(x) else x, dtype=np.float64)


def _residual_correlation(a):
    """Pearson correlation of annotation- and complexity-adjusted expression.

    Within every original ``obs['celltype']`` annotation, each gene is
    regressed on an intercept and log1p(detected-gene count); the correlation is
    taken on the residuals.  This removes the annotation means and the shared
    detection-complexity gradient, which otherwise create large lineage- and
    assay-driven correlations that would dominate a 500-gene panel.
    """
    x = _dense_x(a)
    lab = np.asarray(a.obs['celltype'].astype(str)).ravel()
    q = np.log1p((x > 0).sum(axis=1))
    z = np.empty_like(x)
    for t in np.unique(lab):
        rows = np.flatnonzero(lab == t)
        design = np.column_stack([np.ones(rows.size), q[rows] - q[rows].mean()])
        coef, *_ = np.linalg.lstsq(design, x[rows], rcond=None)
        z[rows] = x[rows] - design @ coef
    norm = np.maximum(np.linalg.norm(z, axis=0), 1e-12)
    return (z.T @ z) / norm[:, None] / norm[None, :]


def fit_signed_graph(earlier, latest, external):
    """Build the damped signed association graph from the two WT stages only.

    Returns a dict with the row-sub-stochastic matrix ``w``, the two replicated
    residual correlation matrices (kept for diagnostics), the informative GO
    term sets and the panel gene names.
    """
    names = [str(v) for v in latest.var_names]
    p = len(names)
    # Align the earlier stage by symbol: a gene absent there can carry no
    # replicated edge, so its row/column simply stays zero.
    earlier_names = [str(v) for v in earlier.var_names]
    earlier_pos = {}
    for j, g in enumerate(earlier_names):
        earlier_pos.setdefault(g, j)
    common = [(i, earlier_pos[g]) for i, g in enumerate(names) if g in earlier_pos]
    c0 = np.zeros((p, p), dtype=np.float64)
    c1 = _residual_correlation(latest)
    if common:
        ci = np.array([i for i, _ in common], dtype=int)
        cj = np.array([j for _, j in common], dtype=int)
        sub = _residual_correlation(earlier[:, cj])
        c0[np.ix_(ci, ci)] = sub
    # Both stages must agree on the sign, and the weaker of the two must clear
    # the pre-registered floor: a sign that replicates in two independent WT
    # samples is the weakest defensible claim, not a causal one.
    good = (np.sign(c0) == np.sign(c1)) & (
        np.minimum(np.abs(c0), np.abs(c1)) >= MIN_RESIDUAL)
    np.fill_diagonal(good, False)
    w = np.where(good, np.sign(c0) * np.minimum(np.abs(c0), np.abs(c1)), 0.0)

    # GO functional similarity only *boosts an existing signed edge*; the Jaccard
    # term carries no sign of its own and never creates an edge.
    informative_sets = [set() for _ in range(p)]
    counts_out = {}
    if isinstance(external, dict):
        gene_terms = external.get('gene_terms') or {}
        parents = external.get('term_parents') or {}
        if isinstance(gene_terms, dict) and isinstance(parents, dict) and gene_terms:
            closure = _ancestor_closure(parents)
            counts = {}
            term_sets = []
            for g in names:
                s = _gene_term_set(g, gene_terms, closure)
                term_sets.append(s)
                for t in s:
                    counts[t] = counts.get(t, 0) + 1
            # Terms shared by 5-50 panel genes are specific enough to be
            # informative and broad enough not to be one gene's private label.
            # The ontology root holds every gene and is excluded by the upper
            # bound without naming it.
            valid = {t for t, n in counts.items()
                     if MIN_TERM_PANEL <= n <= MAX_TERM_PANEL}
            informative_sets = [s & valid for s in term_sets]
            counts_out = counts

    for i in range(p):
        rows = np.flatnonzero(w[i])
        if rows.size == 0:
            continue
        si = informative_sets[i]
        for j in rows:
            sj = informative_sets[j]
            union = len(si | sj)
            if union:
                w[i, j] *= 1.0 + len(si & sj) / union

    # Keep the ten strongest absolute outgoing edges per source, deterministic
    # ties broken by panel order, then make every row sub-stochastic.  This is a
    # sparse association operator, not a causal gene-regulatory network.
    for i in range(p):
        idx = np.argsort(-np.abs(w[i]), kind='stable')
        w[i, idx[TOP_EDGES:]] = 0.0
    w /= np.maximum(np.abs(w).sum(axis=1, keepdims=True), 1.0)

    return dict(w=w, c0=c0, c1=c1, names=names, informative_sets=informative_sets,
                term_counts=counts_out)


def _source_vector(graph, latest, knockout):
    """Negative source on the gene itself, or on its GO analogues if off-panel.

    Returns ``(s, mode, diagnostics)``.  A measured gene detected in fewer cells
    than the sqrt(N) sampling resolution, an absent symbol without GO support,
    or an empty analogue set yields ``s is None``: the parent path then stays
    byte-identical instead of receiving a spurious response.
    """
    names = graph['names']
    p = len(names)
    j = resolve_symbol(latest.var_names, knockout)
    n = latest.n_obs
    x = _dense_x(latest)
    lab = np.asarray(latest.obs['celltype'].astype(str)).ravel()
    types = np.unique(lab)
    diag = dict(mode='none', go_coverage=0.0, direct_degree=0.0,
                analogues=np.array([], dtype=str),
                analogue_weights=np.zeros(0, dtype=float),
                source_norm=0.0, detected=0.0)
    if j is not None:
        det = x[:, j] > 0
        k = int(det.sum())
        diag['detected'] = float(k)
        if k < int(np.ceil(np.sqrt(n))):
            # Indistinguishable from a null gene at this sampling depth: never
            # reroute a measured low-expression gene through the analogue branch.
            diag['mode'] = 'low_detection'
            return None, 'low_detection', diag
        s = np.zeros(p)
        s[j] = -1.0
        diag['mode'] = 'measured'
        diag['go_coverage'] = float(len(graph['informative_sets'][j]))
        diag['direct_degree'] = float(np.count_nonzero(graph['w'][j]))
        diag['detection_by_type'] = np.array(
            [float(det[lab == t].mean()) for t in types], dtype=float)
        diag['source_norm'] = 1.0
        return s, 'measured', diag

    # --- Off-panel branch: GO functional analogues as an inductive prior ------
    if not graph['term_counts']:
        diag['mode'] = 'offpanel_no_go'
        return None, 'offpanel_no_go', diag
    # Term sets were computed for every panel gene against the supplied
    # dictionary; the knocked-out symbol is looked up in the same dictionary.
    closure_sets = graph.get('gene_terms_by_symbol') or {}
    target_terms = closure_sets.get(str(knockout))
    if not target_terms:
        diag['mode'] = 'offpanel_no_go'
        return None, 'offpanel_no_go', diag
    valid = {t for t, c in graph['term_counts'].items()
             if MIN_TERM_PANEL <= c <= MAX_TERM_PANEL}
    target_terms = target_terms & valid
    if not target_terms:
        diag['mode'] = 'offpanel_no_go'
        return None, 'offpanel_no_go', diag
    scores = np.array([
        sum(1.0 / graph['term_counts'][t] for t in target_terms & s)
        for s in graph['informative_sets']], dtype=np.float64)
    order = np.argsort(-scores, kind='stable')
    use = [i for i in order[:TOP_ANALOGUES] if scores[i] > 0]
    if not use:
        diag['mode'] = 'offpanel_no_analogues'
        return None, 'offpanel_no_analogues', diag
    use = np.array(use, dtype=int)
    weights = scores[use] / max(scores[use].sum(), 1e-12)
    s = np.zeros(p)
    s[use] = -weights
    diag['mode'] = 'offpanel_analogues'
    diag['go_coverage'] = float(len(target_terms))
    diag['analogues'] = np.array([names[i] for i in use], dtype=str)
    diag['analogue_weights'] = weights
    diag['direct_degree'] = float(np.count_nonzero(graph['w'][use].any(axis=0)))
    diag['detection_by_type'] = np.array(
        [(x[lab == t][:, use] > 0).mean(axis=0) @ weights for t in types],
        dtype=float)
    diag['source_norm'] = float(np.linalg.norm(s))
    return s, 'offpanel_analogues', diag


def propagate(graph, s, source_index=None):
    """v = sum_{l=1..3} DAMPING**l * s @ A**l, computed by iterative products.

    For a measured knockout the direct term v[k] = s[k] is removed: the test is
    about the downstream program, not about the knocked-out transcript itself.
    Signed cancellations are retained; only the L2 norm is normalised away.
    """
    w = graph['w']
    v = np.zeros_like(s)
    curr = s.astype(np.float64).copy()
    for step in range(1, N_STEPS + 1):
        curr = (curr @ w) * (DAMPING ** step)
        v += curr
    if source_index is not None:
        v[source_index] = 0.0
    norm = float(np.linalg.norm(v))
    if not np.isfinite(norm) or norm <= 0.0:
        return None
    return v / norm


def _wt_contrast_norm(earlier, latest):
    """Median L2 norm of the within-type latest-minus-earlier mean expression.

    Only annotations with at least MIN_TYPE_CELLS cells at *both* stages are
    used, so the scale is not set by a handful of migrating or emerging cells.
    """
    names = [str(v) for v in latest.var_names]
    earlier_names = [str(v) for v in earlier.var_names]
    pos = {}
    for j, g in enumerate(earlier_names):
        pos.setdefault(g, j)
    common = [(i, pos[g]) for i, g in enumerate(names) if g in pos]
    if not common:
        return None
    ci = np.array([i for i, _ in common], dtype=int)
    cj = np.array([j for _, j in common], dtype=int)
    xe = _dense_x(earlier[:, cj])
    xl = _dense_x(latest[:, ci])
    elab = np.asarray(earlier.obs['celltype'].astype(str)).ravel()
    llab = np.asarray(latest.obs['celltype'].astype(str)).ravel()
    contrasts = []
    for t in np.unique(llab):
        m_l = llab == t
        m_e = elab == t
        if m_l.sum() < MIN_TYPE_CELLS or m_e.sum() < MIN_TYPE_CELLS:
            continue
        contrasts.append(xl[m_l].mean(axis=0) - xe[m_e].mean(axis=0))
    if not contrasts:
        return None
    return float(np.median(np.linalg.norm(np.asarray(contrasts), axis=1)))


def network_response(earlier, latest, out, knockout, external):
    """Apply the bounded WT-calibrated signed-network response to the parent output.

    ``out`` is the parent's real-donor AnnData.  The increment is added only on
    donor-positive entries, floored at zero and re-normalised once to CP10k.
    Rows whose increment is exactly zero are left byte-identical to the parent
    (never renormalised), so a null or unsupported knockout cannot drift.
    """
    n, p = out.n_obs, out.n_vars
    diag = dict(mode='none', go_coverage=0.0, edges=0.0, direct_degree=0.0,
                graph_scale=0.0, mean_exposure=0.0, reliability=1.0,
                pre_clip_norm=0.0, post_clip_norm=0.0, mean_abs_dX=0.0,
                bulk_change_norm=0.0, changed_cells=0.0,
                analogues=np.array([], dtype=str),
                analogue_weights=np.zeros(0, dtype=float))

    if earlier is None:
        out.uns['network_response'] = diag
        return out

    graph = fit_signed_graph(earlier, latest, external)
    diag['edges'] = float(np.count_nonzero(graph['w']))
    # The off-panel branch needs the knocked-out symbol's own GO closure from
    # the same supplied dictionary; compute it once, memoised via the graph.
    if isinstance(external, dict) and external.get('gene_terms'):
        closure = _ancestor_closure(external.get('term_parents') or {})
        graph['gene_terms_by_symbol'] = {
            str(knockout): _gene_term_set(str(knockout), external['gene_terms'],
                                           closure)}

    s, mode, sdiag = _source_vector(graph, latest, knockout)
    diag.update({k: v for k, v in sdiag.items() if k != 'detection_by_type'})
    if s is None:
        out.uns['network_response'] = diag
        return out

    src = resolve_symbol(latest.var_names, knockout)
    v = propagate(graph, s, source_index=src)
    if v is None:
        diag['mode'] = mode + '_no_downstream'
        out.uns['network_response'] = diag
        return out

    scale = _wt_contrast_norm(earlier, latest)
    if scale is None or not np.isfinite(scale) or scale <= 0.0:
        diag['mode'] = mode + '_no_scale'
        out.uns['network_response'] = diag
        return out
    diag['graph_scale'] = float(scale)

    reliability = OFFPANEL_RELIABILITY if mode == 'offpanel_analogues' else 1.0
    diag['reliability'] = float(reliability)

    # Per-recipient-annotation exposure: the knockout's own detection fraction,
    # or the analogue-weighted mean detection for an off-panel symbol.
    lab = np.asarray(latest.obs['celltype'].astype(str)).ravel()
    types = np.unique(lab)
    detection = sdiag.get('detection_by_type')
    if detection is None:
        diag['mode'] = mode + '_no_exposure'
        out.uns['network_response'] = diag
        return out
    exposure_by_type = {str(t): float(e) for t, e in zip(types, detection)}
    src_rows = np.asarray(out.obs['source_row'], dtype=int)
    exposure = np.array([exposure_by_type.get(str(lab[i]), 0.0)
                         for i in src_rows], dtype=np.float64)
    diag['mean_exposure'] = float(exposure.mean())

    shift = np.outer(exposure, v) * (HALF_CONTRAST * scale * reliability)
    if not np.all(np.isfinite(shift)):
        diag['mode'] = mode + '_nonfinite'
        out.uns['network_response'] = diag
        return out
    pre = float(np.linalg.norm(shift, axis=1).mean())
    np.clip(shift, -CLIP, CLIP, out=shift)
    diag['pre_clip_norm'] = pre
    diag['post_clip_norm'] = float(np.linalg.norm(shift, axis=1).mean())

    x = _dense_x(out)
    if x.shape != (n, p):
        diag['mode'] = mode + '_shape_mismatch'
        out.uns['network_response'] = diag
        return out
    new = np.where(x > 0.0, np.maximum(x + shift, 0.0), 0.0)
    changed = np.any(shift != 0.0, axis=1)
    diag['changed_cells'] = float(changed.sum())
    if not changed.any():
        diag['mode'] = mode + '_zero_increment'
        out.uns['network_response'] = diag
        return out
    # Renormalise only the cells that actually received an increment; a true
    # zero increment therefore stays byte-identical to the parent.
    res = np.array(x, dtype=np.float32)
    res[changed] = normalize_log(np.ascontiguousarray(new[changed])).toarray()
    delta = res - x.astype(np.float32)
    diag['mean_abs_dX'] = float(np.abs(delta).mean())
    diag['bulk_change_norm'] = float(np.linalg.norm(delta.mean(axis=0)))
    out.X = sparse.csr_matrix(res)
    diag['mode'] = mode
    out.uns['network_response'] = diag
    return out
