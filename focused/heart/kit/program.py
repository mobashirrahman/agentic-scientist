"""Observed-donor heart controls for the AgenticScientist study."""
import re

import numpy as np

CHAMBER = re.compile(r'CM$|^Chamber-Endo$|EndoMT|^Epi$|^Proepi$|^DMP$')


def chamber_cells(stage):
    labels = stage.obs.get('celltype')
    if labels is None:
        raise ValueError('Chamber crop requires the released celltype annotation')
    keep = np.fromiter((bool(CHAMBER.search(str(label))) for label in labels), dtype=bool, count=stage.n_obs)
    if not np.any(keep):
        raise ValueError('No chamber-associated cells in input')
    return stage[keep]


def size(stage):
    xyz = np.asarray(stage.obsm['spatial_3D'], float)
    return float(np.sqrt(np.mean(np.sum((xyz - xyz.mean(axis=0)) ** 2, axis=1))))


def predict(inputs, times, target_time, context):
    mode = context.get('params', {}).get('control', 'copy_last')
    if mode not in {'copy_last', 'crop', 'crop_scale'}:
        raise ValueError(f'Unknown control {mode}')
    crop = mode != 'copy_last' and context['dissection'] == 'heart_chambers_only'
    stages = [chamber_cells(a) for a in inputs] if crop else inputs
    last = stages[-1]
    rng = np.random.default_rng(context['seed'])
    idx = rng.choice(last.n_obs, context['max_cells'], replace=last.n_obs < context['max_cells'])
    out = last[idx].copy()
    if mode == 'crop_scale' and target_time > times[-1]:
        radii = np.log(np.maximum([size(a) for a in stages], 1e-9))
        hourly = np.median(np.diff(radii) / np.diff(times))
        growth = np.exp(np.clip(hourly * (target_time - times[-1]), 0, np.log(2)))
        xyz = np.asarray(out.obsm['spatial_3D'], float)
        out.obsm['spatial_3D'] = (xyz - xyz.mean(axis=0)) * growth
    return out
