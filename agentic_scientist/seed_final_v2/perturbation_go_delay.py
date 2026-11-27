"""GO-breadth-gated developmental delay for the T3 knockout forecast (clean-room d230).

Biology
-------
1. A knockout embryo is first an embryo at its OWN stage.  When the requested
   target time lies at or before the latest supplied WT stage, the matched WT is
   a real-cell mixture of the two WT brackets weighted by elapsed time
   (w_stage = (t_last - t_target) / interval).  This part is gene-blind and is
   the exact meaning of "the WT at the target stage".
2. Loss of a BROADLY acting signalling / cell-adhesion regulator (the public
   test gene is beta-catenin, Ctnnb1) slows progenitor expansion and axis
   growth systemically, so the mutant looks like a developmentally DELAYED
   wild type: the WT at t_target - D.  The public P3 leaders encode this as
   real earlier-stage WT cells mixed into the latest WT ("d230" = 0.23 day;
   d150 -> d230 rises monotonically in severity, mmd_u and variogram).
3. Loss of a lineage-restricted DNA-BINDING TRANSCRIPTION FACTOR instead
   re-allocates cells inside its own lineage; that is what the parent's
   exposure-gated composition rollback, flat component and maturation tilt
   already model.  For those genes this module must do nothing.
4. A non-TF knockout outside the active systemic gate may affect a narrow
   developmental program. Shared GO terms identify the program and detection
   in WT localizes it. Preferentially replace later cells from high-detection
   lineages, using the same earlier-stage donor pool as the systemic delay.

The gate therefore uses ONLY the supplied GO prior and the supplied WT inputs:
  * the knocked-out gene's kept GO terms (annotated to 5-500 prior genes);
  * DNA-binding TF activity GO:0003700 in the term's ancestor closure -> the
    parent lineage-reallocation model owns it, delay gate = 0;
  * signal transduction GO:0007165 or cell communication GO:0007154 in the
    closure -> a systemic regulator (eligible);
  * at least MIN_GO_SUPPORT co-annotated panel genes for the systemic arm;
  * cell-weighted co-expression breadth of the pathway in the latest WT
    (fraction of cells whose cell type expresses at least half the best cell
    type's level) -> the systemic delay ramps from 0.50 to 0.85 breadth;
  * the narrow arm needs at least three co-annotated panel genes, three
    supported labels and at most 0.75 half-peak breadth.

Realisation: the parent forecast is kept except for a seeded fraction of rows
that are replaced by REAL earlier-input cells drawn at the earlier stage's
native composition. The replacement probability depends on the parent row's
lineage. Its mean detection is divided once by the peak lineage mean to
obtain rank_l, then w_l = clip(w_stage + DELAY_DAYS * gate * rank_l / interval,
0, W_MAX).

On any positive mixture the amplitude of the forecast is the real-cell stage
displacement itself. The inherited response calibration runs when the mix
returns the original forecast, which happens whenever no row is replaced.
"""
import numpy as np
import anndata as ad
from scipy import sparse

# ---- pre-registered constants (a priori; only DELAY_DAYS comes from the
#      public "d230" recipe, the others are structural guards) ---------------
DELAY_DAYS = 0.23        # public d230 developmental delay (days)
W_MAX = 0.92             # keep >= 8% of the parent forecast rows
INTERVAL_W_MAX = 0.92    # same cap for the gene-blind stage match
GO_TERM_MIN, GO_TERM_MAX = 5, 500   # vetted term size range (prior genes)
MIN_GO_SUPPORT = 20      # co-annotated panel genes needed to define a pathway
MIN_LABEL_CELLS = 20     # cells needed for a lineage-level pathway score
MODULE_MIN_GENES = 3
MODULE_MIN_LINEAGES = 3
MODULE_MAX_BREADTH = 0.75
BREADTH_LO, BREADTH_SPAN = 0.50, 0.35   # 0 at <=0.50, full at >=0.85 breadth
GO_SIGNAL = ('GO:0007165', 'GO:0007154')   # signal transduction / cell communication
GO_DNA_TF = 'GO:0003700'                   # DNA-binding transcription factor activity
MIX_SEED_OFFSET = 7919

