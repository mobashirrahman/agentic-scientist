"""Whole-transcriptome prior exposure -> composition-only maturation rollback (T3).

Mechanism (gene-agnostic, WT-only, no mutant data): a loss-of-function of a
developmental regulator changes the *abundance* of the lineages that use it, not
a single global expression offset.  The size of that compositional response is
read from the knocked-out gene's own breadth in the supplied whole-transcriptome
wild-type prior (Qiu 2024 TS12-13), which is available for EVERY symbol --
including genes that are not on the 500-gene panel (the real test case, Ctnnb1).
Expression breadth is a dependence proxy, not proof of necessity.

For each latest-WT annotation t we match its panel centroid to a prior cell type
using independently centred/scaled gene signatures (so platform baselines and
absolute levels cannot drive the match), then read that prior type's knockout
detection q_t and mean log expression m_t; ambiguous matches fall back to the
prior's global values.  The bounded absolute exposure

    a_t = q_t * (1 - exp(-m_t / max(q_t, 1e-12)))

is the probability that a cell of that type has at least one affected transcript
(the Poisson "at least one" form), so it stays ~1 for a ubiquitous gene and
approaches 0 continuously for a gene the prior does not see.

The composition law rolls each supported annotation toward its own earlier WT
relative abundance with that exposure as the exponent:

    r_t = clip(e_t / f_t, 0.25, 4)        (>=30 cells of the label at both stages)
    f_new proportional to f_t * r_t ** a_t   (normalised once)

so a broadly expressed gene gives a broad rollback, a prior-null gene gives the
identity law, and no complexity/detection tilt, expression edit, latent delay or
neural network is involved.  There is no fitted constant and no gene-name,
stage-value, coordinate or matched-fraction branch anywhere.

Realisation is a seeded within-annotation resampling of REAL latest-WT cells
(complete permutation cycles plus a prefix per type), so every output row keeps
its donor's whole expression vector and metadata.  The finite-donor budget is
fixed a priori at n=12000 (the planning check in analysis/sampling_check.py used
exactly this budget and sampler).

Maturation-delay donor tilt (added after the composition masses are fixed):
a conditional knockout embryo is commonly *developmentally delayed*, so its
cells sit closer to the earlier wild-type stage.  The axis is measured from the
two supplied WT stages themselves, per annotation:

    d_t = mean(E_prev | annotation t) - mean(E_last | annotation t)   (else global d)
    s_i = (x_i - mu_t) . d_t / |d_t|^2        (fraction of the t-stage gap)

and the donors of that annotation are reweighted by a min-KL exponential tilt
w_i ∝ exp(lam s_i) whose lambda is solved so the tilted mean of s equals
rho (a pre-registered fraction of the gap).  No gene names, no KO-specific code:
the axis comes only from the two WT inputs, and the whole tilt is scaled by the
knockout gene's own absolute exposure in the whole-transcriptome prior so that a
gene the WT never expresses receives essentially no delay (no-harm property).
Weights are clipped to a bounded density ratio and the effective sample size is
kept >= 50%, so real profiles are preserved.  Annotation masses are untouched
(the tilt is strictly within annotation, and the per-type counts are still the
composition law's largest-remainder allocation).

Exposure-gated flat-composition component (added this cycle): a loss-of-function
can also change the RELATIVE occupancy of a lineage (reduced proliferation or
failed specification) without any cell changing its own programme.  When the
knockout gene's whole-prior detection breadth is restricted (q_all < 0.45) AND
the prior gives it real absolute exposure (a_all > 0.02), a fraction

    u = 0.95 * clip((0.45 - q_all)/0.35, 0, 1) * clip((a_all - 0.02)/0.08, 0, 1)

of the donor law is replaced by a flattened latest-WT composition
b_t = min(4 f_t, k f_t**0.55) (k solved so the masses sum to one) with uniform
within-annotation donor weights.  Breadth decides the direction (a broadly
expressed gene acts everywhere, so flattening is not the leading hypothesis) and
absolute exposure only sizes the amplitude.  Every constant is fixed a priori;
the mixture is realised through the same seeded, real-cell sampler, so it adds a
composition response and no expression edit.  Invalid prior support or u = 0
takes the parent realisation path unchanged (the prior-invisible arm reproduces
the parent donor rows exactly for the same seed).

Locally bidirectional WT-interval lineage transport (added this cycle,
perturbation_lineage_transport.py): a single backward direction forces every
lineage to share one interpretation of the interval, so before ``realise`` the
seed donor law is scored per lineage by the observed WT share change plus a
bounded gene-conditioned residual term, and B = 2% of the donor slots are moved
from the lowest- to the highest-scoring disjoint lineages (quota-level, intact
latest-WT donors; unchanged lineages keep their exact parent draws).  The
matched gene-blind comparator (lambda = 0) uses the same donors, budget and
seed background; its inter-arm quota TV and sign reversals are recorded in
``uns['donor_transport']``.  The low-exposure no-harm gate is shared with the
flat component, so a gene the WT barely expresses is bit-identical to the seed.
"""
import numpy as np

