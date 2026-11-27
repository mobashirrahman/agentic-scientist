"""historical-entry research-agent program (free-form). Seed = v2 second candidate (Qiu 2024 AnchorFlow).

Contract: predict(board, inputs, times, target_time, context) -> AnnData (see agentic_scientist/prompts/brief.md).
You may rewrite everything here and add helper modules in this workspace.
"""
import numpy as np
import anndata as ad
from scipy import sparse

from temporal_transport import LatentFlow, SpatialInterpolant, lineages, as_dense, normalize_log
from temporal_complexity import ComplexityPerturbation
from temporal_anchor import AnchorFlow
from temporal_sparse_anchor import realise_sparse_anchor
from temporal_temporal_sampling import (ERY_MARKERS, MIN_ELIGIBLE, erythroid_eligibility,
                             plan_enrichment)
import temporal_metabolic_sampling as mets


# Observation multiplier used for clearly non-cardiac *donors* when the target
# dissection is the heart chambers only.  Fixed a priori from the organiser
# protocol (a few oesophagus-junction cells may remain), NOT fitted/swept.
CHAMBER_MULTIPLIER = 0.05
# Density-growth strength the parent passes to the decoder; the donor law is
# weights ~ exp(DRAW_GROWTH * F * log_growth), so a log multiplier is divided
# by DRAW_GROWTH * F to be reproduced exactly at the unchanged draw.
DRAW_GROWTH = 0.25
MIN_CHAMBER_FACTOR = 1e-6

# Clear non-cardiac annotations in the released heart-region stages (curated
# list in agentic_scientist/data/t1_celltype_map.json, from the organiser protocol).
# These tissues are the ones the precise chamber dissection removes: foregut,
# surface ectoderm, paraxial/extraembryonic/pharyngeal mesoderm, neural tube,
# hepatocytes, septum transversum, gut endoderm and generic epithelium.
# Deliberately NOT included: Blood (the chamber ontology retains it), the
# uncertain cardiac sources Proepicardium, pSHF/aSHF, JCF, NCC, BEC and
# Pericardium (progenitors and epicardial precursors can contribute genuine
# later cardiac tissue), and every cardiac/endothelial/mural class.  Unknown
# names abstain (keep full weight): annotation vocabularies differ by stage.
NONCARDIAC_CLEAR = frozenset({
    'Foregut', 'Surface Ectoderm', 'Paraxial Mesoderm', 'EXEM', 'Neural Tube',
    'pPHM', 'aPHM', 'Hepatocyte', 'ST', 'Gut Endoderm', 'Epithelium',
})


def _donor_mass(flow, mask, factor):
    """Probability mass of ``mask`` under the parent's current donor law."""
    logw = DRAW_GROWTH * factor * np.asarray(flow.log_growth, dtype=np.float64)
    logw = logw - logw.max()
    p = np.exp(logw)
    p /= p.sum()
    return float(p[mask].sum())


def _chamber_correction(latest, sampling, horizon, interval):
    """Fixed donor-weight multiplier for a heart-chamber dissection target.

    Anatomy, not lineage fate: the E12.5 target is a chamber dissection that
    removes surrounding tissue still present in the earlier heart-region
    samples, while earlier cells of a cardiac lineage remain valid donors.  So
    only the *observation probability* of clearly non-cardiac donors is reduced
    (p_chamber ~ p_parent * s(label), s = CHAMBER_MULTIPLIER for that list and
    1 otherwise), at the final donor draw and once, independent of the horizon.
    All donor profiles stay empirical; anchor drift, latent velocity, sparse
    realisation and seeds are untouched.
    """
    info = dict(applied=0.0, multiplier=CHAMBER_MULTIPLIER, factor=0.0,
                n_donors=float(latest.n_obs), n_masked=0.0,
                frac_masked_donors=0.0, retained_support=float(latest.n_obs),
                mass_before=0.0, mass_after=0.0, log_multiplier=None)
    if str(sampling) != 'heart_chambers':
        return info
    if not (np.isfinite(interval) and np.isfinite(horizon)):
        return info
    if interval <= 0 or horizon <= 0:
        return info
    factor = min(horizon / interval, 2.0)   # identical clip to LatentFlow.predict
    if factor <= MIN_CHAMBER_FACTOR:
        return info
    labels = lineages(latest)               # documented alias map, no fitting
    mask = np.isin(labels, list(NONCARDIAC_CLEAR))
    info['factor'] = float(factor)
    info['n_masked'] = float(mask.sum())
    info['frac_masked_donors'] = float(mask.mean())
    info['retained_support'] = float((~mask).sum())
    if not mask.any() or mask.all():
        # No documented non-cardiac annotation, or nothing left to draw from:
        # fall back to the exact parent law.
        return info
    info['log_multiplier'] = mask.astype(np.float64) * np.log(CHAMBER_MULTIPLIER)
    return info


