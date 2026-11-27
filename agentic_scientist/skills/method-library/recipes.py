"""AgenticScientist method library: tested building blocks for predict() programs.

Copy this file into your workspace (cp <ROOT>/agentic_scientist/skills/method-library/recipes.py .) and
`from recipes import ...`. Everything is numpy/scipy/sklearn only, deterministic given `seed`, and passes the
evaluator's static screen (no file, network or process access).
"""
import numpy as np
from scipy import sparse


# ---------- basics ----------
def dense(X):
    """Dense float32 copy of an AnnData .X (sparse or dense)."""
    return (X.toarray() if sparse.issparse(X) else np.asarray(X)).astype(np.float32)


def pca_space(arrays, n_comp=30, n_genes=2000, seed=0):
    """Fit PCA on top-variance genes of the stacked arrays. Returns (transform_fn, gene_idx)."""
    from sklearn.decomposition import PCA
    S = np.vstack(arrays)
    idx = np.argsort(-S.var(0))[:min(n_genes, S.shape[1])]
    p = PCA(n_comp, random_state=seed).fit(S[:, idx])
    return (lambda X: p.transform(X[:, idx])), idx


def knn_transfer(Z_ref, labels_ref, Z_query, k=15):
    """Label query cells by majority vote of their k nearest reference cells."""
    from sklearn.neighbors import KNeighborsClassifier
    return KNeighborsClassifier(k).fit(Z_ref, labels_ref).predict(Z_query)


# ---------- composition ----------
def extrapolate_fractions(frac_list, times, target_time, shrink=0.5, floor=1e-4):
    """Per-type fractions at target_time by log-linear trend over the input stages, shrunk toward the last stage.

    frac_list: list of dicts {type: fraction} (oldest first). shrink in [0, 1]: 0 = pure trend, 1 = copy last.
    """
    types = sorted(set().union(*frac_list))
    L = np.array([[np.log(max(f.get(t, 0), floor)) for t in types] for f in frac_list])
    t = np.asarray(times, float)
    if len(t) >= 2:
        A = np.vstack([t, np.ones_like(t)]).T
        coef, *_ = np.linalg.lstsq(A, L, rcond=None)
        pred = coef[0] * target_time + coef[1]
    else:
        pred = L[-1]
    pred = shrink * L[-1] + (1 - shrink) * pred
    w = np.exp(pred)
    return dict(zip(types, w / w.sum()))


def resample_to_fractions(labels, target_frac, n, seed=0):
    """Indices of n cells drawn from `labels` so type fractions match target_frac (types absent in labels skipped).
    Uses each type's cells before repeating any (keeps diversity)."""
    rng = np.random.default_rng(seed)
    labels = np.asarray(labels)
    types = [t for t in target_frac if (labels == t).any()]
    w = np.array([target_frac[t] for t in types])
    counts = rng.multinomial(n, w / w.sum())
    out = []
    for t, c in zip(types, counts):
        pool = np.flatnonzero(labels == t)
        reps = int(np.ceil(c / len(pool)))
        draw = np.concatenate([rng.permutation(pool) for _ in range(max(reps, 1))])[:c]
        out.append(draw)
    return rng.permutation(np.concatenate(out)) if out else np.array([], int)


# ---------- optimal transport (entropic, unbalanced; numpy) ----------
def sinkhorn_unbalanced(a, b, C, eps=0.05, tau=1.0, iters=500):
    """Unbalanced entropic OT plan between histograms a (n) and b (m) with cost C (n x m).
    tau = marginal relaxation (larger = closer to balanced). Cost is rescaled by its median."""
    C = C / max(np.median(C), 1e-12)
    K = np.exp(-C / eps)
    u, v = np.ones_like(a), np.ones_like(b)
    f = tau / (tau + eps)
    for _ in range(iters):
        u = (a / np.maximum(K @ v, 1e-300)) ** f
        v = (b / np.maximum(K.T @ u, 1e-300)) ** f
    return u[:, None] * K * v[None, :]


