"""Compare scGPT and PCA as donor selectors for retrospective T2 heart forecasts."""
import argparse
import json
from pathlib import Path
import sys

import anndata as ad
import numpy as np
from sklearn.decomposition import PCA
from sklearn.neighbors import NearestNeighbors
from sklearn.preprocessing import normalize

from scgpt_audit import REFERENCE, ROOT, digest, one_to_one
from scgpt_frozen import scgpt_embeddings

sys.path.insert(0, str(ROOT / 'focused/heart'))

from fm.common import SPLITS, STAGES, panel_genes, target_time, write_json
from fm.pilot import PREDICTION_SEEDS, SCORING_SEEDS, SPLIT_NAMES

POOL_SIZE = 4096
POOL_SEED = 83
EMBED_SEED = 42
DIMENSIONS = 32
NEIGHBORS = 64
OUTPUT_CELLS = 3000


def sample_stage(stage, panel):
    path = STAGES[stage]['file']
    source = ad.read_h5ad(path, backed='r')
    try:
        rng = np.random.default_rng(POOL_SEED)
        idx = np.sort(rng.choice(source.n_obs, min(POOL_SIZE, source.n_obs), replace=False))
        return source[idx, panel].to_memory()
    finally:
        source.file.close()


def matrix(cells, genes):
    x = cells[:, genes].X
    return x.toarray() if hasattr(x, 'toarray') else np.asarray(x)


def donor_weights(earlier, latest, horizon, interval):
    """Estimate changes in state frequency from observed nearest neighbors."""
    points = normalize(PCA(DIMENSIONS, svd_solver='randomized', random_state=EMBED_SEED)
                       .fit_transform(np.vstack((earlier, latest))))
    n_early = len(earlier)
    query_idx = np.arange(n_early, len(points))
    neighbors = NearestNeighbors(n_neighbors=NEIGHBORS + 1, metric='cosine')
    indices = neighbors.fit(points).kneighbors(points[query_idx], return_distance=False)
    keep = indices != query_idx[:, None]
    keep &= np.cumsum(keep, axis=1) <= NEIGHBORS
    now = ((indices >= n_early) & keep).sum(axis=1)
    before = NEIGHBORS - now
    density_ratio = ((now + 1) / (before + 1)) * (n_early / len(latest))
    log_change = np.clip(np.log(density_ratio), -np.log(2), np.log(2))
    return 0.5 * min(horizon / interval, 2.0) * log_change


def predict(cells, log_weights, seed):
    noise = np.random.default_rng(seed).gumbel(size=cells.n_obs)
    take = min(OUTPUT_CELLS, cells.n_obs)
    order = np.argpartition(noise + log_weights, -take)[-take:]
    return cells[np.sort(order)].copy()


def make_predictions(stages, representations):
    predictions = {}
    for name in SPLIT_NAMES:
        earlier, latest = SPLITS[name]['inputs'][-2:]
        assert SPLITS[name]['target'] not in (earlier, latest)
        t_early, t_latest = STAGES[earlier]['time'], STAGES[latest]['time']
        weights = {'uniform_donor': np.zeros(stages[latest].n_obs)}
        for arm, latent in representations.items():
            weights[arm] = donor_weights(latent[earlier], latent[latest],
                                         target_time(name) - t_latest, t_latest - t_early)
        predictions[name] = {arm: [predict(stages[latest], w, seed) for seed in PREDICTION_SEEDS]
                             for arm, w in weights.items()}
    return predictions


def score_predictions(predictions):
    from fm.score import score

    results = {}
    for name, arms in predictions.items():
        results[name] = {}
        for arm, samples in arms.items():
            draws = [score(sample, name, SCORING_SEEDS) for sample in samples]
            result = {
                'headline': float(np.mean([d['score'] for d in draws])),
                'metrics': {k: float(np.mean([d['metrics'][k] for d in draws])) for k in draws[0]['metrics']},
                'prediction_draws': draws,
            }
            results[name][arm] = result
            print(f"{name:10} {arm:21} {result['headline']:.3f}", flush=True)
    return results


