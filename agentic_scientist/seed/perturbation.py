"""historical-entry research-agent program (free-form). Seed = v2 second candidate (Qiu 2024 AnchorFlow).

Contract: predict(board, inputs, times, target_time, context) -> AnnData (see agentic_scientist/prompts/brief.md).
You may rewrite everything here and add helper modules in this workspace.
"""
import numpy as np
import anndata as ad
from scipy import sparse

from perturbation_transport import LatentFlow, SpatialInterpolant, lineages, as_dense, normalize_log
import perturbation_prior_composition as prior_comp
from perturbation_anchor import AnchorFlow
from perturbation_sparse_anchor import realise_sparse_anchor
from perturbation_temporal_sampling import (ERY_MARKERS, MIN_ELIGIBLE, erythroid_eligibility,
                             plan_enrichment)
import perturbation_metabolic_sampling as mets
from perturbation_response_calibration import calibrate_response


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
    """T3: predict a conditional knockout (context['knockout']) from WT stages only.

    Architecture: prior-conditioned COMPOSITION-ONLY maturation rollback
    (perturbation_prior_composition.py).  The knocked-out gene's breadth in the
    supplied whole-transcriptome wild-type prior -- q_t, m_t per matched prior
    cell type, absolute exposure a_t = q_t (1 - exp(-m_t/q_t)) -- sizes how far
    each latest-WT annotation rolls back toward its own earlier relative
    abundance.  Real latest-WT donors are then resampled at the new masses.

    A second, gene-agnostic arm tilts the REAL donors of each annotation
    slightly toward their own earlier-stage state along the axis measured from
    the two supplied WT stages (min-KL exponential tilt, mean shift rho of the
    E_prev->E_last gap, annotation masses unchanged).  The mechanism is a
    maturation delay, which is what a conditional knockout embryo commonly
    looks like; its strength scales with the knockout gene's own absolute
    exposure in the whole-transcriptome prior, so a gene the WT does not
    express receives essentially no delay.

    This cycle replaces that single one-centroid axis, in every lineage with
    enough support, by a DETECTION-MATCHED WT-NEIGHBOUR axis
    (perturbation_wt_neighbours.py): latest-WT detection quartiles define shared
    depth bins, a pooled PCA of variable non-GO genes defines a local
    neighbourhood, and up to 15 earlier / 15 leave-self latest neighbours per
    evenly sampled anchor give the earlier-like contrast.  Only genes whose sign
    recurs across two independent WT halves (|change| >= 0.02) and agrees with
    the full contrast are kept; genes sharing a vetted GO term with the knockout
    get double signed weight (the term is a relevance prior, the direction is
    still measured).  The per-lineage interval fraction is breadth- and
    exposure-scaled and capped at 0.6.  A lineage with fewer than five reliable
    GO-linked genes falls back to the seed centroid; if no lineage qualifies the
    whole arm abstains, so a knockout with thin annotation (Mab21l2, three panel
    GO neighbours) reproduces the seed donor rows bit-identically.  Donor
    probability per lineage and depth bin is preserved and every output row
    remains a resampled real WT cell; only the unchanged amplitude calibration
    rescales expression afterwards.

    Deliberate removals from the parent: the detection-state complexity tilt,
    the q_t - q detection *excess* used by the local rollback, and any latent
    expression delay.  The parent's gene-blind downward pseudobulk bias is what
    the diagnostics measured (through-origin severity R^2 of -1.09 / -1.58 /
    -2.32); those arms moved expression/detection, not composition.  Nothing
    here branches on a gene name, stage value, coordinate system or split
    identity, and the same code path runs for an off-panel knockout (the real
    test gene) because the prior covers the whole transcriptome.

    Amplitude calibration (perturbation_response_calibration.py) is applied to
    the mechanism's real-cell output: a knockout displaces the pseudobulk by
    ~0.65 of one WT developmental interval in SIZE (measured on all five dev
    knockouts, two platforms), while a composition change alone moves the means
    by only a few percent.  The direction is left exactly as produced; only the
    per-gene gains are rescaled so the realised response norm is 0.65 x the norm
    of the supplied WT interval (kappa capped at 4, |log gain| capped at 0.75,
    zeros preserved, genes with |Delta-p| < 0.01 untouched).  That leaves the
    Delta-p ranking (de_score / de_direction) unchanged and raises severity.

    Finite-sample ordering (this cycle): within each lineage the weighted
    systematic donor sweep now walks donors by detection-depth quartile, then by
    their projection on the measured WT earlier-like axis, then by source row
    (perturbation_transport_order.py).  The donor law, quotas, systematic phase
    and calibration are unchanged; only the order of the CDF entries changes,
    which reduces the directional error of the realised maturation mixture.  A
    knockout below the mechanism's absolute-exposure floor (and any split
    without an earlier WT stage) keeps the native order and reproduces the
    incumbent donor rows.
    """
    if not inputs:
        raise ValueError('perturbation board needs at least one WT input')
    wt = inputs[-1]
    earlier = inputs[-2] if len(inputs) > 1 else None
    out = prior_comp.predict(wt, earlier, context)
    return calibrate_response(out, wt, earlier, context)


def predict(board, inputs, times, target_time, context):
    fn = {'temporal': predict_temporal, 'heart': predict_heart,
          'embryo': predict_embryo, 'perturbation': predict_perturbation}[board]
    return fn(inputs, times, target_time, context)