_CACHE = {}


def _term_tables(go_prior):
    """Casefolded gene->terms map and term frequencies (cached per prior object)."""
    key = id(go_prior)
    hit = _CACHE.get(key)
    if hit is not None:
        return hit
    gt = go_prior.get('gene_terms') or {}
    cf = {str(g).casefold(): set(str(t) for t in terms) for g, terms in gt.items()}
    freq = {}
    for terms in cf.values():
        for t in terms:
            freq[t] = freq.get(t, 0) + 1
    _CACHE.clear()          # keep one prior object's tables at a time
    _CACHE[key] = (cf, freq)
    return cf, freq


def _ancestors(terms, term_parents):
    """Ancestor closure of a term set through the GO prior's parent links."""
    seen = set(terms)
    stack = list(terms)
    while stack:
        t = stack.pop()
        for p in term_parents.get(t, ()) or ():
            p = str(p)
            if p not in seen:
                seen.add(p)
                stack.append(p)
    return seen


def _diag(**kw):
    d = dict(applied=0.0, reason='', gate=0.0, breadth=0.0, n_support=0.0,
             n_terms=0.0, is_dna_tf=0.0, is_signalling=0.0, w_stage=0.0,
             w_mean=0.0, delay_days=0.0, n_replaced=0.0, n_earlier_unique=0.0)
    d.update(kw)
    return d


def gate_info(go_prior, knockout, wt):
    """GO-topology + WT co-expression breadth gate for a developmental delay.

    Returns (gate in [0,1], diagnostics dict, peak detection, raw mean
    detection by lineage). The gate uses the supplied GO prior and WT stage.
    """
    if not isinstance(go_prior, dict) or not go_prior.get('gene_terms'):
        return (0.0, _diag(reason='no_go_prior'), 1.0, {})
    if knockout is None:
        return (0.0, _diag(reason='no_knockout'), 1.0, {})
    cf, freq = _term_tables(go_prior)
    ko_terms = {t for t in cf.get(str(knockout).casefold(), ())
                if GO_TERM_MIN <= freq.get(t, 0) <= GO_TERM_MAX}
    if not ko_terms:
        return (0.0, _diag(reason='no_vetted_terms'), 1.0, {})
    closure = _ancestors(ko_terms, go_prior.get('term_parents') or {})
    is_tf = float(GO_DNA_TF in closure)
    is_sig = float(any(t in closure for t in GO_SIGNAL))
    base = dict(n_terms=float(len(ko_terms)), is_dna_tf=is_tf, is_signalling=is_sig)
    if is_tf > 0:
        return (0.0, _diag(reason='dna_binding_tf_parent_model', **base), 1.0, {})
    # Panel genes co-annotated to a kept term of the knockout gene.
    genes = [str(g) for g in wt.var_names]
    rel = np.array([bool(ko_terms & cf.get(g.casefold(), set())) for g in genes], dtype=bool)
    n_support = int(rel.sum())
    base['n_support'] = float(n_support)
    if n_support < MODULE_MIN_GENES:
        return (0.0, _diag(reason='thin_go_support', **base), 1.0, {})
    X = wt.X[:, np.flatnonzero(rel)]
    if sparse.issparse(X):
        det = np.asarray(X.getnnz(axis=1)).ravel() / float(n_support)
    else:
        det = np.asarray((np.asarray(X) > 0).sum(axis=1)).ravel() / float(n_support)
    labels = np.asarray(wt.obs['celltype']).astype(str) if 'celltype' in wt.obs else None
    lineage_detection = {}
    if labels is None or labels.size != wt.n_obs:
        breadth = 1.0 if float(det.mean()) > 0 else 0.0
        peak_detection = 1.0
    else:
        counts = {}
        for c in np.unique(labels):
            m = labels == c
            if int(m.sum()) < MIN_LABEL_CELLS:
                continue
            lineage_detection[c] = float(det[m].mean())
            counts[c] = float(m.sum())
        if not lineage_detection:
            return (0.0, _diag(reason='no_supported_lineages', **base), 1.0, {})
        peak_detection = max(lineage_detection.values())
        if not np.isfinite(peak_detection) or peak_detection <= 0:
            return (0.0, _diag(reason='pathway_not_detected', **base), 1.0, {})
        breadth = float(sum(n for c, n in counts.items()
                            if lineage_detection[c] >= 0.5 * peak_detection) / sum(counts.values()))
    bramp = 0.0
    if is_sig > 0 and n_support >= MIN_GO_SUPPORT:
        bramp = float(np.clip((breadth - BREADTH_LO) / BREADTH_SPAN, 0.0, 1.0))
    if (bramp == 0.0 and len(lineage_detection) >= MODULE_MIN_LINEAGES
            and breadth <= MODULE_MAX_BREADTH):
        # The module localizes susceptibility. WT stage differences supply
        # the direction, including changes in the abundance of lineages.
        return (1.0, _diag(reason='narrow_go_module', gate=1.0, breadth=breadth,
                           narrow_module=True, **base), peak_detection, lineage_detection)
    return (bramp, _diag(reason='ok', gate=bramp, breadth=breadth, **base),
            peak_detection, lineage_detection)


