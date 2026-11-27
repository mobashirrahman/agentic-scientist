"""Chamber-conditioned extrapolation of a spatial single-cell population.

The model fits every stage summary at prediction time. A donor supplies both the
molecular profile and tissue location of each output cell. Forecasts are damped
as the prediction horizon exceeds the observed interval.
"""
import re

import anndata as ad
import numpy as np
from scipy import sparse
from scipy.spatial import cKDTree
from scipy.special import softmax


def anatomy(name):
    """Broad anatomical terms from the dissection protocol, independent of age."""
    s = name.lower()
    if re.search(r'cm$|cardiomyocyt|myocardi', s) and 'non' not in s:
        return 'myocardium'
    if re.search(r'endomt|cushion|cush-', s):
        return 'cushion'
    if re.search(r'(^endo$|chamber-endo|endocard)', s):
        return 'endocardium'
    if re.search(r'(^epi$|proepi|epicardi)', s):
        return 'epicardium'
    if re.search(r'(^dmp$|dorsal mesenchymal protrusion)', s):
        return 'septal mesenchyme'
    return 'surroundings'


def normalize(x):
    return x / np.maximum(x.sum(axis=-1, keepdims=True), 1e-12)


def discover_lineages(x, points):
    """Partition a specimen with a single uninformative label."""
    from sklearn.cluster import MiniBatchKMeans
    from sklearn.decomposition import TruncatedSVD

    rng = np.random.default_rng(171)
    rows = rng.choice(x.shape[0], min(x.shape[0], 15000), replace=False)
    components = max(1, min(20, x.shape[1]-1, len(rows)-1))
    svd = TruncatedSVD(n_components=components, random_state=57).fit(x[rows])
    features = svd.transform(x)
    depth = np.log1p(np.diff(x.indptr))
    depth -= depth[rows].mean()
    slope = depth[rows] @ features[rows] / (np.dot(depth[rows],depth[rows]) + .1)
    features -= depth[:,None] * slope
    features /= np.sqrt(features[rows].var(0) + .25)
    spatial = (points - points.mean(0)) / rms(points)
    descriptor = np.column_stack((features, 1.4 * spatial))
    clusters = min(48, max(4, int(np.sqrt(len(points)) / 6.)), len(rows))
    learned = MiniBatchKMeans(clusters, random_state=56, batch_size=min(1500,len(rows)),
                             n_init=3).fit(descriptor[rows])
    return np.char.add('Latent ', learned.predict(descriptor).astype(str))


class Stage:
    """Sufficient statistics of native cell types in one unregistered sample."""

    def __init__(self, a):
        self.x = sparse.csr_matrix(a.X, dtype=np.float32, copy=True)
        self.x.eliminate_zeros()
        self.pos = np.asarray(a.obsm['spatial_3D'], dtype=np.float64)
        if 'celltype' in a.obs:
            labels = np.asarray(a.obs['celltype']).astype(str)
        else:
            labels = np.full(a.n_obs, 'Unknown')
        if 'cm_celltype' in a.obs:
            fine = np.asarray(a.obs['cm_celltype']).astype(str)
            raw, inverse, count = np.unique(fine,return_inverse=True,return_counts=True)
            active = (count[inverse.ravel()] >= 40) & ~np.isin(fine, ('Unknown','unknown','nan','None',''))
            labels = np.array([f'{x}|{f}' if active[i] else x for i,(x,f) in enumerate(zip(labels,fine))])
        self.synthetic = (len(labels) >= 12 and np.unique(labels).size == 1 and
                          anatomy(labels[0].split('|')[0]) == 'surroundings')
        if self.synthetic:
            labels = discover_lineages(self.x, self.pos)
        self.names, self.y, self.n = np.unique(labels,return_inverse=True,return_counts=True)
        self.y = self.y.ravel()
        self.roles = np.array([anatomy(k.split('|')[0]) for k in self.names])
        self.core = self.roles != 'surroundings'
        self.native_anatomy = bool(self.core.any())
        if not np.any(self.core) and 'cm_celltype' in a.obs:
            annotated = ~np.isin(np.asarray(a.obs.cm_celltype).astype(str),
                                 ('Unknown', 'unknown', 'nan', 'None', ''))
            self.core = np.bincount(self.y, weights=annotated) / self.n > 0.5
        self.mask = self.core[self.y]
        self.freq = self.n / self.n.sum()
        self.log = []
        self.linear = []
        self.detect = []
        for j, nj in enumerate(self.n):
            block = self.x[self.y == j]
            self.log.append(np.asarray(block.sum(axis=0)).ravel() / nj)
            self.detect.append(np.bincount(block.indices, minlength=a.n_vars) / nj)
            block.data = np.expm1(block.data)
            self.linear.append(np.asarray(block.sum(axis=0)).ravel() / nj)
        self.log, self.detect, self.linear = map(np.asarray, (self.log, self.detect, self.linear))
        self.depth = np.diff(self.x.indptr)


def niche_interaction(stage):
    """Expression contrast between the interiors and edges of local tissues."""
    roles = stage.roles[stage.y]
    role = np.unique(roles, return_inverse=True)[1].ravel()
    neighbors = cKDTree(stage.pos).query(stage.pos, k=min(48, len(stage.pos)))[1]
    neighbors = np.asarray(neighbors).reshape(len(role), -1)
    purity = (role[:, None] == role[neighbors]).mean(1)
    slope = np.zeros_like(stage.linear)
    rank = np.zeros(len(stage.y), dtype=np.float32)
    for j in range(len(stage.n)):
        rows = np.flatnonzero(stage.y == j)
        if len(rows) < 60 or np.ptp(purity[rows]) < .05:
            continue
        low, high = np.quantile(purity[rows], [.25, .75])
        if high <= low:
            continue
        groups = (rows[purity[rows] <= low], rows[purity[rows] >= high])
        means = []
        for group in groups:
            counts = stage.x[group]
            counts.data = np.expm1(counts.data)
            means.append(np.asarray(counts.mean(0)).ravel())
        slope[j] = np.log((means[1] + 2.) / (means[0] + 2.)) * len(rows) / (len(rows) + 180.)
        rank[rows] = np.clip(2. * (purity[rows] - low) / (high - low) - 1., -1., 1.)
        rank[rows] -= rank[rows].mean()
    return slope, rank


def correspondence(last, past):
    """Soft antecedents for renamed or newly divided populations.

    Contrast type means with the typical gene profile within each stage. Match
    on relative enrichment, then use shared names and broad anatomy as evidence.
    """
    signatures = []
    for s in (last, past):
        a = np.log1p(s.linear)
        a = a - np.mean(a, axis=0)
        signatures.append(a / np.maximum(np.linalg.norm(a, axis=1, keepdims=True), 1e-8))
    similarity = signatures[0] @ signatures[1].T
    same = (last.names[:, None] == past.names[None, :]) & (not (last.synthetic or past.synthetic))
    family = (last.roles[:, None] == past.roles[None, :]) & last.core[:, None]
    return softmax((similarity + 0.35 * same + 0.22 * family) / 0.08, axis=1)


