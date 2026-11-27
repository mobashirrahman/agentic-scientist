"""Preregistered local ablations. Each command handles one board sequentially."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import numpy as np
from scipy import sparse
from scipy.spatial import cKDTree
from agentic_scientist import evaluate
from agentic_scientist.artifacts import write_json
from agentic_scientist.composition import compare
from src.models import TemporalTransport, interpolate

H = evaluate.harness
N = 3000
SEEDS = (42, 101, 211)
SCORING = (301, 302, 303)

VARIANTS = {
    'temporal': ('baseline', 'composition', 'expression'),
    'heart': ('baseline', 'codex', 'geometry', 'expression', 'combined'),
    'embryo': ('baseline', 'geometry', 'combined'),
}
SPLITS = {
    'temporal': ('temporal_test_composition',),
    'heart': ('guard_heart_e85', 'guard_heart_e85_dis'),
    'embryo': ('guard_embryo_e80', 'embryo_early'),
}


def temporal(inputs, times, target, variant, seed):
    earlier, latest = inputs[-2:]
    interval = times[-1] - times[-2]
    model = TemporalTransport(earlier, latest, interval)
    base = model.predict(target - times[-1], state=0, composition=.5, seed=seed)
    if variant == 'baseline':
        return base
    old = TemporalTransport(inputs[0], earlier, times[1] - times[0])
    common = set(old.types) & set(model.types)
    old_type = {label: old.type_index[label] for label in common}
    labels = latest.obs['celltype_group'].to_numpy()
    row_type = np.array([model.type_index[label] for label in labels])
    if variant == 'composition':
        growth = model.growth.copy()
        for idx, label in enumerate(model.types):
            previous = old.growth[old_type[label]] if label in common else 0
            if previous * growth[idx] > 0:
                growth[idx] = np.sign(growth[idx]) * min(abs(previous), abs(growth[idx]))
            else:
                growth[idx] = 0
        probabilities = np.exp(growth[row_type])
        rows = np.random.default_rng(seed).choice(latest.n_obs, N, p=probabilities / probabilities.sum())
        return latest[rows].copy()
    x = base.X.toarray()
    for label in common:
        prior = old.drift[old_type[label]]
        current = model.drift[model.type_index[label]]
        delta = np.where(prior * current > 0, np.sign(current) * np.minimum(abs(prior), abs(current)), 0)
        rows = base.obs['celltype_group'].to_numpy() == label
        # Preserve observed sparsity and keep the shift small.
        x[rows] += (x[rows] > 0) * (.2 * delta)
    base.X = sparse.csr_matrix(np.maximum(x, 0))
    return base


def frame(coords):
    lo, hi = np.quantile(coords, [.01, .99], axis=0)
    return np.median(coords, axis=0), np.maximum(hi - lo, 1e-6)


def heart(inputs, times, target, variant, seed, sampling=None):
    if variant == 'codex':
        return evaluate.load(ROOT / 'humantrack/t2_heart').predict(
            'heart', inputs, times, target, dict(seed=seed, fit_seed=0, n=N, sampling=sampling, params={}))
    latest, earlier = inputs[-1], inputs[-2]
    baseline = TemporalTransport(earlier, latest, times[-1] - times[-2]).predict(
        target - times[-1], state=0, composition=0, seed=seed)
    xy = baseline.obsm['spatial_3D']
    center, size = frame(latest.obsm['spatial_3D'])
    prev_center, prev_size = frame(earlier.obsm['spatial_3D'])
    factor = min(2, (target - times[-1]) / (times[-1] - times[-2]))
    if variant in ('expression', 'combined'):
        source_xy = (earlier.obsm['spatial_3D'] - prev_center) / prev_size
        query_xy = (xy - center) / size
        current_labels = baseline.obs['celltype_group'].to_numpy()
        source_labels = earlier.obs['celltype_group'].to_numpy()
        expression = baseline.X.tolil()
        for label in set(current_labels) & set(source_labels):
            dest = np.flatnonzero(current_labels == label)
            source = np.flatnonzero(source_labels == label)
            tree = cKDTree(source_xy[source])
            distance, match = tree.query(query_xy[dest])
            # Replace one coherent patch per shared type with nearby complete profiles.
            radius = np.linalg.norm(query_xy[dest] - np.median(query_xy[dest], axis=0), axis=1)
            use = (radius <= np.quantile(radius, .25)) & (distance < .20)
            expression[dest[use], :] = earlier.X[source[match[use]], :]
        baseline.X = expression.tocsr()
    if variant in ('geometry', 'combined'):
        scale = np.exp(np.clip(.5 * factor * np.log(size / prev_size), -.18, .18))
        baseline.obsm['spatial_3D'] = (xy - center) * scale + center
    return baseline


def embryo(inputs, times, target, variant, seed):
    left, right = inputs
    fraction = (target - times[0]) / (times[-1] - times[0])
    pred = interpolate(left, right, fraction, seed=seed)
    if variant == 'baseline':
        return pred
    left_center, left_size = frame(left.obsm['spatial_3D'])
    right_center, right_size = frame(right.obsm['spatial_3D'])
    size = np.exp((1 - fraction) * np.log(left_size) + fraction * np.log(right_size))
    early = (left.obsm['spatial_3D'] - left_center) / left_size
    late = (right.obsm['spatial_3D'] - right_center) / right_size
    rng = np.random.default_rng(seed)
    slots = rng.choice(left.n_obs, N, replace=left.n_obs < N)
    source_labels = left.obs['celltype_group'].to_numpy()
    target_labels = right.obs['celltype_group'].to_numpy()
    if variant == 'warp':
        coords = pred.obsm['spatial_3D'].copy()
        labels = pred.obs['celltype_group'].to_numpy()
        early_donor = np.arange(len(coords)) < round(N * (1 - fraction))
        step = np.where(early_donor, fraction, fraction - 1)
        for label in set(source_labels) & set(target_labels):
            a, b = source_labels == label, target_labels == label
            if min(a.sum(), b.sum()) >= 20:
                offset = np.clip(np.median(late[b], axis=0) - np.median(early[a], axis=0), -.05, .05)
                selected = labels == label
                coords[selected] += step[selected, None] * offset * size
        pred.obsm['spatial_3D'] = coords
        return pred
    coords = early[slots].copy()
    for label in set(source_labels) & set(target_labels):
        a, b = source_labels == label, target_labels == label
        if min(a.sum(), b.sum()) >= 20:
            coords[source_labels[slots] == label] += fraction * np.clip(
                np.median(late[b], axis=0) - np.median(early[a], axis=0), -.15, .15)
    if variant == 'combined':
        # Pair profiles and sites in the same spatial ordering without reusing a site.
        donor_xyz = pred.obsm['spatial_3D'] / size
        def spatial_order(xyz):
            bins = np.floor((xyz + .5) * 8).astype(int)
            return np.lexsort((xyz[:, 2], xyz[:, 1], xyz[:, 0], bins[:, 2], bins[:, 1], bins[:, 0]))
        assigned = np.empty_like(coords)
        assigned[spatial_order(donor_xyz)] = coords[spatial_order(coords)]
        coords = assigned
    else:
        coords = coords[rng.permutation(N)]
    pred.obsm['spatial_3D'] = (coords * size).astype(np.float32)
    return pred


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('board', choices=VARIANTS)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--embryo-warp', action='store_true',
                        help='Run the separately registered mild geometry follow-up')
    args = parser.parse_args()
    board = args.board
    if args.embryo_warp and board != 'embryo':
        parser.error('--embryo-warp requires embryo')
    variants = ('warp',) if args.embryo_warp else VARIANTS[board]
    predict = {'temporal': temporal, 'heart': heart, 'embryo': embryo}[board]
    report = {}
    for split in SPLITS[board]:
        spec = H.SPLITS[split]
        inputs = [H.load_stage(path) for path in spec['inputs']]
        if board == 'embryo':
            genes = inputs[0].var_names.intersection(inputs[1].var_names, sort=False)
            inputs = [data[:, genes].copy() for data in inputs]
        ref = inputs[0] if board == 'embryo' else inputs[-1]
        rows = report[split] = {}
        for seed in SEEDS:
            for variant in variants:
                options = {'sampling': H.sampling_for(split)} if board == 'heart' else {}
                pred = predict(inputs, spec['times'], spec['time'], variant, seed, **options)
                if board == 'temporal':
                    cardiac = ref.obs.celltype.isin(set(evaluate._T1MAP['cardiac']) | {'Blood'})
                    result = compare(pred, ref, ref[cardiac])
                else:
                    score, metrics = H.score_split(pred, ref, split, SCORING)
                    result = dict(score=score, metrics=metrics)
                rows.setdefault(variant, {})[str(seed)] = result
                write_json(args.out, report)
                print(split, seed, variant, result.get('score', result.get('failures')), flush=True)


if __name__ == '__main__':
    main()
