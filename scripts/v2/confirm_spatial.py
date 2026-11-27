"""Frozen anatomy candidates, with expression-preserving paired controls."""
import argparse,gc,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from src.data import ROOT,load_stage
from src.models import TemporalTransport,interpolate
from src.v2.transport import SpatialInterpolant,LatentFlow
from scripts.evaluate_candidates import EXPERIMENTS
from scripts.v2.evaluate import score,digest

parser=argparse.ArgumentParser()
parser.add_argument('experiment',choices=['heart_early','heart_late','embryo_early','embryo_late'])
parser.add_argument('--fit-seed',type=int,required=True)
parser.add_argument('--prediction-seed',type=int,required=True)
args=parser.parse_args()
configuration=ROOT/'experiments/v2/spatial_confirmation.json'
plan=json.loads(configuration.read_text())
if dict(fit_seed=args.fit_seed,prediction_seed=args.prediction_seed) not in plan['confirmation_runs']:
 raise ValueError('Unplanned confirmation run')
spec=EXPERIMENTS[args.experiment];kind=args.experiment.split('_')[0]
directory=ROOT/'submissions/v2'/('confirmation_'+args.experiment)/f'fit_{args.fit_seed}_pred_{args.prediction_seed}'
directory.mkdir(parents=True,exist_ok=True)
if (directory/'experiment.json').exists():raise RuntimeError('Existing experiment')
stages=[load_stage(p) for p in spec['inputs']]
if kind=='embryo':
 model=SpatialInterpolant(*stages,seed=args.fit_seed)
 stages=[model.left,model.right];reference=stages[0]
 fraction=(spec['time']-spec['times'][0])/(spec['times'][1]-spec['times'][0])
 first=interpolate(*stages,fraction,seed=args.prediction_seed)
 candidate=model.predict(fraction,seed=args.prediction_seed,**plan['candidates'][kind])
else:
 interval=spec['times'][-1]-spec['times'][-2];horizon=spec['time']-spec['times'][-1]
 model=LatentFlow(*stages[-2:],interval=interval,seed=args.fit_seed);reference=stages[-1]
 first=TemporalTransport(*stages[-2:],interval=interval).predict(horizon,state=0.,composition=0.,seed=args.prediction_seed)
 candidate=model.predict(horizon,seed=args.prediction_seed,**plan['candidates'][kind])
records={}
for name,pred in [('first',first),('geometry',candidate)]:
 pred.write_h5ad(directory/f'{name}.h5ad',compression='gzip')
 records[name]=dict(sha256=digest(directory/f'{name}.h5ad'))
reference.write_h5ad(directory/'reference.h5ad',compression='gzip')
record=dict(experiment=spec,fit_seed=args.fit_seed,prediction_seed=args.prediction_seed,candidates=records,
 confirmation_plan_sha256=digest(configuration),
 code_hashes={p:digest(ROOT/p) for p in ['src/data.py','src/models.py','src/v2/transport.py','scripts/v2/confirm_spatial.py']},
 source_hashes={p:digest(ROOT/'data/raw'/p) for p in spec['inputs']+[spec['target']]})
genes=list(reference.var_names)
del first,candidate,reference,model,stages;gc.collect()
target=load_stage(spec['target'])[:,genes].copy()
target.write_h5ad(directory/'target.h5ad',compression='gzip');del target;gc.collect()
(directory/'experiment.json').write_text(json.dumps(record,indent=2)+'\n')
score(args.experiment,directory,plan['confirmation_scoring_seeds'])
