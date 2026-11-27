"""Follow-up checks on the raw .h5ad files that the first profile raised questions about.

  1. T1: can raw counts be recovered from log1p(CP10k) X (integer test)?
  2. T2: counts layer vs raw.X vs X (why raw.X != counts in some stages)?
  3. T2: fractional counts from E8.0 onward (what the scale looks like).
  4. T3: how X / log1p / normalized_counts relate to counts.
  5. T3: duplicated obs names (same cell in adjacent sections?), section/sample mapping.
  6. T3 and T2 3D connected components (single embryo or several?).
  7. Gene panel overlap for every board, order checks.
  8. Cell-type vocabularies and overlaps across stages.

Run with: .venv/bin/python -I -W ignore scripts/profile_followup.py
"""
import glob
import os
import re

import anndata as ad
import numpy as np
import pandas as pd
import scipy.sparse as sp
from scipy.sparse.csgraph import connected_components
from scipy.spatial import cKDTree

RAW = "/scratch/user/virtual-embryo/data/raw"
PANELS = "/scratch/user/virtual-embryo/data/panels"


def hdr(t):
    print("\n" + "=" * 100)
    print(t)
    print("=" * 100)


def csr(M):
    return M.tocsr() if sp.issparse(M) else sp.csr_matrix(np.asarray(M))


def per_row_min_nonzero(M):
    """Minimum stored value per row, NaN for empty rows (CSR input)."""
    M = csr(M)
    out = np.full(M.shape[0], np.nan)
    nz = np.diff(M.indptr) > 0
    if nz.any():
        starts = M.indptr[:-1][nz]
        out[nz] = np.minimum.reduceat(M.data, starts)
    return out


def section_1_t1():
    hdr("1. T1 raw-count recovery from X = log1p(CP10k(counts))")
    for f in ["E8.5_RNA.h5ad", "E9.5_RNA.h5ad"]:
        a = ad.read_h5ad(os.path.join(RAW, "T1", f))
        X = csr(a.X).astype(np.float64)
        E = X.copy()
        E.data = np.expm1(E.data)
        mins = per_row_min_nonzero(E)
        total = 1e4 / mins                      # implied library size if min count == 1
        rows = np.repeat(np.arange(E.shape[0]), np.diff(E.indptr))
        ratio = E.data * (total[rows] / 1e4)    # should be integer counts
        dev = np.abs(ratio - np.round(ratio))
        print(f"  {f}: implied library size median={np.median(total):.0f} "
              f"(p5={np.quantile(total, .05):.0f}, p95={np.quantile(total, .95):.0f})")
        print(f"     fraction of nonzero entries within 0.05 of an integer: {np.mean(dev < 0.05):.4f}")
        print(f"     median abs deviation from integer: {np.median(dev):.2e}")
        print(f"     implied per-cell UMI total median (sum of rounded ratios): "
              f"{np.median(np.bincount(rows, weights=np.round(ratio), minlength=E.shape[0])):.0f}")
        del a


def section_2_t2_raw():
    hdr("2. T2 counts layer vs raw.X vs X")
    for f in sorted(glob.glob(os.path.join(RAW, "T2", "*.h5ad"))):
        a = ad.read_h5ad(f)
        c = csr(a.layers["counts"]).astype(np.float64)
        R = np.asarray(a.raw.X, dtype=np.float64)
        Rs = sp.csr_matrix(R)
        d = (Rs - c).tocsr()
        n_eq_rows = int(np.sum(np.abs((Rs - c)).sum(axis=1).A1 == 0))
        print(f"  {os.path.basename(f)}:")
        print(f"     raw.X nnz={Rs.nnz:,} vs counts nnz={c.nnz:,}; raw.X integer={bool(np.all(R == np.floor(R)))}")
        print(f"     rows identical raw==counts: {n_eq_rows}/{c.shape[0]}")
        print(f"     raw row sums median={np.median(np.asarray(Rs.sum(1)).ravel()):.2f}, "
              f"counts row sums median={np.median(np.asarray(c.sum(1)).ravel()):.2f}")
        # is raw.X simply counts with some entries zeroed? (raw <= counts everywhere?)
        cd = c.toarray()
        print(f"     raw.X <= counts everywhere: {bool(np.all(R <= cd + 1e-6))}; "
              f"fraction of counts entries retained in raw: "
              f"{float(np.sum(np.minimum(R, cd)) / max(np.sum(cd), 1e-9)):.4f}")
        # what fraction of raw.X nonzeros coincide with counts nonzeros
        both = np.sum((R > 0) & (cd > 0))
        print(f"     raw.X nonzero entries also nonzero in counts: {both:,}/{int((R > 0).sum()):,}")
        del a


