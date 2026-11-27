"""Content profile of each raw .h5ad: X semantics, layers, obs/obsm distributions,
duplicates, and cross-file overlaps. Loads each file fully (RAM is ample).

Run with: .venv/bin/python -I -W ignore scripts/profile_content.py [> out.txt]
"""
import glob
import hashlib
import os
import re
import sys

import anndata as ad
import numpy as np
import pandas as pd
import scipy.sparse as sp
from scipy.sparse.csgraph import connected_components
from scipy.spatial import cKDTree

ROOT = "/scratch/user/virtual-embryo/data/raw"
SCRATCH = "/scratch/user/tmp/claude-7059086/-scratch-user-virtual-embryo/276ca0d4-5ce5-45dc-b11c-442640774cbc/scratchpad"
MARKERS = ["Mab21l2", "Gata4", "Ctnnb1", "Casp4", "Pnliprp1", "Nkx2-5", "Tnnt2", "Myl7", "Hand2", "Tbx5"]


def h(title):
    print("\n" + "#" * 100)
    print("#", title)
    print("#" * 100)


def mat_stats(M, name):
    """Basic value statistics for a matrix that may be sparse or dense."""
    n, g = M.shape
    if sp.issparse(M):
        data = M.data
        nnz = int(M.nnz)
        kind = f"sparse-{M.format}"
    else:
        M = np.asarray(M)
        data = M.ravel()
        nnz = int(np.count_nonzero(M))
        kind = "dense"
    total = n * g
    mn = float(data.min()) if data.size else float("nan")
    mx = float(data.max()) if data.size else float("nan")
    if nnz < total:
        mn = min(mn, 0.0)
    print(f"  [{name}] kind={kind} dtype={M.dtype} shape={(n, g)}")
    print(f"     nnz={nnz:,}  frac_zero={1 - nnz / total:.4f}  min={mn:.4g}  max={mx:.4g}")
    neg = int((data < 0).sum())
    fin = bool(np.isfinite(data).all())
    integer = bool(np.all(data == np.floor(data)))
    print(f"     negatives={neg}  all_finite={fin}  integer_valued={integer}")
    return data


def row_sums(M):
    return np.asarray(M.sum(axis=1), dtype=np.float64).ravel()


def expm1_rowsums(M):
    if sp.issparse(M):
        E = M.tocsr().astype(np.float64, copy=True)
        E.data = np.expm1(E.data)
        return np.asarray(E.sum(axis=1)).ravel()
    return np.expm1(np.asarray(M, dtype=np.float64)).sum(axis=1)


def describe_summary(v, label):
    v = np.asarray(v, dtype=float)
    q = np.quantile(v, [0, 0.05, 0.25, 0.5, 0.75, 0.95, 1])
    print(f"  {label}: min={q[0]:.4g} p5={q[1]:.4g} p25={q[2]:.4g} median={q[3]:.4g} "
          f"p75={q[4]:.4g} p95={q[5]:.4g} max={q[6]:.4g}")


def check_x_semantics(a, label):
    """Decide whether X is raw counts, CP10k-log1p, or other."""
    X = a.X
    print(f"  X type={type(X).__name__}")
    mat_stats(X, "X")
    rs = row_sums(X)
    describe_summary(rs, "row sum of X (raw scale)")
    er = expm1_rowsums(X)
    describe_summary(er, "row sum of expm1(X)")
    med = float(np.median(er))
    if abs(med - 1e4) / 1e4 < 0.02:
        print("  -> expm1(X) rows sum to ~1e4: consistent with log1p(CP10k) (natural log)")
    elif abs(med - 1.0) < 0.02:
        print("  -> expm1(X) rows sum to ~1: consistent with log1p(proportions)")
    # Recover implied counts from smallest nonzero expm1 value per cell (count=1 assumption)
    if sp.issparse(X) and not (label.startswith("T1")):
        pass
    if label.startswith("T1"):
        Xc = X.tocsr().astype(np.float64, copy=True)
        E = Xc.copy()
        E.data = np.expm1(E.data)
        E.eliminate_zeros()  # T1 stores explicit zeros; drop them before taking minima
        # smallest nonzero per row
        mins = np.full(E.shape[0], np.nan)
        for i in range(E.shape[0]):
            seg = E.data[E.indptr[i]:E.indptr[i + 1]]
            if seg.size:
                mins[i] = seg.min()
        implied_total = 1e4 / mins
        describe_summary(implied_total, "implied library size = 1e4 / min nonzero expm1")
        # integer test: expm1 * total / 1e4 should be integers if X = log1p(CP10k(counts))
        scale = np.repeat(implied_total / 1e4, np.diff(E.indptr))
        ratio = E.data * scale
        dev = np.abs(ratio - np.round(ratio))
        print(f"  integer-recovery test: fraction of nonzero entries within 0.05 of an integer count = "
              f"{float(np.mean(dev < 0.05)):.4f}; median abs dev={float(np.median(dev)):.4g}")
        rows_ = np.repeat(np.arange(E.shape[0]), np.diff(E.indptr))
        pos_ = E.data > 0
        per_cell = np.bincount(rows_[pos_], weights=np.round(ratio[pos_] if ratio.shape[0] == pos_.sum() else ratio), minlength=E.shape[0])
        print(f"  implied UMI total per cell: median={float(np.median(per_cell)):.0f}")
    return rs


