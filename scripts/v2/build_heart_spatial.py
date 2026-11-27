"""Build the heart spatial late anchor from GSE282547 Slide-seq (wild-type, E14.5 and E15.5 only).

Rules s10: heart extrapolation window excludes after E9.5 through E13.5; later stages are allowed if disclosed.
Only the pure E14.5/E15.5 Slide-seq pucks are used. Excluded on purpose: E10.5-E13.5 pucks, the Wt1CreER-DTA
mutant, and the mixed Visium sections (e17_e11 contains E11.5; p2_e14 is ambiguous).
Each puck is first exported from its Seurat object by scripts/v2/export_slideseq.R (counts, beads, meta, coords).

Output: data/external/heart_spatial/gse282547_slideseq_<sample>.h5ad with raw counts (log-normalised on the panel by
the harness), obs stage_days / cell_type (RCTD first_type) / spot_class, obsm['spatial'] = puck x, y (Slide-seq
puck units, not microns), and a manifest.json read by shinka_ve.harness.load_anchor.
Run: .venv/bin/python -I scripts/v2/build_heart_spatial.py e14_1 e14_2 e15_1 e15_2
"""
import hashlib
import json
import sys
from pathlib import Path

import anndata as ad
import numpy as np
import pandas as pd
from scipy import io, sparse

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / 'data/external/gse282547_raw'
OUT = ROOT / 'data/external/heart_spatial'
DAYS = {'e14': 14.5, 'e15': 15.5}
GSM = {'e14_1': 'GSM8645806', 'e14_2': 'GSM8645807', 'e15_1': 'GSM9065771', 'e15_2': 'GSM9065772'}


def build(tag):
    day = DAYS[tag.split('_')[0]]
    X = sparse.csr_matrix(io.mmread(RAW / f'{tag}_counts.mtx').T, dtype=np.float32)
    genes = (RAW / f'{tag}_genes.txt').read_text().split('\n')[:X.shape[1]]
    beads = (RAW / f'{tag}_beads.txt').read_text().split('\n')[:X.shape[0]]
    meta = pd.read_csv(RAW / f'{tag}_meta.csv', index_col=0).loc[beads]
    co = pd.read_csv(next(RAW.glob(f'{tag}_coords_*.csv')), index_col=0).loc[beads]
    a = ad.AnnData(X)
    a.var_names, a.obs_names = genes, beads
    a.var_names_make_unique()
    a.obs['stage_days'] = day
    a.obs['cell_type'] = meta['first_type'].astype(str).values
    a.obs['spot_class'] = meta['spot_class'].astype(str).values
    a.obs['sample'] = tag
    a.obsm['spatial'] = co[['x', 'y']].to_numpy(float)
    p = OUT / f'gse282547_slideseq_{tag}.h5ad'
    a.write_h5ad(p, compression='gzip')
    return p.name, dict(source=f'GSE282547 Slide-seq {GSM[tag]} (developing mouse heart spatial atlas, wild type)',
                        stages_days=[day], perturbation=False, values='counts', cells=int(a.n_obs),
                        coords='obsm[spatial]: 2D puck units (not microns), one section',
                        cell_types=sorted(set(a.obs.cell_type)), sha256=hashlib.sha256(p.read_bytes()).hexdigest())


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    mp = OUT / 'manifest.json'
    man = json.loads(mp.read_text()) if mp.exists() else dict(
        note='Heart spatial late anchors (Rules s10: after E13.5, disclosed). GSE282547 Slide-seq E14.5/E15.5 only.',
        files={})
    for tag in sys.argv[1:]:
        name, meta = build(tag)
        man['files'][name] = meta
        print(name, meta['cells'], meta['stages_days'], len(meta['cell_types']), 'types', flush=True)
    mp.write_text(json.dumps(man, indent=1))


if __name__ == '__main__':
    main()
