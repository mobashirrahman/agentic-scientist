"""Single-cell analysis in one call, on allowed data only. Read-only; nothing here is available to predict().

DATA is one of:
  T1/E8.5_RNA.h5ad, T2/E8.75.h5ad, T3/E8.75_gata4_ko_1.h5ad ...   released files (relative to data/raw; held-out refused)
  ext:temporal | ext:heart | ext:embryo                           external data exactly as the program receives it
  ext_spatial:heart                                               context['external_spatial'] for heart
Options shared by every command:
  --filter "stage_days == 14.5"   pandas query on obs before analysis      --max-cells 20000   seeded subsample
  --groupby celltype              obs column (default: celltype / cell_type / leiden, whichever exists)

Commands:
  info DATA                                 shape, obs/obsm columns, value scale, top genes, group sizes
  markers DATA [--n 15]                     top marker genes per group (Wilcoxon, scanpy)
  composition DATA [DATA ...]               group fractions side by side
  compare A B [--n 25] [--pair "a=b,..."]   pseudobulk log-fold-change B vs A, overall and per shared group
                                            (calibrate an external source against our data before using levels)
  cluster DATA [--res 1.0] [--png out.png]  PCA + Leiden + UMAP (PNG), cluster x group table
  spatial DATA [--k 10]                     neighbourhood enrichment z-scores (permutation) and per-group radius
  geneset DATA --go GO:0060070 [--genes a,b]  score cells for a GO set (incl. descendant terms, filtered GO prior)
Example: python agentic_scientist/tools/sc_tool.py compare T1/E9.5_RNA.h5ad ext:temporal --filter "group == 'anchor'"
"""
import argparse
import json
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import sparse

warnings.filterwarnings('ignore')
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
DENY = json.loads((ROOT / 'agentic_scientist/config.json').read_text())['holdout_forbidden']
GENE_SOURCE = {'temporal': 'temporal_val', 'heart': 'heart_early', 'embryo': 'embryo_early'}


def load(spec, args):
    from shinka_ve import harness
    if spec.startswith(('ext:', 'ext_spatial:')):
        kind, board = spec.split(':', 1)
        genes = list(harness.load_stage(harness.SPLITS[GENE_SOURCE[board]]['inputs'][-1]).var_names)
        a = (harness.external_board if kind == 'ext' else harness.external_spatial_board)(board, genes)
        if a is None:
            sys.exit(f'no {kind} data for {board}')
    else:
        if any(d.lower() in spec.lower() for d in DENY) or '..' in spec or spec.startswith('/'):
            sys.exit('refused: held-out or non-released file')
        a = harness.load_stage(spec)
    a.obs_names_make_unique()
    if args.filter:
        try:
            a = a[a.obs.query(args.filter).index].copy()
        except Exception:  # filter names a column this dataset lacks (e.g. compare ours vs external): skip it here
            print(f'(filter not applied to {spec}: columns {list(a.obs.columns)})')
    if args.max_cells and a.n_obs > args.max_cells:
        idx = np.sort(np.random.default_rng(0).choice(a.n_obs, args.max_cells, replace=False))
        a = a[idx].copy()
    a.X = sparse.csr_matrix(a.X, dtype=np.float32)
    return a


def group_col(a, args):
    if args.groupby:
        if args.groupby not in a.obs:
            sys.exit(f'no obs column {args.groupby}; have {list(a.obs.columns)}')
        return args.groupby
    for c in ('celltype', 'cell_type', 'leiden', 'stage_label', 'group'):
        if c in a.obs:
            return c
    return None


def mean_by(a, col):
    out = {}
    for g in pd.unique(a.obs[col].astype(str)):
        m = (a.obs[col].astype(str) == g).to_numpy()
        out[g] = (np.asarray(a.X[m].mean(0)).ravel(), int(m.sum()))
    return out


