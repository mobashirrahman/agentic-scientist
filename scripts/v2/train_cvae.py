"""Fit a T1 conditional NB decoder without observing the held-out E10.5 stage."""
import argparse,gc,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from src.data import ROOT,load_stage
from src.models import TemporalTransport
from src.v2.cvae import ConditionalGenerator
from scripts.v2.evaluate import score,digest

parser=argparse.ArgumentParser()
parser.add_argument('--epochs',type=int,default=10)
parser.add_argument('--fit-seed',type=int,default=0)
parser.add_argument('--prediction-seed',type=int,default=101)
args=parser.parse_args()
directory=ROOT/'submissions/v2/temporal_cvae'/f'fit_{args.fit_seed}_pred_{args.prediction_seed}_epochs_{args.epochs}'
directory.mkdir(parents=True,exist_ok=True)
if (directory/'experiment.json').exists():raise RuntimeError('Existing completed experiment; preserve its evidence')
if (directory/'checkpoint/best.pt').exists():raise RuntimeError('Existing checkpoint: inspect/resume the original process rather than overwriting it')
inputs=['T1/E8.5_RNA.h5ad','T1/E9.5_RNA.h5ad']
stages=[load_stage(p) for p in inputs]
model=ConditionalGenerator(stages,[8.5,9.5],args.fit_seed)
model.train(directory/'checkpoint',epochs=args.epochs)
configs={'first':None,'vae_reconstruction':0.,'vae_time_quarter':.25,'vae_time_half':.5}
records={}
for name,strength in configs.items():
 if name=='first':pred=TemporalTransport(*stages,interval=1.).predict(1.,state=0.,composition=.5,seed=args.prediction_seed)
 else:pred=model.predict(1.,seed=args.prediction_seed,time_strength=strength)
 pred.write_h5ad(directory/f'{name}.h5ad',compression='gzip')
 records[name]=dict(time_strength=strength,sha256=digest(directory/f'{name}.h5ad'))
 del pred;gc.collect()
stages[-1].write_h5ad(directory/'reference.h5ad',compression='gzip')
del model,stages;gc.collect()
# Only now read the held-out developmental stage.
target=load_stage('T1/E10.5_RNA.h5ad')
target.write_h5ad(directory/'target.h5ad',compression='gzip')
del target;gc.collect()
record=dict(experiment=dict(task='T1',inputs=inputs,target='T1/E10.5_RNA.h5ad'),fit_seed=args.fit_seed,
 prediction_seed=args.prediction_seed,candidates=records,
 code_hashes={p:digest(ROOT/p) for p in ['src/data.py','src/models.py','src/v2/transport.py','src/v2/cvae.py','scripts/v2/train_cvae.py']},
 source_hashes={p:digest(ROOT/'data/raw'/p) for p in inputs+['T1/E10.5_RNA.h5ad']})
(directory/'experiment.json').write_text(json.dumps(record,indent=2)+'\n')
score('temporal',directory,[101,102,103,104,105])