import perturbation_lineage_transport as lineage_transport

# ---- pre-registered constants (fixed, never swept on dev) -------------------
MIN_CELLS = 30            # label support required at BOTH WT stages
CLIP_LO, CLIP_HI = 0.25, 4.0   # bound on the observed stage abundance contrast
SIM_MIN = 0.20            # minimum cosine similarity for a confident type match
SIM_MARGIN = 0.05         # required margin over the runner-up prior type
CLIP_Z = 3.0              # bounded signature z-score
SD_FLOOR = 0.1            # per-gene (across-type) SD floor, shared with the check
N_FLOOR, N_DEFAULT, N_CAP = 1000, 7449, 7449
# --- maturation-delay donor tilt knobs/constraints ---------------------------
# The tuner-selected value of ``rho`` (0.34514799029566345) is supplied through
# context['params'] by perturbation_tuned.json; ``perturbation_knobs.json`` is
# deliberately left unchanged so that value is inherited, not re-tuned.  The
# in-code fallback stays at the declared default (0.20) for the empty-params case.
RHO_DEFAULT = 0.20        # a-priori delay fraction of the E_prev->E_last gap
TILT_MIN_CELLS = 30       # donors needed in an annotation to tilt it
TILT_RATIO_LO, TILT_RATIO_HI = 0.25, 4.0   # bounded weight / uniform ratio
TILT_ESS_FRAC = 0.5       # minimum effective sample size share per annotation
TILT_LAMBDA_MAX = 60.0    # bisection ceiling (clipping binds long before this)
EXPOSURE_REF = 0.10       # absolute exposure that counts as a fully exposed gene
# --- exposure-gated flat-composition component (this cycle) ------------------
# A loss-of-function can also change the RELATIVE occupancy of a major lineage
# (reduced proliferation / failed specification) without changing any cell's own
# expression programme.  The component below adds one extra donor law that is a
# *flattened* version of the observed latest-WT annotation composition: it keeps
# real cells and their measured joint expression, but gives every annotation a
# uniform-within-annotation donor weight, so it contributes its own composition
# response independently of the parent's within-annotation maturation tilt.
# Breadth (q_all, the prior detection fraction of the knocked-out gene) decides
# whether a composition response is plausible at all and *sets its direction*;
# absolute exposure a_all only sizes the amplitude.  All constants are fixed a
# priori; none was fitted to a split or a gene.
FLAT_U_MAX = 0.95         # maximum donor-law mass put on the flat component
# w0_c10 raised this ceiling from 0.60 to 0.95 on the measured dose-response of
# the pre-registered donor-law probe (analysis/donor_law_probe.log, w0_c09): the
# restricted-and-exposed knockout (Gata4: q_all 0.157, a_all 0.135) sat at
# u = 0.50 of the way to the flat law and its severity gate opened only weakly,
# while the probe's flat-only arm (u = 1) moved both Gata4 splits monotonically
# toward the truth.  The ceiling is a pure dose on an already-confirmed lever;
# the breadth ramp, exposure ramp, cap and flattening power are unchanged, so
# broadly expressed genes stay near u = 0 through the breadth ramp (the real
# test gene Ctnnb1, q_all 0.67, is unaffected by construction) and
# prior-invisible genes (Mab21l2 q_all 0.014, a_all 0.009) stay exactly on the
# parent path.
FLAT_QBAR = 0.45          # prior breadth at/above which no flattening is added
FLAT_QSPAN = 0.35         # width of the breadth ramp below FLAT_QBAR
FLAT_A_FLOOR = 0.02       # absolute exposure with no support for a response
FLAT_A_SPAN = 0.08        # width of the exposure ramp above FLAT_A_FLOOR
FLAT_POWER = 0.55         # sub-linear type-share exponent (flattening)
FLAT_CAP = 4.0            # a-priori cap on flat/natural mass per annotation


def _resolve_prior_type(prior, knockout):
    """Case-insensitive row resolution in the WHOLE prior (panel membership is irrelevant)."""
    if knockout is None:
        return None
    sym = str(knockout)
    try:
        idx = prior.index
    except AttributeError:
        return None
    if sym in idx:
        return sym
    low = sym.lower()
    for name in idx:
        if str(name).lower() == low:
            return name
    return None


def _signature(x):
    """Centre/scale each gene across types, clip, row-unit-normalise (cosine match)."""
    z = (x - x.mean(0)) / np.maximum(x.std(0), SD_FLOOR)
    z = np.clip(z, -CLIP_Z, CLIP_Z)
    return z / np.maximum(np.linalg.norm(z, axis=1, keepdims=True), 1e-12)


