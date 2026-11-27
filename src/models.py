"""Conservative population interpolation with log-linear spatial scale."""
import anndata as ad
import numpy as np
from scipy import sparse
from .data import sample


def interpolate(left, right, fraction, n=3000, seed=42):
    """Mix measured cell states and match their spatial extents to an intermediate size.

    Preserves real expression covariance. Geometry is rescaled per endpoint, rather
    than overlaying two volumes at different developmental sizes.
    """
    if not 0 <= fraction <= 1:
        raise ValueError('Interpolation fraction must be in [0, 1]')
    genes = left.var_names[left.var_names.isin(right.var_names)]
    left, right = left[:, genes], right[:, genes]
    nl = round(n * (1 - fraction))
    pieces = []
    sizes = []
    centers = []
    for a in (left, right):
        p = np.asarray(a.obsm['spatial_3D'], dtype=float)
        lo, hi = np.quantile(p, [.01, .99], axis=0)
        sizes.append(np.maximum(hi - lo, 1e-6))
        centers.append(np.median(p, axis=0))
    size = np.exp((1 - fraction) * np.log(sizes[0]) + fraction * np.log(sizes[1]))
    for k, (a, count) in enumerate(zip((left, right), (nl, n - nl))):
        if count == 0:
            continue
        part = sample(a, count, seed + k)
        part.obsm['spatial_3D'] = ((part.obsm['spatial_3D'] - centers[k]) * size / sizes[k]).astype(np.float32)
        pieces.append(part)
    result = ad.concat(pieces, join='inner', merge='same')
    result.X = sparse.csr_matrix(result.X, dtype=np.float32)
    result.obs_names = [f'pred_{i}' for i in range(n)]
    result.uns['method'] = 'endpoint mixture; log-linear robust spatial extents'
    result.uns['fraction'] = fraction
    return result


class TemporalTransport:
    """Type-conditional growth and state drift with an empirical conditional decoder.

    Newly appearing labels are carried by real cells at the latest stage. Missing
    ancestor labels are matched by nearest expression centroid, never by a target
    label. State shifts preserve the sampled cell's residual and are bounded.
    """
    def __init__(self, earlier, latest, interval):
        from sklearn.metrics.pairwise import cosine_distances
        self.latest = latest
        self.interval = interval
        self.genes = latest.var_names
        earlier = earlier[:, self.genes]
        labels_a = np.asarray(earlier.obs['celltype_group'] if 'celltype_group' in earlier.obs else earlier.obs['celltype']).astype(str)
        labels_b = np.asarray(latest.obs['celltype_group'] if 'celltype_group' in latest.obs else latest.obs['celltype']).astype(str)
        self.labels = labels_b
        self.types = np.unique(labels_b)
        old_types = np.unique(labels_a)
        old_mean = np.vstack([np.asarray(earlier.X[labels_a == c].mean(0)).ravel() for c in old_types])
        new_mean = np.vstack([np.asarray(latest.X[labels_b == c].mean(0)).ravel() for c in self.types])
        # Match on variable genes to avoid constitutive genes dominating distance.
        feature = np.argsort(np.var(np.vstack([old_mean, new_mean]), axis=0))[-2000:]
        distance = cosine_distances(new_mean[:, feature], old_mean[:, feature])
        ancestors = np.argmin(distance, axis=1)
        for k, c in enumerate(self.types):
            if c in old_types:
                ancestors[k] = np.flatnonzero(old_types == c)[0]
        self.ancestors = dict(zip(self.types, old_types[ancestors]))
        self.drift = np.clip(new_mean - old_mean[ancestors], -.5, .5)
        old_p = np.array([max(np.mean(labels_a == c), .005) for c in self.types])
        new_p = np.array([np.mean(labels_b == c) for c in self.types])
        self.growth = np.clip(np.log(new_p / old_p), -np.log(2), np.log(2))
        self.type_index = {c: k for k, c in enumerate(self.types)}

    def predict(self, horizon, state=.1, composition=.25, n=3000, seed=42, geometry=0.):
        rng = np.random.default_rng(seed)
        factor = min(horizon / self.interval, 2.)
        row_type = np.array([self.type_index[c] for c in self.labels])
        weight = np.exp(composition * factor * self.growth[row_type])
        idx = rng.choice(self.latest.n_obs, n, replace=True, p=weight / weight.sum())
        out = self.latest[idx].copy()
        out.obs_names = [f'pred_{i}' for i in range(n)]
        x = out.X.toarray().astype(np.float32)
        x += state * factor * self.drift[row_type[idx]]
        np.maximum(x, 0, out=x)
        out.X = sparse.csr_matrix(x)
        if geometry and 'spatial_3D' in out.obsm:
            p = out.obsm['spatial_3D']
            out.obsm['spatial_3D'] = ((p - np.median(p, axis=0)) * np.exp(geometry * horizon)).astype(np.float32)
        out.uns['method'] = 'type-conditional growth and state transport; empirical residual decoder'
        out.uns['state_strength'] = state
        out.uns['composition_strength'] = composition
        return out


def spatial_growth(stages, times):
    """Median pairwise log-extent slope, downweighted toward no growth.

    Bounds growth for long extrapolation where dissection varies between stages.
    """
    from scipy.stats import theilslopes
    sizes = []
    for a in stages:
        lo, hi = np.quantile(a.obsm['spatial_3D'], [.01, .99], axis=0)
        sizes.append(np.maximum(hi - lo, 1e-6))
    slopes = [theilslopes(np.log(np.asarray(sizes)[:, d]), times)[0] for d in range(3)]
    return float(np.clip(np.median(slopes), 0, .25))