def section_3_t2_fraction():
    hdr("3. Fractional counts in T2 counts layer")
    for f in sorted(glob.glob(os.path.join(RAW, "T2", "*.h5ad"))):
        a = ad.read_h5ad(f)
        c = csr(a.layers["counts"]).astype(np.float64)
        v = c.data
        frac = v - np.floor(v)
        nonint = frac > 1e-6
        print(f"  {os.path.basename(f)}: non-integer nonzero entries={nonint.mean():.4f} "
              f"min nonzero={v.min():.4g} median nonzero={np.median(v):.4g} "
              f"n_unique nonzero values (first 12 sorted)={np.unique(np.round(v, 4))[:12].tolist()}")
        lib = np.asarray(c.sum(1)).ravel()
        print(f"     per-cell library size (counts) min={lib.min():.3g} median={np.median(lib):.3g} "
              f"max={lib.max():.3g}")
        del a


def section_4_t3_norm():
    hdr("4. T3 normalisation: X vs log1p layer vs normalized_counts vs counts")
    a = ad.read_h5ad(os.path.join(RAW, "T3", "E9.5_mab21l2_ko.h5ad"))
    C = np.asarray(a.layers["counts"], dtype=np.float64)
    NC = np.asarray(a.layers["normalized_counts"], dtype=np.float64)
    X = np.asarray(a.X, dtype=np.float64)
    L = csr(a.layers["log1p"]).toarray().astype(np.float64)
    lib_c = C.sum(1)
    lib_nc = NC.sum(1)
    print(f"  counts integer={bool(np.all(C == np.floor(C)))}; n_counts==row sum counts: "
          f"{bool(np.allclose(a.obs['n_counts'].values, lib_c))}; n_genes==nnz per row: "
          f"{bool(np.array_equal(a.obs['n_genes'].values, (C > 0).sum(1)))}")
    print(f"  normalized_counts integer={bool(np.all(NC == np.floor(NC)))}; "
          f"NC row sums median={np.median(lib_nc):.2f}; NC/C ratio per cell: "
          f"median={np.median(lib_nc / lib_c):.3f}")
    # Hypotheses for X
    def cp10k(M):
        s = M.sum(1, keepdims=True)
        return np.log1p(1e4 * M / np.maximum(s, 1e-12))
    h1 = cp10k(C)
    h2 = cp10k(NC)
    print(f"  max|X - log1p(CP10k(counts))| = {np.abs(X - h1).max():.3f}; "
          f"median per-entry diff on nonzeros={np.median(np.abs(X - h1)[X > 0]):.3f}")
    print(f"  max|X - log1p(CP10k(normalized_counts))| = {np.abs(X - h2).max():.3f}; "
          f"median per-entry diff on nonzeros={np.median(np.abs(X - h2)[X > 0]):.3f}")
    print(f"  max|L - log1p(CP10k(counts))| = {np.abs(L - h1).max():.3f}; "
          f"max|L - X| = {np.abs(L - X).max():.3f}")
    # per-cell implied scale: expm1(X)/counts on nonzero entries
    mask = (C > 0)
    S = np.where(mask, np.expm1(X) / np.where(C > 0, C, 1), np.nan)
    s_med = np.nanmedian(S, axis=1)
    s_spread = np.nanstd(S, axis=1) / np.nanmean(S, axis=1)
    print(f"  implied per-cell scale s_i (expm1(X)/counts): median={np.nanmedian(s_med):.4g} "
          f"; within-cell CV median={np.nanmedian(s_spread):.4g} "
          f"(near 0 means X = log1p(s_i * counts) with a per-cell factor)")
    target = 1e4 / lib_c
    print(f"  s_i vs 1e4/library(counts): correlation={np.corrcoef(np.log(s_med), np.log(target))[0, 1]:.4f}; "
          f"median ratio s_i/(1e4/lib)={np.median(s_med / target):.4g}")
    target2 = 1e4 / lib_nc
    print(f"  s_i vs 1e4/library(normalized_counts): correlation={np.corrcoef(np.log(s_med), np.log(target2))[0, 1]:.4f}; "
          f"median ratio s_i/(1e4/lib_nc)={np.median(s_med / target2):.4g}")
    # Is the library implied by X's expm1 sum, in count units, 1e4 / s_i?
    print(f"  implied library (1e4/s_i) median={np.median(1e4 / s_med):.1f}; counts library median={np.median(lib_c):.1f}; "
          f"NC library median={np.median(lib_nc):.1f}")
    # genewise: is the normalisation a constant per gene (i.e., NC = C * gene factor)?
    ratio_g = np.where(C > 0, NC / np.where(C > 0, C, 1), np.nan)
    print(f"  NC/C ratio across nonzero entries: median={np.nanmedian(ratio_g):.4g}, "
          f"p5={np.nanpercentile(ratio_g, 5):.4g}, p95={np.nanpercentile(ratio_g, 95):.4g}")
    del a


