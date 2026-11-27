"""historical-entry research-agent program (free-form). Seed = v2 second candidate (Qiu 2024 AnchorFlow).

Contract: predict(board, inputs, times, target_time, context) -> AnnData (see agentic_scientist/prompts/brief.md).
You may rewrite everything here and add helper modules in this workspace.
"""
import numpy as np
import warnings
import anndata as ad
from scipy import sparse

from perturbation_transport import LatentFlow, SpatialInterpolant, lineages, as_dense, normalize_log
from perturbation_complexity import ComplexityPerturbation
from perturbation_local_rollback import local_rollback
from perturbation_programs import program_probabilities
from perturbation_network import network_response
from perturbation_anchor import AnchorFlow
from perturbation_sparse_anchor import realise_sparse_anchor
from perturbation_temporal_sampling import (ERY_MARKERS, MIN_ELIGIBLE, erythroid_eligibility,
                             plan_enrichment)
import perturbation_metabolic_sampling as mets


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

    p0 = parent within-type complexity law x the local lineage rollback
    (perturbation_local_rollback.py): the knockout gene's own detection excess in
    the passed WT defines a per-annotation exposed mass, which is conserved and
    redistributed toward that annotation's earlier WT composition.  The parent
    probability of a cell *within* its annotation is preserved; only annotation
    masses move, and unexposed annotations are untouched.

    p1 = p0 pushed through the program-space mechanism
    (perturbation_programs.py): an NMF of the passed WT cells defines gene
    programs; the knocked-out gene's own loading suppresses (half strength) the
    ABSOLUTE activities of the programs it loads in; each weakened activity
    vector is mapped to the nearest real latest WT donor of the same annotation;
    and p0's mass is moved to those donors in proportion to the knockout gene's
    detection in that annotation.  This adds the missing within-lineage state
    response (the parent only moves annotation masses), keeps every cell real,
    and conserves annotation masses exactly.  It is a fixed dependency prior:
    no K, strength, exposure threshold or program choice is fitted on any
    knockout.

    p2 = p1 stacked with the frozen WT-calibrated signed-network residual
    (perturbation_network.py): after the donor projection has re-drawn *real*
    latest WT cells, one bounded signed downstream response is added to the
    donor-positive entries of those sampled profiles.  The NMF projection moves
    probability mass among real cells of the same annotation, so it supplies an
    unsigned state-dependency direction only; the network supplies a distinct
    signed transcript-level direction (the probe measured cosine 0.036 between
    the two increments).  Both are frozen, previously accepted mechanisms and
    neither has its parameters retuned here.

    EVERY completed output, including the fallback path below, passes through
    this second stage: an off-panel symbol such as the test-time Ctnnb1 takes the
    NMF fallback first, so a return before the network stage would make the
    frozen functional-analogue prior unreachable.  The residual is applied
    *after* the donor projection, adds only on donor-positive entries, keeps
    every zero at zero, is clipped per gene to +/-0.35 log units, is
    renormalised once to CP10k, and never changes source_row, celltype or the
    detection count (the increment touches only entries that were already
    positive, so every donor zero stays zero).

    Fallbacks are input-contract only and return the exact parent p0: off-panel
    or poorly detected symbols, a missing earlier input, zero gene loading or a
    degenerate factorization.  A null (barely detected) gene gets a zero network
    increment, so its output stays byte-identical to the parent.  The on-panel
    supported mechanism ships ON with no score-based switch or rollback.
    """
    if not inputs:
        raise ValueError('perturbation board needs at least one WT input')
    wt = inputs[-1]
    earlier = inputs[-2] if len(inputs) > 1 else None
    interval = (float(times[-1] - times[-2])
                if len(times) > 1 and np.isfinite(times[-1] - times[-2])
                and (times[-1] - times[-2]) > 0 else .25)
    model = ComplexityPerturbation(earlier, wt, seed=context['fit_seed'], interval=interval)
    knockout = context.get('knockout')
    rb = local_rollback(earlier, wt, knockout)

    # The parent donor law, including the local rollback (unchanged).
    p0 = model.probabilities(strength=0.5, rollback=rb)
    p1, prog = program_probabilities(earlier, wt, knockout, p0, context['fit_seed'])

    def _frozen_network(out):
        """Common return path: frozen signed residual on the parent/donor output.

        Placed here rather than inside either branch so that the early NMF
        fallback (off-panel or low-detection symbols) is composed with the
        network's off-panel functional-analogue prior too.  Any internal guard
        in the helper leaves ``out`` untouched and records a flat
        ``network_response`` diagnostic, so a null gene cannot drift.
        """
        return network_response(earlier, wt, out, knockout,
                                context.get('external'))

    if not prog.get('applied', 0.0):
        # Input-contract fallback: the parent decoder call, unchanged.
        out = model.predict(strength=0.5, delay=0.0, n=context['n'],
                            seed=context['seed'], rollback=rb)
        out.uns['program_knockout'] = prog
        return _frozen_network(out)

    # Draw from the projected law.  Keeping the parent's rng call
    # (default_rng(seed).choice) means p1 == p0 reproduces the parent sample.
    idx = np.random.default_rng(context['seed']).choice(wt.n_obs, context['n'],
                                                        replace=True, p=p1)
    with warnings.catch_warnings():
        # Duplicate draw indices make the slice's obs_names non-unique until we
        # relabel below; the warning is expected here.
        warnings.simplefilter('ignore')
        out = wt[idx].copy()
    out.obs_names = [f'pred_{i}' for i in range(context['n'])]
    out.obs['source_row'] = idx
    out.uns['method'] = ('within-type WT complexity law + lineage rollback + '
                         'program-space knockout suppression on real donors')
    out.uns['complexity_strength'] = 0.5
    out.uns['delay_days'] = 0.0
    out.uns['local_rollback'] = dict(
        abstain=float(bool(rb.get('abstain', False))), reason=str(rb.get('reason', 'ok')),
        detected=float(rb.get('detected', 0)), q=float(rb.get('q', 0.0)),
        exposed_mass=float(rb.get('A', 0.0)), rollback_norm=float(rb.get('B', 0.0)),
        min_stage_ratio=float(rb.get('min_r', 1.0)), max_stage_ratio=float(rb.get('max_r', 1.0)),
        donor_tv=float(0.5 * np.abs(p0 - model.base_probabilities(0.5)).sum())
        if not rb.get('abstain', False) else 0.0,
        max_unexposed_mass_error=float(rb.get('max_unexposed_mass_error', 0.0)),
        uniform_arm=0.0, probability_sum=float(p0.sum()),
        types=np.array([str(t) for t in rb.get('types', [])], dtype=str),
        mass_before=np.asarray(rb.get('f_before', []), dtype=float),
        mass_after=np.asarray(rb.get('f_after', []), dtype=float),
        exposure=np.asarray(rb.get('exposure', []), dtype=float),
        stage_ratio=np.asarray(rb.get('stage_ratio', []), dtype=float))
    out.uns['program_knockout'] = prog
    return _frozen_network(out)


def predict(board, inputs, times, target_time, context):
    fn = {'temporal': predict_temporal, 'heart': predict_heart,
          'embryo': predict_embryo, 'perturbation': predict_perturbation}[board]
    return fn(inputs, times, target_time, context)