def cmd_info(args):
    a = load(args.data[0], args)
    X = a.X
    print('shape', a.shape, '| obs:', list(a.obs.columns), '| obsm:', list(a.obsm.keys()))
    print('value max', round(float(X.max()), 3), '| expm1 row-sum median', round(float(np.median(np.asarray(X.expm1().sum(1)).ravel())), 1),
          '| nonzero frac', round(X.nnz / np.prod(X.shape), 3))
    m = np.asarray(X.mean(0)).ravel()
    print('top mean genes', [a.var_names[i] for i in np.argsort(-m)[:20]])
    for c in a.obs.columns:
        v = a.obs[c]
        if v.dtype == object or str(v.dtype) == 'category' or v.nunique() < 30:
            print(f'{c}:', v.astype(str).value_counts().head(25).to_dict())
    for k in a.obsm:
        s = np.asarray(a.obsm[k], float)
        print(k, 'min', s.min(0).round(1), 'max', s.max(0).round(1))


def cmd_markers(args):
    import scanpy as sc
    a = load(args.data[0], args)
    col = group_col(a, args)
    a.obs[col] = a.obs[col].astype(str).astype('category')
    sizes = a.obs[col].value_counts()
    a = a[a.obs[col].isin(sizes[sizes >= 10].index).to_numpy()].copy()
    a.obs[col] = a.obs[col].cat.remove_unused_categories()
    sc.tl.rank_genes_groups(a, col, method='wilcoxon', n_genes=args.n)
    r = a.uns['rank_genes_groups']
    for g in r['names'].dtype.names:
        print(f'{g} (n={int((a.obs[col] == g).sum())}):', ', '.join(
            f'{n}({lfc:+.1f})' for n, lfc in zip(r['names'][g], r['logfoldchanges'][g])))


def cmd_composition(args):
    cols = {}
    for d in args.data:
        a = load(d, args)
        col = group_col(a, args)
        cols[d] = a.obs[col].astype(str).value_counts(normalize=True)
    t = pd.DataFrame(cols).fillna(0).round(3)
    print(t.sort_values(t.columns[0], ascending=False).to_string())


def cmd_compare(args):
    A, B = load(args.data[0], args), load(args.data[1], args)
    genes = [g for g in A.var_names if g in set(B.var_names)]
    A, B = A[:, genes], B[:, genes]
    ma, mb = np.asarray(A.X.mean(0)).ravel(), np.asarray(B.X.mean(0)).ravel()
    d = mb - ma
    print(f'{len(genes)} shared genes | pseudobulk corr {np.corrcoef(ma, mb)[0, 1]:.3f} | mean |diff| {np.abs(d).mean():.3f}')
    o = np.argsort(d)
    print('up in B:', ', '.join(f'{genes[i]}({d[i]:+.2f})' for i in o[::-1][:args.n]))
    print('down in B:', ', '.join(f'{genes[i]}({d[i]:+.2f})' for i in o[:args.n]))
    ca, cb = group_col(A, args), group_col(B, args)
    if ca and cb:
        ga, gb = mean_by(A, ca), mean_by(B, cb)
        pairs = dict(p.split('=') for p in args.pair.split(',')) if args.pair else {g: g for g in ga if g in gb}
        for x, y in pairs.items():
            if x in ga and y in gb and ga[x][1] >= 20 and gb[y][1] >= 20:
                dd = gb[y][0] - ga[x][0]
                oo = np.argsort(dd)
                print(f'[{x} (n={ga[x][1]}) -> {y} (n={gb[y][1]})] corr {np.corrcoef(ga[x][0], gb[y][0])[0, 1]:.3f} '
                      f'up: {", ".join(genes[i] for i in oo[::-1][:8])} | down: {", ".join(genes[i] for i in oo[:8])}')
        if not pairs:
            print('no shared group names; pass --pair "ourType=theirType,..."')


def cmd_cluster(args):
    import scanpy as sc
    a = load(args.data[0], args)
    sc.pp.pca(a, n_comps=min(30, a.n_vars - 1))
    sc.pp.neighbors(a, n_neighbors=15)
    sc.tl.leiden(a, resolution=args.res, key_added='leiden_new', flavor='igraph', n_iterations=2)
    col = group_col(a, args)
    print('clusters', a.obs.leiden_new.nunique())
    if col and col != 'leiden_new':
        print(pd.crosstab(a.obs.leiden_new, a.obs[col].astype(str)).to_string())
    if args.png:
        import matplotlib
        matplotlib.use('Agg')
        sc.tl.umap(a)
        sc.pl.umap(a, color=[c for c in ('leiden_new', col) if c], show=False, save=False)
        import matplotlib.pyplot as plt
        plt.savefig(args.png, dpi=110, bbox_inches='tight')
        print('saved', args.png)


