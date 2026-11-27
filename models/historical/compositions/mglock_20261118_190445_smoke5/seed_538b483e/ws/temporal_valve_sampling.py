"""Bounded valve/cushion donor-mass transfer for the temporal (T1) board.

Why
---
The w3_c04 temporal_val diagnosis shows the forecast composition error is
concentrated in two coupled cardiac compartments: LV-CM and RV-CM are over
represented (7.2% / 6.9% predicted versus 3.1% / 3.4% in the target) while the
endocardial/cushion states that valve formation produces -- Endocardium-1/2,
EndoMT Endocardium and Early VIC -- are strongly under represented (about 7.6%
predicted versus 22.9%).  The contractile genes follow the same error: Myl4
(+0.04 predicted versus -0.78 observed) and Myl7 (+0.05 versus -0.61), and
Actc1/Ttn/Slc8a1/Tnnc1 are all under-decreased.

Biology: during early valve elongation the endocardium at the atrioventricular
canal and outflow tract undergoes an endothelial-to-mesenchymal transition into
cushion mesenchyme (EndoMT / Early VIC) while other endocardial populations
keep proliferating, and the cushion/valve cells then expand as a share of the
heart.  So over the observed interval the endocardial family's *valve-state*
fraction rises at the expense of the working myocardium's relative share.  The
latest donor stage already contains scarce but credible cushion-associated
profiles (dual endothelial + cushion-marker cells); the parent's weak
classifier growth odds simply do not draw them at the observed rate.

Mechanism (input-derived, no target access, no stage/split branch)
-----------------------------------------------------------------
1.  On BOTH passed inputs, mark endocardial-family rows that co-detect at least
    two genes from a fixed endothelial module (Nfatc1, Cdh5, Pecam1, Kdr, Tek)
    and at least two from a fixed cushion/EMT module (Sox9, Twist1, Snai1,
    Snai2, Msx1, Msx2, Postn, Has2).  This is a state proxy computed from the
    inputs only; no gene is selected by score.
2.  Let ``f`` be the dual-positive endocardial-family fraction of all rows and
    ``r`` its fraction inside the endocardial + ventricular/outflow donor block.
    The mechanism only fires when both rise between the two inputs, i.e. the
    valve state is measurably expanding in the data we were given.
3.  Dose ``d = min(horizon/interval, 1) * min(0.04, f_latest - f_earlier,
    E, 0.5 * V)`` probability-mass points are moved from the
    ventricular/outflow donors to the endocardial/cushion donors, where ``E``
    and ``V`` are the *parent* donor masses of the two final masks.  The caps
    are structural: 4 percentage points of final donor mass per observed
    interval, no more than the measured input increase, never more than the
    recipient mass (multiplier ``1 + d/E`` stays finite), and never more than
    half the ventricular/outflow mass (so at least half of that compartment is
    retained).  The horizon factor saturates after one observed interval, so a
    2-day test horizon cannot compound the transfer.
4.  The transfer is realised purely as a donor-weight change: recipient odds
    are multiplied by ``1 + d/E`` and ventricular/outflow odds by ``1 - d/V``;
    every other donor keeps its weight and the mass of the pair is conserved.
    Because the parent draws donors with probabilities proportional to
    ``exp(DRAW_GROWTH * F * log_growth)``, adding
    ``log(multiplier) / (DRAW_GROWTH * F)`` to ``log_growth`` reproduces the
    desired probabilities at the unchanged draw (same decoder, same seeds, same
    output processing).  The caller restores ``log_growth`` in a ``finally``
    block so nothing leaks into other boards or later calls.

Guards (all must hold, otherwise the parent draw runs bit-for-bit unchanged):
at least three shared genes per module, at least 30 endocardial and 30
ventricular/outflow cells in both inputs, at least 30 dual-positive latest
rows, finite positive interval and horizon, and increases in both ``f`` and
``r``.  Rows that the erythroid prior owns are excluded from BOTH final masks,
so the erythroid donor budget already measured on the parent is untouched.
"""

import numpy as np

# Endocardial family, raw obs['celltype'] labels *before* the transport module's
# broad aliasing, plus the alias spellings that appear in the released stages.
ENDO_LABELS = frozenset({
    'Endothelium', 'Endocardium', 'Endocardium-1', 'Endocardium-2',
    'EndoMT Endocardium', 'Early VIC',
    'Endo', 'Chamber-Endo', 'Cush-EndoMT-Endo',
})
# Working myocardium + outflow tract, raw labels before broad aliasing.
VENT_LABELS = frozenset({'V-CM', 'vCM', 'LV-CM', 'RV-CM', 'OFT/RV-CM', 'OFT-CM'})
# The only label whose membership needs the cushion co-detection test: a broad
# endothelium annotation can be vascular endothelium (great vessels, yolk sac)
# that is not cardiac valve endocardium, so require the cushion module there.
BROAD_ENDO = 'Endothelium'

