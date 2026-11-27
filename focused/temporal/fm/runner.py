"""Run one workspace program on one split configuration and write a format-checked prediction.

Always started by the evaluation service inside Landlock: it can read only the harness, the Python environment, the
program snapshot and the INPUT stage files of the split (never the target), write only its output directory, and open
no TCP connection.

  python -I fm/runner.py --snapshot DIR --split NAME --seed N --out DIR
Writes OUT/pred.h5ad and OUT/meta.json (ok, n_cells, seconds, error_type, error, trace).
"""
import argparse
import importlib.util
import json
import sys
import time
import traceback
from pathlib import Path

import numpy as np  # noqa: E402

# Inside Landlock the run folder itself is not listable, so the harness module is loaded by file path (and under a
# name no agent module can shadow).
_spec = importlib.util.spec_from_file_location('fm_harness_common', Path(__file__).resolve().parent / 'common.py')
_c = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_c)
MIN_CELLS, SPLITS, STAGES, panel_genes, target_time = _c.MIN_CELLS, _c.SPLITS, _c.STAGES, _c.panel_genes, _c.target_time


def load_inputs(split, genes):
    stages = [_c.load_expression(name, genes) for name in SPLITS[split]['inputs']]
    for stage in stages:
        stage.obs_names_make_unique()
    return stages


def check_and_clean(pred, genes, min_cells, max_cells):
    import anndata as ad
    from scipy import sparse
    if not isinstance(pred, ad.AnnData):
        raise TypeError(f'predict() must return an AnnData, got {type(pred).__name__}')
    if not min_cells <= pred.n_obs <= max_cells:
        raise ValueError(f'prediction must have {min_cells}-{max_cells} cells for this configuration, got {pred.n_obs}')
    available = set(pred.var_names)
    missing = [g for g in genes if g not in available]
    if missing:
        raise ValueError(f'prediction lacks {len(missing)} panel genes, e.g. {missing[:5]}')
    if not pred.var_names.is_unique:
        raise ValueError('prediction var_names are not unique')
    if 'spatial_3D' in pred.obsm:
        raise ValueError('T1 prediction must not contain spatial coordinates')
    if list(pred.var_names) != genes:
        pred = pred[:, genes]
    X = sparse.csr_matrix(pred.X, dtype=np.float32)
    X.eliminate_zeros()
    if not np.isfinite(X.data).all() or (X.data < 0).any():
        raise ValueError('expression must be finite and non-negative (log1p CP10k)')
    out = ad.AnnData(X=X, var=pred.var[[]].copy())
    out.var_names = genes
    out.obs_names = [f'c{i}' for i in range(pred.n_obs)]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--snapshot', required=True)
    ap.add_argument('--split', required=True, choices=list(SPLITS))
    ap.add_argument('--seed', type=int, default=0)
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    meta = dict(split=a.split, seed=a.seed, ok=False)
    t0 = time.time()
    try:
        genes = panel_genes(a.split)
        spec = SPLITS[a.split]
        inputs = load_inputs(a.split, genes)
        times = [STAGES[n]['time'] for n in spec['inputs']]
        tp = Path(a.snapshot) / 'tuned_params.json'  # written only by the harness tuner (fm/tune.py)
        params = json.loads(tp.read_text()) if tp.exists() else {}
        min_cells = spec.get('min_cells', MIN_CELLS)
        context = dict(seed=a.seed, sampling=spec['sampling'], max_cells=spec['max_cells'],
                       min_cells=min_cells, n=3000, genes=list(genes), params=params)
        sys.path.insert(0, str(Path(a.snapshot).resolve()))
        mspec = importlib.util.spec_from_file_location('fm_program', Path(a.snapshot) / 'program.py')
        mod = importlib.util.module_from_spec(mspec)
        mspec.loader.exec_module(mod)
        t1 = time.time()
        pred = mod.predict(inputs, times, float(target_time(a.split)), context)
        meta['predict_seconds'] = round(time.time() - t1, 1)
        pred = check_and_clean(pred, genes, min_cells, spec['max_cells'])
        pred.write_h5ad(out / 'pred.h5ad', compression='gzip')
        meta.update(ok=True, n_cells=int(pred.n_obs))
    except BaseException as e:  # noqa: BLE001 - reported to the service
        meta.update(error_type=type(e).__name__, error=str(e)[:2000], trace=traceback.format_exc()[-6000:])
    meta['seconds'] = round(time.time() - t0, 1)
    (out / 'meta.json').write_text(json.dumps(meta, indent=1))
    return 0 if meta['ok'] else 1


if __name__ == '__main__':
    sys.exit(main())