def compare_layers(a, counts_key, log_key, label):
    print(f"  --- layer relationships ({label})")
    counts = a.layers[counts_key]
    logl = a.layers[log_key]
    counts = counts.tocsr() if sp.issparse(counts) else sp.csr_matrix(np.asarray(counts))
    logl = logl.tocsr() if sp.issparse(logl) else sp.csr_matrix(np.asarray(logl))
    lib = row_sums(counts)
    print(f"  counts layer: integer_valued={bool(np.all(counts.data == np.floor(counts.data)))}, "
          f"nnz={counts.nnz:,}, frac_zero={1 - counts.nnz / np.prod(counts.shape):.4f}")
    describe_summary(lib, "library size (counts row sums)")
    scale = sp.diags(1e4 / np.maximum(lib, 1))
    expected = (scale @ counts).tocsr()
    expected.data = np.log1p(expected.data)
    diff = (logl - expected).tocsr()
    print(f"  max|log1p layer - log1p(CP10k(counts))| = {np.abs(diff.data).max() if diff.nnz else 0.0:.3g}")
    # X vs log1p layer
    X = a.X
    Xs = X.tocsr() if sp.issparse(X) else sp.csr_matrix(np.asarray(X))
    d2 = (Xs - logl).tocsr()
    print(f"  max|X - log1p layer| = {np.abs(d2.data).max() if d2.nnz else 0.0:.3g}")
    # X vs counts
    d3 = (Xs - counts).tocsr()
    print(f"  max|X - counts| = {np.abs(d3.data).max() if d3.nnz else 0.0:.3g}")
    return counts


def obs_value_counts(a, cols=None, max_levels=60):
    print("  obs value counts:")
    for c in (cols or a.obs.columns):
        s = a.obs[c]
        if isinstance(s.dtype, pd.CategoricalDtype):
            vc = s.value_counts(sort=False)
            used = vc[vc > 0]
            print(f"    {c}: categories={len(s.cat.categories)} observed={len(used)}")
            if len(used) <= max_levels:
                for k, v in used.sort_values(ascending=False).items():
                    print(f"        {k!s:<28} {v:>7,}  ({100 * v / len(s):5.2f}%)")
        else:
            print(f"    {c}: dtype={s.dtype} min={s.min()} median={s.median()} max={s.max()} "
                  f"mean={s.mean():.4g} n_unique={s.nunique()}")