def predict_temporal(inputs, times, target_time, context):
    """T1: extrapolate with external anchor drift from Qiu 2024 atlas.

    The anchor drift is realised sparsely (see sparse_anchor.py): a lineage's
    weak added mean is carried by a subset of nuclei at a one-molecule log
    scale instead of being smeared over every donor-zero entry.  This keeps the
    empirical donor profiles and the calibrated mean signal, and conserves the
    per-lineage/gene log-expression budget before CP10k renormalisation.

    The external transfer model is a zero-intercept per-gene diagonal gain
    (temporal_anchor.py): the Qiu anchor centroid is calibrated by a
    nonnegative through-origin slope fitted on matched calibration-type
    centroids, instead of the parent's pooled additive offset.  Additive
    calibration learned from expressing populations can invent an apparent
    future program in lineages where the atlas is nearly silent (the diagnosed
    Myl7 drift in blood/endocardium); a gain maps an atlas-zero centroid to
    zero, so lineage specificity survives platform transfer while supported
    signals can still be scaled up or down.  Gains are bounded to [0.25, 4.0] a
    priori and the anchor shift keeps its existing +/-0.5 clip.

    One bounded source-sampling prior is added *before* the flow's sampling
    (temporal_sampling.py): marker-corroborated primitive erythroblasts are
    drawn at up to twofold odds, capped by an absolute 0.01 probability-mass
    budget that saturates after one observed interval.  The diagnosis showed a
    coherent erythroid/globin under-representation (Blood ~1.4% vs ~14.7% in
    the target, three globins predicted with the wrong sign).  Because the
    intervention only changes donor weights, every sampled profile remains a
    real latest-stage nucleus; the parent's decoding, anchor drift and sparse
    realisation are untouched.  When the guards fail the parent path runs
    unmodified, so unrelated boards and knockouts remain byte-identical.

    A second, additive-only prior composes with it (metabolic_sampling.py): the
    latest-stage donors of each supported, non-erythroid lineage are reweighted
    toward the lower canonical-glycolysis score states that the passed WT
    inputs themselves exhibit.  It runs after the erythroid increment, restores
    each lineage's enriched mass exactly, excludes every erythroid-containing
    lineage, and is injected through the same ``log_growth`` identity, so
    composition, anchor calibration, sparse realisation and seeds are unchanged.

    Finally, a context-conditioned *observation* prior (this module only):
    when the requested dissection is ``context['sampling']=='heart_chambers'``
    the clearly non-cardiac donors of the latest stage (foregut, surface
    ectoderm, pharyngeal/paraxial/extraembryonic mesoderm, neural tube,
    hepatocytes, septum transversum, gut endoderm, epithelium) are drawn at a
    fixed 5% relative probability.  The E12.5 target is a precise heart-chamber
    dissection, so this describes the collection anatomy rather than a loss of
    those lineages; uncertain cardiac sources (proepicardium, SHF, JCF, NCC,
    BEC, pericardium) and Blood keep full weight.  It is a single fixed
    multiplier, applied once at the donor draw, so it cannot grow with the
    horizon, and it is inert for every other sampling flag (temporal_val).
    """
    earlier, latest = inputs[-2], inputs[-1]
    interval = times[-1] - times[-2]
    horizon = target_time - times[-1]
    ext = context.get('external')
    if ext is not None:
        # The external platform (Qiu TS12-13) is calibrated nearest its own
        # stage: the earliest supplied released stage.  With two inputs this is
        # exactly ``earlier``; with the full three-stage test input it is E8.5
        # rather than E9.5.  LatentFlow itself still fits the latest observed
        # pair, so composition/state extrapolation is unchanged.
        model = AnchorFlow(earlier, latest, ext, times[-2], times[-1], 15.0,
                           seed=context['fit_seed'],
                           calibration_reference=inputs[0])
        flow = model.flow           # the LatentFlow that owns the source weights
    else:
        model = LatentFlow(earlier, latest, interval, seed=context['fit_seed'])
        flow = model

    # Source-sampling prior: donor-identity guards must hold in both inputs, at
    # least two shared markers must exist, and the horizon must be positive.
    shared = [g for g in ERY_MARKERS if g in latest.var_names and g in earlier.var_names]
    elig_latest = erythroid_eligibility(latest, shared)
    elig_earlier = erythroid_eligibility(earlier, shared)
    plan = None
    if len(shared) >= 2 and elig_earlier.sum() >= MIN_ELIGIBLE:
        plan = plan_enrichment(flow, elig_latest, horizon, interval)
    if plan is not None:
        # Apply the desired multiplier exactly through the existing sampler:
        # exp(0.25*F*(log_growth + log(m)*1_elig)) / Z gives eligible mass q.
        flow.log_growth = flow.log_growth + elig_latest.astype(np.float64) * (
            np.log(plan['m']) / (0.25 * plan['F']))
        prior = dict(enabled=1.0, n_eligible=float(elig_latest.sum()),
                     frac_annotated=float(np.mean(np.array(
                         [('blood' in s.lower()) or ('erythro' in s.lower())
                          for s in np.asarray(latest.obs['celltype']).astype(str)]))),
                     f=plan['f'], q=plan['q'], m=plan['m'], q0=plan['q0'],
                     mass_binding=float(plan['mass_binding']),
                     tv_change=plan['q'] - plan['f'],
                     tv_budget_ok=float((plan['q'] - plan['f']) <= 0.01 * plan['s'] + 1e-12),
                     ess_before=plan['ess_before'], ess_after=plan['ess_after'])
    else:
        prior = dict(enabled=0.0, n_eligible=float(elig_latest.sum()),
                     f=0.0, q=0.0, m=1.0, q0=0.0, mass_binding=0.0,
                     tv_change=0.0, tv_budget_ok=1.0,
                     ess_before=0.0, ess_after=0.0)

    # --- Composition with the input-calibrated glycolysis state prior ---
    # metabolic_sampling.py reweights latest-stage donors *within* each supported
    # cell type toward the lower-glycolysis states that the passed WT inputs
    # themselves show (the early heart-region inputs decline inside most types).
    # It is applied now, i.e. after the erythroid enrichment above, so its p0 is
    # this instance's already-enriched donor law and the two interventions
    # compose multiplicatively rather than one replacing the other's weights.
    # Every lineage that holds a marker-corroborated erythroid donor is excluded:
    # the erythroid prior owns that lineage's probability budget, so leaving it
    # untouched keeps the erythroid effect measured on the parent intact even if
    # another input annotates erythroid cells under a non-Blood label.
    excluded_labels = (np.unique(np.asarray(flow.labels_b).astype(str)[elig_latest])
                       if elig_latest.any() else np.array([], dtype=str))
    met = None
    if np.isfinite(interval) and np.isfinite(horizon) and interval > 0 and horizon > 0:
        factor = min(max(horizon / interval, 0.0), mets.MAX_FACTOR)
        if factor > 0:
            met = mets.plan_tilt(flow, factor, excluded_labels)

    # --- Chamber-dissection donor law (context['sampling']) -----------------
    # The parent never reads the sampling flag.  For the chamber-restricted
    # target the surrounding tissue of the earlier dissections is removed, so
    # clearly non-cardiac donors get a fixed 5% relative observation
    # probability (see _chamber_correction).  Every other flag, absent flag,
    # invalid horizon or empty mask leaves the parent call exactly as it was.
    chamber = _chamber_correction(latest, context.get('sampling'), horizon, interval)
    if chamber['log_multiplier'] is not None:
        mask = chamber['log_multiplier'] < 0   # nonzero entries = non-cardiac donors
        chamber['mass_before'] = _donor_mass(flow, mask, chamber['factor'])
        chamber['mass_after'] = (CHAMBER_MULTIPLIER * chamber['mass_before'] /
                                 max(CHAMBER_MULTIPLIER * chamber['mass_before']
                                     + (1.0 - chamber['mass_before']), 1e-12))
        chamber['applied'] = 1.0

    def _parent_predict():
        """The parent decoder call, unchanged in arguments, seeds and weights.

        When the chamber correction is active the fixed log multiplier is
        composed into ``log_growth`` for this one draw only: the parent draws
        donors with weights ~ exp(DRAW_GROWTH*F*log_growth), so adding
        log(m)/(DRAW_GROWTH*F) reproduces exactly the desired observation
        factor m at the unchanged RNG stream.  The saved value (which already
        contains the erythroid increment, and any outer metabolic tilt intro-
        duced by the caller) is restored in ``finally``, so the two temporary
        swaps compose and nothing leaks into later calls.
        """
        extra = chamber['log_multiplier']
        if extra is None:
            if ext is not None:
                return model.predict(horizon, n=context['n'], seed=context['seed'],
                                     state=0.35, growth=DRAW_GROWTH, weight=1.0)
            return model.predict(horizon, n=context['n'], seed=context['seed'],
                                 state=0.35, growth=DRAW_GROWTH)
        saved = np.array(flow.log_growth, dtype=float, copy=True)
        try:
            flow.log_growth = saved + extra / (DRAW_GROWTH * chamber['factor'])
            if ext is not None:
                return model.predict(horizon, n=context['n'], seed=context['seed'],
                                     state=0.35, growth=DRAW_GROWTH, weight=1.0)
            return model.predict(horizon, n=context['n'], seed=context['seed'],
                                 state=0.35, growth=DRAW_GROWTH)
        finally:
            flow.log_growth = saved

    if met is None:
        # No observed decline / missing coverage / invalid horizon: exact parent.
        out = _parent_predict()
        out.uns['metabolic_tilt'] = dict(
            applied=False, factor=0.0, genes_used=np.array([], dtype=str),
            genes_used_count=0, score_before=0.0, score_after=0.0,
            global_score_shift=0.0, ess_before=0.0, ess_after=0.0,
            max_type_mass_error=0.0,
            excluded_labels=np.array(excluded_labels, dtype=str),
            n_excluded_labels=int(len(excluded_labels)),
            excluded_mass_before=0.0, excluded_mass_after=0.0)
    else:
        # Algebraic donor-weight swap: the parent draws donors with weights
        # proportional to exp(GROWTH*F*log_growth), so adding
        # log(p1/p0)/(GROWTH*F) reproduces the tilted probabilities at the
        # unchanged draw -- decoder, anchor drift and RNG stream untouched.
        # ``saved`` already contains the erythroid increment from above, and it
        # is restored afterwards so nothing leaks into later calls.
        saved = np.array(flow.log_growth, dtype=float, copy=True)
        try:
            flow.log_growth = saved + met['log_ratio'] / (mets.GROWTH * met['factor'])
            out = _parent_predict()
        finally:
            flow.log_growth = saved
        mets.attach_diagnostics(out, met, applied=True)

    # Flat scalar diagnostics only (h5ad uns cannot store nested structures).
    out.uns['erythroid_prior'] = prior
    out.uns['chamber_sampling'] = {k: v for k, v in chamber.items()
                                   if k != 'log_multiplier'}
    if ext is None:
        return out
    # State-conditioned recipient law for the sparse realisation.  ``flow.zb``
    # are the latest input's own latent coordinates (row-aligned with `latest`),
    # so the placement probabilities are recomputed from the passed WT stage
    # alone; an invalid embedding falls back to the parent uniform law.
    zb = getattr(flow, 'zb', None)
    if zb is not None:
        zb = np.asarray(zb, dtype=np.float64)
        if zb.ndim != 2 or zb.shape[0] != latest.n_obs or not np.all(np.isfinite(zb)):
            zb = None
    return realise_sparse_anchor(out, latest, context['seed'], embedding=zb)


