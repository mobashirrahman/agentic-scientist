"""Load log-normalized released expression and harmonize broad cell labels.

Never reads .raw. Duplicate expression alone is not sufficient at low depth:
T2 late-stage repeats must be in adjacent sections; T3 must share a barcode.
Original labels are retained, because broad aliases are not equivalent subtypes.
"""
from pathlib import Path
import hashlib
import anndata as ad
import numpy as np
from scipy import sparse

ROOT = Path(__file__).resolve().parents[1]

# Broad biological groups shared by T2 E9.5 and the T3 label vocabulary.
# This mapping is used for modelling only; submission labels are ignored by scoring.
LABEL_GROUPS = {
    'vCM': 'Ventricular cardiomyocyte', 'V-CM': 'Ventricular cardiomyocyte',
    'OFT-CM': 'Outflow/right ventricular cardiomyocyte',
    'OFT/RV-CM': 'Outflow/right ventricular cardiomyocyte',
    'Peri': 'Pericardium', 'Proepi': 'Proepicardium',
    'Hepatocytes': 'Hepatocyte', 'SE': 'Surface Ectoderm',
    'Branch Arch': 'Branchial Arch', 'DMP': 'Dorsal mesenchymal protrusion',
    'DPM': 'Dorsal mesenchymal protrusion',
    'Dorsal-PAM': 'Paraxial Mesoderm', 'Lateral-PAM': 'Paraxial Mesoderm',
    'Chamber-Endo': 'Endocardium', 'Cush-EndoMT-Endo': 'Endocardium',
    'BEC': 'Endothelium', 'Great Artery Endoth': 'Endothelium',
    'early-VEC': 'Endothelium',
}


def duplicate_mask(a, relative):
    """Keep first exact count-profile record in each corroborated duplicate chain."""
    keep = np.ones(a.n_obs, dtype=bool)
    if 'spatial_3D' not in a.obsm:
        return keep
    counts = sparse.csr_matrix(a.layers.get('counts', a.X), copy=True)
    counts.sum_duplicates()
    counts.eliminate_zeros()
    counts.sort_indices()
    positions = np.asarray(a.obsm['spatial_3D'])[:, :3]
    levels = np.unique(positions[:, 2])
    if len(levels) < 2:
        return keep
    step = np.median(np.diff(levels))
    is_ko = str(relative).startswith('T3/')
    late_t2 = Path(relative).name in {'E8.0.h5ad', 'E8.25_late.h5ad', 'E8.75.h5ad'}
    if not (is_ko or late_t2):
        return keep
    groups = {}
    for i in range(a.n_obs):
        start, end = counts.indptr[i:i+2]
        key = hashlib.sha256(counts.indices[start:end].tobytes() + counts.data[start:end].tobytes()).digest()
        previous = groups.setdefault(key, [])
        for j in previous:
            if is_ko:
                duplicate = (str(a.obs_names[i]) == str(a.obs_names[j])
                             and np.linalg.norm(positions[i, :2] - positions[j, :2]) < .01)
            else:
                # Registration shifts identical profiles in XY by up to 65 units.
                # Require an adjacent Z section, not an arbitrary XY cutoff.
                duplicate = np.isclose(abs(positions[i, 2] - positions[j, 2]), step, atol=.5)
            if duplicate:
                keep[i] = False
                break
        # Retain the chain history even if this row was itself a duplicate.
        previous.append(i)
    return keep


def load_stage(relative):
    a = ad.read_h5ad(ROOT / 'data/raw' / relative)
    x = sparse.csr_matrix(a.X, dtype=np.float32)
    x.eliminate_zeros()
    keep = duplicate_mask(a, relative)
    obs = a.obs.iloc[np.flatnonzero(keep)].copy()
    if 'celltype' in obs:
        labels = obs['celltype'].astype(str)
        obs['celltype_group'] = labels.map(lambda label: LABEL_GROUPS.get(label, label))
    out = ad.AnnData(x[keep], obs=obs, var=a.var.copy())
    out.obs_names_make_unique()
    if 'spatial_3D' in a.obsm:
        out.obsm['spatial_3D'] = np.asarray(a.obsm['spatial_3D'])[keep, :3].astype(np.float32)
    out.uns['source'] = relative
    out.uns['removed_duplicates'] = int((~keep).sum())
    out.uns['loader_version'] = '2-adjacent-section-and-barcode'
    return out


def sample(a, n=3000, seed=42):
    idx = np.random.default_rng(seed).choice(a.n_obs, n, replace=a.n_obs < n)
    out = a[idx].copy()
    out.obs_names = [f'pred_{i}' for i in range(n)]
    return out
