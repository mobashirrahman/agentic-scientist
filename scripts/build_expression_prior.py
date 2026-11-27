"""Whole-transcriptome expression prior for the T3 (perturbation) board: for every gene, how broadly and how strongly it
is expressed in the early embryo, overall and per cell type. Built from the Qiu et al. 2024 calibration cells already
vetted and disclosed for T1 (Theiler stages 12-13, about E8.0-E9.0; data/external/qiu2024/calibration_*.h5ad).

Why: the T3 test knockout (Ctnnb1) is NOT on the 500-gene MERFISH panel, so a program cannot measure its expression in
the inputs. Every knockout (dev Gata4, Mab21l2, Hand2; test Ctnnb1) gets the same prior through context, so the code
path that sizes the response is the one validated on dev.

Output: data/external/expression_prior/expression_prior.npz + manifest.json
  genes (G,), types (T,), frac_all (G,), mean_all (G,), frac_type (T, G), mean_type (T, G), n_type (T,)
  frac = fraction of cells with >= 1 count; mean = mean log1p(CP10k)

  .venv/bin/python -I scripts/build_expression_prior.py
"""
import hashlib
import json
from pathlib import Path

import anndata as ad
import numpy as np
import scipy.sparse as sp

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'data/external/qiu2024'
OUT = ROOT / 'data/external/expression_prior'


def main():
    files = sorted(SRC.glob('calibration_*.h5ad'))
    genes, n_by, nz_by, sum_by = None, {}, {}, {}
    for f in files:
        a = ad.read_h5ad(f)
        assert set(a.obs['group'].astype(str)) == {'calibration'}, f.name
        if genes is None:
            genes = np.array(a.var_names)
        assert np.array_equal(genes, np.array(a.var_names)), f'{f.name}: gene order differs'
        C = sp.csr_matrix(a.layers['counts'] if 'counts' in a.layers else a.X, dtype=np.float32)
        tot = np.asarray(C.sum(1)).ravel()
        L = sp.csr_matrix(sp.diags(1e4 / np.maximum(tot, 1)) @ C).log1p()
        types = a.obs['cell_type'].astype(str).to_numpy()
        for t in np.unique(types):
            m = types == t
            n_by[t] = n_by.get(t, 0) + int(m.sum())
            nz_by[t] = nz_by.get(t, 0) + np.asarray((C[m] > 0).sum(0)).ravel()
            sum_by[t] = sum_by.get(t, 0) + np.asarray(L[m].sum(0)).ravel()
        print(f'{f.name}: {a.n_obs} cells')
    types = sorted(t for t in n_by if n_by[t] >= 30)
    n = np.array([n_by[t] for t in types], dtype=np.float32)
    frac_type = np.vstack([nz_by[t] / n_by[t] for t in types]).astype(np.float16)
    mean_type = np.vstack([sum_by[t] / n_by[t] for t in types]).astype(np.float16)
    frac_all = (sum(nz_by[t] for t in types) / n.sum()).astype(np.float32)
    mean_all = (sum(sum_by[t] for t in types) / n.sum()).astype(np.float32)
    OUT.mkdir(parents=True, exist_ok=True)
    out = OUT / 'expression_prior.npz'
    np.savez_compressed(out, genes=np.asarray(genes, dtype=str), types=np.asarray(types, dtype=str), frac_all=frac_all, mean_all=mean_all,
                        frac_type=frac_type, mean_type=mean_type, n_type=n)
    man = dict(source='Qiu et al. 2024 Nature 626:1084 (doi 10.1038/s41586-024-07069-w), CELLxGENE census; '
                      'the calibration cells of data/external/qiu2024 (Theiler stages 12-13, ~E8.0-E9.0, wild type)',
               stages=['Theiler stage 12', 'Theiler stage 13'], perturbation=False,
               cells=int(n.sum()), genes=int(len(genes)), types=types,
               files={out.name: dict(sha256=hashlib.sha256(out.read_bytes()).hexdigest())})
    (OUT / 'manifest.json').write_text(json.dumps(man, indent=1))
    idx = {g: i for i, g in enumerate(genes)}
    for g in ('Ctnnb1', 'Gata4', 'Mab21l2', 'Hand2', 'Actb'):
        if g in idx:
            print(f'  {g:8s} frac_all {frac_all[idx[g]]:.2f} mean_all {mean_all[idx[g]]:.2f} '
                  f'types>20%: {int((frac_type[:, idx[g]] > 0.2).sum())}/{len(types)}')


if __name__ == '__main__':
    main()
