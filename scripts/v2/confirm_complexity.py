"""Gata4 replication test of an observational complexity axis, not a KO delta."""
import argparse,gc,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from src.data import ROOT,load_stage
from src.v2.complexity import ComplexityPerturbation
from scripts.v2.evaluate import score,digest

parser=argparse.ArgumentParser();parser.add_argument('experiment',choices=['gata4_1','gata4_2'])
parser.add_argument('--fit-seed',type=int,required=True);parser.add_argument('--prediction-seed',type=int,required=True)
args=parser.parse_args()
configuration=ROOT/'experiments/v2/complexity_confirmation.json';plan=json.loads(configuration.read_text())
if dict(fit_seed=args.fit_seed,prediction_seed=args.prediction_seed) not in plan['confirmation_runs']:raise ValueError('Unplanned confirmation run')
inputs=['T2/E8.5.h5ad','T2/E8.75.h5ad']
target='T3/E8.75_gata4_ko_'+args.experiment[-1]+'.h5ad'
directory=ROOT/'submissions/v2'/('confirmation_'+args.experiment+'_complexity')/f'fit_{args.fit_seed}_pred_{args.prediction_seed}';directory.mkdir(parents=True,exist_ok=True)
if (directory/'experiment.json').exists():raise RuntimeError('Existing experiment')
stages=[load_stage(p) for p in inputs];model=ComplexityPerturbation(*stages,seed=args.fit_seed)
configs={'first':dict(strength=0.),'complexity_medium':plan['parameters']}
records={}
for candidate,config in configs.items():
 pred=model.predict(seed=args.prediction_seed,**config);pred.write_h5ad(directory/f'{candidate}.h5ad',compression='gzip')
 records[candidate]=dict(config=config,sha256=digest(directory/f'{candidate}.h5ad'))
 del pred;gc.collect();print('Built complexity',candidate,flush=True)
stages[-1].write_h5ad(directory/'reference.h5ad',compression='gzip')
record=dict(experiment=dict(task='T3',inputs=inputs,target=target),fit_seed=args.fit_seed,prediction_seed=args.prediction_seed,candidates=records,
 code_hashes={p:digest(ROOT/p) for p in ['src/data.py','src/v2/transport.py','src/v2/complexity.py','scripts/v2/confirm_complexity.py']},
 confirmation_plan_sha256=digest(configuration),source_hashes={p:digest(ROOT/'data/raw'/p) for p in inputs+[target]})
del model,stages;gc.collect()
a=load_stage(target);a.write_h5ad(directory/'target.h5ad',compression='gzip');del a;gc.collect()
(directory/'experiment.json').write_text(json.dumps(record,indent=2)+'\n')
score(args.experiment,directory,plan['confirmation_scoring_seeds'])
