"""Resolve open questions from profile_followup.py.

  A. T1: explicit zeros in X, and integer recovery using strictly positive minima.
  B. T2: what raw.X is (relation to X and to counts), per stage.
  C. T2: duplicated expression profiles, and whether duplicates share spatial coordinates.
  D. T3: which of the candidate formulas the 'log1p' layer follows.
  E. T3: sample_id -> section / z mapping, and where the duplicated records sit.

Run with: .venv/bin/python -I -W ignore scripts/profile_resolve.py
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


def part_a_t1():
    hdr("A. T1: explicit zeros and integer recovery")
    for f in ["E8.5_RNA.h5ad", "E9.5_RNA.h5ad"]:
        a = ad.read_h5ad(os.path.join(RAW, "T1", f))
        X = csr(a.X).astype(np.float64)
        n_explicit = int(np.sum(X.data == 0))
        print(f"  {f}: stored entries={X.nnz:,}; explicit zeros stored={n_explicit:,}")
        E = X.copy()
        E.data = np.expm1(E.data)
        n = E.shape[0]
        rows = np.repeat(np.arange(n), np.diff(E.indptr))
        pos = E.data > 0
        mins = np.full(n, np.inf)
        np.minimum.at(mins, rows[pos], E.data[pos])
        total = 1e4 / mins
        ratio = E.data[pos] * (total[rows[pos]] / 1e4)
        dev = np.abs(ratio - np.round(ratio))
        print(f"     implied library size (1e4 / min positive expm1): median={np.median(total):.0f}, "
              f"p5={np.quantile(total, .05):.0f}, p95={np.quantile(total, .95):.0f}")
        print(f"     fraction of positive entries within 0.05 of an integer count: {np.mean(dev < 0.05):.4f}")
        print(f"     median abs deviation from integer: {np.median(dev):.2e}")
        counts_rounded = np.round(ratio)
        implied_umi = np.bincount(rows[pos], weights=counts_rounded, minlength=n)
        print(f"     implied UMI total per cell: median={np.median(implied_umi):.0f}, "
              f"min={implied_umi.min():.0f}, max={implied_umi.max():.0f}")
        del a


def part_b_t2_raw():
    hdr("B. T2 raw.X vs X vs counts")
    for f in ["E6.75.h5ad", "E7.25.h5ad", "E8.0.h5ad", "E8.25_late.h5ad", "E8.75.h5ad", "E9.5.h5ad"]:
        a = ad.read_h5ad(os.path.join(RAW, "T2", f))
        R = np.asarray(a.raw.X, dtype=np.float64)
        X = csr(a.X).toarray().astype(np.float64)
        C = csr(a.layers["counts"]).toarray().astype(np.float64)
        print(f"  {f}: raw integer={bool(np.all(R == np.floor(R)))}; "
              f"max|raw - X|={np.abs(R - X).max():.3g}; "
              f"fraction entries raw==X: {np.mean(np.isclose(R, X, atol=1e-5)):.4f}; "
              f"max|raw - counts|={np.abs(R - C).max():.3g}; "
              f"fraction entries raw==counts: {np.mean(np.isclose(R, C, atol=1e-5)):.4f}")
        # where do raw and counts disagree? raw-zero but counts-positive?
        only_c = np.sum((R == 0) & (C > 0))
        only_r = np.sum((R > 0) & (C == 0))
        diff_nz = np.sum((R > 0) & (C > 0) & ~np.isclose(R, C, atol=1e-5))
        print(f"     counts>0 but raw==0: {only_c:,}; raw>0 but counts==0: {only_r:,}; "
              f"both>0 but different values: {diff_nz:,}")
        both = (R > 0) & (C > 0)
        if both.any():
            ratio = C[both] / R[both]
            print(f"     where both>0: counts/raw ratio median={np.median(ratio):.4g}, "
                  f"p5={np.quantile(ratio, .05):.4g}, p95={np.quantile(ratio, .95):.4g}")
        del a


def part_c_t2_dups():
    hdr("C. T2 duplicated expression profiles and their spatial positions")
    for f in ["E6.75.h5ad", "E7.25.h5ad", "E8.0.h5ad", "E8.25_late.h5ad", "E8.75.h5ad", "E9.5.h5ad"]:
        a = ad.read_h5ad(os.path.join(RAW, "T2", f))
        C = csr(a.layers["counts"]).toarray()
        _, inv, cnt = np.unique(C, axis=0, return_inverse=True, return_counts=True)
        inv = np.asarray(inv).ravel()
        P = np.asarray(a.obsm["spatial_3D"], dtype=float)
        multi = np.where(cnt[inv] > 1)[0]
        groups = pd.Series(inv[multi]).value_counts()
        lib = C.sum(1)
        n_groups = groups.size
        print(f"  {f}: rows in duplicate groups={multi.size} ({100 * multi.size / len(inv):.2f}%), "
              f"groups={n_groups}, median group size={np.median(groups.values) if n_groups else 0}")
        if n_groups:
            spreads = []
            for g in groups.index[:4000]:
                idx = np.where(inv == g)[0]
                d = np.linalg.norm(P[idx] - P[idx[0]], axis=1).max()
                spreads.append(d)
            spreads = np.array(spreads)
            print(f"     group max spatial spread (3D units): median={np.median(spreads):.3g}, "
                  f"fraction of groups with identical coordinates (<1e-3)={np.mean(spreads < 1e-3):.3f}")
            print(f"     library size of duplicated rows: median={np.median(lib[multi]):.0f} "
                  f"(all cells median={np.median(lib):.0f})")
        del a


def part_d_t3_layers():
    hdr("D. T3 'log1p' layer: which formula it follows")
    a = ad.read_h5ad(os.path.join(RAW, "T3", "E9.5_mab21l2_ko.h5ad"))
    C = np.asarray(a.layers["counts"], dtype=np.float64)
    NC = np.asarray(a.layers["normalized_counts"], dtype=np.float64)
    L = csr(a.layers["log1p"]).toarray().astype(np.float64)
    X = np.asarray(a.X, dtype=np.float64)
    lib = C.sum(1)
    cands = {
        "log1p(counts)": np.log1p(C),
        "log1p(CP10k(counts))": np.log1p(1e4 * C / lib[:, None]),
        "log2(1+CP10k(counts))": np.log2(1 + 1e4 * C / lib[:, None]),
        "log1p(CP1e6(counts))": np.log1p(1e6 * C / lib[:, None]),
        "log1p(counts/median lib * 1e4)": np.log1p(C / np.median(lib) * 1e4),
        "log1p(CP10k(normalized_counts))": np.log1p(1e4 * NC / NC.sum(1, keepdims=True)),
    }
    for k, v in cands.items():
        print(f"  max|L - {k}| = {np.abs(L - v).max():.4g}; max|X - {k}| = {np.abs(X - v).max():.4g}")
    rowsum_expm1 = np.expm1(L).sum(1)
    print(f"  expm1(L) row sums: median={np.median(rowsum_expm1):.4g}, min={rowsum_expm1.min():.4g}, "
          f"max={rowsum_expm1.max():.4g}")
    # per-cell scale implied by L on nonzero entries
    mask = C > 0
    S = np.where(mask, np.expm1(L) / np.where(mask, C, 1), np.nan)
    s = np.nanmedian(S, axis=1)
    print(f"  implied per-cell scale of L: median={np.nanmedian(s):.4g}; 1e4/lib median={np.median(1e4 / lib):.4g}")
    print(f"  X == log1p(CP10k(counts)) within 1e-5 for all entries: "
          f"{np.allclose(X, np.log1p(1e4 * C / lib[:, None]), atol=1e-5)}")
    del a


def part_e_t3_mapping():
    hdr("E. T3 sample_id / section / z mapping and duplicated records")
    a = ad.read_h5ad(os.path.join(RAW, "T3", "E9.5_mab21l2_ko.h5ad"))
    obs = a.obs.copy()
    obs["barcode"] = a.obs_names.astype(str)
    obs["z3d"] = np.asarray(a.obsm["spatial_3D"])[:, 2]
    obs["sample"] = obs["sample_id"].astype(str)
    obs["section_s"] = obs["section"].astype(str)
    obs["zc"] = obs["z_coord"].astype(str)
    m = obs.groupby("sample").agg(n=("z3d", "size"), zc=("zc", lambda s: sorted(set(s))),
                                  sec=("section_s", lambda s: sorted(set(s))),
                                  z3d_min=("z3d", "min"), z3d_max=("z3d", "max"))
    m = m.sort_index(key=lambda idx: idx.astype(int))
    print("  sample_id -> cells, z_coord, section, z (3D) range:")
    print(m.to_string())
    sec_to_samples = obs.groupby("section_s")["sample"].agg(lambda s: sorted(set(s), key=int))
    multi = sec_to_samples[sec_to_samples.apply(len) > 1]
    print(f"  sections shared by more than one sample_id: {multi.to_dict()}")
    dup = obs[obs["barcode"].duplicated(keep=False)]
    combos = dup.groupby("barcode").agg(samples=("sample", lambda s: tuple(sorted(set(s), key=int))),
                                         zs=("zc", lambda s: tuple(sorted(set(s), key=int))))
    print("  duplicated barcodes by (sample pair):")
    print(combos["samples"].value_counts().head(12).to_string())
    print("  duplicated barcodes by z pair:")
    print(combos["zs"].value_counts().head(12).to_string())
    print(f"  sample_id values with embryo_section NaN: {int(obs['embryo_section'].isna().sum())} of {obs.shape[0]} rows")
    del a


def part_f_t2_dup_geometry():
    hdr("F. T2 duplicate pairs: z-step and xy offset between the two members")
    for f in ["E8.0.h5ad", "E8.25_late.h5ad", "E8.75.h5ad", "E9.5.h5ad", "E6.75.h5ad", "E7.25.h5ad"]:
        a = ad.read_h5ad(os.path.join(RAW, "T2", f))
        C = csr(a.layers["counts"]).toarray()
        _, inv, cnt = np.unique(C, axis=0, return_inverse=True, return_counts=True)
        inv = np.asarray(inv).ravel()
        P = np.asarray(a.obsm["spatial_3D"], dtype=float)
        lib = C.sum(1)
        pair_groups = np.where(cnt == 2)[0]
        rows_by_group = {g: np.where(inv == g)[0] for g in pair_groups}
        if not pair_groups.size:
            print(f"  {f}: no pairs")
            continue
        dz, dxy, libs = [], [], []
        for g, idx in rows_by_group.items():
            i, j = idx
            dz.append(abs(P[i, 2] - P[j, 2]))
            dxy.append(np.linalg.norm(P[i, :2] - P[j, :2]))
            libs.append(lib[i])
        dz, dxy, libs = map(np.array, (dz, dxy, libs))
        zs = np.unique(np.round(P[:, 2], 3))
        step = np.median(np.diff(zs))
        print(f"  {f}: pairs={pair_groups.size}; section step={step:.3g}; "
              f"|dz| distribution: median={np.median(dz):.3g}, fraction |dz| == one step={np.mean(np.isclose(dz, step, atol=0.5)):.3f}, "
              f"fraction |dz| == 0={np.mean(dz < 1e-3):.3f}; "
              f"xy offset median={np.median(dxy):.3g}, fraction xy offset < 1={np.mean(dxy < 1):.3f}; "
              f"library median of pair={np.median(libs):.0f}")
        del a


def part_g_sparsity_depth():
    hdr("G. True sparsity (explicit zeros removed) and depth by z-level")
    import glob
    for f in sorted(glob.glob(os.path.join(RAW, "*", "*.h5ad"))):
        a = ad.read_h5ad(f)
        X = csr(a.X)
        n_stored = X.nnz
        n_explicit = int(np.sum(X.data == 0))
        n_true = n_stored - n_explicit
        total = X.shape[0] * X.shape[1]
        print(f"  {os.path.relpath(f, RAW)}: stored={n_stored:,} explicit_zero={n_explicit:,} "
              f"true_nonzero_frac={n_true / total:.4f} true_sparsity={1 - n_true / total:.4f}")
        if "counts" in a.layers.keys():
            C = csr(a.layers["counts"])
            lib = np.asarray(C.sum(1)).ravel()
        elif os.path.basename(f).startswith("E8.5") or os.path.basename(f).startswith("E9.5_RNA"):
            lib = None
        else:
            lib = None
        if lib is not None and "spatial_3D" in a.obsm and "z_coord" in a.obs.columns:
            z = a.obs["z_coord"].astype(str).values
            df = pd.DataFrame({"z": z, "lib": lib})
            med = df.groupby("z")["lib"].median()
            print(f"     per-z-level median counts library: min={med.min():.0f} max={med.max():.0f}; "
                  f"Spearman(z-level index, median) computed below")
            zlev = sorted(df["z"].unique(), key=lambda v: int(v))
            rank = {v: i for i, v in enumerate(zlev)}
            ii = df["z"].map(rank).values
            from scipy.stats import spearmanr
            rho = spearmanr(ii, df["lib"].values).statistic
            print(f"     Spearman(z-level, cell library)={rho:.3f}")
        del a
    # T1 per-cell depth (implied) is in part A; print composition check against doc
    print("\n  T1 E9.5 contains Neural Tube or Paraxial Mesoderm labels? "
          "(doc says both absent at E9.5)")
    a = ad.read_h5ad(os.path.join(RAW, "T1", "E9.5_RNA.h5ad"), backed="r")
    labs = set(a.obs["celltype"].astype(str).unique())
    a.file.close()
    print(f"     Neural Tube: {'Neural Tube' in labs}; Paraxial Mesoderm: {'Paraxial Mesoderm' in labs}")
    a = ad.read_h5ad(os.path.join(RAW, "T1", "E8.5_RNA.h5ad"), backed="r")
    labs8 = a.obs["celltype"].astype(str).value_counts(normalize=True) * 100
    a.file.close()
    print(f"     E8.5 Neural Tube share: {labs8.get('Neural Tube', 0):.2f}% (doc: 4.6%); "
          f"Paraxial Mesoderm share: {labs8.get('Paraxial Mesoderm', 0):.2f}% (doc: 5.56%)")


if __name__ == "__main__":
    part_g_sparsity_depth()
    part_a_t1()
    part_b_t2_raw()
    part_c_t2_dups()
    part_d_t3_layers()
    part_e_t3_mapping()
    part_f_t2_dup_geometry()