def section_5_t3_dups():
    hdr("5. T3 duplicated obs names and section/sample mapping")
    a = ad.read_h5ad(os.path.join(RAW, "T3", "E9.5_mab21l2_ko.h5ad"))
    obs = a.obs.copy()
    obs["barcode"] = a.obs_names.astype(str)
    obs["z3d"] = np.asarray(a.obsm["spatial_3D"])[:, 2]
    obs["x3d"] = np.asarray(a.obsm["spatial_3D"])[:, 0]
    obs["y3d"] = np.asarray(a.obsm["spatial_3D"])[:, 1]
    dupmask = obs["barcode"].duplicated(keep=False)
    print(f"  rows whose barcode occurs more than once: {int(dupmask.sum())}; distinct barcodes: "
          f"{obs.loc[dupmask, 'barcode'].nunique()}; barcodes occurring exactly twice: "
          f"{int((obs['barcode'].value_counts() == 2).sum())}")
    d = obs[dupmask].sort_values(["barcode", "z_coord"])
    pairs = d.groupby("barcode").agg(n=("z3d", "size"), zs=("z_coord", lambda s: tuple(sorted(set(s.astype(str))))),
                                       samples=("sample_id", lambda s: tuple(sorted(set(s.astype(str))))),
                                       z_span=("z3d", lambda s: float(s.max() - s.min())),
                                       xy_span=("x3d", lambda s: float(s.max() - s.min())))
    print("  pairs: count by (z_coord pair):")
    print(pairs["zs"].value_counts().head(15).to_string())
    print(f"  pairs with identical x,y (3D) across the two rows: "
          f"{int(np.sum(d.groupby('barcode')['x3d'].nunique() == 1))} x; "
          f"{int(np.sum(d.groupby('barcode')['y3d'].nunique() == 1))} y (of {pairs.shape[0]})")
    print(f"  pair z-span distribution: {pairs['z_span'].describe().round(2).to_dict()}")
    print(f"  pair xy-span distribution: {pairs['xy_span'].describe().round(2).to_dict()}")
    # section vs sample_id vs z_coord vs embryo_section crosstab
    ct = pd.crosstab(obs["section"].astype(str), obs["sample_id"].astype(str))
    nz = (ct > 0).sum(axis=1)
    print(f"  section -> number of sample_ids it spans: {nz.value_counts().sort_index().to_dict()}")
    cz = pd.crosstab(obs["sample_id"].astype(str), obs["z_coord"].astype(str))
    print(f"  sample_id -> number of z_coord levels: {(cz > 0).sum(axis=1).value_counts().sort_index().to_dict()}")
    ce = obs.groupby(obs["embryo_section"].astype(str), observed=True).agg(
        n=("z3d", "size"), z_mean=("z3d", "mean"), sample=("sample_id", lambda s: tuple(sorted(set(s.astype(str))))),
        sec=("section", lambda s: tuple(sorted(set(s.astype(str))))))
    print("  embryo_section (first 12 rows): n, mean z, sample_ids, sections")
    print(ce.head(12).to_string())
    print(f"  embryo_section NaN count: {int(obs['embryo_section'].isna().sum())}")
    # '-alt' sections
    alt = obs[obs["embryo_section"].astype(str).str.contains("alt", na=False)]
    print(f"  rows labelled *-alt in embryo_section: {len(alt)}; their sample_ids: "
          f"{sorted(set(alt['sample_id'].astype(str)))[:20]}; their z: {sorted(set(alt['z_coord'].astype(str)))[:12]}")
    # Are the duplicate rows the same row in both samples?
    print(f"  number of barcode-duplicate rows that also appear as embryo_section NaN: "
          f"{int(obs.loc[dupmask, 'embryo_section'].isna().sum())}")
    del a


