"""Score the organisers' adversarial controls (and floors) with OUR local scorer on every dev split.

Each control is wrong by construction; a control above the floor (50) means our local scorer has a hole
that agents could exploit on dev but not on the real board.
  .venv/bin/python agentic_scientist/checks/controls.py [--out agentic_scientist/checks/controls.json]
"""
import argparse
import json
from concurrent.futures import ProcessPoolExecutor

import numpy as np
from scipy import sparse

from mgcheck import DEV, ROOT, dense, score, stages


def controls(spec, ref, target, rng):
    X = dense(ref.X)
    out = {}
    def mk(x, coords=None):
        a = ref.copy(); a.X = sparse.csr_matrix(np.clip(x, 0, None).astype(np.float32))
        if coords is not None:
            a.obsm['spatial_3D'] = coords
        return a
    if spec['task'] in ('T1', 'T2'):
        out['floor_copy_last'] = mk(X)
        out['ctrl_scale_ref'] = mk(X * 2.0)
    if spec['task'] == 'T1':
        out['ctrl_shrink_ref'] = mk(X * 0.99)
        out['ctrl_one_cell'] = mk(np.tile(X.mean(0), (X.shape[0], 1)))
    if spec['task'] == 'T2':
        C = np.asarray(ref.obsm['spatial_3D']); T = np.asarray(target.obsm['spatial_3D'])
        out['ctrl_random_cube'] = mk(X, rng.uniform(T.min(0), T.max(0), size=C.shape))
        Cc = C - C.mean(0)
        out['ctrl_squashed_ref'] = mk(X, Cc * np.array([4.0, 1.0, 0.25]) + C.mean(0))
    if spec['task'] == 'T3':
        out['floor_wt_identity'] = mk(X)
        out['ctrl_scale_wt'] = mk(X * 2.0)
        out['ctrl_shrink_wt'] = mk(X * 0.75)
        true_shift = dense(target.X).mean(0) - X.mean(0)
        v = rng.normal(size=X.shape[1]); v *= np.linalg.norm(true_shift) / np.linalg.norm(v)
        out['ctrl_random_dir'] = mk(X + v)
    return out


def run(split):
    rng = np.random.default_rng(0)
    spec, _, ref, target = stages(split)
    res = {}
    for name, pred in controls(spec, ref, target, rng).items():
        s, m = score(pred, target, ref, split)
        res[name] = dict(score=round(s, 2), metrics=m)
    return split, res


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('--out', default=str(ROOT / 'agentic_scientist/checks/controls.json')); a = ap.parse_args()
    with ProcessPoolExecutor(4) as pool:
        rows = dict(pool.map(run, DEV))
    json.dump(rows, open(a.out, 'w'), indent=1)
    holes = [(sp, n, r['score']) for sp, d in rows.items() for n, r in d.items() if n.startswith('ctrl') and r['score'] > 50.5]
    for sp, d in rows.items():
        print(sp, {n: r['score'] for n, r in d.items()})
    print('HOLES (control above floor):', holes or 'none')