def independent_anatomy(stages, genes):
    """Locate cardiac tissue when all supplied annotation names are unfamiliar."""
    from pathlib import Path

    with np.load(Path(__file__).with_name('slide_reference.npz')) as archive:
        index = {g: i for i, g in enumerate(archive['genes'])}
        columns = np.array([index.get(g, -1) for g in genes])
        counts = archive['counts'][:, columns].copy()
        counts[:, columns < 0] = 0.
        labels, times, mass = archive['state'], archive['age'], archive['support']
    references = []
    for time in np.unique(times):
        names = np.unique(labels[times == time])
        evidence = []
        central = []
        for name in names:
            rows = (labels == name) & (times == time)
            if rows.sum() < 3:
                continue
            evidence.append(np.average(1e4 * normalize(counts[rows]), axis=0,
                                       weights=np.sqrt(mass[rows])))
            central.append(name == 'Heart')
        center = np.asarray(central, dtype=bool)
        if not center.any() or center.all():
            continue
        profiles = np.log1p(np.asarray(evidence))
        profiles -= np.median(profiles, axis=0)
        signature = profiles[center].mean(0) - profiles[~center].mean(0)
        relevance = np.sqrt(np.abs(signature) / (np.abs(signature) + profiles.std(0) + .1))
        basis = profiles * relevance
        basis /= np.maximum(np.linalg.norm(basis,axis=1,keepdims=True), 1e-8)
        references.append((basis, center, relevance))
    for stage in stages:
        if stage.core.any():
            stage.roles = np.where(stage.core & (stage.roles == 'surroundings'),
                                   'chamber-associated', stage.roles)
            continue
        observed = np.log1p(stage.linear)
        observed -= np.median(observed, axis=0)
        comparison = []
        for basis, class_mask, relevance in references:
            native = observed * relevance
            native /= np.maximum(np.linalg.norm(native,axis=1,keepdims=True), 1e-8)
            similarity = native @ basis.T
            comparison.append(similarity[:,class_mask].max(1) - similarity[:,~class_mask].max(1))
        if comparison:
            stage.core = np.mean(comparison, axis=0) > 0.
            stage.roles = np.where(stage.core, 'chamber-associated', stage.roles)
            stage.mask = stage.core[stage.y]


def resolve_anatomy(stages, times, genes):
    """Transfer broad anatomy to specimens with an unfamiliar annotation scheme."""
    annotated = [i for i, stage in enumerate(stages) if stage.native_anatomy]
    if not annotated:
        independent_anatomy(stages, genes)
        return
    if len(annotated) == len(stages):
        return
    vocabulary = np.unique(np.concatenate([stages[i].roles for i in annotated]))
    interval = max(float(np.median(np.diff(times))), .1)
    for i, stage in enumerate(stages):
        if stage.native_anatomy:
            continue
        weights = normalize(np.exp(-np.abs(times[annotated] - times[i]) / interval))
        posterior = np.zeros((len(stage.n),len(vocabulary)))
        for j, weight in zip(annotated,weights):
            types = stages[j].roles[:,None] == vocabulary[None,:]
            posterior += weight * (correspondence(stage,stages[j]) @ types)
        key = posterior.argmax(axis=1)
        names = vocabulary[key]
        accepted = (names != 'surroundings') & (posterior.max(axis=1) >= .62)
        stage.roles = np.where(accepted,names,stage.roles)
        stage.core |= accepted
        stage.roles = np.where(stage.core & (stage.roles == 'surroundings'),
                               'chamber-associated',stage.roles)
        stage.mask = stage.core[stage.y]


def rms(p):
    return np.sqrt(np.maximum(p.var(axis=0).sum(), 1e-10))


def temporal_weights(times, target):
    """Each endpoint contrast estimates a velocity over its own time span."""
    age = np.maximum(times[-1] - times[:-1], 1e-5)
    interval = age[-1]
    horizon = max(target - times[-1], 0.)
    w = normalize(np.exp(-(age - interval) / max(interval, 1e-5)))
    step = horizon / (1. + 0.5 * horizon / interval)
    return w, step / age


def region_weights(stages, w, dt, chamber):
    last = stages[-1]
    weights = np.ones(len(last.pos))
    if not np.any(last.mask) or np.all(last.mask):
        return weights
    if chamber:
        # Local support admits a small number of unrecognised chamber residents.
        near = cKDTree(last.pos).query(last.pos, k=min(32, len(last.pos)))[1]
        support = last.mask[near].mean(1)
        return 0.30 * last.mask + 0.70 * support
    def log_odds(stage):
        p = np.clip(stage.mask.mean(), .01, .99)
        return np.log(p / (1 - p))
    change = np.sum([q * h * np.clip(log_odds(last) - log_odds(s), -1.3, 1.3)
                     for s, q, h in zip(stages[:-1], w, dt)])
    field_change = sum(q*h*np.log(rms(last.pos)/rms(s.pos)) for s,q,h in zip(stages[:-1],w,dt))
    contraction = np.clip(-2.4 * field_change, 0., 1.)
    weights[last.mask] *= np.exp(.85 * contraction * change)
    return weights


def growth(stages, w, dt, strength=0.7):
    """Estimate a linear size law from the extent of observed myocardium."""
    radius = []
    for s in stages:
        mask = s.roles[s.y] == 'myocardium'
        if mask.sum() < 50:
            mask = s.mask if s.mask.sum() >= 50 else np.ones(len(s.pos), dtype=bool)
        radius.append(rms(s.pos[mask]))
    delta = np.log(radius[-1] / np.asarray(radius[:-1]))
    return np.exp(np.clip(strength * np.dot(w * dt, delta), -0.1, 0.65))


def lineage_expansion(stages, maps, w, dt):
    """Estimate how each compartment's spread changes within its anatomical role."""
    widths = []
    for stage in stages:
        by_role = {
            role: rms(stage.pos[stage.roles[stage.y] == role])
            for role in np.unique(stage.roles)
        }
        relative = np.zeros(len(stage.n))
        for j in np.flatnonzero(stage.n >= 80):
            extent = rms(stage.pos[stage.y == j])
            relative[j] = np.log(np.clip(extent / by_role[stage.roles[j]], .12, 3.))
        widths.append(relative)
    last = stages[-1]
    shift = np.zeros(len(last.n))
    for stage, match, weight, step, previous in zip(stages[:-1], maps, w, dt, widths[:-1]):
        same_role = last.roles[:, None] == stage.roles[None, :]
        names = last.names[:, None] == stage.names[None, :]
        valid = same_role & (stage.n[None, :] >= 80) & (last.core[:, None] | names)
        supported = match * valid
        mass = supported.sum(1)
        difference = widths[-1] - (supported @ previous) / np.maximum(mass, 1e-8)
        shift += weight * step * mass * np.clip(difference, -.55, .55)
    return np.exp(np.clip(shift, -.45, .45))