def section_6_components():
    hdr("6. 3D connected components (single embryo or several?)")
    for f in ["T3/E9.5_mab21l2_ko.h5ad", "T2/E9.5.h5ad", "T2/E8.25_late.h5ad", "T2/E8.75.h5ad", "T2/E8.0.h5ad",
              "T2/E7.25.h5ad", "T2/E6.75.h5ad"]:
        a = ad.read_h5ad(os.path.join(RAW, f))
        P = np.asarray(a.obsm["spatial_3D"], dtype=float)
        tree = cKDTree(P)
        dd, _ = tree.query(P, k=2)
        r = 3 * np.median(dd[:, 1])
        pairs = tree.query_pairs(r, output_type="ndarray")
        n = P.shape[0]
        A = sp.coo_matrix((np.ones(len(pairs)), (pairs[:, 0], pairs[:, 1])), shape=(n, n))
        nc, lab = connected_components(A, directed=False)
        sizes = np.bincount(lab)
        order = np.argsort(sizes)[::-1]
        print(f"  {f}: r={r:.3g}, components={nc}, sizes>=50: {(sizes >= 50).sum()}")
        for k in order[:4]:
            m = lab == k
            info = ""
            if "sample_id" in a.obs.columns:
                info = f" sample_ids={sorted(set(a.obs['sample_id'].astype(str)[m]))[:40]}"
            print(f"     comp size={sizes[k]:>6}  centroid={np.round(P[m].mean(0), 1).tolist()}  "
                  f"z range=[{P[m,2].min():.1f},{P[m,2].max():.1f}]{info}")
        if nc > 1:
            big = order[0]
            small = [k for k in order[1:] if sizes[k] >= 50]
            if small:
                k = small[0]
                m_big = lab == big
                m_small = lab == k
                dmin = cKDTree(P[m_big]).query(P[m_small], k=1)[0].min()
                print(f"     min distance between largest and second component = {dmin:.3g}")
        del a


