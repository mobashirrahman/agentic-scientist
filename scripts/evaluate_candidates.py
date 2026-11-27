"""Leakage-free candidate comparisons using pinned community/official metric code.

Each experiment fits only its explicitly listed inputs. Evaluation targets are
loaded only after every prediction has been written. Seed-level results are saved
as they complete, so an interrupted run can resume without repeating work.
"""
import argparse
import gc
import hashlib
import json
from pathlib import Path
import sys
import warnings
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
from src.data import ROOT, load_stage, sample
from src.models import TemporalTransport, interpolate, ot_interpolate, lineage_perturbation, spatial_growth

EXPERIMENTS = {
    'temporal': dict(task='T1', inputs=['T1/E8.5_RNA.h5ad', 'T1/E9.5_RNA.h5ad'], times=[8.5,9.5], target='T1/E10.5_RNA.h5ad', time=10.5),
    'heart_early': dict(task='T2', setting='heart', inputs=['T2/E8.25_late.h5ad','T2/E8.75.h5ad'], times=[8.25,8.75], target='T2/E9.5.h5ad', time=9.5),
    'heart_late': dict(task='T2', setting='heart', inputs=['T2/E8.25_late.h5ad','T2/E8.5.h5ad','T2/E8.75.h5ad','T2/E9.5.h5ad'], times=[8.25,8.5,8.75,9.5], target='T2/E10.5.h5ad', time=10.5),
    'embryo_early': dict(task='T2', setting='embryo', inputs=['T2/E6.75.h5ad','T2/E8.0.h5ad'], times=[6.75,8.0], target='T2/E7.25.h5ad', time=7.25),
    'embryo_late': dict(task='T2', setting='embryo', inputs=['T2/E7.25.h5ad','T2/E8.0.h5ad'], times=[7.25,8.0], target='T2/E7.5.h5ad', time=7.5),
    'gata4_1': dict(task='T3', inputs=['T2/E8.75.h5ad'], times=[8.75], target='T3/E8.75_gata4_ko_1.h5ad', time=8.75),
    'gata4_2': dict(task='T3', inputs=['T2/E8.75.h5ad'], times=[8.75], target='T3/E8.75_gata4_ko_2.h5ad', time=8.75),
}


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def build(name, directory, prediction_seed):
    spec = EXPERIMENTS[name]
    stages = [load_stage(path) for path in spec['inputs']]
    task = spec['task']
    candidates = {}
    if task == 'T3':
        candidates['copy'] = dict(kind='lineage', strength=0., depletion=0.)
        for strength in [.2, .5, 1.]:
            candidates[f'lineage_{strength}'] = dict(kind='lineage', strength=strength, depletion=.2 * strength)
        reference = stages[0]
        def predict(config):
            return lineage_perturbation(reference, target='gata4', seed=prediction_seed,
                                        **{k:v for k,v in config.items() if k!='kind'})
    elif spec.get('setting') == 'embryo':
        # Keep all common genes and a fixed gene order, including the val panel.
        genes = stages[0].var_names[stages[0].var_names.isin(stages[1].var_names)]
        stages = [a[:, genes].copy() for a in stages]
        reference = stages[0]
        fraction = (spec['time'] - spec['times'][0]) / (spec['times'][1] - spec['times'][0])
        candidates = {'copy':dict(kind='copy'), 'mixture':dict(kind='mixture'), 'transport':dict(kind='transport')}
        def predict(config):
            if config['kind'] == 'copy':
                return sample(reference, seed=prediction_seed)
            fn = interpolate if config['kind'] == 'mixture' else ot_interpolate
            return fn(*stages, fraction, seed=prediction_seed)
    else:
        reference = stages[-1]
        model = TemporalTransport(stages[-2], reference, spec['times'][-1] - spec['times'][-2])
        horizon = spec['time'] - spec['times'][-1]
        candidates = {'copy':dict(kind='flow', state=0., composition=0., geometry=0.),
                      'composition':dict(kind='flow', state=0., composition=.5, geometry=0.),
                      'flow_light':dict(kind='flow', state=.1, composition=.5, geometry=0.),
                      'flow_medium':dict(kind='flow', state=.25, composition=.5, geometry=0.)}
        if task == 'T2':
            growth = spatial_growth(stages, spec['times'])
            candidates['growth'] = dict(kind='flow', state=0., composition=0., geometry=max(growth,.1))
            candidates['growth_flow'] = dict(kind='flow', state=.1, composition=.25, geometry=max(growth,.1))
        def predict(config):
            return model.predict(horizon, seed=prediction_seed, **{k:v for k,v in config.items() if k!='kind'})
    for candidate, config in candidates.items():
        a = predict(config)
        path = directory / f'{candidate}.h5ad'
        a.write_h5ad(path, compression='gzip')
        print('Built', name, candidate, flush=True)
        del a
        gc.collect()
    reference.write_h5ad(directory / 'reference.h5ad', compression='gzip')
    # Targets never enter model fitting or generation above.
    target = load_stage(spec['target'])
    genes = reference.var_names
    target = target[:, genes].copy()
    target.write_h5ad(directory / 'target.h5ad', compression='gzip')
    record = dict(experiment=spec, candidates=candidates, prediction_seed=prediction_seed,
                  source_hashes={path:digest(ROOT/'data/raw'/path) for path in spec['inputs']+[spec['target']]},
                  code_hashes={path:digest(ROOT/path) for path in ['src/data.py','src/models.py','scripts/evaluate_candidates.py']},
                  prediction_hashes={c:digest(directory/f'{c}.h5ad') for c in candidates})
    (directory/'experiment.json').write_text(json.dumps(record,indent=2)+'\n')


