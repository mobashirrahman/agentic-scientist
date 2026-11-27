"""historical-entry research-agent program (free-form). Seed = v2 second candidate (Qiu 2024 AnchorFlow).

Contract: predict(board, inputs, times, target_time, context) -> AnnData (see agentic_scientist/prompts/brief.md).
You may rewrite everything here and add helper modules in this workspace.
"""
import numpy as np
import anndata as ad
from scipy import sparse

from heart_transport import LatentFlow, SpatialInterpolant, lineages, as_dense, normalize_log
from heart_complexity import ComplexityPerturbation
from heart_anchor import AnchorFlow
from heart_sparse_anchor import realise_sparse_anchor
from heart_temporal_sampling import (ERY_MARKERS, MIN_ELIGIBLE, erythroid_eligibility,
                             plan_enrichment)
import heart_metabolic_sampling as mets
from heart_niche_sampling import plan_cardiac_tilt


def predict_temporal(inputs, times, target_time, context):
    """T1: extrapolate with external anchor drift from Qiu 2024 atlas.

    The anchor drift is realised sparsely (see sparse_anchor.py): a lineage's
    weak added mean is carried by a subset of nuclei at a one-molecule log
    scale instead of being smeared over every donor-zero entry.  This keeps the
    empirical donor profiles and the calibrated mean signal, and conserves the
    per-lineage/gene log-expression budget before CP10k renormalisation.

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
    """
    earlier, latest = inputs[-2], inputs[-1]
    interval = times[-1] - times[-2]
    horizon = target_time - times[-1]
    ext = context.get('external')
    if ext is not None:
        model = AnchorFlow(earlier, latest, ext, times[-2], times[-1], 15.0, seed=context['fit_seed'])
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

    def _parent_predict():
        """The parent decoder call, unchanged in arguments, seeds and weights."""
        if ext is not None:
            return model.predict(horizon, n=context['n'], seed=context['seed'],
                                 state=0.35, growth=0.25, weight=1.0)
        return model.predict(horizon, n=context['n'], seed=context['seed'],
                             state=0.35, growth=0.25)

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
    """T2 heart: extrapolate a spatial (MERFISH-like, ~500 genes) heart population with 3D coords.

    The parent draws latest-stage donors uniformly (growth=0), so it cannot
    represent the expansion of the organised cardiac territory that happens
    between the passed inputs.  ``heart_niche_sampling`` measures, on each input
    stage independently, the fraction of each cell's 31 spatial neighbours that
    are marker-corroborated cardiomyocytes, and turns the *trend* of that local
    field into a small donor reweighting: logit gain clipped to log 2, damped by
    the horizon factor F = horizon/(horizon+interval) and by (1 - mu_b), and
    hard-capped at a total-variation budget of 0.05*F.  Only donor identities
    change (real latest-stage cells stay the source of every profile); the
    deformation (0.25), scale growth (0.5) and seeds are unchanged.  On a flat,
    falling, saturated or unsupported trend the parent path runs unmodified.
    """
    earlier, latest = inputs[-2], inputs[-1]
    interval = times[-1] - times[-2]
    horizon = target_time - times[-1]
    model = LatentFlow(earlier, latest, interval, seed=context['fit_seed'])
    plan = plan_cardiac_tilt(earlier, latest, horizon, interval)
    p = None if plan is None else plan['p']
    out = model.predict(horizon, n=context['n'], seed=context['seed'],
                        state=0.0, growth=0.0, deformation=0.25, scale=0.5,
                        source_probabilities=p)
    if plan is None:
        out.uns['cardiac_niche'] = dict(
            applied=0.0, mu_a=0.0, mu_b=0.0, beta=0.0, f=0.0, tv=0.0, tv_tilt=0.0,
            lam=0.0, ess=0.0, cm_share_parent=0.0, cm_share_pred=0.0, cm_share_gain=0.0,
            noncm_nb_mass_parent=0.0, noncm_nb_mass_pred=0.0, logit_gain=0.0,
            n_seeds_earlier=0.0, n_seeds_latest=0.0, n_markers=0.0, k_field=0.0)
    else:
        out.uns['cardiac_niche'] = dict(
            applied=1.0, mu_a=plan['mu_a'], mu_b=plan['mu_b'], beta=plan['beta'],
            f=plan['F'], tv=plan['tv'], tv_tilt=plan['tv_tilt'], lam=plan['lam'],
            ess=plan['ess'], cm_share_parent=plan['cm_share_parent'],
            cm_share_pred=plan['cm_share_pred'], cm_share_gain=plan['cm_share_gain'],
            noncm_nb_mass_parent=plan['noncm_nb_mass_parent'],
            noncm_nb_mass_pred=plan['noncm_nb_mass_pred'],
            logit_gain=plan['logit_gain'], n_seeds_earlier=plan['n_seeds_earlier'],
            n_seeds_latest=plan['n_seeds_latest'], n_markers=plan['n_markers'],
            k_field=plan['k_field'])
    return out


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