def spatial_profile(coords, label):
    coords = np.asarray(coords, dtype=float)
    print(f"  spatial {label}: shape={coords.shape}")
    for i, ax in enumerate("xyz"[: coords.shape[1]]):
        c = coords[:, i]
        print(f"     {ax}: min={c.min():.4g} max={c.max():.4g} range={c.max() - c.min():.4g} "
              f"mean={c.mean():.4g} std={c.std():.4g} n_unique(6dp)={np.unique(np.round(c, 6)).size}")
    if coords.shape[1] < 3:
        return
    z = np.round(coords[:, 2], 6)
    zu, zc = np.unique(z, return_counts=True)
    print(f"     z levels (6dp): {zu.size}; cells/level min={zc.min()} median={int(np.median(zc))} max={zc.max()}")
    if zu.size <= 60:
        gaps = np.diff(zu)
        if gaps.size:
            print(f"     z spacing: min={gaps.min():.4g} median={np.median(gaps):.4g} max={gaps.max():.4g}")
    # connected components of 3D cloud, radius = 3 x median NN distance
    tree = cKDTree(coords[:, :3])
    dd, _ = tree.query(coords[:, :3], k=2)
    nn = np.median(dd[:, 1])
    r = 3 * nn
    pairs = tree.query_pairs(r, output_type="ndarray")
    n = coords.shape[0]
    if pairs.size:
        A = sp.coo_matrix((np.ones(len(pairs)), (pairs[:, 0], pairs[:, 1])), shape=(n, n))
    else:
        A = sp.coo_matrix((n, n))
    ncomp, lab = connected_components(A, directed=False)
    sizes = np.sort(np.bincount(lab))[::-1]
    big = sizes[sizes >= 50]
    print(f"     median NN dist={nn:.4g}; components at radius {r:.4g}: total={ncomp}, "
          f"components>=50 cells={big.size}, largest sizes={sizes[:8].tolist()}")


def id_prefix_profile(names, label):
    s = pd.Series(names).astype(str)
    m = s.str.extract(r"^(.*?)(\d+)(?:-\d+)?$")
    digits = m[1].dropna()
    prefix = digits.str.slice(0, -4)
    vc = prefix.value_counts()
    print(f"  barcode numeric prefix (digits minus last 4): {vc.size} distinct; top={vc.head(12).to_dict()}")
    print(f"  example names: {list(s.head(3))}")


def read(path):
    return ad.read_h5ad(path)