def deltas(results):
    comparison = {}
    for name, arms in results.items():
        scgpt, pca = arms['scgpt'], arms['pca']
        comparison[name] = {
            'headline': scgpt['headline'] - pca['headline'],
            'prediction_seed_deltas': [a['score'] - b['score'] for a, b in
                                       zip(scgpt['prediction_draws'], pca['prediction_draws'], strict=True)],
            'metrics': {m: scgpt['metrics'][m] - pca['metrics'][m] for m in pca['metrics']},
        }
    return comparison


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model-dir', type=Path, default=REFERENCE / 'whole-human')
    parser.add_argument('--upstream-source', type=Path, default=ROOT / 'vendor/scGPT')
    parser.add_argument('--device', default='cuda')
    parser.add_argument('--out', type=Path, default=ROOT / 'results/scgpt_heart_forecast.json')
    args = parser.parse_args()
    paths = {name: args.model_dir / name for name in ('args.json', 'vocab.json', 'best_model.pt')}
    vocab = json.loads(paths['vocab.json'].read_text())
    orthologs = REFERENCE / 'mgi_homology.tsv'
    mapping = one_to_one(orthologs)
    panel = panel_genes()
    matched = [gene for gene in panel if mapping.get(gene) in vocab]
    stage_names = sorted({stage for name in SPLIT_NAMES for stage in SPLITS[name]['inputs'][-2:]},
                         key=lambda stage: STAGES[stage]['time'])
    stages = {stage: sample_stage(stage, panel) for stage in stage_names}
    matrices = {stage: matrix(stages[stage], matched) for stage in stage_names}
    print(f'Encoding {sum(map(len, matrices.values()))} observed donor cells on {len(matched)} matched genes',
          flush=True)
    frozen, random, loaded = scgpt_embeddings(np.vstack(list(matrices.values())), [mapping[g] for g in matched],
                                              args.model_dir, args.device, args.upstream_source, EMBED_SEED)
    if not np.isfinite(frozen).all() or not np.isfinite(random).all():
        raise RuntimeError('Encoder produced nonfinite values')
    boundaries = np.cumsum([len(x) for x in matrices.values()])[:-1]
    features = {'pca': matrices,
                'scgpt': dict(zip(stage_names, np.split(frozen, boundaries), strict=True)),
                'random_encoder': dict(zip(stage_names, np.split(random, boundaries), strict=True))}
    # Complete and freeze all predicted populations before opening the scoring targets.
    predictions = make_predictions(stages, features)
    results = score_predictions(predictions)
    changes = deltas(results)
    advance = (changes['ho_long']['headline'] >= 0.75
               and min(changes['ho_long']['prediction_seed_deltas']) >= 0
               and all(changes[name]['headline'] >= -0.5 for name in ('val_heart', 'ho_heart')))
    write_json(args.out, {
        'scope': 'Retrospective donor-selector experiment; no hidden test target and no independent specimens.',
        'primary': 'ho_long',
        'criterion': 'At least +0.75 vs PCA on ho_long, both paired prediction draws nonnegative, '
                     'neither shorter replay below -0.50.',
        'advance': advance,
        'matched_genes': len(matched), 'output_genes': len(panel), 'output_cells': OUTPUT_CELLS,
        'orthology_sha256': digest(orthologs), 'device': args.device,
        'pool_seed': POOL_SEED, 'embedding_seed': EMBED_SEED,
        'prediction_seeds': PREDICTION_SEEDS, 'scoring_seeds': SCORING_SEEDS,
        'pool_cells_per_stage': {g: a.n_obs for g, a in stages.items()},
        'projected_dimensions': DIMENSIONS, 'neighbors': NEIGHBORS,
        'checkpoint': {name: digest(path) for name, path in paths.items()},
        'encoder_tensors_loaded': loaded,
        'upstream_source_files': {
            str(p.relative_to(args.upstream_source)): digest(p) for p in sorted(args.upstream_source.rglob('*.py'))
        },
        'splits': {name: SPLITS[name] for name in SPLIT_NAMES},
        'stages_sha256': {name: STAGES[name]['sha256'] for name in STAGES if name != 'E12.5'},
        'results': results,
        'scgpt_minus_pca': changes,
    })
    print(f'Completed. scGPT passed the registered criterion: {advance}. Results: {args.out}', flush=True)


if __name__ == '__main__':
    main()
