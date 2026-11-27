"""Evaluate neural temporal transport from an owned frozen short-run checkpoint."""
import argparse,gc,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
import numpy as np
import torch
from src.data import ROOT,load_stage
from src.models import TemporalTransport
from src.v2.cvae import ConditionalGenerator
from src.v2.neuralflow import NeuralTemporalFlow
from scripts.v2.evaluate import score,digest

parser=argparse.ArgumentParser();parser.add_argument('--fit-seed',type=int,default=0)
parser.add_argument('--prediction-seed',type=int,default=101);parser.add_argument('--checkpoint',type=Path,required=True)
args=parser.parse_args()
checkpoint=args.checkpoint.resolve()
if not checkpoint.is_relative_to(ROOT/'submissions/v2'):raise ValueError('Use an owned v2 experiment checkpoint')
# This is an owned training artifact with its path and hash recorded below; it is
# not an untrusted downloaded model. It includes NumPy preprocessing arrays.
state=torch.load(checkpoint,map_location='cpu',weights_only=False)
inputs=['T1/E8.5_RNA.h5ad','T1/E9.5_RNA.h5ad']
stages=[load_stage(p) for p in inputs]
generator=ConditionalGenerator(stages,[8.5,9.5],seed=args.fit_seed)
assert list(generator.groups)==state['config']['groups'] and generator.genes==state['genes']
np.testing.assert_array_equal(generator.features,state['features'])
np.testing.assert_allclose(generator.feature_mean,state['feature_mean'])
generator.model.load_state_dict(state['state_dict']);del state
model=NeuralTemporalFlow(generator,args.fit_seed)
directory=ROOT/'submissions/v2/temporal_neuralflow'/f'fit_{args.fit_seed}_pred_{args.prediction_seed}'
directory.mkdir(parents=True,exist_ok=True)
if (directory/'experiment.json').exists():raise RuntimeError('Existing experiment')
configs={'first':None,'vae_time':dict(latent_strength=0.,time_strength=.5),
         'neural_flow_light':dict(latent_strength=.15,time_strength=.25),
         'neural_flow_medium':dict(latent_strength=.35,time_strength=.25),
         'neural_flow_only':dict(latent_strength=.35,time_strength=0.)}
records={}
for name,config in configs.items():
 if name=='first':pred=TemporalTransport(*stages,interval=1.).predict(1.,state=0.,composition=.5,seed=args.prediction_seed)
 else:pred=model.predict(1.,seed=args.prediction_seed,**config)
 pred.write_h5ad(directory/f'{name}.h5ad',compression='gzip')
 records[name]=dict(config=config,sha256=digest(directory/f'{name}.h5ad'))
 print('Built neural flow',name,flush=True)
 del pred;gc.collect()
stages[-1].write_h5ad(directory/'reference.h5ad',compression='gzip')
solver=model.solver
record=dict(experiment=dict(task='T1',inputs=inputs,target='T1/E10.5_RNA.h5ad'),fit_seed=args.fit_seed,
 prediction_seed=args.prediction_seed,candidates=records,checkpoint_sha256=digest(checkpoint),solver=solver,
 code_hashes={p:digest(ROOT/p) for p in ['src/data.py','src/models.py','src/v2/transport.py','src/v2/cvae.py','src/v2/neuralflow.py','scripts/v2/evaluate_neuralflow.py']},
 source_hashes={p:digest(ROOT/'data/raw'/p) for p in inputs+['T1/E10.5_RNA.h5ad']})
del model,generator,stages;gc.collect();torch.cuda.empty_cache()
target=load_stage('T1/E10.5_RNA.h5ad');target.write_h5ad(directory/'target.h5ad',compression='gzip')
del target;gc.collect()
(directory/'experiment.json').write_text(json.dumps(record,indent=2)+'\n')
score('temporal',directory,[101,102,103,104,105])