def chamber_scale_guard(stages, times, target, weights, historical_scale):
    """Use cell accumulation and an independent anatomy anchor to bound growth."""
    from pathlib import Path

    with np.load(Path(__file__).with_name('heart_shape_reference.npz')) as atlas:
        endpoint_radius = rms(atlas['points'])
        endpoint_time = float(atlas['time'])
    horizon = max(0., target - times[-1])
    span = endpoint_time - times[-1]
    if span <= 0 or horizon <= 0.:
        return 1.
    last = stages[-1]
    points = last.pos[last.mask]
    current_radius = rms(points)
    centers = points[np.linspace(0, len(points)-1, min(600, len(points)), dtype=int)]
    k = np.maximum(5, np.rint(len(points) * np.array([.004, .018, .065])).astype(int))
    k = np.unique(k)
    dimension = 3.
    if len(k) >= 2:
        median = np.maximum(np.median(cKDTree(points).query(centers,k=k)[0], axis=0),1e-6)
        axis = np.log(median)
        axis -= axis.mean()
        log_count = np.log(k)
        slope = np.dot(axis, log_count) / max(np.dot(axis,axis), 1e-8)
        dimension = np.clip(slope, 1.5, 3.)
    support_count = np.array([stage.mask.sum() + 1. for stage in stages])
    observed_spacing = []
    for stage in stages:
        tissue = stage.pos[stage.mask]
        if len(tissue) < 50:
            observed_spacing.append(np.nan)
            continue
        rows = np.linspace(0,len(tissue)-1,min(500,len(tissue)),dtype=int)
        radius = cKDTree(tissue).query(tissue[rows], k=16)[0][:,-1]
        observed_spacing.append(max(float(np.median(radius)),1e-6))
    spacing = np.asarray(observed_spacing)
    use = support_count[:-1] >= 50.
    density = np.where(np.isfinite(spacing), np.maximum(spacing / spacing[-1], 1e-6), 1.)
    # Native support can change through sampling density as well as tissue
    # growth. A volume proxy reduces sensitivity to hard input cell caps.
    masses = support_count * density**dimension
    rate = np.log(masses[-1] / masses[:-1]) / np.maximum(times[-1] - times[:-1], 1e-5)
    from_counts = np.sum(weights[use] * rate[use]) * horizon / dimension
    historical = np.log(historical_scale)
    if from_counts <= max(historical, 0.):
        return 1.
    underfilled = np.clip((from_counts - max(historical, 0.)) / from_counts, 0., 1.)
    fraction = min(horizon / span, 1.)
    ratio = max(endpoint_radius / current_radius, 1e-6)
    log_extent = fraction * np.log(ratio)
    log_volume = np.log1p(fraction * np.expm1(dimension * np.log(ratio))) / dimension
    from_atlas = (1. - underfilled) * log_extent + underfilled * log_volume
    correction = min(from_atlas - historical, from_counts - historical)
    return np.exp(np.clip(correction, 0., .45))


def systematic_sample(weight, n, rng):
    order = rng.permutation(len(weight))
    cdf = np.cumsum(normalize(weight[order]))
    cdf[-1] = 1.
    src = order[np.searchsorted(cdf, (np.arange(n) + rng.random()) / n)]
    return rng.permutation(src)


def external_bulk(genes):
    """Panel-matched E9.5/E14.5 wild-type whole-heart bulk replicate contrasts."""
    from pathlib import Path
    with np.load(Path(__file__).with_name('bulk_reference.npz')) as ref:
        ages = np.unique(ref['age'])
        index = {g:i for i,g in enumerate(ref['genes'])}
        order = [index.get(g, -1) for g in genes]
        counts = ref['counts'][:, order].copy()
        counts[:, np.asarray(order) < 0] = 0
        log = np.log(normalize(counts + .5) * 1e6)
        groups = [log[ref['age'] == age] for age in ages]
        diff = groups[-1].mean(0) - groups[0].mean(0)
        noise = sum(g.var(0) / len(g) for g in groups)
        diff *= diff**2 / (diff**2 + noise + .01)
        rep = anatomical_bulk(genes)
        valid = np.all(np.isfinite(rep),axis=0)
        if np.any(valid):
            region = np.mean(rep[:,valid],axis=0)
            scaling = np.median(np.abs(diff[valid])) / max(np.median(np.abs(region)),.05)
            consensus = np.clip(region * scaling,-3.5,3.5)
            agree = 1. / (1. + np.abs(rep[0,valid] - rep[1,valid]))
            diff[valid] += .45 * agree * (consensus - diff[valid])
        return ages, np.clip(diff, -3., 3.)

def observed_counts(x):
    """Recover a row's unit molecule count, including sparse and empty rows."""
    unit = np.min(np.where(x > 0, x, np.inf), axis=1, keepdims=True)
    return np.rint(x / np.maximum(unit, 1e-8)).astype(np.int32)

def atlas_evidence(last, genes):
    """Match native populations to metacells in two independent 10x experiments.

    Feature centring within a platform reduces gene-specific assay efficiencies.
    Bidirectional soft matching supplies a composition contrast and a conditional
    expression contrast. Only stage-separated wild-type hearts enter the assets.
    """
    from pathlib import Path
    root = Path(__file__).resolve().parent
    values, frequencies, ages = [], [], []
    for name in ('early_reference.npz', 'atlas_reference.npz'):
        with np.load(root / name) as ref:
            index = {g:i for i, g in enumerate(ref['genes'])}
            cols = np.array([index.get(g, -1) for g in genes])
            a = ref['mu'][:, cols].copy()
            a[:, cols < 0] = 0
            values.append(a)
            frequencies.append(ref['frequency'])
            ages.append(float(ref['time']))
    def profile(x, background):
        z = np.log1p(x) - background
        return z / np.maximum(np.linalg.norm(z, axis=1, keepdims=True), 1e-6)
    source_bg = np.median(np.log1p(last.linear), axis=0)
    native = profile(last.linear, source_bg)
    reference_bg = np.median(np.log1p(values[0]), axis=0)
    abundance, conditional, alignment = [], [], []
    for value, freq in zip(values, frequencies):
        sim = native @ profile(value, reference_bg).T
        forward = softmax(sim / .075 + .4 * np.log(freq + 1e-8), axis=1)
        reverse = softmax(sim.T / .075 + .35 * np.log(last.freq + 1e-8), axis=1)
        abundance.append(freq @ reverse)
        conditional.append(forward @ value)
        alignment.append(np.sum(forward * sim, axis=1))
    change = np.log((conditional[1] + 2.) / (conditional[0] + 2.))
    mass = np.log((abundance[1] + .001) / (abundance[0] + .001))
    with np.load(root / 'lineage_references.npz') as ref:
        index = {g: i for i, g in enumerate(ref['genes'])}
        columns = np.array([index.get(g, -1) for g in genes])
        replicates = ref['mean'][:, :, columns].copy()
        replicates[:, :, columns < 0] = 0.
        support = ref['size']
        sample_age = ref['age']
    courses, scatter = [], []
    for age in ages:
        take = sample_age == age
        means = replicates[take]
        size = support[take]
        per_sample = normalize(size)
        centers = np.einsum('sk,skg->kg', per_sample, means) / np.maximum(per_sample.sum(0)[:, None], 1e-10)
        if not courses:
            center_background = np.median(np.log1p(centers), axis=0)
        similarity = native @ profile(centers, center_background).T
        match = softmax(similarity / .075 + .4 * np.log(per_sample.mean(0) + 1e-8), axis=1)
        available = size / (size + 16.)
        local = match[None, :, :] * available[:, None, :]
        evidence = local.sum(2)
        observed = np.log(normalize(local) @ means + 2.)
        reliability = normalize(evidence.T).T
        mean = np.sum(observed * reliability[:, :, None], axis=0)
        courses.append(mean)
        scatter.append(np.mean((observed - mean)**2, axis=0) / len(size))
    replicated = courses[1] - courses[0]
    precision = (replicated**2 + .08) / (replicated**2 + .08 + scatter[0] + scatter[1])
    change = precision * replicated
    # A whole-heart reference only informs surrounding tissue insofar as
    # the reference actually supports the matching cell state at both ages.
    score = np.minimum(*alignment)
    if last.core.any():
        support = max(float(np.median(score[last.core])), .05)
        reliability = np.where(last.core, 1., np.clip(score / support, 0., 1.))
        change *= reliability[:, None]
    return np.clip(change, -2.5, 2.5), np.clip(mass, -2.5, 2.5), ages

