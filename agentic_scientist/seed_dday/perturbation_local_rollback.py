"""Local lineage rollback: conserve knockout-exposed mass, roll its composition back.

Hypothesis (gene-blind, WT-only).  A developmental block can retain earlier states
inside the lineages that depend on a gene instead of deleting an expressing
population and pushing its relative mass onto unrelated tissue.  For every WT
annotation type t we compare its mass f_t at the latest WT stage with its mass e_t
at the preceding WT stage, and compare the knockout gene's detection in that type
q_t with its global detection q.  Only types with a genuine knockout *excess*
exposure a_t = max(0, q_t - q) are touched, and their affected mass is conserved:

    f'_t = f_t (1 - a_t) + A * f_t a_t r_t / B,      r_t = clip(e_t / f_t, 0.5, 2)
    A    = sum_t f_t a_t,                            B = sum_t f_t a_t r_t

The first term keeps every type's baseline mass, the second redistributes only the
exposed mass A towards the earlier-stage composition (r_t > 1 for a type that was
relatively more abundant earlier).  Unexposed types therefore keep their mass
exactly.  There is no fitted exponent, strength or clip: the amplitude is the
observed detection excess and the observed stage contrast.

This is a maturation-arrest prior applied in a gene-blind direction: every exposed
type is rolled toward its earlier abundance.  The gene-specificity comes only from
the exposure a_t measured in the passed WT input.  It is not a claim that the
knockout causes arrest.  Off-panel symbols, poorly detected symbols, missing
earlier input, A == 0, or a degenerate (constant) r among exposed types all abstain
to the uniform WT law: the parent's generic complexity tilt is dropped.
"""
import numpy as np
from scipy import sparse

MIN_CELLS = 30          # support at BOTH WT stages, pre-registered
CLIP_LO, CLIP_HI = 0.5, 2.0   # pre-registered prior, never swept


def resolve_symbol(var_names, symbol):
    """Exact-first, then case-insensitive resolution; first column on duplicates.

    Returns None when the symbol is absent.  ``var_names`` may contain duplicate
    entries; ``names.index`` keeps the first column consistently, matching the
    single-gene selection used by the diagnostics.
    """
    if symbol is None:
        return None
    names = [str(v) for v in var_names]
    sym = str(symbol)
    if sym in names:
        return names.index(sym)
    low = sym.lower()
    for j, n in enumerate(names):
        if n.lower() == low:
            return j
    return None


def _detection(wt, j):
    """Boolean detection (X > 0) on the same log1p matrix the sampler uses."""
    col = wt.X[:, j]
    if sparse.issparse(col):
        return np.asarray((col > 0).toarray()).ravel().astype(bool)
    return np.asarray(col).ravel() > 0


def _fallback(reason, n_types):
    """Exact uniform WT abstention, with the reason recorded."""
    return dict(abstain=True, reason=reason,
                ratio=np.ones(n_types), f_before=np.full(n_types, np.nan),
                f_after=np.full(n_types, np.nan), exposure=np.zeros(n_types),
                stage_ratio=np.ones(n_types), q=0.0, A=0.0, B=0.0,
                detected=0, min_r=1.0, max_r=1.0,
                max_unexposed_mass_error=0.0, types=np.array([], dtype=object))


def local_rollback(earlier, wt, knockout):
    """Compute the per-WT-type mass multipliers f'_t / f_t and their diagnostics.

    All inputs come from the passed WT AnnData objects: the annotation strata are
    the ORIGINAL ``obs['celltype']`` labels (the same strata that
    ComplexityPerturbation uses), the stage contrast is the observed WT composition
    change, and the exposure is the knockout symbol's own detection in the passed
    WT.  No gene name, stage value or dataset constant enters beyond the passed
    symbol.
    """
    wlab = np.asarray(wt.obs['celltype'].astype(str)).ravel()
    types = np.unique(wlab)
    n = wt.n_obs
    f = np.array([np.mean(wlab == t) for t in types], dtype=float)
    n_latest = np.array([(wlab == t).sum() for t in types], dtype=int)

    if earlier is None:
        return _fallback('no_earlier_input', len(types))
    alab = np.asarray(earlier.obs['celltype'].astype(str)).ravel()
    e = np.array([np.mean(alab == t) for t in types], dtype=float)
    n_earlier = np.array([(alab == t).sum() for t in types], dtype=int)

    j = resolve_symbol(wt.var_names, knockout)
    if j is None:
        return _fallback('uniform_offpanel', len(types))
    det = _detection(wt, j)
    k = int(det.sum())
    q = k / float(n)
    # A gene seen in fewer cells than the sqrt(N) sampling resolution is
    # indistinguishable from a null gene; abstain exactly (never a small tilt).
    if k < int(np.ceil(np.sqrt(n))):
        return _fallback('uniform_low_detection', len(types))

    shrink = np.sqrt(n)
    kt = np.array([det[wlab == t].sum() for t in types], dtype=float)
    q_t = (kt + shrink * q) / (n_latest + shrink)
    a = np.maximum(0.0, q_t - q)
    supported = (n_earlier >= MIN_CELLS) & (n_latest >= MIN_CELLS)
    a = np.where(supported, a, 0.0)

    r = np.clip(e / np.maximum(f, 1.0 / n), CLIP_LO, CLIP_HI)
    A = float(f @ a)
    B = float(f @ (a * r))
    exposed = a > 0
    if A <= 0.0 or B <= 0.0 or exposed.sum() == 0:
        return _fallback('no_exposed_mass', len(types))
    # Degenerate rollback: with a constant r among exposed types the second term
    # is exactly f_t a_t and f' == f, so the mechanism carries no information.
    if np.ptp(r[exposed]) <= 0.0:
        return _fallback('no_stage_contrast_variation', len(types))

    f_new = f * (1.0 - a) + A * f * a * r / B
    ratio = f_new / f
    unexposed = ~exposed
    err = float(np.max(np.abs(f_new[unexposed] - f[unexposed]))) if unexposed.any() else 0.0
    return dict(abstain=False, reason='ok', ratio=ratio, f_before=f, f_after=f_new,
                exposure=a, stage_ratio=r, q=float(q), A=A, B=B, detected=k,
                min_r=float(r[exposed].min()), max_r=float(r[exposed].max()),
                max_unexposed_mass_error=err, types=types)