def ot_drift(Z_early, Z_late, eps=0.05, tau=1.0, max_cells=1500, seed=0):
    """Per-cell displacement of late cells implied by OT from early to late in a latent space.
    Returns (late_idx, displacement) where displacement[i] = barycentric step that brought late cell i from early."""
    rng = np.random.default_rng(seed)
    ie = rng.choice(len(Z_early), min(max_cells, len(Z_early)), replace=False)
    il = rng.choice(len(Z_late), min(max_cells, len(Z_late)), replace=False)
    from scipy.spatial.distance import cdist
    P = sinkhorn_unbalanced(np.full(len(ie), 1 / len(ie)), np.full(len(il), 1 / len(il)),
                            cdist(Z_early[ie], Z_late[il], 'sqeuclidean'), eps, tau)
    col = P.sum(0)
    bary = (P.T @ Z_early[ie]) / np.maximum(col[:, None], 1e-12)
    return il, Z_late[il] - bary


# ---------- response calibration (T3 severity / DE) ----------
def apply_pseudobulk_shift(X, shift, rng=None, per_cell_noise=0.0):
    """Add a gene-wise shift (log space) to cells, clip at 0. Keeps zeros zero where shift <= 0 to preserve sparsity."""
    Y = X + shift[None, :]
    Y[(X == 0) & (shift[None, :] <= 0)] = 0
    if per_cell_noise and rng is not None:
        Y += rng.normal(0, per_cell_noise, Y.shape) * (Y > 0)
    return np.clip(Y, 0, None)


def rescale_response(X_pred, X_ref, factor):
    """Scale a prediction's pseudobulk response (vs reference) by `factor` while keeping cell-level structure:
    shift each gene by (factor - 1) * Δmean. Use it to put severity's slope β near 1 once the direction is right."""
    d = X_pred.mean(0) - X_ref.mean(0)
    return apply_pseudobulk_shift(X_pred, (factor - 1) * d)


# ---------- spatial ----------
def rms(C):
    Cc = C - C.mean(0)
    return float(np.sqrt((Cc ** 2).sum(1).mean()))


def rescale_coords(C, factor):
    """Scale coordinates about their centroid (scale_log_ratio = log factor relative to the unscaled cloud)."""
    m = C.mean(0)
    return (C - m) * factor + m


def growth_factor(radii, times, target_time, shrink=0.3):
    """Extrapolated rms-radius ratio target/last from the log-radius trend over input stages, shrunk toward 1."""
    t, r = np.asarray(times, float), np.log(np.asarray(radii, float))
    slope = np.polyfit(t, r, 1)[0] if len(t) >= 2 else 0.0
    return float(np.exp((1 - shrink) * slope * (target_time - t[-1])))


def procrustes_align(A, B):
    """Rigid (rotation + translation, det=+1) alignment of point cloud A onto B using matched rows."""
    ma, mb = A.mean(0), B.mean(0)
    U, _, Vt = np.linalg.svd((A - ma).T @ (B - mb))
    D = np.eye(A.shape[1])
    D[-1, -1] = np.sign(np.linalg.det(U @ Vt))
    R = U @ D @ Vt
    return (A - ma) @ R + mb


def neighbourhood_profiles(C, labels, types, k=15):
    """Fraction of each type among each cell's k spatial neighbours (n x len(types))."""
    from sklearn.neighbors import NearestNeighbors
    idx = NearestNeighbors(n_neighbors=k + 1).fit(C).kneighbors(C, return_distance=False)[:, 1:]
    ti = {t: i for i, t in enumerate(types)}
    M = np.zeros((len(C), len(types)))
    lab = np.asarray(labels)
    for j in range(k):
        cols = np.array([ti.get(x, -1) for x in lab[idx[:, j]]])
        ok = cols >= 0
        M[np.flatnonzero(ok), cols[ok]] += 1.0 / k
    return M


def patch_resample(C, n, patch=30, seed=0):
    """Draw whole spatial patches (a seed cell + its nearest neighbours) instead of single cells, so the
    prediction keeps real local tissue organisation (helps neighborhood_mmd and its T2 gate)."""
    from sklearn.neighbors import NearestNeighbors
    rng = np.random.default_rng(seed)
    nn = NearestNeighbors(n_neighbors=min(patch, len(C))).fit(C)
    out = []
    while sum(len(o) for o in out) < n:
        s = rng.integers(len(C))
        out.append(nn.kneighbors(C[s:s + 1], return_distance=False)[0])
    return np.concatenate(out)[:n]
