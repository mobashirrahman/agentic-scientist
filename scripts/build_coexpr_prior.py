"""Build a 100% wild-type signed gene-to-panel co-expression prior for T3 (off-panel knockouts).

Uses ONLY the already-vetted Qiu et al. 2024 Theiler 12-13 calibration cells (<= E9.0, wild type,
data/external/qiu2024/calibration_*.h5ad; zero forbidden stages, zero mutant data). Computes for every
whole-transcriptome gene (~53k mouse symbols, including off-panel knockouts like Ctnnb1) its Pearson
correlation with every 500-gene MERFISH panel gene:
  * corr_all    : global WT correlation across all 38,090 TS12-13 cells (lineage + intrinsic)
  * corr_within : within-cell-type centered WT correlation (cell-intrinsic co-regulation)

Output: data/external/coexpr_prior/coexpr_prior.npz + manifest.json (disclosed in docs/external_provenance.json).
"""
import hashlib
import json
import time
from pathlib import Path

import anndata as ad
import numpy as np
import scipy.sparse as sp

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'data/external/coexpr_prior'


def _corr_matrix(X, P):
    """Pearson correlation (n_genes x n_panel) between sparse X (n x G) and dense P (n x K)."""
    n = X.shape[0]
    P_c = P - P.mean(0, keepdims=True)
    P_sd = np.sqrt((P_c ** 2).mean(0, keepdims=True))
    valid_p = P_sd.ravel() > 1e-8
    P_z = np.zeros_like(P_c)
    P_z[:, valid_p] = P_c[:, valid_p] / P_sd[:, valid_p]

    mu = np.asarray(X.mean(0)).ravel().astype(np.float64)
    sq = np.asarray(X.multiply(X).mean(0)).ravel().astype(np.float64)
    sd = np.sqrt(np.maximum(sq - mu ** 2, 0.0))
    valid_g = sd > 1e-8
    cov = np.asarray(X.T @ P_z, dtype=np.float64) / float(n)
    corr = np.zeros_like(cov, dtype=np.float32)
    corr[valid_g] = np.clip(cov[valid_g] / sd[valid_g, None], -1.0, 1.0).astype(np.float32)
    return corr


def main():
    t0 = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    panel = list(ad.read_h5ad(ROOT / 'data/raw/T2/E8.75.h5ad', backed='r').var_names)
    files = sorted((ROOT / 'data/external/qiu2024').glob('calibration_*.h5ad'))
    parts, groups = [], []
    for f in files:
        a = ad.read_h5ad(f)
        a.obs_names_make_unique()
        parts.append(a)
        groups.append(np.full(a.n_obs, f.stem.replace('calibration_', ''), dtype=object))
    adata = ad.concat(parts, join='inner')
    adata.obs_names_make_unique()
    grp = np.concatenate(groups)
    X = sp.csr_matrix(adata.X, dtype=np.float32)
    if X.nnz and X.data.max() > 30:
        lib = np.asarray(X.sum(1)).ravel()
        X = sp.diags(1e4 / np.maximum(lib, 1.0)) @ X
        X.data = np.log1p(X.data)
    X = X.tocsr()

    genes = np.asarray(adata.var_names.tolist(), dtype='U')
    gidx = {g: i for i, g in enumerate(genes)}
    panel_names = np.asarray([g for g in panel if g in gidx], dtype='U')
    p_idx = np.array([gidx[g] for g in panel_names], dtype=np.int64)
    P = X[:, p_idx].toarray().astype(np.float64)

    corr_all = _corr_matrix(X, P)

    # Within-lineage centered correlation: subtract group means on both X and P
    # Done efficiently via group-sum adjustment without densifying X!
    n = X.shape[0]
    uniq = np.unique(grp)
    P_w = P.copy()
    g_means_X = {}
    g_counts = {}
    for u in uniq:
        m = grp == u
        cnt = int(m.sum())
        if cnt < 20:
            P_w[m] = 0.0
            continue
        P_w[m] -= P[m].mean(0, keepdims=True)
        g_counts[u] = cnt
        g_means_X[u] = np.asarray(X[m].mean(0)).ravel().astype(np.float64)
    P_wsd = np.sqrt((P_w ** 2).mean(0, keepdims=True))
    valid_pw = P_wsd.ravel() > 1e-8
    P_wz = np.zeros_like(P_w)
    P_wz[:, valid_pw] = P_w[:, valid_pw] / P_wsd[:, valid_pw]
    # Because P_wz has zero mean inside every group u, X_centered^T @ P_wz == X^T @ P_wz!
    # We only need within-group variance of X: E[(X - mu_g)^2] = E[X^2] - sum_u (n_u/n) * mu_u^2
    sq = np.asarray(X.multiply(X).mean(0)).ravel().astype(np.float64)
    between = np.zeros(X.shape[1], dtype=np.float64)
    for u, cnt in g_counts.items():
        between += (cnt / float(n)) * (g_means_X[u] ** 2)
    sd_w = np.sqrt(np.maximum(sq - between, 0.0))
    valid_gw = sd_w > 1e-8
    cov_w = np.asarray(X.T @ P_wz, dtype=np.float64) / float(n)
    corr_within = np.zeros_like(cov_w, dtype=np.float32)
    corr_within[valid_gw] = np.clip(cov_w[valid_gw] / sd_w[valid_gw, None], -1.0, 1.0).astype(np.float32)

    out_npz = OUT / 'coexpr_prior.npz'
    np.savez_compressed(
        out_npz,
        genes=genes,
        panel=panel_names,
        corr_all=corr_all.astype(np.float16),
        corr_within=corr_within.astype(np.float16),
    )
    sha = hashlib.sha256(out_npz.read_bytes()).hexdigest()
    man = dict(
        source='Qiu et al. 2024 (Nature 626:1084) Theiler 12-13 calibration cells only (data/external/qiu2024/calibration_*.h5ad)',
        stages=['Theiler stage 12', 'Theiler stage 13'],
        stages_days=[8.0, 8.5, 9.0],
        perturbation=False,
        cells=int(n),
        n_genes=int(len(genes)),
        n_panel=int(len(panel_names)),
        files={'coexpr_prior.npz': {'sha256': sha, 'cells': int(n)}},
    )
    (OUT / 'manifest.json').write_text(json.dumps(man, indent=2) + '\n')
    print(f'Wrote {out_npz} ({out_npz.stat().st_size / 1e6:.1f} MB) in {time.time() - t0:.1f}s; sha256={sha[:16]}')
    for ko in ('Ctnnb1', 'Gata4', 'Hand2', 'Mef2c', 'Mab21l2'):
        if ko in gidx:
            rw = corr_within[gidx[ko]]
            tp = [(panel_names[i], round(float(rw[i]), 3)) for i in np.argsort(rw)[-5:][::-1]]
            print(f'  within-lineage {ko:8s}: + {tp}')


if __name__ == '__main__':
    main()
