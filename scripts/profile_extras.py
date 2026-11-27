"""Last checks for the data report.

  1. T3 raw.X relation to X and counts; T3 uns['name'].
  2. Matched-WT check: pseudobulk Pearson of KO vs WT (T2/E9.5) on the 500-gene panel,
     compared with the 0.956 figure the task page quotes for 'matched WT unchanged'.
  3. T1: fraction of E9.5 cells whose label also occurs at E8.5 (doc: about two thirds new).
  4. Robust spatial extents (p1 to p99) and per-z-level cell counts for every 3D file.

Run with: .venv/bin/python -I -W ignore scripts/profile_extras.py
"""
import os

import anndata as ad
import numpy as np
import pandas as pd
import scipy.sparse as sp

RAW = "/scratch/user/virtual-embryo/data/raw"


def hdr(t):
    print("\n" + "=" * 100)
    print(t)
    print("=" * 100)


def csr(M):
    return M.tocsr() if sp.issparse(M) else sp.csr_matrix(np.asarray(M))


def part1_t3_raw():
    hdr("1. T3 raw.X and uns")
    a = ad.read_h5ad(os.path.join(RAW, "T3", "E9.5_mab21l2_ko.h5ad"))
    R = np.asarray(a.raw.X, dtype=np.float64)
    X = np.asarray(a.X, dtype=np.float64)
    C = np.asarray(a.layers["counts"], dtype=np.float64)
    print(f"  raw.X == X (max abs diff) = {np.abs(R - X).max():.3g}; "
          f"fraction equal = {np.mean(np.isclose(R, X, atol=1e-5)):.4f}")
    print(f"  raw.X == counts (max abs diff) = {np.abs(R - C).max():.3g}")
    print(f"  raw.X integer={bool(np.all(R == np.floor(R)))}, raw nnz={int((R > 0).sum()):,}")
    print(f"  uns['name'] = {a.uns.get('name')!r}")
    print(f"  uns['log1p'] = {a.uns.get('log1p')!r}")
    del a


def part2_matched_wt():
    hdr("2. Pseudobulk absolute correlation KO vs matched WT")
    ko = ad.read_h5ad(os.path.join(RAW, "T3", "E9.5_mab21l2_ko.h5ad"))
    wt9 = ad.read_h5ad(os.path.join(RAW, "T2", "E9.5.h5ad"))
    wt875 = ad.read_h5ad(os.path.join(RAW, "T2", "E8.75.h5ad"))
    assert list(ko.var_names) == list(wt9.var_names)
    def pb(a, layer=None):
        M = a.X if layer is None else a.layers[layer]
        M = csr(M)
        return np.asarray(M.mean(axis=0)).ravel()
    pko = pb(ko)
    pko_c = pb(ko, "counts")
    for name, a in [("WT E9.5 (T2)", wt9), ("WT E8.75 (T2)", wt875)]:
        pw = pb(a)
        pwc = pb(a, "counts")
        r_log = np.corrcoef(pko, pw)[0, 1]
        r_cnt = np.corrcoef(pko_c, pwc)[0, 1]
        # pseudobulk on size-normalised counts (CP10k)
        ko_cp = csr(ko.layers["counts"]).astype(float)
        ko_cp = sp.diags(1e4 / np.asarray(ko_cp.sum(1)).ravel()) @ ko_cp
        wt_cp = csr(a.layers["counts"]).astype(float)
        wt_cp = sp.diags(1e4 / np.asarray(wt_cp.sum(1)).ravel()) @ wt_cp
        r_cp = np.corrcoef(np.asarray(ko_cp.mean(0)).ravel(), np.asarray(wt_cp.mean(0)).ravel())[0, 1]
        print(f"  KO vs {name}: Pearson(log-X means)={r_log:.4f}; Pearson(count means)={r_cnt:.4f}; "
              f"Pearson(CP10k means)={r_cp:.4f}")
    print("  (the task page quotes 0.956 for absolute pseudobulk correlation of matched WT)")
    for a in [ko, wt9, wt875]:
        del a


def part3_t1_overlap():
    hdr("3. T1 label overlap: fraction of E9.5 cells with a label that also occurs at E8.5")
    e85 = ad.read_h5ad(os.path.join(RAW, "T1", "E8.5_RNA.h5ad"), backed="r")
    e95 = ad.read_h5ad(os.path.join(RAW, "T1", "E9.5_RNA.h5ad"), backed="r")
    l85 = set(e85.obs["celltype"].astype(str).unique())
    l95 = e95.obs["celltype"].astype(str)
    shared = l95.isin(l85)
    print(f"  shared label names: {len(l85 & set(l95.unique()))}")
    print(f"  E9.5 cells with a label also present at E8.5: {shared.mean() * 100:.1f}%; "
          f"cells with a label new at E9.5: {(~shared).mean() * 100:.1f}%")
    l85c = e85.obs["celltype"].astype(str)
    print(f"  E8.5 cells with a label also present at E9.5: {l85c.isin(set(l95.unique())).mean() * 100:.1f}%")
    e85.file.close()
    e95.file.close()


def part4_spatial():
    hdr("4. Robust spatial extents and per-z-level counts (spatial_3D)")
    files = ["T2/E6.75.h5ad", "T2/E7.25.h5ad", "T2/E8.0.h5ad", "T2/E8.25_late.h5ad", "T2/E8.75.h5ad",
             "T2/E9.5.h5ad", "T3/E9.5_mab21l2_ko.h5ad"]
    for f in files:
        a = ad.read_h5ad(os.path.join(RAW, f), backed="r")
        P = np.asarray(a.obsm["spatial_3D"], dtype=float)
        a.file.close()
        rng = [np.quantile(P[:, i], 0.99) - np.quantile(P[:, i], 0.01) for i in range(3)]
        zs = np.round(P[:, 2], 3)
        zu, zc = np.unique(zs, return_counts=True)
        print(f"  {f}: n={P.shape[0]}, p1-p99 extent x={rng[0]:.0f} y={rng[1]:.0f} z={rng[2]:.0f}; "
              f"full extent x={np.ptp(P[:, 0]):.0f} y={np.ptp(P[:, 1]):.0f} z={np.ptp(P[:, 2]):.0f}; "
              f"z-levels={zu.size}; cells/z-level median={int(np.median(zc))}; "
              f"mean={P.mean(0).round(1).tolist()}")


if __name__ == "__main__":
    part1_t3_raw()
    part2_matched_wt()
    part3_t1_overlap()
    part4_spatial()
