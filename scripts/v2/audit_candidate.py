"""Audit provisional v2 files without changing or submitting predictions."""
import json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
import anndata as ad
import h5py
import numpy as np
from scipy import sparse
from src.data import ROOT
from scripts.v2.evaluate import digest
from scripts.v2.prepare_candidate import BOARDS

directory=ROOT/'submissions/second_candidate'
panels=json.loads((ROOT/'data/panels/index.json').read_text())
manifest={};report={};verified=set()
for group,board in BOARDS.items():
 item=json.loads((directory/(group+'.json')).read_text());path=ROOT/item['file']
 if digest(path)!=item['sha256']:raise RuntimeError('Changed prediction: '+board)
 for p,sha in item['code_sha256'].items():
  if digest(ROOT/p)!=sha:raise RuntimeError('Changed code: '+p)
 for p,sha in item['source_sha256'].items():
  if p in verified:continue
  if digest(ROOT/'data/raw'/p)!=sha:raise RuntimeError('Changed source: '+p)
  verified.add(p)
 a=ad.read_h5ad(path);contract=panels[board]
 genes=(ROOT/'data/panels'/contract['genes_file']).read_text().splitlines()
 assert list(a.var_names)==genes and a.n_vars==contract['n_genes']
 assert a.n_obs==3000 and contract['min_cells']<=a.n_obs<=contract['max_cells']
 values=a.X.data if sparse.issparse(a.X) else np.asarray(a.X)
 assert values.dtype==np.float32 and np.isfinite(values).all() and (values>=0).all()
 assert a.obs_names.is_unique and len(a.obs.columns)==0
 assert path.stat().st_size<=1200*10**6
 with h5py.File(path) as h5:assert 'raw' not in h5 and len(h5['layers'])==0
 if contract['needs_coords']:
  assert a.obsm['spatial_3D'].shape==(3000,3) and np.isfinite(a.obsm['spatial_3D']).all()
 item['method']='v2 '+group+' frozen candidate'
 manifest[board]=item
 report[board]=dict(cells=a.n_obs,genes=a.n_vars,sha256=item['sha256'],bytes=path.stat().st_size,local_structure=True)
(directory/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
(directory/'audit.json').write_text(json.dumps(dict(status='local checks passed',boards=report,
 limitations=['Provisional candidates; confirmation does not validate hidden-test transfer',
 'Heart gain is predominantly scale; neighborhood/state improvement not established',
 'No official attempt authorized by this audit']),indent=2)+'\n')
print(json.dumps(report,indent=2))
