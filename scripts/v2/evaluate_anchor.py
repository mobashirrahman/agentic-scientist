"""Backtest the external late-anchor T1 model: E8.5+E9.5 (+Qiu 2024 TS12/13/TS23) -> E10.5."""
import argparse,gc,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from src.data import ROOT,load_stage
from src.models import TemporalTransport
from src.v2.anchor import AnchorFlow,load_external
from scripts.v2.evaluate import score,digest

parser=argparse.ArgumentParser()
parser.add_argument('--fit-seed',type=int,required=True);parser.add_argument('--prediction-seed',type=int,required=True)
parser.add_argument('--phase',choices=['development','confirmation'],required=True)
args=parser.parse_args()
plan_path=ROOT/'experiments/v2/anchor_plan.json';plan=json.loads(plan_path.read_text())
run=dict(fit_seed=args.fit_seed,prediction_seed=args.prediction_seed)
if run not in plan[f'{args.phase}_runs']:raise ValueError('Run not in the frozen plan')
seeds=plan[f'{args.phase}_scoring_seeds'];bt=plan['backtest']
directory=ROOT/'submissions/v2'/f'anchor_{args.phase}'/f'fit_{args.fit_seed}_pred_{args.prediction_seed}'
directory.mkdir(parents=True,exist_ok=True)
ext_dir=ROOT/'data/external/qiu2024';ext_files=sorted(ext_dir.glob('*.h5ad'))
if not (directory/'experiment.json').exists():
 stages=[load_stage(p) for p in bt['inputs']]
 external=load_external(ext_files,list(stages[-1].var_names))
 model=AnchorFlow(*stages,external,bt['t_earlier'],bt['t_latest'],bt['t_anchor'],seed=args.fit_seed)
 horizon=bt['t_target']-bt['t_latest']
 records={}
 for name,cfg in plan['candidates'].items():
  if name=='first':pred=TemporalTransport(*stages,interval=1.).predict(1.,state=0.,composition=.5,seed=args.prediction_seed)
  else:pred=model.predict(horizon,seed=args.prediction_seed,**cfg)
  pred.write_h5ad(directory/f'{name}.h5ad',compression='gzip');records[name]=dict(config=cfg,sha256=digest(directory/f'{name}.h5ad'))
  del pred;gc.collect();print('built',name,flush=True)
 stages[-1].write_h5ad(directory/'reference.h5ad',compression='gzip')
 diag=dict(calibration_types=model.calibration_types,calibration_counts=model.calibration_counts,
  anchor_counts=model.anchor_counts,types_with_drift=sorted(model.drift),
  offset_abs_median=float(abs(model.offset).median() if hasattr(model.offset,'median') else 0))
 import numpy as np;diag['offset_abs_median']=float(np.median(np.abs(model.offset)))
 diag['drift_abs_mean']={t:float(np.mean(np.abs(d))) for t,d in model.drift.items()}
 record=dict(experiment=dict(task='T1',inputs=bt['inputs'],target=bt['target']),fit_seed=args.fit_seed,
  prediction_seed=args.prediction_seed,candidates=records,plan_sha256=digest(plan_path),diagnostics=diag,
  code_hashes={p:digest(ROOT/p) for p in ['src/data.py','src/models.py','src/v2/transport.py','src/v2/anchor.py','scripts/v2/evaluate_anchor.py']},
  source_hashes={p:digest(ROOT/'data/raw'/p) for p in bt['inputs']+[bt['target']]},
  external_hashes={p.name:digest(p) for p in ext_files})
 del model,stages,external;gc.collect()
 target=load_stage(bt['target']);target.write_h5ad(directory/'target.h5ad',compression='gzip');del target;gc.collect()
 (directory/'experiment.json').write_text(json.dumps(record,indent=2)+'\n')
score('anchor',directory,seeds)
