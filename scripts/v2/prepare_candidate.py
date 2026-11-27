"""Build reviewable second-candidate artifacts locally; never upload or submit."""
import argparse,gc,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
import anndata as ad
import numpy as np
from src.data import ROOT,load_stage
from src.v2.transport import LatentFlow,SpatialInterpolant
from src.v2.complexity import ComplexityPerturbation
from scripts.v2.evaluate import digest

BOARDS={'temporal':'T1:test','heart':'T2:heart:test_extrap',
        'embryo':'T2:embryo:test_interp','perturbation':'T3:bcatenin'}

def build(group):
 directory=ROOT/'submissions/second_candidate';directory.mkdir(parents=True,exist_ok=True)
 board=BOARDS[group];path=directory/(board.replace(':','__')+'.h5ad')
 if path.exists():raise RuntimeError('Existing candidate must not be silently replaced')
 panels=json.loads((ROOT/'data/panels/index.json').read_text());seed=42;fit_seed=0
 if group in ('temporal','heart'):
  sources=(['T1/E9.5_RNA.h5ad','T1/E10.5_RNA.h5ad'] if group=='temporal'
           else ['T2/E9.5.h5ad','T2/E10.5.h5ad'])
  stages=[load_stage(p) for p in sources];model=LatentFlow(*stages,interval=1.,seed=fit_seed)
  plan=ROOT/'experiments/v2'/('temporal_confirmation.json' if group=='temporal' else 'spatial_confirmation.json')
  frozen=json.loads(plan.read_text())
  config=(dict(frozen['parameters'],horizon=2.) if group=='temporal'
          else dict(frozen['candidates']['heart'],horizon=2.))
  pred=model.predict(seed=seed,**config)
 elif group=='embryo':
  sources=['T2/E7.5.h5ad','T2/E8.0.h5ad'];stages=[load_stage(p) for p in sources]
  model=SpatialInterpolant(*stages,seed=fit_seed)
  plan=ROOT/'experiments/v2/spatial_confirmation.json'
  config=dict(json.loads(plan.read_text())['candidates']['embryo'],fraction=.5)
  pred=model.predict(seed=seed,**config)
 else:
  sources=['T2/E8.5.h5ad','T2/E8.75.h5ad'];stages=[load_stage(p) for p in sources]
  model=ComplexityPerturbation(*stages,seed=fit_seed)
  plan=ROOT/'experiments/v2/complexity_confirmation.json'
  config=json.loads(plan.read_text())['parameters'];pred=model.predict(seed=seed,**config)
 genes=(ROOT/'data/panels'/panels[board]['genes_file']).read_text().splitlines()
 pred=pred[:,genes].copy()
 clean=ad.AnnData(pred.X.astype(np.float32),var=pred.var.iloc[:,:0].copy())
 clean.obs_names=[f'historical-entry_v2_{i}' for i in range(clean.n_obs)]
 if panels[board]['needs_coords']:clean.obsm['spatial_3D']=pred.obsm['spatial_3D'].astype(np.float32)
 clean.uns['method']='historical-entry observed-stage transport and empirical observation model v2'
 clean.write_h5ad(path,compression='gzip')
 record=dict(board=board,file=str(path.relative_to(ROOT)),sha256=digest(path),config=config,
  seed=seed,fit_seed=fit_seed,cells=clean.n_obs,genes=clean.n_vars,status='provisional local candidate; not approved or submitted',
  confirmation_plan_sha256=digest(plan),source_sha256={p:digest(ROOT/'data/raw'/p) for p in sources},
  code_sha256={p:digest(ROOT/p) for p in ['src/data.py','src/v2/transport.py','src/v2/complexity.py','scripts/v2/prepare_candidate.py']})
 (directory/(group+'.json')).write_text(json.dumps(record,indent=2)+'\n')
 print(json.dumps(record,indent=2),flush=True)
 del pred,clean,model,stages;gc.collect()

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('group',choices=list(BOARDS))
 build(parser.parse_args().group)
