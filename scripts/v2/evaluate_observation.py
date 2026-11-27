"""Separate observation-depth and developmental-state ablations for the heart."""
import argparse,gc,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from src.data import ROOT,load_stage
from src.models import TemporalTransport
from src.v2.observation import ObservationFlow
from scripts.v2.evaluate import score,digest

parser=argparse.ArgumentParser();parser.add_argument('experiment',choices=['heart_early','heart_late'])
args=parser.parse_args();inputs=['T2/E8.25_late.h5ad','T2/E8.5.h5ad','T2/E8.75.h5ad'];times=[8.25,8.5,8.75]
if args.experiment=='heart_late':inputs.append('T2/E9.5.h5ad');times.append(9.5);target='T2/E10.5.h5ad';target_time=10.5
else:target='T2/E9.5.h5ad';target_time=9.5
name=args.experiment+'_observation';directory=ROOT/'submissions/v2'/name/'fit_0_pred_101';directory.mkdir(parents=True,exist_ok=True)
if (directory/'experiment.json').exists():raise RuntimeError('Existing experiment')
stages=[load_stage(p) for p in inputs];model=ObservationFlow(stages,times)
configs={'first':None,'detection_light':dict(observation=.25),'detection_medium':dict(observation=.5),
         'detection_strong':dict(observation=.75),'detection_flow':dict(observation=.5,state=.15,growth=.25)}
records={}
for candidate,config in configs.items():
 if candidate=='first':pred=TemporalTransport(stages[-2],stages[-1],times[-1]-times[-2]).predict(target_time-times[-1],state=0.,composition=0.,seed=101)
 else:pred=model.predict(target_time-times[-1],seed=101,**config)
 pred.write_h5ad(directory/f'{candidate}.h5ad',compression='gzip')
 records[candidate]=dict(config=config,sha256=digest(directory/f'{candidate}.h5ad'))
 del pred;gc.collect();print('Built observation',candidate,flush=True)
stages[-1].write_h5ad(directory/'reference.h5ad',compression='gzip')
record=dict(experiment=dict(task='T2',setting='heart',inputs=inputs,target=target),fit_seed=0,prediction_seed=101,
 candidates=records,observation_audit=model.audit,
 code_hashes={p:digest(ROOT/p) for p in ['src/data.py','src/models.py','src/v2/transport.py','src/v2/observation.py','scripts/v2/evaluate_observation.py']},
 source_hashes={p:digest(ROOT/'data/raw'/p) for p in inputs+[target]})
del model;gc.collect()
a=load_stage(target);a.write_h5ad(directory/'target.h5ad',compression='gzip')
(directory/'experiment.json').write_text(json.dumps(record,indent=2)+'\n')
del stages,a;gc.collect();score(name,directory,[101,102,103,104,105])
