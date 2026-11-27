"""Independently audit the ready files, selection evidence, portal receipts and quota."""
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import anndata as ad
import h5py
import numpy as np
from scipy import sparse
from src.data import ROOT


def digest(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def require(condition,message):
    if not condition:raise RuntimeError(message)


def main():
    directory=ROOT/'submissions/ready'
    manifest=json.loads((directory/'manifest.json').read_text())
    expected={'T1:test','T2:heart:test_extrap','T2:embryo:test_interp','T3:bcatenin'}
    require(set(manifest)==expected,'Incomplete board set')
    panels=json.loads((ROOT/'data/panels/index.json').read_text())
    receipts=json.loads((directory/'portal_checks.json').read_text())
    quota=json.loads((directory/'quota_check.json').read_text())
    require(set(receipts)==expected,'Missing portal receipts')
    for state in ('before','after'):
        for board in expected:
            item=quota[state]['official_per_board'][board]
            require(item['used']==0 and item['limit']==2,f'Official attempts changed: {board}')
    choices=json.loads((directory/'selection_and_confirmation.json').read_text())
    for group,item in choices.items():
        for experiment,confirmation in item['confirmation'].items():
            require(confirmation['seeds']==[11,23,37] and confirmation['prediction_seed']==43,'Wrong confirmation draws')
            require(confirmation['selection_sha256']==digest(ROOT/'submissions/selection.json'),'Changed frozen selection')
            original=json.loads((ROOT/'submissions/development'/experiment/'prediction_43/confirmation.json').read_text())
            require(original==confirmation,'Copied confirmation differs from source')
            seed_rows=[]
            for seed in confirmation['seeds']:
                rows=json.loads((ROOT/'submissions/development'/experiment/'prediction_43'/f'confirmation_{seed}.json').read_text())
                seed_rows.append(rows)
            for candidate,values in confirmation['scores'].items():
                require(values==[r[candidate]['task_score'] for r in seed_rows],'Confirmation score mismatch')
        difference=[x['difference_mean'] for x in item['confirmation'].values()]
        if item['fallback']:
            require(all(x<0 for x in difference) and item['candidate']=='copy','Incorrect fallback')
    report={}
    verified_sources=set()
    for board,item in manifest.items():
        p=ROOT/item['file']
        require(digest(p)==item['sha256'],f'Output hash mismatch: {board}')
        require(p.stat().st_size<=1200*10**6,'File too large')
        for path,expected_hash in item['code_sha256'].items():
            require(digest(ROOT/path)==expected_hash,f'Code changed: {path}')
        for path,expected_hash in item['source_sha256'].items():
            if path not in verified_sources:
                require(digest(ROOT/'data/raw'/path)==expected_hash,f'Source changed: {path}')
                verified_sources.add(path)
        a=ad.read_h5ad(p)
        contract=panels[board]
        genes=(ROOT/'data/panels'/contract['genes_file']).read_text().splitlines()
        require(list(a.var_names)==genes,f'Wrong gene order: {board}')
        require(a.n_obs==3000 and contract['min_cells']<=a.n_obs<=contract['max_cells'],'Wrong cell count')
        require(a.n_vars==contract['n_genes'],'Wrong gene count')
        values=a.X.data if sparse.issparse(a.X) else np.asarray(a.X)
        require(values.dtype==np.float32 and np.isfinite(values).all() and (values>=0).all(),'Invalid expression')
        # anndata 0.13 exposes X as a synthetic layers[None] entry. Check the
        # physical HDF5 payload rather than treating that view as an extra layer.
        with h5py.File(p, 'r') as h5:
            require('raw' not in h5 and len(h5['layers']) == 0, 'Unexpected raw/layer payload')
        require('celltype' not in a.obs and a.obs_names.is_unique,'Unexpected label/duplicate observation names')
        if contract['needs_coords']:
            require(a.obsm['spatial_3D'].shape==(3000,3),'Wrong coordinate shape')
            require(np.isfinite(a.obsm['spatial_3D']).all(),'Invalid coordinates')
        receipt=receipts[board]
        require(receipt.get('format_only') is True and receipt.get('ok') is True,'Portal did not accept format')
        require(receipt.get('bundle_key')==board and receipt.get('sha256')==item['sha256'],'Wrong portal receipt')
        require(not receipt.get('problems'),'Portal problems reported')
        report[board]=dict(cells=a.n_obs,genes=a.n_vars,sha256=item['sha256'],
            bytes=p.stat().st_size,local_structure=True,portal_format=True,official_attempts_used=0)
    result=dict(status='passed',boards=report,source_files_verified=len(verified_sources),
        selection_sha256=digest(ROOT/'submissions/selection.json'),
        limitations=['Offline backtests do not forecast hidden test scores',
                     'Heart and perturbation final predictions are empirical no-change anchors',
                     'This bundle is Human Team preparation, not Agent Team evidence'])
    (directory/'audit.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