def prior_exposure(wt, prior, knockout):
    """Per-latest-annotation exposure a_t from the gene's whole-transcriptome WT prior.

    Returns a dict with ``exposure`` (aligned to ``np.unique(wt.obs['celltype'])``,
    i.e. the same strata the composition law uses) plus the diagnostics recorded in
    ``uns``.  A missing prior, a symbol absent from the prior, or too little shared
    signal yields an explicit identity law (all exposures 0, reason recorded); no
    template is ever synthesised.
    """
    wlab = np.asarray(wt.obs['celltype'].astype(str)).ravel()
    types = np.unique(wlab)
    n_types = len(types)
    base = dict(abstain=True, reason='', exposure=np.zeros(n_types),
                prior_frac_all=np.nan, prior_mean_all=np.nan,
                confident_mapping_mass=0.0, exposed_mass=0.0,
                prior_type=np.array([''] * n_types, dtype=str),
                confidence=np.zeros(n_types),
                similarity=np.zeros(n_types),
                types=np.asarray([str(t) for t in types], dtype=str))

    if prior is None or not hasattr(prior, 'index') or not hasattr(prior, 'columns'):
        base['reason'] = 'no_expression_prior'
        return base
    prior_types = [str(c)[len('mean:'):] for c in prior.columns
                   if str(c).startswith('mean:')]
    if not prior_types:
        base['reason'] = 'prior_without_type_columns'
        return base
    gene_row = _resolve_prior_type(prior, knockout)
    if gene_row is None:
        base['reason'] = 'symbol_absent_from_prior'
        return base
    row = prior.loc[gene_row]
    base['prior_frac_all'] = float(row['frac_all'])
    base['prior_mean_all'] = float(row['mean_all'])

    # Shared symbols (first column on duplicates) between the panel and the prior.
    names = [str(v) for v in wt.var_names]
    seen = set()
    cols, genes = [], []
    for j, g in enumerate(names):
        if g in seen or g not in prior.index:
            continue
        seen.add(g)
        cols.append(j)
        genes.append(g)
    if len(genes) < 2 or n_types < 2:
        base['reason'] = 'too_few_shared_genes'
        return base

    # Observed WT annotation centroids (original celltype strata).
    n_cells = wt.n_obs
    counts = np.array([(wlab == t).sum() for t in types], dtype=float)
    a = np.empty((n_types, len(genes)), dtype=np.float64)
    for i, t in enumerate(types):
        rows = np.flatnonzero(wlab == t)
        a[i] = np.asarray(wt[rows].X[:, cols].mean(0)).ravel()
    b = prior.loc[genes, ['mean:' + p for p in prior_types]].to_numpy(dtype=float).T

    sim = _signature(a) @ _signature(b).T
    order = np.argsort(-sim, axis=1)
    best = order[:, 0]
    best_sim = sim[np.arange(n_types), best]
    second_sim = sim[np.arange(n_types), order[:, 1]] if len(prior_types) > 1 else np.full(n_types, -1.0)
    confident = (best_sim >= SIM_MIN) & ((best_sim - second_sim) >= SIM_MARGIN)

    q = np.array([row['frac:' + prior_types[j]] if c else row['frac_all']
                  for j, c in zip(best, confident)], dtype=float)
    m = np.array([row['mean:' + prior_types[j]] if c else row['mean_all']
                  for j, c in zip(best, confident)], dtype=float)
    exposure = q * (1.0 - np.exp(-m / np.maximum(q, 1e-12)))
    exposure = np.clip(np.nan_to_num(exposure, nan=0.0, posinf=0.0, neginf=0.0), 0.0, 1.0)

    f = counts / max(float(counts.sum()), 1.0)
    base.update(abstain=False, reason='ok', exposure=exposure,
                confident_mapping_mass=float(f[confident].sum()),
                exposed_mass=float(f @ exposure),
                prior_type=np.asarray([prior_types[j] for j in best], dtype=str),
                confidence=confident.astype(float), similarity=best_sim.astype(float))
    return base


def composition_law(earlier, wt, exposure):
    """Relative-mass multipliers f_new/f_t from the observed WT stage contrast.

    Supports only labels with >=MIN_CELLS at BOTH stages (r_t=1 elsewhere), clips
    the observed contrast, and normalises once.  Note that this final normalisation
    can still move a label with zero exposure (its f is divided by a sum that
    changed); exact unaffected-mass conservation is NOT claimed.
    """
    wlab = np.asarray(wt.obs['celltype'].astype(str)).ravel()
    types = np.unique(wlab)
    n_types = len(types)
    f = np.array([(wlab == t).sum() for t in types], dtype=float)
    f /= max(float(f.sum()), 1.0)
    out = dict(abstain=True, reason='', target=f.copy(), f_before=f, stage_ratio=np.ones(n_types),
               supported=np.zeros(n_types), max_unsupported_mass_error=0.0,
               types=np.asarray([str(t) for t in types], dtype=str))
    a = np.asarray(exposure, dtype=float)
    if a.shape != (n_types,):
        a = np.zeros(n_types)
    if earlier is None:
        out['reason'] = 'no_earlier_input'
        return out
    alab = np.asarray(earlier.obs['celltype'].astype(str)).ravel()
    e = np.array([(alab == t).sum() for t in types], dtype=float)
    n_e = e.copy()
    e /= max(float(e.sum()), 1.0)
    n_l = np.array([(wlab == t).sum() for t in types], dtype=float)
    supported = (n_l >= MIN_CELLS) & (n_e >= MIN_CELLS)
    unsupported = ~supported
    r = np.ones(n_types)
    r[supported] = np.clip(e[supported] / np.maximum(f[supported], 1e-12), CLIP_LO, CLIP_HI)
    target = f * np.power(r, a)
    total = float(target.sum())
    if not np.all(np.isfinite(target)) or total <= 0:
        out['reason'] = 'degenerate_target'
        return out
    target = target / total
    out.update(abstain=False, reason='ok', target=target, stage_ratio=r,
               supported=supported.astype(float),
               max_unsupported_mass_error=float(np.max(np.abs(target[unsupported] - f[unsupported])))
               if unsupported.any() else 0.0)
    return out


