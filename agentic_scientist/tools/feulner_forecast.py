"""Expression-only heart development split on Feulner WT Drop-seq biological replicates."""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
from scipy import sparse

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from agentic_scientist.artifacts import file_sha, write_json
from agentic_scientist.evaluate import load, load_params, screen_workspace
from shinka_ve import harness


# Marker sets present on the 500-gene heart panel (and in the T1 transcriptome). A cell's compartment = the set with the
# highest mean z-scored marker expression; cells with no marker signal stay 'other'.
COMPARTMENTS = {
    'myocardium': ['Myl7', 'Nppa', 'Myl4', 'Myh7', 'Ttn'],
    'endocardium_endothelium': ['Pecam1', 'Cdh5', 'Npr3', 'Emcn'],
    'epicardium': ['Wt1', 'Tbx18', 'Upk3b', 'Tcf21'],
    'mesenchyme_fibroblast': ['Postn', 'Col1a1', 'Col3a1', 'Twist1'],
    'blood': ['Gata1'],
}


def forecast(predict, earlier, latest, target_loader, seed, params):
    """Fit compartment marker scaling on the last input and score only after prediction."""
    genes = list(latest.var_names)
    marker_sets = {k: [g for g in markers if g in genes] for k, markers in COMPARTMENTS.items()}
    marker_sets = {k: markers for k, markers in marker_sets.items() if markers}
    markers = list(dict.fromkeys(g for group in marker_sets.values() for g in group))
    if not markers:
        raise ValueError('Feulner panel lacks compartment markers')

    def marker_matrix(a):
        x = a[:, markers].X
        return x.toarray() if sparse.issparse(x) else np.asarray(x)

    ref = marker_matrix(latest)
    center, scale = ref.mean(0), ref.std(0) + 1e-6
    def labels(a):
        z = (marker_matrix(a) - center) / scale
        scores = np.column_stack([z[:, [markers.index(g) for g in group]].mean(1) for group in marker_sets.values()])
        return np.where(scores.max(1) > .25, np.array(list(marker_sets))[scores.argmax(1)], 'other')

    # Pass only expression, the input marker labels and the stage times to the candidate.
    import anndata as ad
    inputs = []
    for a in (earlier, latest):
        stage = ad.AnnData(a.X.copy(), var=a.var.iloc[:, :0].copy())
        stage.obs['celltype'] = labels(a)
        inputs.append(stage)
    ctx = dict(seed=seed, fit_seed=0, n=3000, params=params, sampling='heart_dissected', knockout=None,
               external=None, external_spatial=None, dynamics=None)
    pred = predict('heart', inputs, [14.5, 16.5], 18.5, ctx)
    # This assay measures expression only. Check the normal heart limits and panel, without requiring coordinates.
    if not 1000 <= pred.n_obs <= harness.MAX_CELLS['heart'] or not pred.var_names.is_unique:
        raise ValueError('invalid Feulner prediction size or duplicate genes')
    pred = pred[:, genes]
    def profiles(a):
        x = sparse.csr_matrix(a.X, dtype=np.float64, copy=True)
        if not np.isfinite(x.data).all() or (x.data < 0).any():
            raise ValueError('invalid Feulner expression')
        x.data = np.expm1(x.data)
        if not np.isfinite(x.data).all():
            raise ValueError('invalid linear-scale Feulner expression')
        group = labels(a)
        # Per-total-cell compartment contributions capture mass as well as expression.
        out = {'all': np.log1p(np.asarray(x.mean(0)).ravel())}
        for k in [*marker_sets, 'other']:
            out[k] = np.log1p(np.asarray(x[group == k].sum(0)).ravel() / a.n_obs)
        return out

    baseline, candidate = profiles(latest), profiles(pred)
    target = target_loader()
    reps = target.obs['replicate']
    if reps.isna().any() or len(reps.unique()) < 2:
        raise ValueError('Feulner target requires identified biological replicates')
    results = {}
    for rep in sorted(reps.unique()):
        part = target[reps == rep]
        truth = profiles(part)
        errors = {}
        for k, v in truth.items():
            copy_error = float(np.abs(baseline[k] - v).mean())
            pred_error = float(np.abs(candidate[k] - v).mean())
            errors[k] = dict(copy_mae=copy_error, prediction_mae=pred_error, gain=copy_error - pred_error)
        results[str(rep)] = dict(cells=part.n_obs, profiles=errors)
    return dict(split='feulner_e185', seed=seed, genes=len(genes), replicates=results,
                gain=float(np.mean([r['profiles']['all']['gain'] for r in results.values()])))


def evaluate(ws, seed=101):
    error = screen_workspace(ws)
    if error:
        raise ValueError(error)
    directory = ROOT / harness.EXTERNAL['heart']
    path = directory / harness.FEULNER
    manifest = json.loads((directory / 'manifest.json').read_text())
    if file_sha(path) != manifest['files'][path.name]['sha256']:
        raise ValueError('Feulner source differs from the disclosed manifest')
    panel = (ROOT / 'data/panels/T2__heart__test_extrap.genes.txt').read_text().split()
    def stages(days):
        return harness.load_anchor(directory, [path], panel, feulner_days=days)
    sources = stages([14.5, 16.5])
    days = sources.obs.stage_days
    return forecast(load(ws).predict, sources[days == 14.5], sources[days == 16.5], lambda: stages([18.5]),
                    seed, load_params(ws).get('heart', {}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('workspace', type=Path)
    parser.add_argument('--seed', type=int, default=101)
    parser.add_argument('--json', type=Path)
    args = parser.parse_args()
    result = evaluate(args.workspace.resolve(), args.seed)
    if args.json:
        write_json(args.json, result)
    print(json.dumps(result, allow_nan=False))
