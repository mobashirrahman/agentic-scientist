"""T1 lineage transport (human track, built from scratch, 2026-11-19).

Idea decoded from the leaderboard name P3LT_T1_E12p5_CT3_N0f_k150w100_pt_lhs (hints only, no published method):
  1. joint PCA embedding of all input stages (HVGs);
  2. pseudotime: a ridge map from embedding to embryonic day, fitted on the input stages;
  3. lineage transport: each last-stage cell gets a velocity = its position minus the centroid of its kNN
     predecessors in the previous stage, smoothed over its k nearest last-stage neighbours (k~150);
  4. lineage mass: last-stage clusters grow by the ratio of their mass to the mass mapped onto them from the
     previous stage, extrapolated over the horizon (unbalanced transport);
  5. output cells are REAL last-stage donors, picked near each cell's extrapolated position (keeps cell realism),
     optionally with a bounded cluster-level expression shift on expressed entries;
  6. sampling='heart_chambers' (E12.5 test protocol): non-cardiac tissue is dropped.
All knobs are in KNOBS; tune with tune_t1.py (Latin hypercube on the dev splits).
"""
import numpy as np
import anndata as ad
from scipy import sparse
from sklearn.cluster import MiniBatchKMeans
from sklearn.decomposition import PCA
from sklearn.linear_model import Ridge
from sklearn.neighbors import NearestNeighbors

KNOBS = dict(n_hvg=3000, n_pc=40, k_pred=30, k_smooth=150, alpha=0.6, growth=0.5, growth_clip=3.0,
             n_clusters=40, donor_k=50, donor_temp=1.0, expr_shift=0.0, pt_weight=0.0, uncertain_w=0.3,
             max_cells=5118)

CARDIAC = {"Endothelium", "OFT/RV-CM", "IFT-CM", "AVC-CM", "RV-CM", "LV-CM", "SV-CM", "V-CM", "OFT-CM",
           "Endocardium", "Endocardium-1", "Endocardium-2", "EndoMT Endocardium", "Early VIC", "Epicardium",
           "NCC-derived", "Blood", "Macrophage"}
UNCERTAIN = {"Proepicardium", "pSHF", "aSHF", "JCF", "Pericardium", "NCC", "BEC"}


def _hvg(mats, n):
    x = sparse.vstack(mats).tocsr()
    mu = np.asarray(x.mean(0)).ravel()
    var = np.asarray(x.multiply(x).mean(0)).ravel() - mu ** 2
    disp = np.where(mu > 1e-3, var / (mu + 1e-6), 0)
    # rank dispersion within mean bins (Seurat-like) to avoid picking only high-mean genes
    bins = np.digitize(np.log1p(mu), np.quantile(np.log1p(mu[mu > 1e-3]), np.linspace(0, 1, 21)[1:-1]))
    z = np.zeros_like(disp)
    for b in np.unique(bins):
        m = (bins == b) & (mu > 1e-3)
        if m.sum() > 2:
            z[m] = (disp[m] - disp[m].mean()) / (disp[m].std() + 1e-9)
    return np.argsort(-z)[:n]


def _embed(inputs, kn, rng):
    sub = []
    for a in inputs:
        idx = rng.choice(a.n_obs, min(a.n_obs, 6000), replace=False)
        sub.append(sparse.csr_matrix(a.X[idx]))
    genes = _hvg(sub, kn['n_hvg'])
    dense = [np.asarray(sparse.csr_matrix(a.X)[:, genes].todense(), dtype=np.float32) for a in inputs]
    allx = np.vstack(dense)
    mu, sd = allx.mean(0), allx.std(0) + 1e-3
    pca = PCA(kn['n_pc'], random_state=0, svd_solver='randomized').fit((np.vstack([d[rng.choice(len(d), min(len(d), 6000), replace=False)] for d in dense]) - mu) / sd)
    return [pca.transform((d - mu) / sd) for d in dense]