def _shared_columns(earlier, wt):
    """Column indices of the shared symbols in each input (first occurrence, wt order)."""
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
    return np.asarray(cw, dtype=int), np.asarray(ce, dtype=int), genes


def _column_means(X, rows, cols):
    """Mean of the selected columns over ``rows`` (dense or sparse safe)."""
    return np.asarray(X[rows][:, cols].mean(0)).ravel().astype(np.float64)


def _tilt_weights(s, rho):
    """Exponential-tilt weights whose weighted mean of ``s`` is ``rho``.

    ``w ∝ exp(lam s)`` is the minimum-KL reweighting of the uniform donor law
    with a prescribed mean.  ``lam`` is solved by bisection, then shrunk (never
    raised) while the effective sample size is below TILT_ESS_FRAC of the
    annotation or the largest per-donor density ratio exceeds TILT_RATIO_HI:
    those are the declared ceilings, so a wide within-annotation spread of
    states can leave the realised shift below the target rather than
    over-concentrating the donor law.  (The left tail is not floored: cells far
    from the axis are legitimately down-weighted, and the ESS bound already
    keeps any single donor from dominating.)
    """
    n = float(s.size)

    def w_of(lam):
        z = lam * s
        z = z - z.max()
        w = np.exp(z)
        return w / w.sum()

    if float(w_of(TILT_LAMBDA_MAX) @ s) <= rho:
        lam = TILT_LAMBDA_MAX
    else:
        lo, hi = 0.0, TILT_LAMBDA_MAX
        for _ in range(40):
            mid = 0.5 * (lo + hi)
            if float(w_of(mid) @ s) < rho:
                lo = mid
            else:
                hi = mid
        lam = 0.5 * (lo + hi)
    w = w_of(lam)
    for _ in range(24):
        ess = 1.0 / float(np.sum(w * w))
        if (ess >= TILT_ESS_FRAC * n and float(np.max(w) * n) <= TILT_RATIO_HI) or lam <= 1e-6:
            break
        lam *= 0.8
        w = w_of(lam)
    ess = 1.0 / float(np.sum(w * w))
    return w, float(lam), float(w @ s), float(ess), float(np.max(w) * n)


