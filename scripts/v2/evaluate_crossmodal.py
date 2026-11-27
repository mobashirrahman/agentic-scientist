"""Forecast spatial E10.5 with only RNA/spatial inputs at or before E9.5."""
import gc,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from src.data import ROOT,load_stage
from src.models import TemporalTransport
from src.v2.crossmodal import RNAStateGuide
from scripts.v2.evaluate import score,digest

name='heart_late_crossmodal';directory=ROOT/'submissions/v2'/name/'fit_0_pred_101';directory.mkdir(parents=True,exist_ok=True)
if (directory/'experiment.json').exists():raise RuntimeError('Existing experiment')
inputs=['T1/E8.5_RNA.h5ad','T1/E9.5_RNA.h5ad','T2/E8.75.h5ad','T2/E9.5.h5ad']
rna=[load_stage(p) for p in inputs[:2]]
spatial=load_stage(inputs[-1]);previous=load_stage(inputs[-2])
model=RNAStateGuide(rna,spatial,[8.5,9.5],1.,seed=0);del rna;gc.collect()
configs={'first':None,'rna_light':dict(strength=.25),'rna_medium':dict(strength=.5),
         'rna_strong':dict(strength=1.),'rna_geometry':dict(strength=.5,geometry_scale=.5)}
records={}
for candidate,config in configs.items():
 if candidate=='first':pred=TemporalTransport(previous,spatial,interval=.75).predict(1.,state=0.,composition=0.,seed=101)
 else:pred=model.predict(seed=101,**config)
 pred.write_h5ad(directory/f'{candidate}.h5ad',compression='gzip')
 records[candidate]=dict(config=config,sha256=digest(directory/f'{candidate}.h5ad'))
 del pred;gc.collect();print('Built RNA guide',candidate,flush=True)
spatial.write_h5ad(directory/'reference.h5ad',compression='gzip')
record=dict(experiment=dict(task='T2',setting='heart',inputs=inputs,target='T2/E10.5.h5ad'),fit_seed=0,prediction_seed=101,
 candidates=records,crossmodal_audit=model.audit,
 code_hashes={p:digest(ROOT/p) for p in ['src/data.py','src/models.py','src/v2/transport.py','src/v2/crossmodal.py','scripts/v2/evaluate_crossmodal.py']},
 source_hashes={p:digest(ROOT/'data/raw'/p) for p in inputs+['T2/E10.5.h5ad']})
del model,spatial,previous;gc.collect()
# Neither RNA E10.5 nor spatial E10.5 has been used above.
a=load_stage('T2/E10.5.h5ad');a.write_h5ad(directory/'target.h5ad',compression='gzip');del a;gc.collect()
(directory/'experiment.json').write_text(json.dumps(record,indent=2)+'\n')
score(name,directory,[101,102,103,104,105])
