"""Published T1 metric panel scored on paired local target/reference draws."""
import warnings
import numpy as np
from fm.common import SPLITS, load_expression

_STAGE_CACHE = {}


def load_stage(name, genes):
    key = (name, tuple(genes))
    if key not in _STAGE_CACHE:
        _STAGE_CACHE[key] = load_expression(name, genes)
    return _STAGE_CACHE[key]


def target_and_reference(split, genes):
    s = SPLITS[split]
    return load_stage(s['target'], genes), load_stage(s['reference'], genes)


def score(pred, split, scoring_seeds):
    """Mean T1 headline over scoring seeds, per-seed headlines and mean per-metric skill (x100)."""
    from vec_local_score.local_score import score_many
    genes = list(pred.var_names)
    target, reference = target_and_reference(split, genes)
    cache = {f'/fm-memory/{k}': v for k, v in dict(prediction=pred, target=target, reference=reference).items()}
    per_seed, metrics = [], {}
    for s in scoring_seeds:
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            rows = score_many('T1', ['/fm-memory/prediction'], '/fm-memory/target', '/fm-memory/reference',
                              setting='heart', seed=s, cache=cache)
        for r in rows:
            per_seed.append(r['task_score'])
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