def maturation_tilt(earlier, wt, rho):
    """Within-annotation min-KL donor tilt along the WT E_prev -> E_last axis.

    Returns ``(weights, diag, axis)``: per-donor weights aligned to ``wt``
    (``None`` when the mechanism abstains), flat diagnostics, and the global
    axis vectors used for the realised-response diagnostics.
    """
    diag = dict(applied=False, reason='', rho_target=float(rho), rho_realised=0.0,
                n_shared_genes=0, n_tilted=0, tilted_mass=0.0, ess_frac_min=1.0,
                max_weight_ratio=1.0, d_norm=0.0, pseudo_rho=0.0,
                pseudo_corr_d=0.0, tilted_types=np.array([], dtype=str),
                mean_s=np.zeros(0), type_mass=np.zeros(0))
    axis = dict(d=np.zeros(0), cols=np.zeros(0, dtype=int))
    if earlier is None:
        diag['reason'] = 'no_earlier_input'
        return None, diag, axis
    if not np.isfinite(rho) or rho <= 0:
        diag['reason'] = 'zero_rho'
        return None, diag, axis
    wlab = np.asarray(wt.obs['celltype'].astype(str)).ravel()
    alab = np.asarray(earlier.obs['celltype'].astype(str)).ravel()
    types = np.unique(wlab)
    cw, ce, genes = _shared_columns(earlier, wt)
    diag['n_shared_genes'] = len(genes)
    if len(genes) < 10 or len(types) < 1:
        diag['reason'] = 'too_few_shared_genes'
        return None, diag, axis
    Xw, Xe = wt.X, earlier.X
    d_global = (_column_means(Xe, np.arange(earlier.n_obs), ce)
                - _column_means(Xw, np.arange(wt.n_obs), cw))
    d2 = float(d_global @ d_global)
    diag['d_norm'] = float(np.sqrt(max(d2, 0.0)))
    if not np.isfinite(d2) or d2 <= 1e-8:
        diag['reason'] = 'degenerate_axis'
        return None, diag, axis
    W = np.ones(wt.n_obs, dtype=np.float64)
    mass, mean_s, tilted = [], [], []
    ess_min, ratio_max = 1.0, 1.0
    for t in types:
        rows = np.flatnonzero(wlab == t)
        if rows.size < TILT_MIN_CELLS:
            continue
        mu = _column_means(Xw, rows, cw)
        erows = np.flatnonzero(alab == t)
        if erows.size >= TILT_MIN_CELLS:
            d = _column_means(Xe, erows, ce) - mu
        else:
            d = d_global
        dd = float(d @ d)
        if not np.isfinite(dd) or dd <= 1e-8:
            continue
        proj = np.asarray(Xw[rows][:, cw] @ d).ravel().astype(np.float64)
        s = (proj - float(mu @ d)) / dd
        if not np.all(np.isfinite(s)) or float(s.std()) <= 1e-9:
            continue
        w, _lam, ms, ess, rmax = _tilt_weights(s, rho)
        W[rows] = w * float(rows.size)
        mass.append(float(rows.size))
        mean_s.append(ms)
        tilted.append(str(t))
        ess_min = min(ess_min, ess / float(rows.size))
        ratio_max = max(ratio_max, rmax)
    if not tilted:
        diag['reason'] = 'no_supported_annotation'
        return None, diag, axis
    mass = np.asarray(mass, dtype=float)
    mean_s = np.asarray(mean_s, dtype=float)
    diag.update(applied=True, reason='ok', n_tilted=int(len(tilted)),
                tilted_mass=float(mass.sum() / max(float(wt.n_obs), 1.0)),
                ess_frac_min=float(ess_min), max_weight_ratio=float(ratio_max),
                rho_realised=float(mass @ mean_s / mass.sum()),
                tilted_types=np.asarray(tilted, dtype=str),
                mean_s=mean_s, type_mass=mass)
    axis = dict(d=d_global, cols=cw)
    return W, diag, axis


def absolute_exposure(q_all, m_all):
    """Whole-gene absolute exposure a = q (1 - exp(-m/q)); 0 when unsupported.

    The Poisson "at least one affected transcript per cell" form.  It is ~1 for
    a gene the prior detects everywhere and falls continuously to 0 for a gene
    the wild type never expresses, so the same number sizes the response for an
    on-panel and an off-panel knockout gene alike.
    """
    try:
        q = float(q_all)
        m = float(m_all)
    except Exception:
        return 0.0
    if not np.isfinite(q) or not np.isfinite(m) or q <= 0:
        return 0.0
    a = q * (1.0 - np.exp(-m / q))
    return float(a) if np.isfinite(a) and a > 0 else 0.0


def flat_component_masses(f, power=FLAT_POWER, cap=FLAT_CAP):
    """Flattened annotation masses b_t = min(cap f_t, k f_t**power), sum 1.

    ``f`` is the observed latest-WT composition.  Power < 1 shrinks the share of
    the dominant annotations and (after normalisation) raises mid-frequency ones;
    the cap bounds any single annotation to ``cap`` times its natural mass so a
    rare label cannot be inflated without limit.  ``k`` is solved by bisection on
    sum_t b_t = 1 (the sum is monotone in k and reaches cap > 1 at k -> inf).
    """
    f = np.asarray(f, dtype=float)
    f = np.where(np.isfinite(f) & (f > 0), f, 0.0)
    if float(f.sum()) <= 0:
        return np.full(f.size, 1.0 / max(f.size, 1), dtype=float)
    f = f / float(f.sum())
    shape = np.power(f, power)
    hi = 1.0
    for _ in range(60):
        if float(np.minimum(cap * f, hi * shape).sum()) >= 1.0:
            break
        hi *= 4.0
    lo = 0.0
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        if float(np.minimum(cap * f, mid * shape).sum()) < 1.0:
            lo = mid
        else:
            hi = mid
    b = np.minimum(cap * f, hi * shape)
    return b / max(float(b.sum()), 1e-12)


def donor_law(wt, types, masses, weights=None):
    """Per-donor probability law: type mass x normalised within-type donor weight.

    ``weights`` is the parent's per-donor tilt (None = uniform).  Normalising the
    weight INSIDE the type is what makes the type masses exact and keeps every
    donor a real latest-WT cell; this is exactly the law ``realise`` samples.
    """
    wlab = np.asarray(wt.obs['celltype'].astype(str)).ravel()
    p = np.zeros(wt.n_obs, dtype=np.float64)
    for t, m in zip(types, np.asarray(masses, dtype=float)):
        rows = np.flatnonzero(wlab == t)
        if rows.size == 0:
            continue
        if weights is None:
            w = np.ones(rows.size, dtype=np.float64)
        else:
            w = np.asarray(weights[rows], dtype=np.float64)
            w = np.where(np.isfinite(w) & (w > 0), w, 0.0)
            if float(w.sum()) <= 0:
                w = np.ones(rows.size, dtype=np.float64)
        p[rows] = max(float(m), 0.0) * w / float(w.sum())
    return p


