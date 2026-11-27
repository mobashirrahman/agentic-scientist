"""Independent stochastic confirmation of the frozen temporal transport model."""
import argparse,gc,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from src.data import ROOT,load_stage
from src.models import TemporalTransport
from src.v2.transport import LatentFlow
from scripts.v2.evaluate import score,digest

parser=argparse.ArgumentParser();parser.add_argument('--fit-seed',type=int,required=True)
parser.add_argument('--prediction-seed',type=int,required=True);args=parser.parse_args()
configuration=ROOT/'experiments/v2/temporal_confirmation.json';config=json.loads(configuration.read_text())
if dict(fit_seed=args.fit_seed,prediction_seed=args.prediction_seed) not in config['confirmation_runs']:
 raise ValueError('Run not in the frozen confirmation plan')
directory=ROOT/'submissions/v2/confirmation_temporal'/f'fit_{args.fit_seed}_pred_{args.prediction_seed}'
directory.mkdir(parents=True,exist_ok=True)
if not (directory/'experiment.json').exists():
 inputs=['T1/E8.5_RNA.h5ad','T1/E9.5_RNA.h5ad'];stages=[load_stage(p) for p in inputs]
 model=LatentFlow(*stages,interval=1.,seed=args.fit_seed)
 first=TemporalTransport(*stages,interval=1.).predict(1.,state=0.,composition=.5,seed=args.prediction_seed)
 candidate=model.predict(seed=args.prediction_seed,**config['parameters'])
 records={}
 for name,pred in [('first',first),('flow',candidate)]:
  pred.write_h5ad(directory/f'{name}.h5ad',compression='gzip')
  records[name]=dict(sha256=digest(directory/f'{name}.h5ad'))
 stages[-1].write_h5ad(directory/'reference.h5ad',compression='gzip')
 record=dict(experiment=dict(task='T1',inputs=inputs,target='T1/E10.5_RNA.h5ad'),fit_seed=args.fit_seed,
  prediction_seed=args.prediction_seed,candidates=records,confirmation_plan_sha256=digest(configuration),
  code_hashes={p:digest(ROOT/p) for p in ['src/data.py','src/models.py','src/v2/transport.py','scripts/v2/confirm_temporal.py']},
  source_hashes={p:digest(ROOT/'data/raw'/p) for p in inputs+['T1/E10.5_RNA.h5ad']})
 del model,first,candidate,stages;gc.collect()
 target=load_stage('T1/E10.5_RNA.h5ad');target.write_h5ad(directory/'target.h5ad',compression='gzip');del target;gc.collect()
 (directory/'experiment.json').write_text(json.dumps(record,indent=2)+'\n')
score('temporal',directory,config['confirmation_scoring_seeds'])
