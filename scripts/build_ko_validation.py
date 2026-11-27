"""Build extra T3 validation splits from PUBLIC external knockout scRNA-seq with matched wild type (allowed data:
all stages <= E9.5, no Ctnnb1/Wnt-pathway or Gata4 alleles; disclosed in docs/EXTERNAL_SOURCES.md).

Output (data/external/ko_validation/<name>/): wt_<stage>.h5ad and ko_<stage>.h5ad in the T3 layout the harness feeds
programs: X = log1p(CP10k) over the 500-gene MERFISH panel (like the released stages; raw counts in layers['counts'];
genes absent from the source are zero), obs['celltype'] by label transfer from the released MERFISH stages (kNN on the
same representation), obsm['spatial_3D'] = zeros (no
coordinates in scRNA-seq; T3 metrics are non-spatial), obs['source'], obs['genotype'], obs['stage'].

  .venv/bin/python -I scripts/build_ko_validation.py hand2

Sources:
  hand2  de Soysa et al. 2019 Nature, GEO GSE126128 (10x, heart-region dissections, WT vs Hand2-null at E7.75/E8.25/E9.25)
  mef2c  Muncie-Vasic et al. 2025 Genes Dev, GEO GSE280543 (10x multiome snRNA, heart tube, WT vs Mef2c-null at E8.5/E9.0,
         2 embryos each; E7.75 not used). Fetched by scripts/ko_fetch/fetch_mef2c.sh (panel rows only, streamed).
  nkx25  Li et al. 2016 Dev Cell, GEO GSE76118 (Smart-seq-like single cardiac cells, HTSeq counts; WT E8.5 and E9.5
         Nkx2-5 wt/mutant cardiomyocytes; E10.5 and reporter/cell-line samples dropped).
"""
import gzip
import sys
from pathlib import Path

import anndata as ad
import numpy as np
import pandas as pd
import scipy.sparse as sp

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'data/external/ko_validation'
PANEL_REF = ['data/raw/T2/E8.5.h5ad', 'data/raw/T2/E8.75.h5ad', 'data/raw/T2/E9.5.h5ad']


def panel():
    return list(ad.read_h5ad(ROOT / PANEL_REF[1], backed='r').var_names)


def label_model(genes):
    """kNN cell-type classifier on log-normalised panel expression of the released MERFISH stages."""
    from sklearn.decomposition import PCA
    from sklearn.neighbors import KNeighborsClassifier
    Xs, ys = [], []
    for f in PANEL_REF:
        a = ad.read_h5ad(ROOT / f)[:, genes]
        Xs.append(a.X.toarray() if sp.issparse(a.X) else np.asarray(a.X))  # already log1p(CP10k)
        ys.append(a.obs['celltype'].astype(str).to_numpy())
    X, y = np.vstack(Xs), np.concatenate(ys)
    keep = y != 'Unknown'
    X, y = X[keep], y[keep]
    mu, sd = X.mean(0), X.std(0) + 1e-6
    pca = PCA(30, random_state=0).fit((X - mu) / sd)
    knn = KNeighborsClassifier(15, weights='distance').fit(pca.transform((X - mu) / sd), y)
    return lambda Z: knn.predict(pca.transform((Z - mu) / sd))


def lognorm(C):
    """log1p(CP10k) of a counts matrix over the panel genes (MERFISH totals are panel totals)."""
    C = sp.csr_matrix(C, dtype=np.float32)
    s = np.asarray(C.sum(1)).ravel()
    return sp.csr_matrix(sp.diags(1e4 / np.maximum(s, 1)) @ C).log1p()


def to_adata(counts, cells, genes_src, genes, meta):
    """counts: cells x genes_src (sparse/dense) -> T3 layout on the panel."""
    idx = {g: i for i, g in enumerate(genes_src)}
    cols = [idx.get(g) for g in genes]
    M = sp.csr_matrix(counts)
    X = sp.lil_matrix((M.shape[0], len(genes)), dtype=np.float32)
    have = [(j, c) for j, c in enumerate(cols) if c is not None]
    if have:
        jj, cc = zip(*have)
        X[:, list(jj)] = M[:, list(cc)].toarray().astype(np.float32)
    C = sp.csr_matrix(X)
    a = ad.AnnData(X=lognorm(C).astype(np.float32), obs=pd.DataFrame(meta, index=pd.Index(cells, name=None)),
                   var=pd.DataFrame(index=genes))
    a.layers['counts'] = C
    a.obsm['spatial_3D'] = np.zeros((a.n_obs, 3), np.float32)
    a.obsm['spatial'] = np.zeros((a.n_obs, 2), np.float32)
    return a, len(have)


