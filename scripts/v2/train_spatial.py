"""Observed-stage joint spatial decoder; official holdout excluded from training."""
import argparse,gc,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from src.data import ROOT,load_stage
from src.models import TemporalTransport
from src.v2.spatial_vae import SpatialGenerator
from scripts.v2.evaluate import score,digest

parser=argparse.ArgumentParser();parser.add_argument('experiment',choices=['heart_early','heart_late'])
parser.add_argument('--epochs',type=int,default=20);parser.add_argument('--fit-seed',type=int,default=0)
parser.add_argument('--prediction-seed',type=int,default=101)
args=parser.parse_args()
inputs=['T2/E8.25_late.h5ad','T2/E8.5.h5ad','T2/E8.75.h5ad'];times=[8.25,8.5,8.75]
if args.experiment=='heart_late':inputs.append('T2/E9.5.h5ad');times.append(9.5);target='T2/E10.5.h5ad';target_time=10.5
else:target='T2/E9.5.h5ad';target_time=9.5
name=args.experiment+'_spatial_vae';directory=ROOT/'submissions/v2'/name/f'fit_{args.fit_seed}_pred_{args.prediction_seed}_epochs_{args.epochs}'
directory.mkdir(parents=True,exist_ok=True)
if (directory/'checkpoint/best.pt').exists():raise RuntimeError('Existing checkpoint; inspect original worker before restarting')
stages=[load_stage(p) for p in inputs]
model=SpatialGenerator(stages,times,args.fit_seed)
model.train(directory/'checkpoint',args.epochs)
configs={'first':None,'hurdle_reconstruct':dict(time_strength=0.,composition=0.),
         'hurdle_future':dict(time_strength=.5),'hurdle_joint':dict(time_strength=.5,joint=True)}
records={}
for candidate,config in configs.items():
 if candidate=='first':pred=TemporalTransport(stages[-2],stages[-1],times[-1]-times[-2]).predict(target_time-times[-1],state=0.,composition=0.,seed=args.prediction_seed)
 else:pred=model.predict(target_time-times[-1],seed=args.prediction_seed,**config)
 pred.write_h5ad(directory/f'{candidate}.h5ad',compression='gzip')
 records[candidate]=dict(config=config,sha256=digest(directory/f'{candidate}.h5ad'))
 del pred;gc.collect();print('Built spatial VAE',candidate,flush=True)
stages[-1].write_h5ad(directory/'reference.h5ad',compression='gzip')
record=dict(experiment=dict(task='T2',setting='heart',inputs=inputs,target=target,times=times),fit_seed=args.fit_seed,
 prediction_seed=args.prediction_seed,candidates=records,
 code_hashes={p:digest(ROOT/p) for p in ['src/data.py','src/models.py','src/v2/transport.py','src/v2/multistage.py','src/v2/relative_flow.py','src/v2/spatial_vae.py','scripts/v2/train_spatial.py']},
 source_hashes={p:digest(ROOT/'data/raw'/p) for p in inputs+[target]})
del model,stages;gc.collect()
a=load_stage(target);a.write_h5ad(directory/'target.h5ad',compression='gzip');del a;gc.collect()
(directory/'experiment.json').write_text(json.dumps(record,indent=2)+'\n')
score(name,directory,[101,102,103,104,105])
