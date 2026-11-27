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
"""
import numpy as np

# ---- pre-registered constants (fixed, never swept on dev) -------------------
MIN_CELLS = 30            # label support required at BOTH WT stages
CLIP_LO, CLIP_HI = 0.25, 4.0   # bound on the observed stage abundance contrast
SIM_MIN = 0.20            # minimum cosine similarity for a confident type match
SIM_MARGIN = 0.05         # required margin over the runner-up prior type
CLIP_Z = 3.0              # bounded signature z-score
SD_FLOOR = 0.1            # per-gene (across-type) SD floor, shared with the check
N_FLOOR, N_DEFAULT, N_CAP = 1000, 12000, 20000


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


def cell_budget(context):
    """Fixed finite-donor budget: clip(max(context[n], 12000), 1000, 20000)."""
    try:
        n = int(context.get('n', N_DEFAULT))
    except Exception:
        n = N_DEFAULT
    return int(np.clip(max(n, N_DEFAULT), N_FLOOR, N_CAP))


def realise(wt, target, types, n, seed):
    """Largest-remainder allocation to n real WT donors, seeded within-type cycles.

    Floor each n*f_t, give the remainder to the largest fractional remainders in
    stable (sorted-type) order, then draw each type's donors from ONE RNG
    permutation repeated in complete cycles plus a prefix.  Row order of each
    type is fixed, so the draw depends only on ``seed`` and the masses.
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
        perm = rng.permutation(donors)
        cycles = k // len(perm)
        if cycles:
            chosen.append(np.tile(perm, cycles))
        rest = k - cycles * len(perm)
        if rest:
            chosen.append(perm[:rest])
    idx = np.concatenate(chosen) if chosen else np.zeros(0, dtype=int)
    return idx, counts


def predict(wt, earlier, context):
    """Compose exposure -> composition law -> real WT donors; return the AnnData prediction."""
    prior = context.get('expression_prior')
    exp = prior_exposure(wt, prior, context.get('knockout'))
    law = composition_law(earlier, wt, exp['exposure'])
    n = cell_budget(context)
    idx, counts = realise(wt, law['target'], law['types'], n, context['seed'])
    if idx.size == 0:   # impossible in practice; fall back to a plain WT bootstrap
        idx = np.random.default_rng(context['seed']).integers(0, wt.n_obs, n)
    out = wt[idx].copy()
    out.obs_names = [f'pred_{i}' for i in range(out.n_obs)]
    out.obs['source_row'] = idx.astype(np.int64)
    out.uns['method'] = ('whole-transcriptome prior exposure x WT stage-contrast composition '
                         'rollback; real latest-WT donors, no complexity tilt')
    # ---- flat diagnostics (h5ad uns keeps scalars / arrays) ------------------
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
    return out
