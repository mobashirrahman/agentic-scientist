"""[late variant: TS24-TS25 only, group anchor_late] Fetch a rule-compliant subset of Qiu et al. 2024 (Nature 626:1084) from CELLxGENE Census.

Challenge rules section 10 (Task 1): external data after E9.5 up to and including
E13.5 is excluded; anything after E13.5 may be used if disclosed. Census carries
only Theiler stages, which are coarse, so we use a conservative whitelist:

  calibration: TS12, TS13  (~E8.0-E9.0, earlier than the released E9.5)
  anchor:      TS23        (~E15; TS22 straddles E13.5-E15 and is never fetched)

The stage filter is applied server-side inside the Census query, so cells from
TS14-TS22 are never transferred. Every returned row is asserted against the
whitelist before anything is written. Run with the separate census venv:

  /scratch/user/venvs/census/bin/python -I scripts/v2/fetch_qiu2024.py
"""
import hashlib
import json
from pathlib import Path

import anndata as ad
import cellxgene_census
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'data/external/qiu2024'
CENSUS_VERSION = '2025-11-08'
COLLECTION_DOI = '10.1038/s41586-024-07069-w'
# Major-cell-cluster datasets covering lineages present in the T1 heart-region dissection.
DATASETS = {
    'cardiomyocytes': '57b15e23-7838-4cae-8d72-9d4735b6d0f4',
    'endothelium': '361eef7c-ea8b-4289-95ee-2cffa42c0353',
    'hepatocytes': '977e6167-e91a-435c-a5a4-ceefc88fdb32',
    'mesoderm': 'dcfa2614-7ca7-4d82-814c-350626eccb26',
    'epithelial': '96a9b396-654b-4507-acaf-5019987250f0',
    'primitive_erythroid': 'a83d919c-87ac-4fe8-a655-71180168ec68',
}
GROUPS = {
    'anchor_late': ['Theiler stage 24', 'Theiler stage 25'],  # ~E16-E17: after E13.5 under any Theiler mapping
}
ALLOWED = {s for v in GROUPS.values() for s in v}
CAP = 4000  # cells per (dataset, cell_type, group); keeps cardiomyocytes complete
SEED = 0


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(SEED)
    manifest = dict(source='Qiu et al. 2024 Nature 626:1084', doi=COLLECTION_DOI,
                    census_version=CENSUS_VERSION, groups=GROUPS, cap=CAP, seed=SEED, files={})
    with cellxgene_census.open_soma(census_version=CENSUS_VERSION) as census:
        mouse = census['census_data']['mus_musculus']
        for group, stages in GROUPS.items():
            for name, dataset in DATASETS.items():
                flt = f"dataset_id == '{dataset}' and development_stage in {stages!r}"
                obs = mouse.obs.read(value_filter=flt, column_names=[
                    'soma_joinid', 'development_stage', 'donor_id', 'cell_type']).concat().to_pandas()
                assert set(obs.development_stage.astype(str)) <= ALLOWED, 'forbidden stage returned'
                chosen = []
                for _, rows in obs.groupby(obs.cell_type.astype(str)):
                    ids = rows.soma_joinid.to_numpy()
                    chosen.extend(rng.choice(ids, min(CAP, len(ids)), replace=False))
                if not chosen:
                    continue
                a = cellxgene_census.get_anndata(census, 'Mus musculus', X_name='raw',
                    obs_coords=np.sort(np.array(chosen)),
                    obs_column_names=['dataset_id', 'development_stage', 'donor_id', 'cell_type', 'assay'],
                    var_column_names=['feature_id', 'feature_name'])
                assert set(a.obs.development_stage.astype(str)) <= ALLOWED, 'forbidden stage returned'
                assert set(a.obs.dataset_id.astype(str)) == {dataset}
                a.var_names = a.var.feature_name.astype(str).to_numpy()
                a.var_names_make_unique()
                a.obs['qiu_cluster'] = name
                a.obs['group'] = group
                path = OUT / f'{group}_{name}.h5ad'
                a.write_h5ad(path, compression='gzip')
                with path.open('rb') as f:
                    sha = hashlib.file_digest(f, 'sha256').hexdigest()
                manifest['files'][path.name] = dict(cells=int(a.n_obs), sha256=sha,
                    stages=sorted(set(a.obs.development_stage.astype(str))),
                    donors=sorted(set(a.obs.donor_id.astype(str))))
                print(group, name, a.shape, flush=True)
    (OUT / 'manifest_late.json').write_text(json.dumps(manifest, indent=2) + '\n')


if __name__ == '__main__':
    main()
