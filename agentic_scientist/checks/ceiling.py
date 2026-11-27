"""Split-half ceiling per dev split, as the organisers define it: half of the real target scored against the other half.
Shows how much headroom each board really has.
  .venv/bin/python agentic_scientist/checks/ceiling.py
"""
import json
from concurrent.futures import ProcessPoolExecutor

import numpy as np

from mgcheck import DEV, ROOT, score, stages


def run(split):
    spec, _, ref, target = stages(split)
    out = []
    for seed in (0, 1):
        idx = np.random.default_rng(seed).permutation(target.n_obs)
        a, b = target[idx[: len(idx) // 2]].copy(), target[idx[len(idx) // 2:]].copy()
        out.append(score(a, b, ref, split)[0])
    return split, dict(board=spec['board'], ceiling=round(float(np.mean(out)), 2), halves=[round(x, 2) for x in out])


if __name__ == '__main__':
    with ProcessPoolExecutor(4) as pool:
        rows = dict(pool.map(run, DEV))
    json.dump(rows, open(ROOT / 'agentic_scientist/checks/ceiling.json', 'w'), indent=1)
    for k, v in rows.items():
        print(k, v)