def mix(out, wt, earlier, times, target_time, context):
    """Total wrapper around the delay realisation.

    The contract of this experiment is that the delay path can only ever ADD a
    real-cell stage correction: on ANY branch that cannot produce a valid
    positive mixture (zero weights, zero draw, missing genes, or a numerical
    or concatenation failure) the parent forecast is returned unchanged.
    The previous race of this design was rejected because one fallback branch
    raised instead of returning the parent; this wrapper makes that promise
    total, and the failure is recorded in the diagnostics for the audit.
    """
    try:
        return _mix_impl(out, wt, earlier, times, target_time, context)
    except Exception as exc:      # defensive: never break a prediction
        return out, _diag(reason='fallback_exception:' + type(exc).__name__)


def _mix_impl(out, wt, earlier, times, target_time, context):
    """Replace a seeded, lineage-scaled fraction of ``out`` rows by real earlier WT cells.

    Returns (possibly new AnnData, diagnostics).  The parent path is returned
    untouched when no row is replaced.
    """
    if earlier is None or times is None or len(times) < 2:
        return out, _diag(reason='no_earlier_input')
    t_prev, t_last = float(times[-2]), float(times[-1])
    interval = t_last - t_prev
    if not (np.isfinite(interval) and interval > 0 and np.isfinite(float(target_time))):
        return out, _diag(reason='invalid_times')
    # Elapsed-time weight of the WT stage that the knockout resembles.  It is
    # kept UNCLIPPED before the delay is added: a target later than the latest
    # input must not gain earlier-stage rows just because a delay exists (the
    # delayed stage would still lie beyond the observed window).  Only the
    # final per-row weight is clipped to [0, W_MAX].
    base_w = float((t_last - float(target_time)) / interval)
    w_stage = float(np.clip(base_w, 0.0, INTERVAL_W_MAX))
    gate, ginfo, peak_detection, lineage_detection = gate_info(
        context.get('external'), context.get('knockout'), wt
    )
    delay_days = DELAY_DAYS * gate
    # --- per-row replacement weight: stage match (gene-blind) + lineage delay --
    n = int(out.n_obs)
    if n < 2:
        return out, _diag(reason='too_few_rows', w_stage=w_stage, gate=gate,
                          delay_days=delay_days)
    if lineage_detection and gate > 0:
        labels = (np.asarray(out.obs['celltype']).astype(str)
                  if 'celltype' in out.obs else None)
        if labels is None or labels.size != n:
            # With no label mapping the narrow arm cannot localize its delay.
            if ginfo.get('narrow_module'):
                w_row = np.full(n, w_stage)
                gate = delay_days = 0.0
            else:
                w_row = np.full(n, float(np.clip(base_w + delay_days / interval, 0.0, W_MAX)))
        else:
            w_row = np.full(n, base_w, dtype=float)
            for c, mean_detection in lineage_detection.items():
                m = labels == c
                if m.any():
                    w_row[m] += delay_days * (mean_detection / peak_detection) / interval
            w_row = np.clip(w_row, 0.0, W_MAX)
    else:
        w_row = np.full(n, w_stage, dtype=float)
    base = {k: ginfo.get(k) for k in ('gate', 'breadth', 'n_support', 'n_terms',
                                      'is_dna_tf', 'is_signalling', 'narrow_module') if k in ginfo}
    base.update(w_stage=w_stage, gate=gate, delay_days=delay_days,
                w_mean=float(w_row.mean()) if n else 0.0)
    if float(w_row.max()) <= 0:
        return out, _diag(reason='zero_weight', **base)
    rng = np.random.default_rng(int(context.get('seed', 0)) + MIX_SEED_OFFSET)
    replace = rng.random(n) < w_row
    k = int(replace.sum())
    if k <= 0:
        # ``base`` already carries w_mean; the earlier duplicate kwarg raised
        # TypeError here instead of returning the parent forecast (w3_c06 veto).
        return out, _diag(reason='zero_draw', **base)
    k = min(k, n - 1)
    genes = [str(g) for g in out.var_names]
    epos = {str(g): j for j, g in enumerate(earlier.var_names)}
    if any(g not in epos for g in genes) or earlier.n_obs < 1:
        return out, _diag(reason='earlier_missing_genes', **base)
    keep = np.flatnonzero(~replace)
    if keep.size == 0:                     # keep at least one parent row
        keep = np.arange(1, dtype=int)
    k = int(n - keep.size)
    # Earlier-stage donors at native composition: full permutation cycles + prefix.
    perm = rng.permutation(int(earlier.n_obs))
    reps = int(np.ceil(k / float(earlier.n_obs)))
    erows = np.tile(perm, reps)[:k]
    e = earlier[erows][:, genes].copy()
    a = out[keep].copy()
    # Harmonise obs / obsm so the two real-cell blocks concatenate cleanly.
    cols = [c for c in a.obs.columns if c in e.obs.columns]
    a.obs = a.obs[cols].copy()
    e.obs = e.obs[cols].copy()
    for c in cols:
        if (str(a.obs[c].dtype) == 'category' or str(e.obs[c].dtype) == 'category'
                or a.obs[c].dtype == object or e.obs[c].dtype == object):
            a.obs[c] = a.obs[c].astype(str)
            e.obs[c] = e.obs[c].astype(str)
    a.obs['source_stage'] = 'latest_or_response'
    e.obs['source_stage'] = 'delayed'
    for blk in (a, e):
        blk.var = blk.var.iloc[:, :0].copy()
        blk.uns = {}
        for _k in [k for k in blk.layers if k is not None]: del blk.layers[_k]
        blk.obsp = {}
    okeys = [kk for kk in a.obsm.keys()
             if kk in e.obsm.keys()
             and np.asarray(a.obsm[kk]).ndim == 2 and np.asarray(e.obsm[kk]).ndim == 2
             and np.asarray(a.obsm[kk]).shape[1] == np.asarray(e.obsm[kk]).shape[1]]
    a.obsm = {kk: np.asarray(a.obsm[kk], dtype=np.float64) for kk in okeys}
    e.obsm = {kk: np.asarray(e.obsm[kk], dtype=np.float64) for kk in okeys}
    if sparse.issparse(a.X) != sparse.issparse(e.X):
        a.X = sparse.csr_matrix(a.X)
        e.X = sparse.csr_matrix(e.X)
    res = ad.concat([a, e], join='inner')
    res.var = out.var.copy()
    res.obs_names = [f'pred_{i}' for i in range(res.n_obs)]
    res.uns = dict(out.uns)
    res.uns['go_delay'] = _diag(applied=1.0, reason='ok', n_replaced=float(k),
                                n_earlier_unique=float(len(np.unique(erows))), **base)
    return res, res.uns['go_delay']