def section_7_panels():
    hdr("7. Panel overlap and order against the data files")
    names = {}
    for p in sorted(glob.glob(os.path.join(RAW, "*", "*.h5ad"))):
        tag = os.path.relpath(p, RAW)
        a = ad.read_h5ad(p, backed="r")
        names[tag] = list(a.var_names)
        a.file.close()
    panels = {}
    for p in sorted(glob.glob(os.path.join(PANELS, "*.genes.txt"))):
        panels[os.path.basename(p).replace(".genes.txt", "")] = [l.rstrip("\n") for l in open(p) if l.strip()]
    for pname, pg in panels.items():
        print(f"  panel {pname}: n={len(pg)} unique={len(set(pg))}")
        for tag, vn in names.items():
            inter = [g for g in pg if g in set(vn)]
            missing = [g for g in pg if g not in set(vn)]
            same_order = (pg == [g for g in vn if g in set(pg)]) if inter else False
            equal_set = set(pg) == set(vn)
            if len(inter) == 0:
                continue
            print(f"     vs {tag:<26} present={len(inter)}/{len(pg)}  missing={len(missing)}"
                  f"  equal-set={equal_set}  panel order = file order (restricted)={same_order}"
                  + (f"  missing e.g. {missing[:4]}" if missing else ""))
    # gene-set equality between data files
    print("\n  var-name sets across data files:")
    tags = list(names.keys())
    for i, t1 in enumerate(tags):
        for t2 in tags[i + 1:]:
            s1, s2 = set(names[t1]), set(names[t2])
            if len(s1) == len(s2) and s1 == s2:
                print(f"     {t1} == {t2} (same set, same order={names[t1] == names[t2]})")
    print("\n  heart 500 vs embryo 498 vs E8.0 500 set differences:")
    heart = set(panels["T2__heart__val_interp"])
    emb = set(panels["T2__embryo__val_interp"])
    e8 = set(names["T2/E8.0.h5ad"])
    e675 = set(names["T2/E6.75.h5ad"])
    print(f"     embryo_val - heart = {sorted(emb - heart)}; heart - embryo_val = {sorted(heart - emb)}")
    print(f"     E8.0 var == heart panel set: {e8 == heart}; E6.75 var == embryo_val panel set: {e675 == emb}")
    emb_t = set(panels["T2__embryo__test_interp"])
    print(f"     embryo_test - embryo_val = {sorted(emb_t - emb)}; embryo_val - embryo_test = {sorted(emb - emb_t)}")
    print(f"     heart_val_extrap == heart_val_interp == heart_test: "
          f"{panels['T2__heart__val_extrap'] == panels['T2__heart__val_interp'] == panels['T2__heart__test_extrap']}")
    print(f"     gata4 == bcatenin panel: {panels['T3__gata4'] == panels['T3__bcatenin']}; "
          f"T3 gata4 == heart panel: {panels['T3__gata4'] == panels['T2__heart__val_interp']}")
    print(f"     T3 var order == heart panel order: {names['T3/E9.5_mab21l2_ko.h5ad'] == panels['T2__heart__val_interp']}")
    print(f"     T2 heart stages var order identical to heart panel: "
          f"{all(names[t] == panels['T2__heart__val_interp'] for t in ['T2/E8.25_late.h5ad','T2/E8.75.h5ad','T2/E9.5.h5ad'])}")
    print(f"     T2 E6.75/E7.25 var order == embryo val panel: "
          f"{names['T2/E6.75.h5ad'] == panels['T2__embryo__val_interp']} / {names['T2/E7.25.h5ad'] == panels['T2__embryo__val_interp']}")
    print(f"     T2 E8.0 var order == heart panel: {names['T2/E8.0.h5ad'] == panels['T2__heart__val_interp']}")
    print(f"     T1 E8.5 var order == T1 panel: {names['T1/E8.5_RNA.h5ad'] == panels['T1__val']}; "
          f"E9.5 == T1 panel: {names['T1/E9.5_RNA.h5ad'] == panels['T1__val']}")
    print(f"     Casp4 / Pnliprp1 in heart panel: {'Casp4' in heart} / {'Pnliprp1' in heart}; "
          f"in embryo val: {'Casp4' in emb} / {'Pnliprp1' in emb}")
    print(f"     Casp4 / Pnliprp1 in E6.75: {'Casp4' in e675} / {'Pnliprp1' in e675}; in E8.0: {'Casp4' in e8} / {'Pnliprp1' in e8}")
    print(f"     embryo_test - E6.75 var = {sorted(emb_t - e675)}; E6.75 var - embryo_test = {sorted(e675 - emb_t)}")
    print(f"     E8.0 - E6.75 = {len(e8 - e675)} genes")


