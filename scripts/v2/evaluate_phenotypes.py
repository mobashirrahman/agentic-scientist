"""Phenotype harmonization ablations for multi-stage heart prediction."""
import argparse,gc,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from src.data import ROOT,load_stage
from src.models import TemporalTransport
from src.v2.phenotypes import harmonize_phenotypes
from src.v2.relative_flow import RelativeMultiStageFlow
from scripts.v2.evaluate import score,digest

parser=argparse.ArgumentParser();parser.add_argument('experiment',choices=['heart_early','heart_late'])
args=parser.parse_args();inputs=['T2/E8.25_late.h5ad','T2/E8.5.h5ad','T2/E8.75.h5ad'];times=[8.25,8.5,8.75]
if args.experiment=='heart_late':inputs.append('T2/E9.5.h5ad');times.append(9.5);target='T2/E10.5.h5ad';target_time=10.5
else:target='T2/E9.5.h5ad';target_time=9.5
name=args.experiment+'_phenotypes';directory=ROOT/'submissions/v2'/name/'fit_0_pred_101';directory.mkdir(parents=True,exist_ok=True)
if (directory/'experiment.json').exists():raise RuntimeError('Existing experiment')
original=[load_stage(p) for p in inputs]
first=TemporalTransport(original[-2],original[-1],times[-1]-times[-2]).predict(target_time-times[-1],state=0.,composition=0.,seed=101)
first.write_h5ad(directory/'first.h5ad',compression='gzip')
records={'first':dict(config=None,sha256=digest(directory/'first.h5ad'))};audits={}
del first;gc.collect()
for clusters in [8,16]:
 stages,audit=harmonize_phenotypes(original,clusters);audits[str(clusters)]=audit
 model=RelativeMultiStageFlow(stages,times)
 for variant,config in [('composition',dict(state=0.,growth=.5)),('state',dict(state=.15,growth=.25)),('joint',dict(state=.15,growth=.25,deformation=.25,scale=.5))]:
  candidate=f'k{clusters}_{variant}'
  pred=model.predict(target_time-times[-1],seed=101,**config)
  pred.write_h5ad(directory/f'{candidate}.h5ad',compression='gzip')
  records[candidate]=dict(config=dict(clusters=clusters,**config),sha256=digest(directory/f'{candidate}.h5ad'))
  del pred;gc.collect();print('Built phenotype',candidate,flush=True)
 del stages,model;gc.collect()
original[-1].write_h5ad(directory/'reference.h5ad',compression='gzip')
record=dict(experiment=dict(task='T2',setting='heart',inputs=inputs,target=target),fit_seed=0,prediction_seed=101,
 candidates=records,phenotype_audits=audits,
 code_hashes={p:digest(ROOT/p) for p in ['src/data.py','src/models.py','src/v2/transport.py','src/v2/multistage.py','src/v2/relative_flow.py','src/v2/phenotypes.py','scripts/v2/evaluate_phenotypes.py']},
 source_hashes={p:digest(ROOT/'data/raw'/p) for p in inputs+[target]})
del original;gc.collect()
a=load_stage(target);a.write_h5ad(directory/'target.h5ad',compression='gzip');del a;gc.collect()
(directory/'experiment.json').write_text(json.dumps(record,indent=2)+'\n')
score(name,directory,[101,102,103,104,105])
