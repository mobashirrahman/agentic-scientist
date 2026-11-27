"""Build the first selected P3 bundle after fresh-seed confirmation.

This command generates local artifacts only. It never consumes official attempts.
"""
import gc
import hashlib
import importlib.metadata as metadata
import json
from pathlib import Path
import platform
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import anndata as ad
import numpy as np
from src.data import ROOT,load_stage
from src.models import TemporalTransport,interpolate,ot_interpolate,lineage_perturbation,spatial_growth
from scripts.evaluate_candidates import digest

BOARDS={'temporal':'T1:test','heart':'T2:heart:test_extrap',
        'embryo':'T2:embryo:test_interp','perturbation':'T3:bcatenin'}


def main():
    selection=json.loads((ROOT/'submissions/selection.json').read_text())
    final=ROOT/'submissions/ready'
    final.mkdir(parents=True,exist_ok=True)
    if (final/'manifest.json').exists():raise RuntimeError('An existing ready bundle must not be silently replaced')
    confirmations={}
    choices={}
    for group,item in selection.items():
        checks={}
        for name in item['experiments']:
            p=ROOT/'submissions/development'/name/'prediction_43/confirmation.json'
            result=json.loads(p.read_text())
            if result['selection_sha256']!=digest(ROOT/'submissions/selection.json'):
                raise RuntimeError('Confirmation was performed against a different frozen selection')
            checks[name]=result
        fallback=item['candidate']!='copy' and all(c['difference_mean']<0 for c in checks.values())
        config=item['config'].copy()
        if fallback:
            path=ROOT/'submissions/development'/item['experiments'][0]/'prediction_42/experiment.json'
            config=json.loads(path.read_text())['candidates']['copy']
        choices[group]=dict(candidate='copy' if fallback else item['candidate'], config=config,
                            fallback=fallback,confirmation=checks)
    panels=json.loads((ROOT/'data/panels/index.json').read_text())
    manifest={}
    for group,board in BOARDS.items():
        config=choices[group]['config'].copy()
        kind=config.pop('kind')
        if group=='temporal':
            sources=['T1/E9.5_RNA.h5ad','T1/E10.5_RNA.h5ad']
            stages=[load_stage(p) for p in sources]
            pred=TemporalTransport(*stages,interval=1.).predict(2.,seed=42,**config)
        elif group=='heart':
            sources=['T2/E8.25_late.h5ad','T2/E8.5.h5ad','T2/E8.75.h5ad','T2/E9.5.h5ad','T2/E10.5.h5ad']
            stages=[load_stage(p) for p in sources]
            if config['geometry']:
                config['geometry']=max(spatial_growth(stages,[8.25,8.5,8.75,9.5,10.5]),.1)
            pred=TemporalTransport(stages[-2],stages[-1],interval=1.).predict(2.,seed=42,**config)
        elif group=='embryo':
            sources=['T2/E7.5.h5ad','T2/E8.0.h5ad']
            stages=[load_stage(p) for p in sources]
            genes=stages[0].var_names[stages[0].var_names.isin(stages[1].var_names)]
            stages=[a[:,genes].copy() for a in stages]
            if kind=='copy':
                from src.data import sample
                pred=sample(stages[0])
            else:
                fn=interpolate if kind=='mixture' else ot_interpolate
                pred=fn(*stages,.5,seed=42)
        else:
            sources=['T2/E8.75.h5ad']
            stages=[load_stage(p) for p in sources]
            pred=lineage_perturbation(stages[0],target='bcatenin',seed=42,**config)
        genes=(ROOT/'data/panels'/panels[board]['genes_file']).read_text().splitlines()
        pred=pred[:,genes].copy()
        # The portal assigns types independently. Submit no cell-type labels.
        clean=ad.AnnData(pred.X.astype(np.float32),var=pred.var.iloc[:,:0].copy())
        clean.obs_names=[f'historical-entry_{i}' for i in range(clean.n_obs)]
        clean.uns['method']=str(pred.uns.get('method',choices[group]['candidate']))
        if panels[board]['needs_coords']:
            clean.obsm['spatial_3D']=pred.obsm['spatial_3D'].astype(np.float32)
        path=final/(board.replace(':','__')+'.h5ad')
        clean.write_h5ad(path,compression='gzip')
        manifest[board]=dict(file=str(path.relative_to(ROOT)),method=choices[group]['candidate'],
            group=group,config=config,cells=clean.n_obs,genes=clean.n_vars,seed=42,
            sha256=digest(path),source_sha256={p:digest(ROOT/'data/raw'/p) for p in sources},
            removed_duplicates={p:int(a.uns.get('removed_duplicates',0)) for p,a in zip(sources,stages)},
            selection_sha256=digest(ROOT/'submissions/selection.json'),
            code_sha256={p:digest(ROOT/p) for p in ['src/data.py','src/models.py','scripts/prepare_submission.py']})
        print(board,choices[group]['candidate'],digest(path),flush=True)
        del pred,clean,stages
        gc.collect()
    (final/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    (final/'selection_and_confirmation.json').write_text(json.dumps(choices,indent=2)+'\n')
    packages=['anndata','numpy','pandas','scipy','scikit-learn','veckit','vec-community-kit','requests']
    (final/'environment.json').write_text(json.dumps(dict(python=platform.python_version(),
        packages={p:metadata.version(p) for p in packages}),indent=2)+'\n')

if __name__=='__main__':main()