def main():
    files = sorted(glob.glob(os.path.join(ROOT, "*", "*.h5ad")))
    # order: T1, T2, T3
    row_hashes = {}
    celltypes = {}
    for path in files:
        tag = os.path.relpath(path, ROOT)
        h(f"FILE {tag}")
        a = read(path)
        print(f"  shape={a.shape}  obs_names unique={a.obs_names.is_unique} n_dup_obs={int(a.obs_names.duplicated().sum())}")
        print(f"  layers={list(a.layers.keys())}  raw={'yes' if a.raw is not None else 'no'}")
        if a.raw is not None:
            print(f"  raw shape={a.raw.shape}; raw var == var: {list(a.raw.var_names) == list(a.var_names)}")
        # X semantics
        label = tag.split("/")[0] + "/" + os.path.basename(path)
        if "counts" in a.layers.keys() and "log1p" in a.layers.keys():
            compare_layers(a, "counts", "log1p", "counts/log1p")
        if "counts" in a.layers.keys() and "log1p" not in a.layers.keys():
            print("  (counts layer without log1p)")
        if "counts" in a.layers.keys() and "log1p" in a.layers.keys() and "normalized_counts" in a.layers.keys():
            nc = a.layers["normalized_counts"]
            c = a.layers["counts"]
            lib = np.asarray(c.sum(1)).ravel()
            print(f"  normalized_counts: {type(nc).__name__} {nc.dtype}; "
                  f"row sums median={np.median(np.asarray(nc.sum(1)).ravel()):.4g}")
            rs = np.asarray(nc.sum(1)).ravel()
            ratio = rs / np.maximum(lib, 1)
            describe_summary(ratio, "normalized_counts row sum / counts row sum")
            ncd = np.asarray(nc)
            cd = np.asarray(c)
            print(f"  normalized_counts == counts? max abs diff = {np.abs(ncd - cd).max():.4g}")
            # log1p layer vs log1p(normalized_counts)
            L = a.layers["log1p"].tocsr()
            exp_nc = np.log1p(ncd)
            print(f"  max|log1p layer - log1p(normalized_counts)| = {np.abs(L.toarray() - exp_nc).max():.3g}")
            print(f"  max|X - log1p layer| = {np.abs(np.asarray(a.X) - L.toarray()).max():.3g}")
        if "counts" in a.layers.keys():
            if not ("log1p" in a.layers.keys() and "normalized_counts" in a.layers.keys()):
                pass
            counts = a.layers["counts"]
            # raw vs counts
            if a.raw is not None:
                Rw = a.raw.X
                Rw_s = Rw.tocsr() if sp.issparse(Rw) else sp.csr_matrix(np.asarray(Rw))
                Cs = counts.tocsr() if sp.issparse(counts) else sp.csr_matrix(np.asarray(counts))
                d = (Rw_s - Cs).tocsr()
                print(f"  max|raw.X - counts layer| = {np.abs(d.data).max() if d.nnz else 0.0:.3g}")
        # X semantics (raw or log)
        rs = check_x_semantics(a, label)

        # obs
        h_obs = f"  obs columns: {list(a.obs.columns)}"
        print(h_obs)
        obs_value_counts(a)
        # obsm
        print("  obsm:")
        for k in a.obsm.keys():
            M = np.asarray(a.obsm[k])
            print(f"    {k}: shape={M.shape} dtype={M.dtype}")
            if k.startswith("spatial"):
                spatial_profile(M, k)
            elif M.shape[1] <= 3:
                for i in range(M.shape[1]):
                    describe_summary(M[:, i], f"    col{i}")
        if "spatial_3D" in a.obsm:
            if "z_coord" in a.obs.columns:
                z3 = np.asarray(a.obsm["spatial_3D"])[:, 2]
                zc = a.obs["z_coord"].astype(str).values
                tab = pd.DataFrame({"z_coord": zc, "z3d": z3}).groupby("z_coord")["z3d"].agg(["min", "max", "count"])
                print("  z_coord vs spatial_3D z (first 8 levels):")
                print(tab.head(8).to_string())
                print(f"  distinct z_coord levels={tab.shape[0]}")
        # spatial_2D vs 3D columns
        if "spatial_2D" in a.obsm:
            s2 = np.asarray(a.obsm["spatial_2D"])
            print(f"  spatial_2D col3 unique values (first 10): {np.unique(np.round(s2[:, 2], 4))[:10].tolist()}")
            print(f"  spatial_2D cols1-2 vs spatial_3D cols1-2 identical? {np.allclose(s2[:, :2], np.asarray(a.obsm['spatial_3D'])[:, :2])}")
        id_prefix_profile(a.obs_names, label)

        # duplicates of obs names
        if not a.obs_names.is_unique:
            dup = a.obs_names[a.obs_names.duplicated(keep=False)]
            print(f"  duplicate obs names: {len(dup)} rows, {dup.nunique()} distinct labels; first: {list(dup[:4])}")
            dd = a.obs.loc[dup.unique()[:3]]
            print(dd.head(6).to_string())

        # row hashes for cross-file duplicate detection
        Xs = a.X.tocsr() if sp.issparse(a.X) else np.asarray(a.X)
        hashes = []
        for i in range(a.shape[0]):
            if sp.issparse(Xs):
                row = Xs[i]
                key = row.indices.tobytes() + row.data.tobytes()
            else:
                key = Xs[i].tobytes()
            hashes.append(hashlib.md5(key).hexdigest())
        hs = pd.Series(hashes)
        print(f"  exact duplicate X rows within file: {int(hs.duplicated().sum())}")
        row_hashes[tag] = set(hashes)
        if "celltype" in a.obs.columns:
            celltypes[tag] = a.obs["celltype"].astype(str).value_counts().to_dict()
        # var names saved for panel checks
        np.save(os.path.join(SCRATCH, tag.replace("/", "__") + ".varnames.npy"),
                np.array(a.var_names, dtype=object), allow_pickle=True)
        # markers (use CSC for fast column access)
        Xc = a.X.tocsc() if sp.issparse(a.X) else np.asarray(a.X)
        for g in MARKERS:
            if g in a.var_names:
                j = list(a.var_names).index(g)
                col = np.asarray(Xc[:, j].toarray() if sp.issparse(Xc) else Xc[:, j]).ravel()
                print(f"  marker {g}: present, X mean={col.mean():.4g}, frac>0={np.mean(col > 0):.3f}")
            else:
                print(f"  marker {g}: absent from var")
        del a

    h("CROSS-FILE exact-duplicate X rows")
    keys = list(row_hashes.keys())
    for i in range(len(keys)):
        for j in range(i + 1, len(keys)):
            ov = len(row_hashes[keys[i]] & row_hashes[keys[j]])
            if ov:
                print(f"  {keys[i]} vs {keys[j]}: {ov} identical rows")
    print("  (no line above means no identical X rows across files)")


if __name__ == "__main__":
    main()