def cell_budget(context):
    """Fixed finite-donor budget: clip(max(context[n], 12000), 1000, 20000)."""
    try:
        n = int(context.get('n', N_DEFAULT))
    except Exception:
        n = N_DEFAULT
    return int(np.clip(max(n, N_DEFAULT), N_FLOOR, N_CAP))


def realise(wt, target, types, n, seed, weights=None):
    """Largest-remainder allocation to n real WT donors, seeded within-type draws.

    Floor each n*f_t, give the remainder to the largest fractional remainders in
    stable (sorted-type) order, then draw each type's donors from ONE RNG
    permutation repeated in complete cycles plus a prefix.  Row order of each
    type is fixed, so the draw depends only on ``seed`` and the masses.  When
    ``weights`` (per-donor, >=0) is given, that type's donors are drawn with
    replacement at those weights instead of uniformly; the type's cell count is
    unchanged, so annotation masses stay exact either way.
    """
    target = np.asarray(target, dtype=float)
    target = np.where(np.isfinite(target) & (target > 0), target, 0.0)
    target = target / max(float(target.sum()), 1e-12)
    counts = np.floor(n * target).astype(int)
    rem = int(n - counts.sum())
    if rem > 0:
        frac = n * target - counts
        order = np.argsort(-frac, kind='stable')
        counts[order[:rem]] += 1
    wlab = np.asarray(wt.obs['celltype'].astype(str)).ravel()
    rng = np.random.default_rng(seed)
    chosen = []
    for t, k in zip(types, counts):
        k = int(k)
        if k <= 0:
            continue
        donors = np.flatnonzero(wlab == t)
        if weights is None:
            perm = rng.permutation(donors)
            cycles = k // len(perm)
            if cycles:
                chosen.append(np.tile(perm, cycles))
            rest = k - cycles * len(perm)
            if rest:
                chosen.append(perm[:rest])
        else:
            p = np.asarray(weights[donors], dtype=float)
            p = np.where(np.isfinite(p) & (p > 0), p, 0.0)
            if p.sum() <= 0:
                p = np.ones(len(donors), dtype=float)
            p = p / p.sum()
            # Systematic (low-variance) resampling: counts differ from k*p_i by
            # less than one, so the tilted mean is realised without the extra
            # duplicate-driven distribution noise of iid weighted draws.
            c = np.cumsum(p) * k
            u = np.arange(k, dtype=float) + rng.random()
            pos = np.searchsorted(c, u, side='left')
            chosen.append(donors[np.minimum(pos, len(donors) - 1)])
    idx = np.concatenate(chosen) if chosen else np.zeros(0, dtype=int)
    return idx, counts