# Fixed marker modules (shared measured genes are used per input).
ENDO_MODULE = ('Nfatc1', 'Cdh5', 'Pecam1', 'Kdr', 'Tek')
CUSHION_MODULE = ('Sox9', 'Twist1', 'Snai1', 'Snai2', 'Msx1', 'Msx2',
                  'Postn', 'Has2')
DETECTED_IN_MODULE = 2     # >= 2 genes of each module must be nonzero
MIN_SHARED_GENES = 3       # per module, otherwise the state proxy is undefined
MIN_CELLS = 30             # per donor family in BOTH inputs
MIN_DUAL = 30              # dual-positive latest rows needed to plan a transfer
MAX_DOSE = 0.04            # cap on transferred probability mass per interval
DRAW_GROWTH = 0.25         # parent donor growth coefficient (unchanged)


def _module_detection(a, genes):
    """Per-row count of detected (>0 log1p) genes of a fixed module."""
    pos = a.var_names.get_indexer(list(genes))
    ok = pos >= 0
    if int(ok.sum()) < MIN_SHARED_GENES:
        return None, []
    x = a.X[:, pos[ok]]
    x = x.toarray() if hasattr(x, 'toarray') else np.asarray(x)
    used = [g for g, keep in zip(genes, ok) if keep]
    return (np.asarray(x) > 0.0).sum(axis=1), used


def _family_masks(a):
    """Raw-label endocardial and ventricular/outflow masks (no aliasing)."""
    labels = np.asarray(a.obs['celltype']).astype(str)
    return (labels, np.isin(labels, list(ENDO_LABELS)),
            np.isin(labels, list(VENT_LABELS)))


def plan_valve_transfer(flow, horizon, interval, excluded=None):
    """Plan the bounded endocardial/cushion <- ventricular/outflow transfer.

    ``flow`` is the fitted LatentFlow (``AnchorFlow.flow`` when external data is
    used) evaluated *after* the erythroid, metabolic and chamber multipliers
    have been composed into ``log_growth``; the recovered parent probabilities
    therefore already include them.  ``excluded`` marks latest rows owned by
    the erythroid prior (their probabilities and masks must not move).

    Returns ``None`` when any guard fails, which lets the caller reproduce the
    unmodified parent draw exactly.
    """
    if not (np.isfinite(interval) and np.isfinite(horizon)):
        return None
    if interval <= 0 or horizon <= 0:
        return None
    F = float(min(horizon / interval, 2.0))
    s = float(min(horizon / interval, 1.0))
    if F <= 0 or s <= 0:
        return None

    latest, earlier = flow.latest, flow.earlier
    lab_l, endo_l, vent_l = _family_masks(latest)
    _, endo_e, vent_e = _family_masks(earlier)
    if endo_l.sum() < MIN_CELLS or vent_l.sum() < MIN_CELLS:
        return None
    if endo_e.sum() < MIN_CELLS or vent_e.sum() < MIN_CELLS:
        return None

    det_e_l, genes_e = _module_detection(latest, ENDO_MODULE)
    det_c_l, genes_c = _module_detection(latest, CUSHION_MODULE)
    det_e_e, _ = _module_detection(earlier, ENDO_MODULE)
    det_c_e, _ = _module_detection(earlier, CUSHION_MODULE)
    if det_e_l is None or det_c_l is None or det_e_e is None or det_c_e is None:
        return None

    dual_l = (det_e_l >= DETECTED_IN_MODULE) & (det_c_l >= DETECTED_IN_MODULE)
    dual_e = (det_e_e >= DETECTED_IN_MODULE) & (det_c_e >= DETECTED_IN_MODULE)
    n_dual_l = int((dual_l & endo_l).sum())
    n_dual_e = int((dual_e & endo_e).sum())
    if n_dual_l < MIN_DUAL:
        return None

    f_l = float(n_dual_l / max(int(latest.n_obs), 1))
    f_e = float(n_dual_e / max(int(earlier.n_obs), 1))
    block_l = int((endo_l | vent_l).sum())
    block_e = int((endo_e | vent_e).sum())
    r_l = float(n_dual_l / max(block_l, 1))
    r_e = float(n_dual_e / max(block_e, 1))
    # The state must be measurably expanding in the passed inputs: both the
    # whole-input fraction and the within-cardiac-block fraction must rise.
    if not (f_l > f_e and r_l > r_e):
        return None

    # Final masks: every explicit endocardial/cushion donor is a recipient, but
    # a row carrying only the broad Endothelium annotation must also pass the
    # cushion co-detection test.  Erythroid-eligible rows are owned by the
    # erythroid prior and are removed from both sides.
    if excluded is None:
        excl = np.zeros(int(latest.n_obs), dtype=bool)
    else:
        excl = np.asarray(excluded, dtype=bool).ravel()
        if excl.shape[0] != int(latest.n_obs):
            return None
    broad = lab_l == BROAD_ENDO
    recipient = endo_l & (~broad | dual_l) & (~excl)
    source = vent_l & (~excl)
    n_recip, n_src = int(recipient.sum()), int(source.sum())
    if n_recip < MIN_CELLS or n_src < MIN_CELLS:
        return None

    # Parent donor probabilities p under the composed log weights.
    log_growth = np.asarray(flow.log_growth, dtype=float).ravel()
    w = np.exp(DRAW_GROWTH * F * log_growth)
    total = float(w.sum())
    if not np.isfinite(total) or total <= 0.0:
        return None
    p = w / total
    E = float(p[recipient].sum())
    V = float(p[source].sum())
    if not (E > 0.0 and V > 0.0):
        return None

    # Structural caps: 4 pp per observed interval, no more than the measured
    # input increase, no more than the recipient mass, and keep >= 50% of the
    # ventricular/outflow mass.
    d = s * float(min(MAX_DOSE, f_l - f_e, E, 0.5 * V))
    if not (d > 0.0):
        return None

    mult = np.ones_like(p)
    mult[recipient] *= 1.0 + d / E
    mult[source] *= 1.0 - d / V
    # Algebraic donor-weight increment for exp(DRAW_GROWTH * F * log_growth).
    log_increment = np.log(mult) / (DRAW_GROWTH * F)
    log_increment = np.nan_to_num(log_increment, nan=0.0, posinf=0.0,
                                  neginf=0.0)

    p_new = p * mult
    p_new = p_new / p_new.sum()
    return {
        'log_increment': log_increment,
        'recipient': recipient,
        'source': source,
        'F': F,
        's': s,
        'f_earlier': f_e,
        'f_latest': f_l,
        'r_earlier': r_e,
        'r_latest': r_l,
        'dose': d,
        'E_before': E,
        'V_before': V,
        'E_after': float(p_new[recipient].sum()),
        'V_after': float(p_new[source].sum()),
        'n_recipients': float(n_recip),
        'n_sources': float(n_src),
        'n_dual_latest': float(n_dual_l),
        'endo_genes': genes_e,
        'cushion_genes': genes_c,
        'recipient_odds': float(1.0 + d / E),
        'source_odds': float(1.0 - d / V),
        'mass_retained_pair': float((p_new[recipient].sum()
                                     + p_new[source].sum())
                                    / max(E + V, 1e-12)),
        'ess_before': float(1.0 / max(float(p @ p), 1e-300)),
        'ess_after': float(1.0 / max(float(p_new @ p_new), 1e-300)),
    }


