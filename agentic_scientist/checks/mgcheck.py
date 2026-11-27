"""Shared helpers for AgenticScientist sanity checks (not part of the agents' evaluator)."""
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from agentic_scientist import evaluate as _ev  # noqa: E402,F401  (registers heart_long / mab21l2 splits)
from shinka_ve import harness  # noqa: E402
from src.data import load_stage  # noqa: E402

DEV = _ev.SETS['dev']['splits']


def stages(split):
    spec = harness.SPLITS[split]
    inputs = [load_stage(p) for p in spec['inputs']]
    if spec['board'] == 'embryo':
        g = inputs[0].var_names[inputs[0].var_names.isin(inputs[1].var_names)]
        inputs = [a[:, g].copy() for a in inputs]
    ref = inputs[-1].copy()
    target = load_stage(spec['target'])[:, list(ref.var_names)].copy()
    return spec, inputs, ref, target


def score(pred, target, ref, split, seed=101):
    """Official local scorer on an explicit truth (lets the ceiling use one half of the target as truth)."""
    spec = harness.SPLITS[split]
    r, = harness.score_arrays(pred, target, ref, spec['task'], spec.get('setting', 'heart'), [seed])
    return float(r['task_score']), {row['metric']: round(float(row['skill']) * 100, 1) for row in r.get('rows', [])}


def dense(X):
    return X.toarray() if hasattr(X, 'toarray') else np.asarray(X)
