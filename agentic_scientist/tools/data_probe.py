"""Summarise an allowed dataset. Usage: python agentic_scientist/tools/data_probe.py T2/E8.5.h5ad [gene1,gene2,...]
Paths are relative to data/raw. Held-out evaluation targets are refused."""
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
DENY = json.loads((ROOT / 'agentic_scientist/config.json').read_text())['holdout_forbidden']
rel = sys.argv[1]
if any(d.lower() in rel.lower() for d in DENY):
    sys.exit('refused: held-out evaluation target')
import anndata as ad, numpy as np
a = ad.read_h5ad(ROOT / 'data/raw' / rel)
print('shape', a.shape, '| obs:', list(a.obs.columns), '| obsm:', list(a.obsm.keys()))
for c in ('celltype', 'cell_type', 'major_cell_type', 'leiden'):
    if c in a.obs:
        print(c, a.obs[c].value_counts().head(25).to_dict()); break
X = a.X.toarray() if hasattr(a.X, 'toarray') else np.asarray(a.X)
m = X.mean(0); print('top mean genes', [a.var_names[i] for i in np.argsort(-m)[:25]])
print('X range', float(X.min()), float(X.max()), 'mean nnz frac', float((X > 0).mean()))
if 'spatial_3D' in a.obsm:
    s = np.asarray(a.obsm['spatial_3D']); print('spatial_3D min', s.min(0).round(1), 'max', s.max(0).round(1))
if len(sys.argv) > 2:
    for g in sys.argv[2].split(','):
        if g in a.var_names:
            v = X[:, list(a.var_names).index(g)]; print(g, 'mean', round(float(v.mean()), 3), 'frac>0', round(float((v > 0).mean()), 3))
