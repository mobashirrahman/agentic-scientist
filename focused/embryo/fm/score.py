"""Official-scorer wrapper for T2 embryo: vec_local_score.score_many (veckit metrics, copy_last floor = reference
stage, split-half ceiling of the target) plus the official T2 headline structure gate, plus the native-occupancy
diagnostic used to keep predictions on one input embryo's own coordinate cloud."""
import sys
import warnings
from pathlib import Path

import numpy as np

from fm.common import SPLITS, STAGES

SHAPE = ('d2_shape', 'occupancy_dice', 'scale_log_ratio')
_VECKIT = Path('/scratch/user/virtual-embryo/vendor/veckit')
_STAGE_CACHE = {}


def load_stage(name, genes):
    import anndata as ad
    key = (name, tuple(genes))
    if key not in _STAGE_CACHE:
        a = ad.read_h5ad(STAGES[name]['file'])
        missing = [g for g in genes if g not in set(a.var_names)]
        if missing:
            raise KeyError(f'stage {name} lacks {len(missing)} prediction genes, e.g. {missing[:5]}')
        _STAGE_CACHE[key] = a[:, list(genes)].copy()
    return _STAGE_CACHE[key]


def native_occupancy(pred, stages, seed=0):
    """Official occupancy Dice of the prediction against the best input stage (1 = one native cloud)."""
    if str(_VECKIT) not in sys.path:
        sys.path.insert(0, str(_VECKIT))
    from common.shape_metrics import occupancy_dice
    p = np.asarray(pred.obsm['spatial_3D'], dtype=float)
    best = 0.0
    for a in stages:
        q = np.asarray(a.obsm['spatial_3D'], dtype=float)
        if len(q) and np.isfinite(q).all():
            best = max(best, occupancy_dice(p, q, seed=seed)[0])
    return float(best)


def t2_gated(rows):
    """Official T2 headline: shape points multiplied by min(1, neighbourhood skill / 50)."""
    nb = next((100 * r['skill'] for r in rows if r['metric'] == 'neighborhood_mmd'), 0.0)
    g = min(1.0, max(nb, 0.0) / 50.0)
    return float(sum(r['points'] * (g if r['metric'] in SHAPE else 1.0) for r in rows))


def target_and_reference(split, genes):
    s = SPLITS[split]
    return load_stage(s['target'], genes), load_stage(s['reference'], genes)


def score(pred, split, scoring_seeds):
    """Mean gated headline over scoring seeds, per-seed headlines and mean per-metric skill (x100)."""
    from vec_local_score.local_score import score_many
    genes = list(pred.var_names)
    target, reference = target_and_reference(split, genes)
    cache = {f'/fm-memory/{k}': v for k, v in dict(prediction=pred, target=target, reference=reference).items()}
    per_seed, metrics = [], {}
    for s in scoring_seeds:
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            rows = score_many('T2', ['/fm-memory/prediction'], '/fm-memory/target', '/fm-memory/reference',
                              setting='embryo', seed=s, cache=cache)
        for r in rows:
            per_seed.append(t2_gated(r['rows']))
            for row in r['rows']:
                metrics.setdefault(row['metric'], []).append(100 * float(row['skill']))
    sd = float(np.std(per_seed, ddof=1)) if len(per_seed) > 1 else None
    return dict(score=float(np.mean(per_seed)), seed_scores=per_seed, seed_sd=sd,
                metrics={k: float(np.mean(v)) for k, v in metrics.items()})


def combine(results, splits):
    """Weighted board score over splits (each split's weight from SPLITS); None if any split failed."""
    if any('score' not in results.get(s, {}) for s in splits):
        return None
    w = [SPLITS[s]['weight'] for s in splits]
    return float(sum(results[s]['score'] * x for s, x in zip(splits, w)) / sum(w))