def attach_diagnostics(out, plan, applied=True):
    """Store the transfer as flat scalars/arrays (h5ad cannot nest dicts)."""
    if plan is None:
        out.uns['valve_transfer'] = dict(
            applied=False, dose=0.0, f_earlier=0.0, f_latest=0.0,
            r_earlier=0.0, r_latest=0.0, E_before=0.0, V_before=0.0,
            E_after=0.0, V_after=0.0, recipient_odds=1.0, source_odds=1.0,
            realized_recipient_share=0.0, realized_source_share=0.0,
            mass_retained_pair=1.0, n_recipients=0.0, n_sources=0.0,
            n_dual_latest=0.0, ess_before=0.0, ess_after=0.0,
            endo_genes=np.array([], dtype=str),
            cushion_genes=np.array([], dtype=str))
        return out
    out.uns['valve_transfer'] = dict(
        applied=bool(applied),
        dose=float(plan['dose']),
        f_earlier=float(plan['f_earlier']),
        f_latest=float(plan['f_latest']),
        r_earlier=float(plan['r_earlier']),
        r_latest=float(plan['r_latest']),
        E_before=float(plan['E_before']),
        V_before=float(plan['V_before']),
        E_after=float(plan['E_after']),
        V_after=float(plan['V_after']),
        recipient_odds=float(plan['recipient_odds']),
        source_odds=float(plan['source_odds']),
        realized_recipient_share=float(plan.get('realized_recipient_share', 0.0)),
        realized_source_share=float(plan.get('realized_source_share', 0.0)),
        mass_retained_pair=float(plan['mass_retained_pair']),
        n_recipients=float(plan['n_recipients']),
        n_sources=float(plan['n_sources']),
        n_dual_latest=float(plan['n_dual_latest']),
        ess_before=float(plan['ess_before']),
        ess_after=float(plan['ess_after']),
        endo_genes=np.array(plan['endo_genes'], dtype=str),
        cushion_genes=np.array(plan['cushion_genes'], dtype=str),
    )
    return out