def predict(wt, earlier, context):
    """Compose exposure -> composition law -> maturation tilt -> flat mix -> donors."""
    prior = context.get('expression_prior')
    exp = prior_exposure(wt, prior, context.get('knockout'))
    law = composition_law(earlier, wt, exp['exposure'])
    n = cell_budget(context)
    # Delay-tilt strength: the pre-registered fraction ``rho`` of the observed
    # E_prev -> E_last gap (a knob; identical for every knockout gene), scaled
    # by the knockout gene's own whole-prior absolute exposure so that a gene
    # the wild type never expresses receives essentially no delay.
    params = context.get('params') or {}
    try:
        rho = float(params.get('rho', RHO_DEFAULT))
    except Exception:
        rho = RHO_DEFAULT
    q_all, m_all = exp['prior_frac_all'], exp['prior_mean_all']
    a_all = absolute_exposure(q_all, m_all)
    scale = float(np.clip(a_all / EXPOSURE_REF, 0.0, 1.0))
    weights, tilt, axis = maturation_tilt(earlier, wt, rho * scale)
    # --- exposure-gated flat-composition donor component ---------------------
    # Breadth gate: a gene whose prior detection is broad (q_all >= FLAT_QBAR)
    # acts in nearly every lineage, so a relative-occupancy change is not the
    # leading hypothesis and the parent path runs untouched.  Absolute exposure
    # sizes the amplitude (a strong ramp above FLAT_A_FLOOR, zero below it), so
    # a gene the wild type barely expresses (Mab21l2, a_all 0.009) and any
    # invalid prior support reproduce the parent donor rows exactly.
    u = 0.0
    if (not exp['abstain']) and np.isfinite(q_all) and a_all > FLAT_A_FLOOR:
        u = (FLAT_U_MAX
             * float(np.clip((FLAT_QBAR - float(q_all)) / FLAT_QSPAN, 0.0, 1.0))
             * float(np.clip((a_all - FLAT_A_FLOOR) / FLAT_A_SPAN, 0.0, 1.0)))
        if not np.isfinite(u) or u <= 0:
            u = 0.0
    p_parent = donor_law(wt, law['types'], law['target'], weights)
    if u > 0:
        # b_t flattens the OBSERVED latest-WT composition (not the rolled-back
        # one): this component is the "occupancy changed" hypothesis, and it
        # keeps uniform within-annotation donor weights so it is independent of
        # the parent's within-type maturation tilt.
        b = flat_component_masses(law['f_before'])
        p_flat = donor_law(wt, law['types'], b, None)
        p_mix = (1.0 - u) * p_parent + u * p_flat
        wlab = np.asarray(wt.obs['celltype'].astype(str)).ravel()
        masses = np.array([float(p_mix[wlab == t].sum()) for t in law['types']])
        idx, counts = realise(wt, masses, law['types'], n, context['seed'],
                              weights=p_mix)
    else:
        # Exact parent path: same target masses, same tilt weights, same RNG
        # stream, so the donor rows are identical to w0_c00 for this seed.
        b = np.asarray(law['f_before'], dtype=float)
        masses = np.asarray(law['target'], dtype=float)
        p_flat = p_parent
        p_mix = p_parent
        idx, counts = realise(wt, law['target'], law['types'], n, context['seed'],
                              weights=weights)
    # --- WT-interval lineage transport (this cycle) --------------------------
    # A single backward time direction forces every supported lineage to take
    # the same interpretation of one interval.  perturbation_lineage_transport
    # scores each lineage by the observed WT share change plus a bounded,
    # gene-conditioned term (the seed donor law's pseudobulk residual after
    # removing global level, detection and the generic WT interval axis) and
    # moves B = 2% of N donor slots from the lowest- to the highest-scoring
    # disjoint lineages.  Additions/removals are quota-level, so unchanged
    # lineages keep their exact parent draws and every output row is an intact
    # latest-WT cell.  The low-exposure no-harm gate is shared with the flat
    # component (a_all > FLAT_A_FLOOR): a barely expressed gene is unchanged.
    transport = lineage_transport.plan(
        wt, earlier, law['types'], p_mix, counts, n, context,
        active=((not exp['abstain']) and np.isfinite(a_all)
                and a_all > FLAT_A_FLOOR),
        a_all=a_all)
    if transport.get('applied', 0.0) > 0:
        idx_t, counts_t = lineage_transport.retarget(
            wt, idx, counts, law['types'], p_mix, transport, context['seed'])
        if idx_t is not None and counts_t is not None:
            idx, counts = idx_t, counts_t
            masses = np.asarray(counts, dtype=float) / max(float(np.sum(counts)), 1.0)
        else:
            transport = lineage_transport._flat_diag('retarget_failed')
    if idx.size == 0:   # impossible in practice; fall back to a plain WT bootstrap
        idx = np.random.default_rng(context['seed']).integers(0, wt.n_obs, n)
    out = wt[idx].copy()
    out.obs_names = [f'pred_{i}' for i in range(out.n_obs)]
    out.obs['source_row'] = idx.astype(np.int64)
    out.uns['method'] = ('whole-transcriptome prior exposure x WT stage-contrast composition '
                         'rollback + within-annotation min-KL maturation-delay donor tilt; '
                         'real latest-WT donors, no expression edits')
    # Realised pseudobulk response along the measured maturation axis (diagnostic).
    tilt['rho_used'] = float(rho * scale)
    if tilt['applied']:
        p = np.asarray(out.X.mean(0)).ravel().astype(np.float64)
        r = np.asarray(wt.X.mean(0)).ravel().astype(np.float64)
        v = (p - r)[axis['cols']]
        d = axis['d']
        dd = float(d @ d)
        if dd > 0:
            tilt['pseudo_rho'] = float(v @ d / dd)
        if np.std(v) > 0 and np.std(d) > 0:
            tilt['pseudo_corr_d'] = float(np.corrcoef(v, d)[0, 1])
    # ---- flat diagnostics (h5ad uns keeps scalars / arrays) ------------------
    out.uns['maturation_tilt'] = dict(
        applied=float(bool(tilt['applied'])), reason=str(tilt['reason']),
        rho_target=float(tilt['rho_target']), rho_used=float(tilt['rho_used']),
        rho_realised=float(tilt['rho_realised']), n_shared_genes=float(tilt['n_shared_genes']),
        n_tilted=float(tilt['n_tilted']), tilted_mass=float(tilt['tilted_mass']),
        ess_frac_min=float(tilt['ess_frac_min']),
        max_weight_ratio=float(tilt['max_weight_ratio']),
        d_norm=float(tilt['d_norm']), pseudo_rho=float(tilt['pseudo_rho']),
        pseudo_corr_d=float(tilt['pseudo_corr_d']),
        tilted_types=np.asarray(tilt['tilted_types'], dtype=str),
        mean_s=np.asarray(tilt['mean_s'], dtype=float))
    out.uns['prior_exposure'] = dict(
        abstain=float(bool(exp['abstain'])), reason=str(exp['reason']),
        prior_frac_all=float(exp['prior_frac_all']),
        prior_mean_all=float(exp['prior_mean_all']),
        confident_mapping_mass=float(exp['confident_mapping_mass']),
        exposed_mass=float(exp['exposed_mass']),
        types=exp['types'], exposure=np.asarray(exp['exposure'], dtype=float),
        prior_type=np.asarray(exp['prior_type'], dtype=str),
        confidence=np.asarray(exp['confidence'], dtype=float),
        similarity=np.asarray(exp['similarity'], dtype=float))
    # Donor-law TV versus the uniform latest-WT law (how much the sampled law moved).
    p_donor = np.zeros(wt.n_obs, dtype=float)
    wlab = np.asarray(wt.obs['celltype'].astype(str)).ravel()
    for t, m in zip(law['types'], law['target']):
        rows = np.flatnonzero(wlab == t)
        p_donor[rows] = m / max(len(rows), 1)
    out.uns['composition_law'] = dict(
        abstain=float(bool(law['abstain'])), reason=str(law['reason']),
        n_cells=float(out.n_obs),
        types=law['types'], mass_before=np.asarray(law['f_before'], dtype=float),
        mass_after=np.asarray(law['target'], dtype=float),
        stage_ratio=np.asarray(law['stage_ratio'], dtype=float),
        supported=np.asarray(law['supported'], dtype=float),
        counts=np.asarray(counts, dtype=float),
        max_unsupported_mass_error=float(law['max_unsupported_mass_error']),
        donor_tv=float(0.5 * np.abs(p_donor - 1.0 / wt.n_obs).sum()))
    # --- flat-component diagnostics (parent vs realised composition) ---------
    p_real = np.asarray(counts, dtype=float) / max(float(np.sum(counts)), 1.0)
    n_type = np.array([(wlab == t).sum() for t in law['types']], dtype=float)
    p_uniform_type = n_type / max(float(n_type.sum()), 1.0)
    out.uns['donor_mixture'] = dict(
        applied=float(u > 0), u=float(u),
        prior_frac_all=float(q_all), prior_mean_all=float(m_all),
        a_all=float(a_all),
        types=np.asarray(law['types'], dtype=str),
        mass_parent=np.asarray(law['target'], dtype=float),
        mass_mix=np.asarray(masses, dtype=float),
        mass_flat=(np.asarray(b, dtype=float) if u > 0
                   else np.asarray(law['target'], dtype=float)),
        mass_realised=p_real,
        component_tv=(float(0.5 * np.abs(b - law['target']).sum()) if u > 0 else 0.0),
        flat_tv_vs_observed=(float(0.5 * np.abs(b - law['f_before']).sum())
                             if u > 0 else 0.0),
        type_tv_realised_vs_parent=float(
            0.5 * np.abs(p_real - np.asarray(law['target'], dtype=float)).sum()),
        type_tv_realised_vs_uniform=float(0.5 * np.abs(p_real - p_uniform_type).sum()),
        donor_tv_vs_parent_law=float(0.5 * np.abs(p_mix - p_parent).sum()))
    # --- WT-interval lineage-transport diagnostics (flat scalars/arrays) -----
    out.uns['donor_transport'] = dict(
        applied=float(transport.get('applied', 0.0)),
        reason=str(transport.get('reason', '')),
        lam=float(transport.get('lam', 0.0)),
        budget=float(transport.get('budget', 0.0)),
        n_supported=float(transport.get('n_supported', 0.0)),
        n_add=float(transport.get('n_add', 0.0)),
        n_rem=float(transport.get('n_rem', 0.0)),
        residual_norm=float(transport.get('residual_norm', 0.0)),
        n_panel_genes=float(transport.get('n_panel_genes', 0.0)),
        a_all=float(transport.get('a_all', 0.0)),
        tv_candidate_vs_parent=float(transport.get('tv_candidate_vs_parent', 0.0)),
        tv_blind_vs_parent=float(transport.get('tv_blind_vs_parent', 0.0)),
        tv_candidate_vs_blind=float(transport.get('tv_candidate_vs_blind', 0.0)),
        n_sign_reversals=float(transport.get('n_sign_reversals', 0.0)),
        types=np.asarray(transport.get('types', np.asarray([], dtype=str)), dtype=str),
        quotas=np.asarray(transport.get('quotas', np.zeros(0)), dtype=float),
        add=np.asarray(transport.get('add', np.zeros(0)), dtype=float),
        rem=np.asarray(transport.get('rem', np.zeros(0)), dtype=float),
        scores=np.asarray(transport.get('scores', np.zeros(0)), dtype=float),
        blind=np.asarray(transport.get('blind', np.zeros(0)), dtype=float))
    return out