def read_hand2_csv(path, genes):
    """GEO CSV: genes x cells, header = barcodes with a -<gem group> suffix. Stream it; keep panel genes only."""
    want = set(genes)
    rows, names = [], []
    with gzip.open(path, 'rt') as f:
        header = f.readline().rstrip('\n').split(',')[1:]
        cells = [h.strip('"') for h in header]
        for line in f:
            g, rest = line.split(',', 1)
            g = g.strip('"')
            if g in want:
                names.append(g)
                rows.append(np.array(rest.split(','), dtype=np.float32))
    M = sp.csr_matrix(np.vstack(rows).T)  # cells x panel genes present
    return cells, names, M


def build_hand2():
    raw = OUT / 'raw/hand2'
    genes = panel()
    lab = label_model(genes)
    groups = {  # file -> gem group -> (stage, genotype); from the GEO sample records of GSE126128
        'GSE126128_E775E825_WTKO_10X.csv.gz': {**{g: (7.75, 'WT') for g in (1, 2, 3, 4, 5)},
                                              **{g: (7.75, 'Hand2_KO') for g in (6, 7, 8)},
                                              **{g: (8.25, 'WT') for g in (9, 10)},
                                              **{g: (8.25, 'Hand2_KO') for g in (11, 12)}},
        'GSE126128_E925_WTKO_10X.csv.gz': {1: (9.25, 'WT'), 2: (9.25, 'WT'), 3: (9.25, 'Hand2_KO'), 4: (9.25, 'Hand2_KO')},
    }
    out = OUT / 'hand2'
    out.mkdir(parents=True, exist_ok=True)
    parts = []
    for fname, gmap in groups.items():
        cells, names, M = read_hand2_csv(raw / fname, genes)
        gem = np.array([int(c.rsplit('-', 1)[1]) for c in cells])
        stage = np.array([gmap[g][0] for g in gem])
        geno = np.array([gmap[g][1] for g in gem])
        meta = dict(source=f'GSE126128:{fname}', gem_group=gem, stage=stage, genotype=geno, time=stage)
        a, n = to_adata(M, [f'{fname[10:14]}_{c}' for c in cells], names, genes, meta)
        print(f'{fname}: {a.n_obs} cells, {n}/{len(genes)} panel genes present')
        parts.append(a)
    a = ad.concat(parts, merge='same')
    X = a.X.toarray()
    a.obs['celltype'] = lab(X)
    for (st, gt), sub in a.obs.groupby(['stage', 'genotype']):
        b = a[sub.index].copy()
        f = out / f"{'wt' if gt == 'WT' else 'ko'}_E{st:g}.h5ad"
        b.write_h5ad(f)
        print(f'  {f.name}: {b.n_obs} cells; top types {b.obs["celltype"].value_counts().head(5).to_dict()}')