def cycling_mask(genes):
    from pathlib import Path
    markers = set(Path(__file__).with_name('cycle_genes.txt').read_text().split())
    return np.array([str(g).upper() in markers for g in genes])

def anatomical_bulk(genes):
    """Independent E9.5-to-E14.5 ventricular microarrays, processed by age."""
    from pathlib import Path
    with np.load(Path(__file__).with_name('ventricle_expression.npz')) as ref:
        index = {g:i for i,g in enumerate(ref['genes'])}
        col = np.array([index.get(g,-1) for g in genes])
        a = ref['direction'][:,col].copy()
        a[:,col < 0] = np.nan
        return a

def coherent_bulk_step(stages, genes, step):
    """Regularize a bulk change on co-expression relationships shared across stages."""
    if np.max(np.abs(step)) < 1e-8:
        return step
    signatures = []
    for stage in stages:
        data = np.log1p(stage.linear)
        weight = normalize(np.sqrt(stage.n))
        center = np.average(data, axis=0, weights=weight)
        centered = data - center
        z = centered * np.sqrt(weight[:, None])
        z /= np.maximum(np.linalg.norm(z, axis=0, keepdims=True), .1)
        signatures.append(z.T @ z)
    structure = np.asarray(signatures)
    agreement = np.abs(np.mean(np.sign(structure), axis=0))
    relation = structure.mean(0) * agreement
    np.fill_diagonal(relation, 0.)
    edge = np.maximum(np.abs(relation) - .45, 0.) * np.sign(relation)
    row_mass = np.abs(edge).sum(1)
    scale = max(float(np.quantile(row_mass, .85)), 1.)
    laplacian = (np.diag(row_mass) - edge) / scale
    sites = anatomical_bulk(genes)
    have = np.all(np.isfinite(sites), axis=0)
    certainty = np.ones(len(genes))
    if have.any():
        site_agreement = 1. / (1. + np.abs(sites[0,have] - sites[1,have]))
        certainty[have] = .6 + .8 * site_agreement
    regularized = np.linalg.solve(np.diag(certainty) + .9 * laplacian, certainty * step)
    return regularized * (np.abs(step).sum() / max(np.abs(regularized).sum(), 1e-8))


def inferred_progress(genes, times, target, ages, direction):
    """Fit a regularized rate curve from independent late-age replicates."""
    from pathlib import Path
    root = Path(__file__).resolve().parent
    with np.load(root / 'bulk_progress.npz') as late, np.load(root / 'bulk_reference.npz') as base:
        later_time = float(late['age'][0])
        earlier = np.log(normalize(base['counts'][base['age'] == ages[-1]] + .5))
        later = np.log(normalize(late['counts'] + .5))
        base_index = {g: i for i, g in enumerate(base['genes'])}
        late_index = {g: i for i, g in enumerate(late['genes'])}
    change = np.zeros(len(genes))
    variance = np.ones(len(genes))
    for k, gene in enumerate(genes):
        if gene in base_index and gene in late_index:
            a = earlier[:, base_index[gene]]
            b = later[:, late_index[gene]]
            change[k] = b.mean() - a.mean()
            variance[k] = a.var()/len(a) + b.var()/len(b) + .035

    span = max(np.ptp(ages), .1)
    later_gap = max((later_time - ages[-1]) / span, .05)
    # Rate proportional to exp(curvature * developmental time).
    candidates = np.r_[np.linspace(-4., -.1, 40), np.linspace(.1, 2., 20)]
    tail_ratio = np.exp(candidates) * np.expm1(candidates * later_gap) / np.expm1(candidates)
    error = (change[None, :] - tail_ratio[:, None] * direction[None, :])**2
    loss = error / variance[None, :] + .18 * (candidates[:, None] + .8)**2
    posterior = softmax(-.5 * loss, axis=0)

    start = float(times[-1])
    end = max(float(target), start)
    def clock(t):
        relative = (t - ages[0]) / span
        inside = np.clip(relative, 0., 1.)
        result = np.expm1(candidates * inside) / np.expm1(candidates)
        extension = max(relative - 1., 0.)
        edge_rate = candidates * np.exp(candidates) / np.expm1(candidates)
        return result + edge_rate * (-np.expm1(-extension))
    progress = clock(end) - clock(start)
    if start < ages[0]:
        elapsed = min(end, ages[0]) - start
        progress += clock(ages[0] + elapsed) * np.exp(-(ages[0] - start) / span)
    return np.clip(progress @ posterior, 0., 1.)


def lineage_autocorrelation(stage, rng, sampled=None):
    """Fit within-lineage short-range expression correlations and donor latents."""
    coefficients = np.zeros_like(stage.log)
    donor_latent = None
    if sampled is not None:
        donor_latent = np.zeros((len(sampled),stage.x.shape[1]), dtype=np.float32)
    for j, size in enumerate(stage.n):
        if size < 60:
            continue
        rows = np.flatnonzero(stage.y == j)
        data = stage.x[rows]
        points = stage.pos[rows]
        k = min(17, len(rows))
        tree = cKDTree(points)
        fit = rng.choice(len(rows), min(2200, len(rows)), replace=False)
        chosen = fit
        if sampled is not None:
            donors = np.flatnonzero(stage.y[sampled] == j)
            donor_ids = np.searchsorted(rows, sampled[donors])
            chosen = np.r_[fit, donor_ids]
        indices = tree.query(points[chosen], k=k)[1][:,1:]
        adj = sparse.csr_matrix(
            (np.full(indices.size, 1. / (k - 1), dtype=np.float32),
             indices.ravel(), np.arange(0, indices.size + 1, k - 1)),
            shape=(len(chosen),len(rows))
        )
        observed = data[fit].toarray()
        mean = observed.mean(0)
        sd = np.sqrt(observed.var(0) + .12)
        observed -= mean
        lag = (adj @ data).toarray()
        lag -= mean
        lag_sd = np.sqrt(lag[:len(fit)].var(0) + .12 / (k - 1))
        coefficients[j] = np.clip((observed * lag[:len(fit)]).mean(0) / (sd * lag_sd), -.6, .6)
        coefficients[j] *= len(fit) / (len(fit) + 200.)
        if sampled is not None:
            donor_latent[donors] = np.clip(lag[len(fit):] / lag_sd, -2., 2.)
    return coefficients, donor_latent


def spatial_residual(stages, maps, w, dt, src, seed):
    """Continue observed changes in covariance with each cell's neighbourhood."""
    rng = np.random.default_rng(seed)
    last = stages[-1]
    observed, spatial = lineage_autocorrelation(last, rng, src)
    shift = np.zeros_like(observed)
    for past, match, q, step in zip(stages[:-1], maps, w, dt):
        previous, _ = lineage_autocorrelation(past, rng)
        shift += q * step * np.clip(observed - match @ previous, -.35, .35)
    cell = last.y[src]
    effect = .8 * shift[cell] * spatial
    for j in np.unique(cell):
        rows = cell == j
        effect[rows] -= effect[rows].mean(0)
    return np.clip(effect, -.55, .55)