def predict_heart(inputs, times, target_time, context):
    """T2 heart: extrapolate a spatial (MERFISH-like, ~500 genes) heart population with 3D coords."""
    earlier, latest = inputs[-2], inputs[-1]
    interval = times[-1] - times[-2]
    horizon = target_time - times[-1]
    model = LatentFlow(earlier, latest, interval, seed=context['fit_seed'])
    return model.predict(horizon, n=context['n'], seed=context['seed'],
                         state=0.0, growth=0.0, deformation=0.25, scale=0.5)


def predict_embryo(inputs, times, target_time, context):
    """T2 embryo: interpolate a whole-embryo spatial population between two bracketing stages."""
    left, right = inputs[0], inputs[-1]
    fraction = (target_time - times[0]) / (times[-1] - times[0])
    model = SpatialInterpolant(left, right, seed=context['fit_seed'])
    return model.predict(fraction, n=context['n'], seed=context['seed'], mode='transport', deformation=0.5)


def predict_perturbation(inputs, times, target_time, context):
    """T3: predict a conditional knockout (context['knockout']) from WT stages only."""
    earlier, wt = inputs[-2], inputs[-1]
    model = ComplexityPerturbation(earlier, wt, seed=context['fit_seed'])
    return model.predict(strength=0.5, delay=0.0, n=context['n'], seed=context['seed'])


def predict(board, inputs, times, target_time, context):
    fn = {'temporal': predict_temporal, 'heart': predict_heart,
          'embryo': predict_embryo, 'perturbation': predict_perturbation}[board]
    return fn(inputs, times, target_time, context)