def score(name, directory, seeds):
    from vec_local_score.local_score import score_many
    record=json.loads((directory/'experiment.json').read_text())
    for path,expected in record['code_hashes'].items():
        if digest(ROOT/path)!=expected:
            raise RuntimeError(f'Code changed after predictions were built: {path}')
    candidates=record['candidates']
    for c in candidates:
        if digest(directory/f'{c}.h5ad')!=record['prediction_hashes'][c]:
            raise RuntimeError(f'Prediction changed: {c}')
    cache={}
    spec=EXPERIMENTS[name]
    for seed in seeds:
        output=directory/f'seed_{seed}.json'
        if output.exists():
            print('Cached',name,seed,flush=True)
            continue
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            results=score_many(spec['task'], [directory/f'{c}.h5ad' for c in candidates],
                directory/'target.h5ad',directory/'reference.h5ad',setting=spec.get('setting','heart'),
                seed=seed,cache=cache)
        output.write_text(json.dumps(dict(zip(candidates,results)),indent=2)+'\n')
        print(name,seed,{c:r['task_score'] for c,r in zip(candidates,results)},flush=True)
    rows={}
    for c in candidates:
        values=[json.loads((directory/f'seed_{s}.json').read_text())[c]['task_score'] for s in seeds]
        rows[c]=dict(scores=values, mean=float(np.mean(values)),sd=float(np.std(values,ddof=1)) if len(values)>1 else 0.)
    (directory/'summary.json').write_text(json.dumps(dict(seeds=seeds,candidates=rows),indent=2)+'\n')


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('experiment',choices=EXPERIMENTS)
    parser.add_argument('--seeds',nargs='+',type=int,default=[0,1,2])
    parser.add_argument('--prediction-seed',type=int,default=42)
    parser.add_argument('--score-only',action='store_true')
    args=parser.parse_args()
    directory=ROOT/'submissions/development'/args.experiment/f'prediction_{args.prediction_seed}'
    directory.mkdir(parents=True,exist_ok=True)
    if not args.score_only:
        if (directory/'experiment.json').exists():
            raise RuntimeError('Existing experiment: use --score-only or a different prediction seed')
        build(args.experiment,directory,args.prediction_seed)
    score(args.experiment,directory,args.seeds)

if __name__=='__main__':
    main()