def tissue_patch_catalog(stage, rng):
    """Measure expression above a patch's aggregate lineage composition."""
    from sklearn.cluster import MiniBatchKMeans

    rows = rng.choice(len(stage.y), min(len(stage.y), 18000), replace=False)
    points = stage.pos[rows]
    k = min(len(rows), max(1, int(np.sqrt(len(rows)) / 2.)))
    learned = MiniBatchKMeans(n_clusters=k, batch_size=min(1500, len(rows)),
                             n_init=2, random_state=63).fit(points)
    labels = learned.labels_
    sizes = np.bincount(labels, minlength=k)
    composition = np.bincount(labels * len(stage.n) + stage.y[rows],
                              minlength=k * len(stage.n)).reshape(k, -1)
    composition = normalize(composition)
    x = stage.x[rows]
    x.data = np.expm1(x.data)
    membership = sparse.csr_matrix(
        (1. / np.maximum(sizes[labels], 1), (labels, np.arange(len(rows)))),
        shape=(k, len(rows)),
    )
    values = (membership @ x).toarray()
    residual = np.log((values + 2.) / (composition @ stage.linear + 2.))
    centers = learned.cluster_centers_
    keep = sizes >= max(1, min(20, len(rows) // k))
    region = stage.pos[stage.mask] if stage.mask.sum() >= 50 else stage.pos
    radii = np.linalg.norm(centers - region.mean(0), axis=1) / rms(region)
    profiles = np.log1p(values[keep])
    profiles -= np.average(profiles, axis=0, weights=sizes[keep])
    profiles /= np.maximum(np.linalg.norm(profiles, axis=1, keepdims=True), 1e-8)
    return centers[keep], composition[keep], residual[keep], sizes[keep], radii[keep], profiles


def external_cardiac_patches(stage, mix, residual, size, genes, start, target, strength):
    """Estimate changes in regional cardiac enrichment from spatial references."""
    from pathlib import Path

    mass = mix[:, stage.core].sum(1)
    selected = mass > 0.
    result = np.zeros_like(residual)
    if np.count_nonzero(selected) < 3:
        return result
    with np.load(Path(__file__).with_name('cardiac_spatial_reference.npz')) as ref:
        index = {g: i for i, g in enumerate(ref['genes'])}
        columns = np.array([index.get(g, -1) for g in genes])
        expression = ref['mean'][:, columns].copy()
        expression[:, columns < 0] = 0.
        time, sample, sample_mass = ref['age'], ref['sample'], ref['size']
    native = normalize(mix[selected][:, stage.core]) @ stage.linear[stage.core]
    native = np.log1p(1e4 * normalize(native * np.exp(residual[selected])))
    weight = normalize(mass[selected] * size[selected])

    def unit_rows(contrast):
        return contrast / np.maximum(np.linalg.norm(contrast, axis=1, keepdims=True), 1e-8)

    native = unit_rows(native - weight @ native)
    ages = np.unique(time)
    contrasts, confidence = [], []
    for age in ages:
        keep = time == age
        values = np.log1p(expression[keep])
        support = sample_mass[keep].astype(float)
        section = sample[keep]
        for name in np.unique(section):
            rows = section == name
            support[rows] /= support[rows].sum()
        prevalence = normalize(support)
        centered = values - prevalence @ values
        similarity = native @ unit_rows(centered).T
        paired = softmax(similarity / .085 + np.log(prevalence + 1e-8), axis=1)
        contrasts.append(paired @ centered)
        confidence.append((paired * similarity).sum(1))
    span = np.ptp(ages)
    a = np.clip((start - ages[0]) / span, 0., 1.)
    b = np.clip(a + (target - start) / span, 0., 1.)
    distance = max(ages[0] - start, start - ages[-1], 0.)
    progress = (np.sqrt(b) - np.sqrt(a)) * np.exp(-distance / span)
    factor = mass[selected] * np.clip(np.minimum(*confidence), 0., 1.)
    state = np.clip(contrasts[-1] - contrasts[0], -.85, .85)
    result[selected] = factor[:,None] * strength * progress * state
    return result


def projected_patch_motion(stages, maps, weights, steps, source, seed, genes, start, target, strength):
    """Extrapolate the within-patch expression component in overlapping tissues."""
    from scipy.spatial.distance import cdist

    rng = np.random.default_rng(seed)
    last = stages[-1]
    centers, mix, residual, size, radius, signature = tissue_patch_catalog(last, rng)
    change = np.zeros_like(residual)
    for old, ancestry, weight, duration in zip(stages[:-1], maps, weights, steps):
        _, old_mix, previous, old_size, old_radius, old_signature = tissue_patch_catalog(old, rng)
        reverse = normalize(ancestry.T * last.freq)
        old_mix = old_mix @ reverse
        cost = cdist(np.sqrt(mix), np.sqrt(old_mix), 'sqeuclidean')
        cost += .55 * np.maximum(1. - signature @ old_signature.T, 0.)
        if last.mask.sum() >= 50 and old.mask.sum() >= 50:
            cost += .12 * np.minimum((radius[:, None] - old_radius[None, :])**2, 4.)
        scale = max(float(np.median(cost.min(1))), .12)
        kernel = np.exp(-cost / scale)
        left, right = normalize(size), normalize(old_size)
        v = np.ones(len(right))
        for _ in range(18):
            u = (left / np.maximum(kernel @ v, 1e-14))**.72
            v = (right / np.maximum(kernel.T @ u, 1e-14))**.72
        posterior = normalize(kernel * v[None, :])
        reliability = (posterior * np.exp(-cost)).sum(1)
        change += weight * duration * reliability[:,None] * np.clip(residual - posterior @ previous, -.75, .75)
    change += external_cardiac_patches(last, mix, residual, size, genes, start, target, strength)
    k = min(4, len(centers))
    if k == 1:
        out = np.tile(change[0], (len(source), 1))
    else:
        distance, neighbor = cKDTree(centers).query(last.pos[source], k=k)
        kernels = normalize(np.exp(-2. * (distance / np.maximum(distance[:, -1:], 1e-8))**2))
        out = np.einsum('ij,ijk->ik', kernels, change[neighbor])
    cell = last.y[source]
    for j in np.unique(cell):
        take = cell == j
        out[take] -= out[take].mean(0)
    return np.clip(out, -.45, .45)


def maturational_quantiles(stages, maps, w, dt, source, fold):
    """Transport conditional expression quantiles along lineage maturation."""
    last = stages[-1]
    gene_count = last.x.shape[1]
    effect = np.zeros((len(source), gene_count),dtype=np.float32)

    def score(stage, rows, axis):
        values = np.asarray(stage.x[rows] @ axis).ravel().astype(float)
        values -= values.mean()
        depth = np.log1p(stage.depth[rows])
        depth -= depth.mean()
        slope = np.dot(values, depth) / (np.dot(depth, depth) + .01 * len(depth))
        return values - slope * depth

    for j, size in enumerate(last.n):
        rows = np.flatnonzero(last.y == j)
        if size < 85:
            continue
        axis = np.log(fold[j]) * np.sqrt(last.detect[j] + .005)
        strength = np.linalg.norm(axis)
        if strength < .02:
            continue
        axis /= strength
        current = score(last, rows, axis)
        sd = np.sqrt(current.var()+.05)
        grid = np.linspace(.025,.975,25)
        quantiles = np.quantile(current,grid)
        shift = np.zeros(len(grid))
        for older, mat, weight, step in zip(stages[:-1], maps, w, dt):
            supported = np.flatnonzero(older.n >= 85)
            nearest = supported[np.argsort(mat[j,supported])[-4:]]
            mass = mat[j,nearest].sum()
            if mass < .35:
                continue
            observed = np.zeros(len(grid))
            for k in nearest:
                old_rows = np.flatnonzero(older.y == k)
                values = score(older, old_rows, axis)
                observed += mat[j,k] * np.quantile(values,grid) / mass
            difference = quantiles - observed
            shift += weight * step * mass * np.clip(difference,-.6*sd,.6*sd)
        selected = np.flatnonzero(last.y[source] == j)
        latent = current[np.searchsorted(rows,source[selected])]
        motion = np.interp(latent, quantiles, shift)
        if len(motion) > 0:
            motion -= motion.mean()
        response = np.sum(axis**2 * np.clip(last.log[j], .25, 2.0))
        effect[selected] = np.clip(motion[:,None] * axis[None,:] / response, -.5, .5)
    return effect


def sliced_displacement(source, dest, probes, seed, sweeps=2):
    """Smooth sliced-quantile transport in 3D, extended to arbitrary probe sites."""
    rng = np.random.default_rng(seed)
    center = source.mean(0)
    sd = rms(source)
    axes = np.linalg.eigh(np.cov(source.T))[1]
    x = ((source - center) @ axes) / sd
    # Fix each axis direction from the sample's skew so a rigid rotation
    # preserves the sequence of sampled transport directions.
    signs = np.where(np.mean(x**3, axis=0) < 0, -1., 1.)
    axes *= signs
    x *= signs
    y = (dest - center) @ axes / sd
    z = (probes - center) @ axes / sd
    quantiles = np.linspace(.003,.997,90)
    for _ in range(sweeps):
        dirs = np.vstack([np.eye(3),rng.normal(size=(11,3))])
        dirs /= np.linalg.norm(dirs,axis=1,keepdims=True)
        for direction in dirs:
            a = np.quantile(x @ direction,quantiles)
            b = np.quantile(y @ direction,quantiles)
            displacement = np.clip(b-a,-.7,.7)
            z += .52 * np.interp(z@direction,a,displacement)[:,None]*direction
            x += .52 * np.interp(x@direction,a,displacement)[:,None]*direction
    return center + sd*z@axes.T - probes


def intrinsic_frame(points):
    """Return a proper principal frame with data-derived axis directions."""
    axes = np.linalg.eigh(points.T @ points)[1]
    skew = np.mean((points @ axes)**3, axis=0)
    axes *= np.where(skew < 0., -1., 1.)
    if np.linalg.det(axes) < 0.:
        axes[:, np.argmin(np.abs(skew))] *= -1.
    return axes


def serial_section_projection(points, original, roles, seed):
    """Observe an expanded tissue on the input's native serial-section grid."""
    measured = np.round(original[:, 2], 2)
    levels, count = np.unique(measured, return_counts=True)
    levels = levels[count >= 8]
    if len(levels) < 5 or count[count >= 8].sum() < .75 * len(original):
        return points
    spacing = np.diff(levels)
    step = np.median(spacing)
    if step <= 0. or np.mean(np.abs(spacing / step - np.rint(spacing / step)) < .05) < .85:
        return points
    expansion = rms(points) / rms(original)
    mid = np.median(points[:, 2])
    rng = np.random.default_rng(seed)
    latent = points[:,2] + step * max(expansion - 1., 0.) * rng.uniform(-.5, .5, len(points))
    sections = mid + step * np.rint((latent - mid) / step)
    delta = sections - points[:,2]
    distance, nearby = cKDTree(points).query(points, k=min(24, len(points)))
    dev = points[nearby] - points[:,None,:]
    kernel = np.exp(-.5 * (distance / np.maximum(distance[:,-1:], 1e-8))**2)
    kernel *= roles[nearby] == roles[:,None]
    kernel = normalize(kernel)
    mean = np.einsum('ij,ijk->ik', kernel, dev)
    dev -= mean[:,None,:]
    overlap = kernel * dev[:,:,2]
    denominator = np.einsum('ij,ij->i', overlap, dev[:,:,2]) + .16 * step**2
    slope = np.einsum('ij,ijk->ik', overlap, dev[:,:,:2]) / denominator[:,None]
    moved = points.copy()
    moved[:,:2] += delta[:,None] * np.clip(slope, -1., 1.)
    moved[:,2] = sections
    spread = rms(points)**2 - moved[:,2].var()
    current = moved[:,:2].var(0).sum()
    if spread <= 0. or current <= 0.:
        return points
    origin = moved[:,:2].mean(0)
    moved[:,:2] = origin + (moved[:,:2] - origin) * np.sqrt(spread / current)
    return moved

def bracket_rotation(early, late, x, y, first_weight, last_weight):
    """Align the intrinsic frames using supported lineage landmarks."""
    first_mass = np.bincount(early.y, weights=first_weight, minlength=len(early.n))
    last_mass = np.bincount(late.y, weights=last_weight, minlength=len(late.n))
    first_center = np.array([np.dot(first_weight[early.y == j], x[early.y == j]) /
                             max(first_mass[j], 1e-8) for j in range(len(early.n))])
    last_center = np.array([np.dot(last_weight[late.y == j], y[late.y == j]) /
                            max(last_mass[j], 1e-8) for j in range(len(late.n))])
    match = correspondence(late, early) * (first_mass[None,:] > 15.)
    support = match.sum(1)
    comparable = (last_mass > 15.) & (support >= .60)
    if np.count_nonzero(comparable) >= 4:
        a = normalize(match[comparable]) @ first_center
        b = last_center[comparable]
        weight = normalize(np.sqrt(last_mass[comparable]) * support[comparable])
        a -= weight @ a
        b -= weight @ b
        u, s, vh = np.linalg.svd(a.T @ (b * weight[:,None]))
        if s[1] > .1 * s[0] and s[0] > 1e-8:
            u[:, -1] *= np.linalg.det(u @ vh)
            return u @ vh
    return intrinsic_frame(x[first_weight > 0]) @ intrinsic_frame(y[last_weight > 0]).T


def observed_interval(stages, inputs, times, target, chamber, n, rng):
    """Predict within the observed ages by blending aligned cell populations."""
    right = int(np.searchsorted(times, target, side='left'))
    right = min(right, len(stages) - 1)
    current = stages[right]
    empty = np.empty(0)
    upper_weight = region_weights([current], empty, empty, chamber)
    if right == 0 or np.isclose(target, times[right], atol=1e-8, rtol=0.):
        rows = systematic_sample(upper_weight, n, rng)
        return ad.AnnData(current.x[rows].copy(), var=inputs[right].var.copy(),
                          obsm={'spatial_3D': current.pos[rows].astype(np.float32)})

    left = right - 1
    previous = stages[left]
    alpha = (target - times[left]) / (times[right] - times[left])
    lower_weight = region_weights([previous], empty, empty, chamber)

    def relative(position, weight):
        centered = position - np.average(position, weights=weight, axis=0)
        radius = np.sqrt(np.average(np.sum(centered**2, axis=1), weights=weight))
        return centered / max(radius, 1e-8), max(radius, 1e-8)

    x, first_radius = relative(previous.pos, lower_weight)
    y, last_radius = relative(current.pos, upper_weight)
    axes = bracket_rotation(previous, current, x, y, lower_weight, upper_weight)
    number = int(np.rint(n * alpha))
    rows = systematic_sample(lower_weight, n - number, rng)
    cols = systematic_sample(upper_weight, number, rng)
    points = np.concatenate((x[rows] @ axes, y[cols]))
    # A large change in field coverage makes its physical size depend more
    # on the nearer embryo. Shape and expression keep the chronological mix.
    first_fraction = previous.mask.mean()
    last_fraction = current.mask.mean()
    contrast = abs(np.log((last_fraction + .02) / (first_fraction + .02)))
    sharpen = 1. + min(contrast, 2.)
    phase = alpha**sharpen / (alpha**sharpen + (1. - alpha)**sharpen)
    radius = np.exp((1. - phase) * np.log(first_radius) + phase * np.log(last_radius))
    points *= radius / rms(points)
    expression = sparse.vstack((previous.x[rows], current.x[cols]), format='csr')
    order = rng.permutation(n)
    return ad.AnnData(expression[order], var=inputs[right].var.copy(),
                      obsm={'spatial_3D': points[order].astype(np.float32)})


def predict(inputs, times, target_time, context):
    """Forecast log1p CP10k and three-dimensional cell locations."""
    times = np.asarray(times, dtype=float)
    stages = [Stage(a) for a in inputs]
    resolve_anatomy(stages, times, inputs[-1].var_names)
    last = stages[-1]
    w, dt = temporal_weights(times, target_time)
    chamber = context['dissection'] == 'heart_chambers_only'
    rng, noise = [np.random.default_rng(s) for s in np.random.SeedSequence(context['seed']).spawn(2)]
    params = context.get('params') or {}
    if target_time <= times[-1]:
        return observed_interval(stages, inputs, times, target_time, chamber, context['max_cells'], rng)
    weight = region_weights(stages, w, dt, chamber)
    maps = [correspondence(last, s) for s in stages[:-1]]
    if chamber:
        annotated = [(mat, s, q) for mat, s, q in zip(maps, stages[:-1], w) if s.core.any()]
        if annotated:
            incoming = sum(q * (mat @ s.core.astype(float)) for mat, s, q in annotated)
            incoming /= sum(q for _, _, q in annotated)
            if last.mask.any():
                # Purely geometric adjacency can also pick up excised body wall.
                rows = ~last.mask
                weight[rows] *= .45 + .9 * incoming[last.y[rows]]
            elif incoming.max() > .5:
                last.core = incoming > .5
                last.mask = last.core[last.y]
                weight = region_weights(stages, w, dt, chamber)
    depth_mean = last.detect.sum(1)
    previous = [mat @ s.detect.sum(1) for mat, s in zip(maps, stages[:-1])]
    depth_change = sum(q * h * (depth_mean - p) for p, q, h in zip(previous, w, dt))
    for j in range(len(last.n)):
        rows = np.flatnonzero(last.y == j)
        sd = max(float(last.depth[rows].std()), 1.)
        z = (last.depth[rows] - depth_mean[j]) / sd
        tilt = np.clip(params.get('depth_tilt', .65) * depth_change[j] / sd, -.85, .85)
        mult = np.exp(np.clip(z * tilt, -2., 2.))
        weight[rows] *= mult / np.average(mult, weights=np.maximum(weight[rows], 1e-20))
    # A broad dissection contains a separate surrounding field. The region
    # model estimates its tissue budget independently of within-organ growth.
    if not chamber:
        zone_mass = np.bincount(last.mask, weights=weight, minlength=2)

    def specialized(s):
        return np.isin(s.roles, ('epicardium', 'cushion', 'septal mesenchyme'))
    def odds(s):
        total = s.n[s.core].sum()
        founders = max(1., np.sqrt(total))
        mass = s.n[specialized(s)].sum()
        return np.log((mass + founders) / (total - mass + founders))
    growth_rate = sum(q * h * np.clip(odds(last) - odds(s), -2., 2.) for s, q, h in zip(stages[:-1], w, dt))
    weight[specialized(last)[last.y]] *= np.exp(.75 * growth_rate)
    cycle = cycling_mask(inputs[-1].var_names)
    if np.any(cycle):
        index = last.detect[:, cycle].mean(axis=1) / np.maximum(last.detect.mean(axis=1), .005)
        for zone in np.unique(last.core):
            keep = last.core == zone
            avg = np.average(index[keep], weights=last.n[keep])
            potential = np.clip(np.log((index + .25)/(avg + .25)), -1., 1.)
            rows = last.mask == zone
            weight[rows] *= np.exp(.65 * np.dot(w, dt) * potential[last.y[rows]])
    if not chamber:
        actual_mass = np.bincount(last.mask, weights=weight, minlength=2)
        balance = np.divide(zone_mass, actual_mass, out=np.ones(2), where=actual_mass > 0.)
        weight *= balance[last.mask.astype(np.intp)]
    delta = np.zeros_like(last.linear)
    for s, mat, q, h in zip(stages[:-1], maps, w, dt):
        prev = mat @ s.linear
        delta += q * h * np.clip(np.log((last.linear + 1.) / (prev + 1.)), -1.5, 1.5)
    background = np.zeros(delta.shape[1])
    evidence = 0.
    for s, mat, q, h in zip(stages[:-1], maps, w, dt):
        off_target = mat @ (~s.core).astype(float)
        confident = (~last.core) & (off_target > .75) & (mat.max(1) > .55)
        if confident.sum() >= 4:
            obs = np.log((last.linear[confident] + 1.) / ((mat @ s.linear)[confident] + 1.))
            shift = np.median(obs, axis=0)
            uncertainty = np.median(np.abs(obs - shift), axis=0)
            reliability = np.abs(shift) / (np.abs(shift) + uncertainty + .25)
            background += q * h * shift * reliability
            evidence += q
    if evidence > 0 and last.core.any():
        delta[last.core] -= .7 * background
    # Weights in molecule space preserve zeros and cross-gene variation.
    fold = np.exp(np.clip(params.get('expression', 0.32) * delta, -0.85, 0.85))
    age_strength = params.get('maturation', 1.)
    ages, b = external_bulk(inputs[-1].var_names)
    pace = age_strength * inferred_progress(inputs[-1].var_names, times, target_time, ages, b)
    bulk_step = coherent_bulk_step(stages, inputs[-1].var_names, pace * b)
    fold *= np.exp(np.clip(bulk_step, -.95, .95))[None, :] ** np.where(last.core, 1., .25)[:, None]
    atlas_change, atlas_mass, ages = atlas_evidence(last, inputs[-1].var_names)
    span = max(ages[1] - ages[0], 1.)
    elapsed = max(0., target_time - times[-1])
    distance = max(0., ages[0] - times[-1], times[-1] - ages[1])
    if ages[0] <= times[-1] <= ages[1]:
        start = np.clip((times[-1] - ages[0]) / span, 0., 1.)
        end = np.clip(start + elapsed / span, 0., 1.)
        atlas_step = np.sqrt(end) - np.sqrt(start)
    else:
        atlas_step = np.sqrt(min(elapsed / span, 1.)) * np.exp(-distance / span)
    fold *= np.exp(np.clip(age_strength * atlas_step * atlas_change, -.9, .9))
    weighted_mass = np.bincount(last.y, weights=weight, minlength=len(last.n))
    for zone in np.unique(last.core):
        keep = last.core == zone
        prior = normalize(last.freq[keep]) @ last.linear[keep]
        output_mix = normalize(weighted_mass[keep])
        if zone:
            # Bulk heart changes already include population abundance shifts.
            # Remove the estimated mixture component before applying the
            # measured molecular direction to this dissection's forecast mix.
            elapsed_in_atlas = np.clip((min(target_time, ages[1]) - max(times[-1], ages[0])) / span,0.,1.)
            atlas_mix = normalize(last.freq[keep] * np.exp(elapsed_in_atlas * atlas_mass[keep]))
            population_step = np.log((atlas_mix @ last.linear[keep] + 1.) / (prior + 1.))
            state_direction = bulk_step - .5 * np.clip(population_step,-.5,.5)
            forecast_prior = output_mix @ last.linear[keep]
            desired = normalize(forecast_prior * np.exp(state_direction)) * 1e4
        else:
            desired = normalize(prior * np.exp(.25*bulk_step)) * 1e4
        actual = output_mix @ (normalize(last.linear[keep] * fold[keep]) * 1e4)
        residual = np.log((desired + 1.) / (actual + 1.))
        fold[keep] *= np.exp(.65 * np.clip(residual, -1.6, 1.6))
    measured = []
    for s,mat,q,h in zip(stages[:-1],maps,w,dt):
        observed = np.log1p(last.linear)-np.log1p(mat @ s.linear)
        direction = np.clip(atlas_change,-1.5,1.5)
        relevant = np.sqrt(last.detect+.001)
        signal = (relevant*observed*direction).sum(1)
        scale = (relevant*direction**2).sum(1)
        measured.append(q*h*signal / np.maximum(scale,1.))
    advance = np.sum(measured,axis=0)
    prior = min(1.,np.dot(w,dt))
    differential = np.clip(advance-np.average(advance,weights=last.freq),-.45,.45)
    fold *= np.exp(differential[:,None]*np.clip(atlas_change,-1.4,1.4)*prior)
    src = systematic_sample(weight, context['max_cells'], rng)
    cell = last.y[src]
    counts = observed_counts(np.expm1(last.x[src].toarray()))
    budget = counts.sum(1, keepdims=True)
    slope, rank = niche_interaction(last)
    interaction = np.zeros_like(slope)
    for stage, match, local_weight, step in zip(stages[:-1], maps, w, dt):
        earlier, _ = niche_interaction(stage)
        same_role = (last.roles[:, None] == stage.roles[None, :])
        support = (match * same_role).sum(1, keepdims=True)
        interaction += local_weight * step * support * np.clip(slope - match @ earlier, -1., 1.)
    extra_development = spatial_residual(stages, maps, w, dt, src, context['seed'] + 912)
    phase_shape = maturational_quantiles(stages, maps, w, dt, src, fold)
    patch = projected_patch_motion(stages, maps, w, dt, src, context['seed'] + 371,
                                   inputs[-1].var_names, times[-1], target_time, age_strength)
    ratio = fold[cell] * np.exp(.85 * rank[src, None] * interaction[cell] + extra_development + phase_shape + patch)
    random = np.random.default_rng(context['seed'] + 56)
    retained = random.binomial(counts, np.minimum(ratio, 1.))
    local_rate = .4 * counts + .6 * (last.linear[cell] / 1e4) * budget
    extra = random.poisson(np.minimum(np.maximum(ratio-1., 0.) * local_rate, 1e4))
    mol = (retained + extra).astype(np.float32)
    empty = mol.sum(1) == 0
    mol[empty] = counts[empty]
    expr = np.log1p(1e4 * normalize(mol)).astype(np.float32)
    pos = last.pos[src].copy()
    repeated = np.ones(len(src), dtype=bool)
    repeated[np.unique(src, return_index=True)[1]] = False
    if repeated.any():
        spacing = cKDTree(last.pos).query(pos[repeated], k=min(8, len(last.pos)))[0][:, -1]
        pos[repeated] += .22 * spacing[:, None] * noise.normal(size=(repeated.sum(), 3))
    size_growth = growth(stages, w, dt, params.get('spatial_growth', 0.70))
    pos = (pos - pos.mean(axis=0)) * size_growth
    ev = np.maximum(size_growth-1., 0.)
    origin = pos.copy()
    smooth = np.zeros_like(pos)
    # Relative extents are inferred from complete fields. When predicting a
    # cropped chamber population, keep the local expansion tied to its wall.
    relative_growth = np.ones(len(last.n)) if chamber else lineage_expansion(stages, maps, w, dt)
    for j in range(len(last.names)):
        rows = last.y[src] == j
        if rows.sum() < 3:
            continue
        smooth[rows] = relative_growth[j] * (pos[rows] - pos[rows].mean(0))
    step = .65 * ev * smooth
    pos += step
    pos *= rms(origin) / rms(pos)
    projected_size = rms(pos)
    cell = last.y[src]
    epi = np.flatnonzero(last.roles[cell] == 'epicardium')
    muscle = last.roles[cell] == 'myocardium'
    if len(epi) > 10 and muscle.sum() > 30:
        neighbors = cKDTree(pos).query(pos,k=min(32,len(pos)))[1]
        contact = muscle[neighbors].mean(1)
        # Epicardium covers the abluminal surface. Locally mixed source sites near
        # the outer myocardium provide a scaffold for its descendants.
        radial = np.linalg.norm(pos - pos[muscle].mean(0),axis=1) / rms(pos)
        probability = contact * (1-contact) * np.clip(radial,.25,2.) * (~muscle)
        probability *= ~np.isin(last.roles[cell], ('endocardium','cushion'))
        if probability.sum() > 0:
            random = np.random.default_rng(context['seed']+412)
            fraction = -np.expm1(-np.dot(w,dt))
            rows = epi[random.random(len(epi)) < fraction]
            site = random.choice(len(pos),len(rows),p=normalize(probability))
            pos[rows] = .12 * pos[rows] + .88 * pos[site]
    pos *= projected_size / rms(pos)
    roles = last.roles[last.y[src]]
    inner_wall = roles == 'endocardium'
    muscle = roles == 'myocardium'
    if inner_wall.sum() >= 30 and muscle.sum() >= 50:
        near = cKDTree(pos).query(pos, k=min(32, len(pos)))[1]
        contact = inner_wall[near].mean(1) * muscle[near].mean(1)
        sites = np.flatnonzero((muscle | inner_wall) & (contact > 0.))
        surface_rng = np.random.default_rng(context['seed'] + 337)
        eligible = np.flatnonzero(inner_wall)
        fraction = -.5 * np.expm1(-np.dot(w, dt))
        moving = eligible[surface_rng.random(len(eligible)) < fraction]
        if len(sites) and len(moving):
            target = surface_rng.choice(sites, size=len(moving), p=normalize(contact[sites]))
            boundary = pos[inner_wall]
            donor = cKDTree(boundary).query(pos[target], k=1)[1]
            physical_size = rms(pos)
            pos[moving] = .65 * boundary[donor] + .35 * pos[target]
            pos *= physical_size / rms(pos)
    random = np.random.default_rng(context['seed']+248)
    base = region_weights(stages,w,dt,chamber)
    n_support = min(3500,len(pos))
    ref = last.pos[random.choice(len(last.y),n_support,p=normalize(base))]
    ref = (ref-ref.mean(0))*rms(pos)/rms(ref) + pos.mean(0)
    sample = pos[random.choice(len(pos),n_support,replace=False)]
    drift = sliced_displacement(sample,ref,pos,314)
    size = rms(pos)
    pos += .65*drift
    pos *= size/rms(pos)
    if chamber and last.mask.sum() >= 70:
        pos *= chamber_scale_guard(stages, np.asarray(times), target_time, w, size_growth)
    pos = serial_section_projection(pos, last.pos[src], last.roles[last.y[src]], context['seed'] + 624)
    return ad.AnnData(sparse.csr_matrix(expr), var=inputs[-1].var.copy(),
                      obsm={'spatial_3D': pos.astype(np.float32)})
