"""Virtual Embryo Challenge predictor (evolvable). Seed = second human candidate.

predict(board, inputs, times, target_time, context) -> AnnData; see shinka_ve/harness.py.
Helpers from src.v2 may be used, extended, or replaced by new code inside the block.
"""
import os as _os
import sys as _sys
_sys.path.insert(0, _os.environ.get('VE_ROOT', '/scratch/user/virtual-embryo'))
import numpy as np
import anndata as ad
from scipy import sparse

from src.v2.transport import LatentFlow, SpatialInterpolant, lineages, as_dense, normalize_log
from src.v2.complexity import ComplexityPerturbation
from src.v2.anchor import AnchorFlow


# EVOLVE-BLOCK-START
def predict_temporal(inputs, times, target_time, context):
    """T1: extrapolate with external anchor drift from Qiu 2024 atlas."""
    earlier, latest = inputs[-2], inputs[-1]
    interval = times[-1] - times[-2]
    horizon = target_time - times[-1]
    ext = context.get('external')
    if ext is not None:
        model = AnchorFlow(earlier, latest, ext, times[-2], times[-1], 15.0, seed=context['fit_seed'])
        return model.predict(horizon, n=context['n'], seed=context['seed'], state=0.35, growth=0.25, weight=1.0)
    model = LatentFlow(earlier, latest, interval, seed=context['fit_seed'])
    return model.predict(horizon, n=context['n'], seed=context['seed'], state=0.35, growth=0.25)


def predict_heart(inputs, times, target_time, context):
    """T2 heart: extrapolate a spatial (MERFISH-like, ~500 genes) heart population with 3D coords."""
    earlier, latest = inputs[-2], inputs[-1]
    interval = times[-1] - times[-2]
    horizon = target_time - times[-1]
    model = LatentFlow(earlier, latest, interval, seed=context['fit_seed'])
    return model.predict(horizon, n=context['n'], seed=context['seed'],
                         state=0.0, growth=0.0, deformation=0.25, scale=0.5)


def predict_embryo(inputs, times, target_time, context):
    """T2 embryo: interpolate a whole-embryo spatial population between two bracketing stages."""
    left, right = inputs[0], inputs[-1]
    fraction = (target_time - times[0]) / (times[-1] - times[0])
    model = SpatialInterpolant(left, right, seed=context['fit_seed'])
    return model.predict(fraction, n=context['n'], seed=context['seed'], mode='transport', deformation=0.5)


def predict_perturbation(inputs, times, target_time, context):
    """T3: predict a conditional knockout (context['knockout']) from WT stages only."""
    earlier, wt = inputs[-2], inputs[-1]
    model = ComplexityPerturbation(earlier, wt, seed=context['fit_seed'])
    return model.predict(strength=0.5, delay=0.0, n=context['n'], seed=context['seed'])


def predict(board, inputs, times, target_time, context):
    fn = {'temporal': predict_temporal, 'heart': predict_heart,
          'embryo': predict_embryo, 'perturbation': predict_perturbation}[board]
    return fn(inputs, times, target_time, context)
# EVOLVE-BLOCK-END


def run_experiment(split: str, seed: int = 101, fit_seed: int = 0, scoring_seeds=(101, 102)):
    """Entrypoint called by evaluate.py (not evolvable)."""
    import sys
    module = sys.modules[__name__]
    from shinka_ve.harness import run_split, score_split, SPLITS
    pred, reference = run_split(module, split, seed, fit_seed)
    score, metrics = score_split(pred, reference, split, list(scoring_seeds))
    return dict(split=split, board=SPLITS[split]['board'], score=score, metrics=metrics)
