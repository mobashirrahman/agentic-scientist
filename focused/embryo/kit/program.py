"""Starting program: an empirical endpoint mixture placed on one native embryo scaffold.

Expression: real cells drawn from the two bracketing stages in proportion to the interpolation fraction. Geometry:
every output cell keeps one input embryo's own coordinate cloud (the nearer bracket, scaled isotropically to the
log-linearly interpolated RMS radius). Cells drawn from the other bracket take the position of one of their nearest
scaffold cells in a shared expression embedding, so the output remains a single coherent anatomy.

Contract: predict(inputs, times, target_time, context) -> AnnData. See TASK.md.
"""
import anndata as ad
import numpy as np
from scipy import sparse
from sklearn.decomposition import TruncatedSVD
from sklearn.neighbors import NearestNeighbors

K_NEIGHBOURS = 10
N_COMPONENTS = 30


def _dense(x):
    return x.toarray() if sparse.issparse(x) else np.asarray(x)


def _rms(a):
    p = np.asarray(a.obsm['spatial_3D'], dtype=float)
    center = p.mean(axis=0)
    return float(np.sqrt(((p - center) ** 2).sum(axis=1).mean())), center


def _embed(scaffold, other, seed):
    """Shared low-rank expression space; each bracket centred to remove stage-wide offsets."""
    xs, xo = _dense(scaffold.X), _dense(other.X)
    xs, xo = xs - xs.mean(0), xo - xo.mean(0)
    svd = TruncatedSVD(n_components=min(N_COMPONENTS, xs.shape[1] - 1), random_state=seed)
    svd.fit(np.vstack([xs, xo]))
    return svd.transform(xs), svd.transform(xo)


def predict(inputs, times, target_time, context):
    left, right = inputs[0], inputs[-1]
    fraction = (target_time - times[0]) / (times[-1] - times[0])
    if not 0 <= fraction <= 1:
        raise ValueError('Interpolation fraction must be in [0, 1]')
    genes = left.var_names[left.var_names.isin(right.var_names)]
    brackets = (left[:, genes], right[:, genes])
    n, seed = min(int(context.get('n', 3000)), int(context['max_cells'])), context['seed']

    counts = (round(n * (1 - fraction)), n - round(n * (1 - fraction)))
    radii, centers = zip(*(_rms(a) for a in brackets))
    radius = np.exp((1 - fraction) * np.log(radii[0]) + fraction * np.log(radii[1]))
    k_scaffold = 0 if fraction <= 0.5 else 1
    scaffold = brackets[k_scaffold]
    scaffold_xyz = ((np.asarray(scaffold.obsm['spatial_3D'], dtype=float) - centers[k_scaffold])
                    * radius / max(radii[k_scaffold], 1e-12))

    rng = np.random.default_rng(seed + 7)
    pieces = []
    for k, (a, count) in enumerate(zip(brackets, counts)):
        if count == 0:
            continue
        idx = np.random.default_rng(seed + k).choice(a.n_obs, count, replace=a.n_obs < count)
        part = a[idx].copy()
        if k == k_scaffold:
            xyz = scaffold_xyz[idx]
        else:
            es, eo = _embed(scaffold, part, seed)
            nbr = NearestNeighbors(n_neighbors=min(K_NEIGHBOURS, scaffold.n_obs)).fit(es).kneighbors(eo)[1]
            xyz = scaffold_xyz[nbr[np.arange(len(nbr)), rng.integers(0, nbr.shape[1], len(nbr))]]
        part.obsm['spatial_3D'] = xyz.astype(np.float32)
        pieces.append(part)

    result = ad.concat(pieces, join='inner', merge='same')
    result.X = sparse.csr_matrix(result.X, dtype=np.float32)
    result.obs_names = [f'pred_{i}' for i in range(result.n_obs)]
    result.uns['method'] = 'empirical endpoint mixture on one native scaffold, isotropic log-linear RMS radius'
    result.uns['fraction'] = fraction
    result.uns['scaffold_bracket'] = int(k_scaffold)
    return result