def build_mef2c():
    raw = OUT / 'raw/mef2c'
    genes = panel()
    lab = label_model(genes)
    samples = {'GSM8600343': (8.5, 'WT'), 'GSM8600344': (8.5, 'WT'), 'GSM8600342': (8.5, 'Mef2c_KO'), 'GSM8600345': (8.5, 'Mef2c_KO'),
               'GSM8600338': (9.0, 'WT'), 'GSM8600341': (9.0, 'WT'), 'GSM8600339': (9.0, 'Mef2c_KO'), 'GSM8600340': (9.0, 'Mef2c_KO')}
    parts = []
    for g, (st, gt) in samples.items():
        bc = pd.read_csv(raw / f'{g}_barcodes.tsv.gz', header=None)[0].astype(str).tolist()
        feats = pd.read_csv(raw / f'{g}_features.tsv.gz', sep='\t', header=None)
        keep = [int(x) for x in open(raw / f'{g}_keep.txt')]
        names = feats.iloc[[k - 1 for k in keep], 1].tolist()
        pos = {k: i for i, k in enumerate(keep)}
        m = pd.read_csv(raw / f'{g}_panel.mtx', sep=' ', header=None, comment='#', names=['r', 'c', 'v'])
        M = sp.csr_matrix((m.v.to_numpy(np.float32), (m.c.to_numpy() - 1, m.r.map(pos).to_numpy())), shape=(len(bc), len(keep)))
        tot = np.asarray(M.sum(1)).ravel()
        ok = tot >= 200                      # drop empty / ambient barcodes (panel-count floor)
        meta = dict(source=f'GSE280543:{g}', sample=g, stage=st, genotype=gt, time=st)
        a, n = to_adata(M[ok], [f'{g}_{b}' for b, k in zip(bc, ok) if k], names, genes, meta)
        print(f'{g} E{st} {gt}: {a.n_obs} cells (of {len(bc)}), {n}/{len(genes)} panel genes')
        parts.append(a)
    write_groups(ad.concat(parts, merge='same'), lab, OUT / 'mef2c')


def build_nkx25():
    import json
    raw = OUT / 'raw/nkx25'
    genes = panel()
    lab = label_model(genes)
    sym = {}
    for f in (OUT / 'raw/mef2c').glob('*_features.tsv.gz'):   # Ensembl -> symbol (same mm10 10x reference)
        t = pd.read_csv(f, sep='\t', header=None)
        sym.update(dict(zip(t[0], t[1])))
        break
    titles = json.loads((raw / 'gsm_titles.json').read_text())
    groups = {'e8.5_A_': (8.5, 'WT'), 'e8.5_V_': (8.5, 'WT'), 'e9.5_Nkx2.5wt': (9.5, 'WT'), 'e9.5_Nkx2.5mut': (9.5, 'Nkx2-5_KO')}
    rows, cells, meta = [], [], dict(source=[], stage=[], genotype=[], time=[])
    ens = None
    for f in sorted((raw / 'cells').glob('GSM*.txt.gz')):
        gsm = f.name.split('_')[0]
        hit = [v for k, v in groups.items() if titles.get(gsm, '').startswith(k)]
        if not hit:
            continue
        t = pd.read_csv(f, sep='\t', header=None, index_col=0)[1]
        t = t[~t.index.str.startswith('__')]
        if ens is None:
            ens = t.index
        rows.append(t.reindex(ens).fillna(0).to_numpy(np.float32))
        cells.append(gsm)
        st, gt = hit[0]
        for k, v in (('source', f'GSE76118:{gsm}'), ('stage', st), ('genotype', gt), ('time', st)):
            meta[k].append(v)
    names = [sym.get(e, e) for e in ens]
    M = sp.csr_matrix(np.vstack(rows))
    a, n = to_adata(M, cells, names, genes, meta)
    tot = np.asarray(a.layers['counts'].sum(1)).ravel()
    a = a[tot >= 500].copy()               # plate-based: drop failed wells
    print(f'nkx25: {a.n_obs} cells, {n}/{len(genes)} panel genes')
    # Sorted cardiomyocytes, ~130-160 cells per group: the official T3 scorer runs a 30-component PCA per cell type, so
    # keep the one type with enough cells in every group (ventricular CMs, Nkx2-5's main domain).
    write_groups(a, lab, OUT / 'nkx25', only='V-CM')


def write_groups(a, lab, out, only=None):
    out.mkdir(parents=True, exist_ok=True)
    a.obs['celltype'] = lab(a.X.toarray())
    if only:
        a = a[a.obs['celltype'] == only].copy()
    for (st, gt), sub in a.obs.groupby(['stage', 'genotype']):
        b = a[sub.index].copy()
        f = out / f"{'wt' if gt == 'WT' else 'ko'}_E{st:g}.h5ad"
        b.write_h5ad(f)
        print(f'  {f.name}: {b.n_obs} cells; top types {b.obs["celltype"].value_counts().head(5).to_dict()}')


if __name__ == '__main__':
    {'hand2': build_hand2, 'mef2c': build_mef2c, 'nkx25': build_nkx25}[sys.argv[1]]()
