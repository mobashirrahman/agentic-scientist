"""Audit public aggregation, local normalization controls and spatial resolution."""
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
import numpy as np
import anndata as ad
from vec_local_score.local_score import WEIGHTS,DIRECTION,skill
from common.shape_metrics import occupancy_dice,d2_distance,_canonicalise
from src.data import ROOT

report={}
official=json.loads((ROOT/'submissions/ready/official_status.json').read_text())
report['aggregation']={board:dict(weighted=sum(row['metrics'][m]*w for m,w in WEIGHTS[row['task']].items()),
    official=row['headline']) for board,row in official.items()}
for row in report['aggregation'].values():row['difference']=row['official']-row['weighted']
report['private_parity']='unverified; heart aggregation discrepancy remains unresolved'
controls={}
for name in ['temporal','heart_late','embryo_late','gata4_1']:
 result=json.loads((ROOT/'submissions/development'/name/'prediction_42/seed_0.json').read_text())
 result=next(iter(result.values()))
 values=[];ceiling=[];flags=[]
 for row in result['rows']:
  direction=DIRECTION[row['metric']]
  values.append(100*row['weight']*skill(row['floor'],row['floor'],row['ceiling'],direction))
  ceiling.append(100*row['weight']*skill(row['ceiling'],row['floor'],row['ceiling'],direction))
  if row['degenerate'] or row['undefined']:flags.append(row['metric'])
 controls[name]=dict(floor=float(sum(values)),ceiling=float(sum(ceiling)),uninformative_metrics=flags)
 if not flags:
  assert abs(sum(values)-50)<.02 and abs(sum(ceiling)-100)<.02
report['normalization_controls']=controls
root=ROOT/'submissions/v2/embryo_late/fit_0_pred_101'
a=ad.read_h5ad(root/'target.h5ad')
p=np.asarray(a.obsm['spatial_3D'])
rng=np.random.default_rng(771)
base=p[rng.choice(len(p),min(len(p),2000),replace=False)]
rotation=np.array([[0.,-1,0],[1,0,0],[0,0,1]])
dice,resolution=occupancy_dice(base,base@rotation+np.array([123.,-45,88.]))
d2=d2_distance(base,base@rotation+np.array([123.,-45,88.]))
d2_null=d2_distance(base,base)
assert abs(dice-1.)<1e-6 and abs(d2-d2_null)<1e-6
report['rigid_rotation_control']=dict(dice=dice,d2=d2,d2_self=d2_null,voxel_over_nn=resolution,
    note='D2 independently samples distance pairs in each cloud; compare transformation to its nonzero Monte Carlo self baseline.')
resolution_rows=[]
for n in [500,1000,2000]:
 for grid in [4,8,16]:
  pa=p[rng.choice(len(p),n,replace=False)];pb=p[rng.choice(len(p),n,replace=False)]
  value,ratio=occupancy_dice(pa,pb,n_grid=grid)
  resolution_rows.append(dict(cells=n,grid=grid,raw_dice=value,voxel_over_nn=ratio))
report['resolution_sampling']=resolution_rows
report['interpretation']='Grid-size changes are auxiliary diagnostics only; published metric configuration is unchanged.'
(ROOT/'submissions/v2/scoring_audit.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
fig,axes=plt.subplots(2,4,figsize=(14,7),constrained_layout=True)
for column,name in enumerate(['target','first','registered','motion_half']):
 stage=ad.read_h5ad(root/f'{name}.h5ad')
 coords=np.asarray(stage.obsm['spatial_3D'])
 coords=coords[rng.choice(len(coords),min(3000,len(coords)),replace=False)]
 z,_=_canonicalise(coords)
 for row,(x,y) in enumerate([(0,1),(0,2)]):
  axes[row,column].scatter(z[:,x],z[:,y],s=1,alpha=.25,c='#2563eb',rasterized=True)
  axes[row,column].set(xlim=(-3,3),ylim=(-3,3),aspect='equal',xlabel=f'PC{x+1} / RMS',ylabel=f'PC{y+1} / RMS')
  axes[row,column].set_title(name.replace('_',' '))
fig.suptitle('Released E7.5 backtest: PCA-normalized geometry (independent axis signs)')
fig.savefig(ROOT/'submissions/v2/embryo_geometry_diagnostic.png',dpi=180)
