"""Version-2 frozen-input experiments, paired metrics and checkpointed scorer draws."""
import argparse
import gc
import hashlib
import json
from pathlib import Path
import sys
import warnings
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
import numpy as np
from src.data import ROOT,load_stage
from src.models import TemporalTransport,interpolate,lineage_perturbation
from src.v2.transport import LatentFlow,SpatialInterpolant,LineageDelay
from scripts.evaluate_candidates import EXPERIMENTS


def digest(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def build(name,directory,prediction_seed,fit_seed):
    spec=EXPERIMENTS[name]
    stages=[load_stage(p) for p in spec['inputs']]
    task=spec['task']
    records={}
    if spec.get('setting')=='embryo':
        model=SpatialInterpolant(stages[0],stages[1],seed=fit_seed)
        stages=[model.left,model.right]
        reference=stages[0]
        fraction=(spec['time']-spec['times'][0])/(spec['times'][1]-spec['times'][0])
        configs={'first':dict(mode='first'), 'registered':dict(mode='registered'),
                 'motion_half':dict(mode='transport',deformation=.5),'motion_full':dict(mode='transport',deformation=1.)}
        def predict(config):
            if config['mode']=='first':return interpolate(*stages,fraction,seed=prediction_seed)
            return model.predict(fraction,seed=prediction_seed,**config)
    elif task=='T3':
        # Existing spec's only input is WT; add the officially unlocked earlier
        # WT stage. The knockout target never enters the transport fit.
        earlier=load_stage('T2/E8.5.h5ad')
        spec=dict(spec,inputs=['T2/E8.5.h5ad',*spec['inputs']])
        model=LineageDelay(earlier,stages[0],interval=.25,seed=fit_seed)
        reference=stages[0]
        configs={'first':dict(delay=0.,depletion=0.),'depletion':dict(delay=0.,depletion=.2),
                 'delay_quarter':dict(delay=.0625,depletion=.1),'delay_half':dict(delay=.125,depletion=.2)}
        def predict(config):return model.predict(seed=prediction_seed,**config)
    else:
        reference=stages[-1]
        interval=spec['times'][-1]-spec['times'][-2]
        horizon=spec['time']-spec['times'][-1]
        model=LatentFlow(stages[-2],stages[-1],interval,fit_seed)
        baseline=TemporalTransport(stages[-2],stages[-1],interval)
        configs={'first':dict(state=0.,growth=.5 if task=='T1' else 0.,deformation=0.,scale=0.),
                 'density':dict(state=0.,growth=.25,deformation=0.,scale=0.),
                 'flow_light':dict(state=.15,growth=.25,deformation=0.,scale=0.),
                 'flow_medium':dict(state=.35,growth=.25,deformation=0.,scale=0.)}
        if task=='T2':
            configs['joint']=dict(state=.15,growth=.25,deformation=.25,scale=.5)
            configs['geometry']=dict(state=0.,growth=0.,deformation=.25,scale=.5)
        def predict(config):
            if config is configs['first']:
                return baseline.predict(horizon,state=0.,composition=.5 if task=='T1' else 0.,seed=prediction_seed)
            return model.predict(horizon,seed=prediction_seed,**config)
    for candidate,config in configs.items():
        pred=predict(config)
        path=directory/f'{candidate}.h5ad'
        pred.write_h5ad(path,compression='gzip')
        records[candidate]=dict(config=config,sha256=digest(path))
        del pred;gc.collect()
        print('Built v2',name,candidate,flush=True)
    reference.write_h5ad(directory/'reference.h5ad',compression='gzip')
    target=load_stage(spec['target'])[:,reference.var_names].copy()
    target.write_h5ad(directory/'target.h5ad',compression='gzip')
    meta=dict(experiment=spec,fit_seed=fit_seed,prediction_seed=prediction_seed,candidates=records,
              code_hashes={p:digest(ROOT/p) for p in ['src/data.py','src/models.py','src/v2/transport.py','scripts/v2/evaluate.py']},
              source_hashes={p:digest(ROOT/'data/raw'/p) for p in spec['inputs']+[spec['target']]},
              solver=getattr(model,'solver',getattr(getattr(model,'flow',None),'solver',{})))
    (directory/'experiment.json').write_text(json.dumps(meta,indent=2)+'\n')
    return meta


def stress_score(result):
    """Predeclared conservative scenario, NOT a reconstruction of private scoring.

    Suppress positive shape bonuses if neighborhood skill is below the floor.
    Keep published totals and raw metrics as the primary recorded calculation.
    """
    if result['task']!='T2':return result['task_score']
    skills={r['metric']:r['skill'] for r in result['rows']}
    total=result['task_score']
    if skills['neighborhood_mmd']<.5:
        for row in result['rows']:
            if row['metric'] in ('d2_shape','occupancy_dice','scale_log_ratio'):
                total-=100*row['weight']*max(row['skill']-.5,0.)
    return round(total,2)


def score(name,directory,seeds):
    from vec_local_score.local_score import score_many
    record=json.loads((directory/'experiment.json').read_text())
    for path,sha in record['code_hashes'].items():
        if digest(ROOT/path)!=sha:raise RuntimeError(f'Code changed after build: {path}')
    for c,item in record['candidates'].items():
        if digest(directory/f'{c}.h5ad')!=item['sha256']:raise RuntimeError(f'Prediction changed: {c}')
    spec=record['experiment'];candidates=list(record['candidates']);cache={}
    for seed in seeds:
        path=directory/f'seed_{seed}.json'
        if path.exists():continue
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            result=score_many(spec['task'],[directory/f'{c}.h5ad' for c in candidates],directory/'target.h5ad',
                directory/'reference.h5ad',setting=spec.get('setting','heart'),seed=seed,cache=cache)
        for r in result:r['conservative_shape_stress']=stress_score(r)
        path.write_text(json.dumps(dict(zip(candidates,result)),indent=2)+'\n')
        print(name,record['prediction_seed'],seed,{c:r['task_score'] for c,r in zip(candidates,result)},flush=True)
    summary={}
    for candidate in candidates:
        rows=[json.loads((directory/f'seed_{s}.json').read_text()) for s in seeds]
        values=[r[candidate]['task_score'] for r in rows]
        paired=[r[candidate]['task_score']-r['first']['task_score'] for r in rows]
        summary[candidate]=dict(scores=values,mean=float(np.mean(values)),sd=float(np.std(values,ddof=1)),
            differences=paired,paired_mean=float(np.mean(paired)),
            metrics={metric:float(np.mean([r[candidate]['raw_pred'][metric] for r in rows]))
                     for metric in rows[0][candidate]['raw_pred'] if all(isinstance(r[candidate]['raw_pred'][metric],(int,float)) for r in rows)})
    (directory/'summary.json').write_text(json.dumps(dict(seeds=seeds,candidates=summary),indent=2)+'\n')


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('experiment',choices=EXPERIMENTS)
    parser.add_argument('--prediction-seed',type=int,default=101)
    parser.add_argument('--fit-seed',type=int,default=0)
    parser.add_argument('--seeds',nargs='+',type=int,default=[101,102,103,104,105])
    parser.add_argument('--score-only',action='store_true')
    args=parser.parse_args()
    directory=ROOT/'submissions/v2'/args.experiment/f'fit_{args.fit_seed}_pred_{args.prediction_seed}'
    directory.mkdir(parents=True,exist_ok=True)
    if not args.score_only:
        if (directory/'experiment.json').exists():raise RuntimeError('Existing experiment; use --score-only to resume scoring')
        build(args.experiment,directory,args.prediction_seed,args.fit_seed)
    score(args.experiment,directory,args.seeds)

if __name__=='__main__':main()
