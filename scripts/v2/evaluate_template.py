"""Two bracketed-stage template ablations; no target anatomy enters registration."""
import argparse,gc,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from src.data import ROOT,load_stage
from src.models import interpolate
from src.v2.template import CoherentTemplate
from scripts.v2.evaluate import score,digest
from scripts.evaluate_candidates import EXPERIMENTS

parser=argparse.ArgumentParser();parser.add_argument('experiment',choices=['embryo_early','embryo_late'])
args=parser.parse_args();spec=EXPERIMENTS[args.experiment]
directory=ROOT/'submissions/v2'/(args.experiment+'_template')/'fit_0_pred_101'
directory.mkdir(parents=True,exist_ok=True)
if (directory/'experiment.json').exists():raise RuntimeError('Existing experiment')
stages=[load_stage(p) for p in spec['inputs']]
model=CoherentTemplate(*stages,seed=0)
stages=[model.left,model.right]
fraction=(spec['time']-spec['times'][0])/(spec['times'][1]-spec['times'][0])
configs={'first':None,'motion_half':'motion','template_left':'left','template_right':'right'}
records={}
for name,mode in configs.items():
 if name=='first':pred=interpolate(*stages,fraction,seed=101)
 elif mode=='motion':pred=model.predict(fraction,seed=101,mode='transport',deformation=.5)
 else:pred=model.predict_template(fraction,seed=101,template=mode)
 pred.write_h5ad(directory/f'{name}.h5ad',compression='gzip')
 records[name]=dict(template=mode,sha256=digest(directory/f'{name}.h5ad'))
 del pred;gc.collect();print('Built template',name,flush=True)
stages[0].write_h5ad(directory/'reference.h5ad',compression='gzip')
a=load_stage(spec['target'])[:,stages[0].var_names].copy();a.write_h5ad(directory/'target.h5ad',compression='gzip')
record=dict(experiment=spec,fit_seed=0,prediction_seed=101,candidates=records,
 code_hashes={p:digest(ROOT/p) for p in ['src/data.py','src/models.py','src/v2/transport.py','src/v2/template.py','scripts/v2/evaluate_template.py']},
 source_hashes={p:digest(ROOT/'data/raw'/p) for p in spec['inputs']+[spec['target']]})
(directory/'experiment.json').write_text(json.dumps(record,indent=2)+'\n')
del stages,a,model;gc.collect()
score(args.experiment,directory,[101,102,103,104,105])