def cmd_spatial(args):
    from sklearn.neighbors import NearestNeighbors
    a = load(args.data[0], args)
    key = next((k for k in ('spatial_3D', 'spatial', 'spatial_2D') if k in a.obsm), None)
    if key is None:
        sys.exit('no spatial coordinates in obsm')
    P = np.asarray(a.obsm[key], float)
    col = group_col(a, args)
    lab = a.obs[col].astype(str).to_numpy()
    types, codes = np.unique(lab, return_inverse=True)
    nn = NearestNeighbors(n_neighbors=args.k + 1).fit(P).kneighbors(P, return_distance=False)[:, 1:]
    T = len(types)

    def counts(c):
        M = np.zeros((T, T))
        np.add.at(M, (np.repeat(c, args.k), c[nn].ravel()), 1)
        return M
    obs = counts(codes)
    rng = np.random.default_rng(0)
    perm = np.stack([counts(rng.permutation(codes)) for _ in range(50)])
    z = (obs - perm.mean(0)) / (perm.std(0) + 1e-9)
    keep = np.bincount(codes, minlength=T) >= 20
    print(f'coords {key} dims {P.shape[1]} | k={args.k} | neighbourhood enrichment z (rows: cell, cols: neighbour)')
    print(pd.DataFrame(z[np.ix_(keep, keep)], index=types[keep], columns=types[keep]).round(1).to_string())
    c = P.mean(0)
    r_all = np.sqrt(((P - c) ** 2).sum(1))
    print('rms radius all', round(float(np.sqrt((r_all ** 2).mean())), 2))
    print('per-group median distance to centroid:',
          {t: round(float(np.median(r_all[codes == i])), 1) for i, t in enumerate(types) if keep[i]})


def cmd_geneset(args):
    from shinka_ve import harness
    go = harness.go_prior()
    a = load(args.data[0], args)
    genes = set(args.genes.split(',')) if args.genes else set()
    if args.go:
        kids = {}
        for t, ps in go['term_parents'].items():
            for p in ps:
                kids.setdefault(p, []).append(t)
        terms, stack = set(), [args.go]
        while stack:
            t = stack.pop()
            if t not in terms:
                terms.add(t)
                stack.extend(kids.get(t, []))
        genes |= {g for g, ts in go['gene_terms'].items() if terms & set(ts)}
        print(args.go, go['term_names'].get(args.go), f'| {len(terms)} terms incl. descendants | {len(genes)} genes')
    use = [g for g in a.var_names if g in genes]
    print(f'{len(use)} in this dataset:', ', '.join(use[:60]))
    if not use:
        return
    s = np.asarray(a[:, use].X.mean(1)).ravel()
    col = group_col(a, args)
    if col:
        print(pd.Series(s, index=a.obs[col].astype(str).to_numpy()).groupby(level=0).mean().sort_values(ascending=False)
              .round(3).to_string())
    else:
        print('mean score', round(float(s.mean()), 3))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('command', choices=['info', 'markers', 'composition', 'compare', 'cluster', 'spatial', 'geneset'])
    ap.add_argument('data', nargs='+')
    ap.add_argument('--filter')
    ap.add_argument('--max-cells', type=int, default=30000)
    ap.add_argument('--groupby')
    ap.add_argument('--n', type=int, default=15)
    ap.add_argument('--pair')
    ap.add_argument('--res', type=float, default=1.0)
    ap.add_argument('--png')
    ap.add_argument('--k', type=int, default=10)
    ap.add_argument('--go')
    ap.add_argument('--genes')
    args = ap.parse_args()
    globals()[f'cmd_{args.command}'](args)


if __name__ == '__main__':
    main()