def predict_temporal(inputs, times, target_time, context):
    kn = dict(KNOBS, **(context.get('params') or {}))
    rng = np.random.default_rng(context.get('fit_seed', 0))
    emb = _embed(inputs, kn, rng)
    L, P = inputs[-1], inputs[-2]
    xl, xp = emb[-1], emb[-2]
    d = float(times[-1] - times[-2])
    h = float(target_time - times[-1])

    # pseudotime direction (optional): ridge from embedding to day, its gradient adds a global maturation drift
    pt_dir = np.zeros(xl.shape[1])
    if kn['pt_weight'] > 0:
        r = Ridge(alpha=10.0).fit(np.vstack(emb), np.concatenate([np.full(len(e), t) for e, t in zip(emb, times)]))
        pt_dir = r.coef_ / (np.linalg.norm(r.coef_) ** 2 + 1e-9)  # displacement per day along the time axis

    # lineage transport: velocity from kNN predecessors, smoothed over last-stage neighbours
    kp = int(kn['k_pred'])
    _, ip = NearestNeighbors(n_neighbors=kp).fit(xp).kneighbors(xl)
    v = (xl - xp[ip].mean(1)) / d
    ks = int(min(kn['k_smooth'], len(xl) - 1))
    nn_l = NearestNeighbors(n_neighbors=ks).fit(xl)
    _, il = nn_l.kneighbors(xl)
    v = v[il].mean(1)
    v = v + kn['pt_weight'] * pt_dir
    y = xl + kn['alpha'] * h * v

    # lineage mass: forward-map previous stage onto last-stage clusters
    km = MiniBatchKMeans(int(kn['n_clusters']), random_state=0, n_init=3).fit(xl)
    cl = km.labels_
    C = km.n_clusters
    fl = np.bincount(cl, minlength=C) / len(cl)
    _, fwd = NearestNeighbors(n_neighbors=1).fit(xl).kneighbors(xp)
    fp = np.bincount(cl[fwd[:, 0]], minlength=C) / len(xp)
    g = np.clip((fl + 1e-3) / (fp + 1e-3), 1 / kn['growth_clip'], kn['growth_clip'])
    w_cl = fl * g ** (kn['growth'] * h / d)
    w = (w_cl / np.maximum(fl, 1e-9))[cl]

    # protocol: heart-chambers sampling drops non-cardiac tissue
    if context.get('sampling') == 'heart_chambers' and 'celltype' in L.obs:
        lab = L.obs['celltype'].astype(str).values
        w = w * np.array([1.0 if t in CARDIAC else kn['uncertain_w'] if t in UNCERTAIN else 0.0 for t in lab])
    w = w / w.sum()

    n = int(min(kn['max_cells'], 5118))
    prng = np.random.default_rng(context.get('seed', 0))
    src = prng.choice(len(xl), n, replace=True, p=w)

    # donors near each extrapolated position (real cells)
    dk = int(min(kn['donor_k'], len(xl)))
    dist, cand = nn_l.kneighbors(y[src], n_neighbors=dk)
    scale = np.median(dist[:, 1:2]) + 1e-9
    logit = -(dist / scale) ** 2 / max(kn['donor_temp'], 1e-6)
    pr = np.exp(logit - logit.max(1, keepdims=True))
    pr /= pr.sum(1, keepdims=True)
    pick = cand[np.arange(n), (pr.cumsum(1) > prng.random((n, 1))).argmax(1)]

    X = sparse.csr_matrix(L.X, dtype=np.float32)[pick].copy()
    if kn['expr_shift'] > 0:
        # cluster-level log-expression delta over one interval (cluster mean minus its predecessors' mean)
        XL = sparse.csr_matrix(L.X, dtype=np.float32)
        XP = sparse.csr_matrix(P.X, dtype=np.float32)
        oh_l = sparse.csr_matrix((np.ones(len(cl)), (cl, np.arange(len(cl)))), shape=(C, len(cl)))
        pc = cl[il[:, 0]]  # placeholder for shape; predecessors per cluster below
        rows, cols = [], []
        for c in range(C):
            mem = np.flatnonzero(cl == c)
            pr_c = np.unique(ip[mem].ravel())
            rows.append(np.asarray(XL[mem].mean(0)).ravel() - np.asarray(XP[pr_c].mean(0)).ravel())
        delta = np.vstack(rows) * (kn['expr_shift'] * h / d)
        Xc = X.tocoo()
        Xc.data = np.maximum(Xc.data + delta[cl[pick][Xc.row], Xc.col], 0).astype(np.float32)
        X = Xc.tocsr()
        X.eliminate_zeros()
        del oh_l, pc
    out = ad.AnnData(X, var=L.var.copy())
    out.obs['celltype'] = L.obs['celltype'].astype(str).values[pick] if 'celltype' in L.obs else 'NA'
    out.obs_names = [f'c{i}' for i in range(n)]
    return out