def section_8_vocab():
    hdr("8. Cell-type vocabularies and overlaps across stages")
    labels = {}
    for p in sorted(glob.glob(os.path.join(RAW, "*", "*.h5ad"))):
        tag = os.path.relpath(p, RAW).replace("/", ":").replace(".h5ad", "")
        a = ad.read_h5ad(p, backed="r")
        labels[tag] = a.obs["celltype"].astype(str).value_counts()
        if "cm_celltype" in a.obs.columns:
            labels[tag + "|cm"] = a.obs["cm_celltype"].astype(str).value_counts()
        a.file.close()
    for tag, vc in labels.items():
        print(f"  {tag}: {len(vc)} labels")
    print()
    base = ["T1:E8.5_RNA", "T1:E9.5_RNA", "T2:E6.75", "T2:E7.25", "T2:E8.0", "T2:E8.25_late", "T2:E8.75", "T2:E9.5",
            "T3:E9.5_mab21l2_ko"]
    for i, t1 in enumerate(base):
        for t2 in base[i + 1:]:
            s1, s2 = set(labels[t1].index), set(labels[t2].index)
            ov = sorted(s1 & s2)
            if ov:
                print(f"  {t1} vs {t2}: shared={len(ov)} (Jaccard={len(ov) / len(s1 | s2):.2f}) "
                      f"{ov if len(ov) <= 14 else ''}")
            else:
                print(f"  {t1} vs {t2}: shared=0")
    print("\n  Name-set differences that look like the same type under a different label:")
    print("   T2:E9.5 only:", sorted(set(labels['T2:E9.5'].index) - set(labels['T3:E9.5_mab21l2_ko'].index)))
    print("   T3 only    :", sorted(set(labels['T3:E9.5_mab21l2_ko'].index) - set(labels['T2:E9.5'].index)))
    print("   T1 E9.5 only vs T2 E9.5:", sorted(set(labels['T1:E9.5_RNA'].index) - set(labels['T2:E9.5'].index)))
    print("   T2 E9.5 only vs T1 E9.5:", sorted(set(labels['T2:E9.5'].index) - set(labels['T1:E9.5_RNA'].index)))
    print("\n  cm_celltype overlaps among heart stages (E8.0/E8.25/E8.75/E9.5/T3):")
    cm = ["T2:E8.0|cm", "T2:E8.25_late|cm", "T2:E8.75|cm", "T2:E9.5|cm", "T3:E9.5_mab21l2_ko|cm"]
    if "T3:E9.5_mab21l2_ko|cm" not in labels:
        cm = cm[:-1]
    for c in cm:
        print(f"  {c}: {sorted(labels[c].index)}")
    print("\n  T2 heart stages with multiple labels: E8.25 vs E8.75 shared:",
          len(set(labels['T2:E8.25_late'].index) & set(labels['T2:E8.75'].index)))


if __name__ == "__main__":
    # section_1_t1 is superseded by scripts/profile_resolve.py part A (explicit zeros broke the minimum here)
    section_2_t2_raw()
    section_3_t2_fraction()
    section_4_t3_norm()
    section_5_t3_dups()
    section_6_components()
    section_7_panels()
    section_8_vocab()
