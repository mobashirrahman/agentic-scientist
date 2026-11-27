"""Heart late anchor from Feulner et al. 2024 (GEO GSE150817, Drop-seq, dissected wild-type hearts).
Rules s10: heart window excludes >E9.5..E13.5; E14.5/E16.5/E18.5 kept (P0/P4/P7 dropped). Raw counts stored;
the harness log-normalises on the panel. Run: .venv/bin/python -I scripts/v2/build_heart_anchor_feulner.py
"""
import gzip
import hashlib
import json
from pathlib import Path

import anndata as ad
import numpy as np
import pandas as pd
from scipy import sparse

ROOT = Path(__file__).resolve().parents[2]
RAW, OUT = ROOT / 'data/external/feulner2024_raw', ROOT / 'data/external/heart_anchor'
DAYS = {'E14.5': 14.5, 'E16.5': 16.5, 'E18.5': 18.5}


def main():
    OUT.mkdir(exist_ok=True)
    meta = pd.read_csv(RAW / 'GSE150817_perinatheart.metadata.final_cells.tsv.gz', sep='\t', index_col=0)
    with gzip.open(RAW / 'GSE150817_perinatheart.raw_umi_counts.final_cells.tsv.gz', 'rt') as f:
        cells = f.readline().rstrip('\n').split('\t')[1:]
        idx = np.where(np.array([meta.Age.get(c) in DAYS for c in cells]))[0]
        genes, rows = [], []
        for line in f:
            p = line.rstrip('\n').split('\t')
            genes.append(p[0])
            rows.append(sparse.csr_matrix(np.asarray(p[1:], dtype=np.float32)[idx]))
    cs = [cells[i] for i in idx]
    a = ad.AnnData(sparse.vstack(rows).T.tocsr())
    a.var_names, a.obs_names = genes, cs
    a.var_names_make_unique()
    m = meta.loc[cs]
    a.obs['stage_days'] = m.Age.map(DAYS).astype(float).values
    a.obs['age'] = m.Age.values
    a.obs['cell_type'] = m.cell_type.astype(str).values
    a.obs['replicate'] = m.Biological_replicate.astype(str).values
    a.obs['source'] = 'Feulner2024_GSE150817'
    p = OUT / 'feulner2024_heart_E14.5-E18.5.h5ad'
    a.write_h5ad(p, compression='gzip')
    man = dict(note='Late-stage wild-type heart anchors (Rules s10: after E13.5, disclosed). Per-cell obs[stage_days] checked by shinka_ve/harness.load_anchor.',
               files={p.name: dict(source='Feulner et al. 2024 bioRxiv 10.1101/2024.03.05.583423; GEO GSE150817 (perinatheart, Drop-seq, dissected whole hearts, wild type)',
                                   stages_days=sorted(set(a.obs.stage_days.tolist())), perturbation=False, values='counts',
                                   cells=int(a.n_obs), sha256=hashlib.sha256(p.read_bytes()).hexdigest(),
                                   cells_per_stage=a.obs.age.value_counts().to_dict(), cell_types=sorted(set(a.obs.cell_type)))})
    (OUT / 'manifest.json').write_text(json.dumps(man, indent=1))
    print(a.shape, a.obs.age.value_counts().to_dict())


if __name__ == '__main__':
    main()
