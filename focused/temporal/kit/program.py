"""Empirical T1 sampler with bounded changes in broad donor-type frequencies."""
import numpy as np

ALIASES = {
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


def _groups(stage):
    return np.asarray([ALIASES.get(label, label) for label in stage.obs['celltype'].astype(str)])


def predict(inputs, times, target_time, context):
    earlier, latest = inputs[-2:]
    group_earlier, group_latest = _groups(earlier), _groups(latest)
    types, inverse, counts = np.unique(group_latest, return_inverse=True, return_counts=True)
    earlier_fractions = np.array([max(np.mean(group_earlier == label), .005) for label in types])
    growth = np.clip(np.log((counts / latest.n_obs) / earlier_fractions), -np.log(2), np.log(2))
    horizon = min((target_time - times[-1]) / (times[-1] - times[-2]), 2.0)
    weights = np.exp(.5 * horizon * growth[inverse])
    rng = np.random.default_rng(context['seed'])
    rows = rng.choice(latest.n_obs, context['n'], replace=True, p=weights / weights.sum())
    out = latest[rows].copy()
    out.obs_names = [f'pred_{i}' for i in range(out.n_obs)]
    return out