def ot_interpolate(left, right, fraction, n=3000, seed=42, support=800):
    """Entropic transport using expression PCs and normalized 3D positions.

    A finite-support fused feature/geometry cost registers endpoints. Draws cell
    pairs from the coupling and transports their full expression and coordinates.
    """
    from scipy.special import logsumexp
    from scipy.spatial.distance import cdist
    from sklearn.decomposition import TruncatedSVD
    left = sample(left, min(support, left.n_obs), seed)
    right = sample(right[:, left.var_names], min(support, right.n_obs), seed + 1)
    joined = sparse.vstack([left.X, right.X])
    basis = TruncatedSVD(n_components=20, random_state=0).fit_transform(joined)
    scale = np.maximum(np.std(basis, axis=0), .1)
    za, zb = np.split(basis / scale, [left.n_obs])
    positions, sizes = [], []
    for a in (left, right):
        p = a.obsm['spatial_3D']
        lo, hi = np.quantile(p, [.01, .99], axis=0)
        size = np.maximum(hi - lo, 1e-6)
        positions.append((p - np.median(p, axis=0)) / size)
        sizes.append(size)
    cost = cdist(za, zb, 'sqeuclidean') / 20 + 2 * cdist(*positions, 'sqeuclidean')
    logkernel = -cost / .15
    u, v = np.zeros(left.n_obs), np.zeros(right.n_obs)
    for _ in range(150):
        u = -np.log(left.n_obs) - logsumexp(logkernel + v[None, :], axis=1)
        v = -np.log(right.n_obs) - logsumexp(logkernel + u[:, None], axis=0)
    coupling = np.exp(logkernel + u[:, None] + v[None, :])
    rng = np.random.default_rng(seed)
    pairs = rng.choice(coupling.size, n, p=coupling.ravel() / coupling.sum())
    ia, ib = np.unravel_index(pairs, coupling.shape)
    out = left[ia].copy()
    out.X = sparse.csr_matrix((1 - fraction) * left.X[ia] + fraction * right.X[ib], dtype=np.float32)
    size = np.exp((1 - fraction) * np.log(sizes[0]) + fraction * np.log(sizes[1]))
    out.obsm['spatial_3D'] = (((1 - fraction) * positions[0][ia] + fraction * positions[1][ib]) * size).astype(np.float32)
    out.obs_names = [f'pred_{i}' for i in range(n)]
    out.uns['method'] = 'entropic expression/spatial transport interpolation'
    return out


MESODERM = {'V-CM', 'vCM', 'A-CM', 'OFT/RV-CM', 'OFT-CM', 'IFT-CM', 'SV-CM',
            'aPHM', 'pPHM', 'SHF', 'aSHF', 'pSHF', 'JCF', 'Peri', 'Pericardium',
            'Endo', 'Endocardium', 'Intra-Endoth-1', 'Intra-Endoth-2', 'HEM-Endoth',
            'Chamber-Endo', 'Cush-EndoMT-Endo', 'Proepi', 'Proepicardium',
            'FHF', 'LPM', 'PAM-1', 'PAM-2', 'PAM-3', 'PAM-4', 'SOM', 'Allantois',
            'ExEM-1', 'ExEM-2'}
SHF = {'SHF', 'aSHF', 'pSHF', 'aPHM', 'pPHM', 'OFT-CM', 'OFT/RV-CM'}


def lineage_perturbation(wt, strength=.25, depletion=.2, target='bcatenin', n=3000, seed=42):
    """Lineage-restricted sign prior; no response transferred from Mab21l2.

    Nonmesoderm expression and coordinates remain identical to sampled WT rows.
    No Ctnnb1 knockout value is fabricated: it is absent from the panel.
    """
    rng = np.random.default_rng(seed)
    labels = np.asarray(wt.obs['celltype']).astype(str)
    weight = np.ones(wt.n_obs)
    weight[np.isin(labels, list(SHF))] = max(1 - depletion, .05)
    idx = rng.choice(wt.n_obs, n, replace=True, p=weight / weight.sum())
    out = wt[idx].copy()
    out.obs['source_row'] = idx
    out.obs_names = [f'pred_{i}' for i in range(n)]
    affected = np.isin(labels[idx], list(MESODERM))
    if target == 'bcatenin':
        # High/medium-confidence signs in PLAN 3.2 and literature review 6.
        genes = {'Isl1': -1., 'Bmp4': -.7, 'Fgf8': -.4,
                 'Tbx2': -.3, 'Tbx3': -.3, 'Pitx2': -.3}
    elif target == 'gata4':
        genes = {'Gata4': -1., 'Gata6': -.5, 'Mef2c': -.5, 'Hand2': -.5,
                 'Tnnt2': -.5, 'Myh7': -.5, 'Actc1': -.5, 'Nppa': -.5}
    else:
        raise ValueError(target)
    x = out.X.toarray().astype(np.float32)
    for gene, change in genes.items():
        if gene in out.var_names:
            j = out.var_names.get_loc(gene)
            x[affected, j] *= np.exp(strength * change)
    out.X = sparse.csr_matrix(x)
    out.uns['method'] = 'Mesp1-lineage composition and shrunk signed expression prior'
    out.uns['strength'] = strength
    out.uns['depletion'] = depletion
    out.uns['perturbation'] = target
    return out
