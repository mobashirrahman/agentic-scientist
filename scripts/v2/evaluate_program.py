"""Evaluate frozen WT-derived program coefficients on each Gata4 replicate."""
import argparse,gc,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
import numpy as np
from src.data import ROOT,load_stage
from src.v2.programs import ProgramPerturbation
from scripts.v2.evaluate import score,digest

parser=argparse.ArgumentParser();parser.add_argument('experiment',choices=['gata4_1','gata4_2'])
args=parser.parse_args();target='T3/E8.75_gata4_ko_'+args.experiment[-1]+'.h5ad'
cache=ROOT/'submissions/v2/wt_programs.npz';fit=json.loads((ROOT/'submissions/v2/wt_programs.json').read_text())
if digest(cache)!=fit['coefficients_sha256']:raise RuntimeError('Program checkpoint changed')
weights=np.load(cache,allow_pickle=False)
wt=load_stage('T2/E8.75.h5ad')[:,list(weights['genes'])].copy()
model=ProgramPerturbation(wt,weights['gata4'])
directory=ROOT/'submissions/v2'/(args.experiment+'_program')/'fit_0_pred_101';directory.mkdir(parents=True,exist_ok=True)
if (directory/'experiment.json').exists():raise RuntimeError('Existing experiment')
configs={'first':dict(strength=0.),'program_light':dict(strength=.25),'program_medium':dict(strength=.5),
         'program_strong':dict(strength=1.),'program_depletion':dict(strength=.5,depletion=.2)}
records={}
for name,config in configs.items():
 pred=model.predict(seed=101,**config)
 pred.write_h5ad(directory/f'{name}.h5ad',compression='gzip')
 records[name]=dict(config=config,sha256=digest(directory/f'{name}.h5ad'))
 del pred;gc.collect();print('Built program',name,flush=True)
wt.write_h5ad(directory/'reference.h5ad',compression='gzip')
# The KO is only read by evaluation after program fitting and generation.
a=load_stage(target)[:,wt.var_names].copy();a.write_h5ad(directory/'target.h5ad',compression='gzip')
record=dict(experiment=dict(task='T3',inputs=['T2/E8.75.h5ad','T1/E8.5_RNA.h5ad','T1/E9.5_RNA.h5ad'],target=target),
 fit_seed=0,prediction_seed=101,candidates=records,program_fit=fit,
 code_hashes={p:digest(ROOT/p) for p in ['src/data.py','src/v2/transport.py','src/v2/programs.py','scripts/v2/evaluate_program.py']},
 source_hashes={'T2/E8.75.h5ad':digest(ROOT/'data/raw/T2/E8.75.h5ad'),target:digest(ROOT/'data/raw'/target)})
(directory/'experiment.json').write_text(json.dumps(record,indent=2)+'\n')
del a,wt,model;gc.collect();score(args.experiment,directory,[101,102,103,104,105])
