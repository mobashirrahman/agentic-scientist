"""Embryo-setting anchor from the Extended Mouse Atlas (Imaz-Rosshandler et al. 2024; wild-type whole-embryo scRNA).

Rules s10 (embryo interpolation): no data strictly between E7.25 and E8.0. Kept: E6.5, E6.75, E7.0, E7.25 and
E8.0-E9.5. Dropped: E7.5, E7.75 and 'Mixed gastrulation' (pooled, no single stage). Author cell types, clusters and
embeddings are NOT kept (they were computed with the held-out stages). Genes: the released embryo MERFISH panel.
Cap: 6000 cells per stage (seeded). Run: .venv/bin/python -I scripts/v2/build_embryo_anchor.py
"""
import hashlib
import json
import sys
from pathlib import Path

import anndata as ad
import numpy as np
import pandas as pd
from scipy import sparse

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from shinka_ve import harness  # noqa: E402

RAW = ROOT / 'data/external/ema_raw/ExtendedMouseAtlas'
OUT = ROOT / 'data/external/embryo_anchor'
KEEP = {'E6.5': 6.5, 'E6.75': 6.75, 'E7.0': 7.0, 'E7.25': 7.25, 'E8.0': 8.0, 'E8.25': 8.25, 'E8.5': 8.5,
        'E8.75': 8.75, 'E9.0': 9.0, 'E9.25': 9.25, 'E9.5': 9.5}
CAP, SEED = 6000, 0


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    genes = list(harness.load_stage(harness.SPLITS['embryo_early']['inputs'][-1]).var_names)
    a = ad.read_h5ad(RAW / 'embryo_complete.h5ad', backed='r')
    stage = a.obs['stage'].astype(str)
    rng = np.random.default_rng(SEED)
    rows = []
    for st in KEEP:
        idx = np.where(stage.to_numpy() == st)[0]
        rows.extend(sorted(rng.choice(idx, min(CAP, len(idx)), replace=False)))
    rows = np.array(sorted(rows))
    sym = a.var['mgi_symbol'].astype(str).to_numpy()
    pick = {}
    for j, g in enumerate(sym):
        pick.setdefault(g, j)
    cols = [pick[g] for g in genes if g in pick]
    cols_arr = np.array(cols)
    X = sparse.vstack([sparse.csr_matrix(np.asarray(a.X[rows[i:i + 2000]])[:, cols_arr], dtype=np.float32)
                       for i in range(0, len(rows), 2000)]).tocsr()
    X.data = np.exp2(X.data) - 1  # atlas values are log2(1 + size-factor-scaled counts); undo so the harness
    b = ad.AnnData(X)              # re-normalises on the panel like the released data (log1p, 1e4 per cell)
    b.obs_names = list(a.obs['cell'].astype(str).to_numpy()[rows])
    b.var_names = [sym[j] for j in cols]
    b.obs['stage_days'] = stage.iloc[rows].map(KEEP).astype(float).to_numpy()
    b.obs['stage_label'] = stage.iloc[rows].to_numpy()
    b.obs['source'] = 'ExtendedMouseAtlas'
    assert not ((b.obs.stage_days > 7.25) & (b.obs.stage_days < 8.0)).any()
    p = OUT / 'extended_mouse_atlas_embryo.h5ad'
    b.write_h5ad(p, compression='gzip')
    man = dict(note='Embryo anchor (Rules s10: nothing strictly between E7.25 and E8.0). Disclosed in docs/EXTERNAL_SOURCES.md.',
               files={p.name: dict(source='Extended Mouse Atlas, Imaz-Rosshandler et al. 2024 (marionilab.github.io/ExtendedMouseAtlas)',
                                   stages_days=sorted(set(b.obs.stage_days.tolist())), perturbation=False,
                                   values='counts', cells=int(b.n_obs), genes=int(b.n_vars),
                                   cells_per_stage=b.obs.stage_label.value_counts().to_dict(),
                                   sha256=hashlib.sha256(p.read_bytes()).hexdigest())})
    (OUT / 'manifest.json').write_text(json.dumps(man, indent=1))
    print(b.shape, b.obs.stage_label.value_counts().to_dict())


if __name__ == '__main__':
    main()
