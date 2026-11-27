"""Geo-seq (GSE171588, WT E6.5-E7.25 only) pseudobulk per embryo, and MERFISH pseudobulk, in log2 mean-FPKM space."""
import gzip, re
from pathlib import Path
import numpy as np, pandas as pd
D = Path(__file__).resolve().parents[2] / 'data/external_candidates/geoseq'

def embryo_table(f):
    t = pd.read_csv(f, sep='\t', index_col=0)
    t = t[~t.index.duplicated()].astype(float)
    if 'Log2' in f.name:            # stored as log2(FPKM+1)
        t = np.power(2.0, t) - 1
    return t.clip(lower=0)

def layer(col):                     # E=epiblast, M=mesoderm, else endoderm/positional bins
    s = col.split('_')[-1]
    s = re.sub(r'^\d+', '', s)
    return 'epi' if s.startswith('E') else 'mes' if s.startswith('M') else 'other'

def stage(st, layers=None):
    """{embryo: Series log2(mean FPKM + 1) over samples}"""
    out = {}
    for f in sorted(D.glob(f'GSE171588_E{st}_*.txt.gz')):
        t = embryo_table(f)
        if layers:
            t = t[[c for c in t.columns if layer(c) in layers]]
        out[f.name.split('_')[2]] = np.log2(t.mean(axis=1) + 1)
    return out

def merfish(a, genes):
    import scipy.sparse as sp
    X = a[:, genes].X
    X = X.toarray() if sp.issparse(X) else np.asarray(X)
    m = np.expm1(X).mean(0) if X.max() < 30 else X.mean(0)   # X is log1p-normalised
    return pd.Series(np.log2(m + 1e-3 * m.mean() + 1e-9), index=genes)
