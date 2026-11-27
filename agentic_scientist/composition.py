"""T1 blood guard in the published test configuration (E8.5, E9.5, E10.5 -> E12.5, heart chambers).

A blood-heavy E12.5 forecast is implausible for a chamber dissection. The guard: the forecast's blood-like share may not exceed the last input's (E10.5) share.
"""
import numpy as np

BLOOD = ('Hba-a1', 'Hba-a2', 'Hbb-bs', 'Hbb-bt')
THRESHOLD = 3.0  # mean log1p CP10k of the adult globins


def blood_share(data):
    genes = [g for g in BLOOD if g in data.var_names]
    if len(genes) < 2:
        raise ValueError('insufficient blood markers')
    expression = np.asarray(data[:, genes].X.mean(axis=1)).ravel()
    if not expression.size or not np.isfinite(expression).all():
        raise ValueError('invalid blood marker expression')
    return float((expression > THRESHOLD).mean())


CARDIOMYOCYTE = ('Tnnt2', 'Ttn', 'Ryr2')
CM_THRESHOLD = 1.5  # mean log1p CP10k; on released E9.5/E10.5 labels: recall 0.81-0.89, precision 0.94-0.96


def cardiomyocyte_share(data):
    genes = [g for g in CARDIOMYOCYTE if g in data.var_names]
    if len(genes) < 2:
        raise ValueError('insufficient cardiomyocyte markers')
    expression = np.asarray(data[:, genes].X.mean(axis=1)).ravel()
    return float((expression > CM_THRESHOLD).mean())


# Tissues the organisers list as outside the heart chambers (same list the T1 seed conditions on) plus the
# heart-field progenitors of the pharyngeal/dorsal mesoderm.
NON_CHAMBER = frozenset(x.lower() for x in (
    'Foregut', 'Surface Ectoderm', 'SE', 'Paraxial Mesoderm', 'EXEM', 'Neural Tube', 'pPHM', 'aPHM', 'Hepatocyte',
    'Hepatocytes', 'ST', 'Gut Endoderm', 'Epithelium', 'aSHF', 'pSHF', 'SHF', 'JCF'))
CM_TOLERANCE = 0.9


def chamber_cardiomyocyte_share(last_input):
    """Cardiomyocyte-like share of the last input once the non-chamber tissues are set aside."""
    if 'celltype' not in last_input.obs:
        return cardiomyocyte_share(last_input)
    keep = ~np.isin(np.char.lower(last_input.obs['celltype'].to_numpy(dtype=str)), list(NON_CHAMBER))
    return cardiomyocyte_share(last_input[keep]) if keep.sum() >= 100 else cardiomyocyte_share(last_input)


def blood_guard(prediction, last_input):
    """Blood may not exceed the last input's share, and a heart-CHAMBER forecast may not be depleted of
    cardiomyocyte-like cells: at least CM_TOLERANCE x their share in the last input's chamber tissues.
    (TEST: a forecast with 6% cardiomyocytes, from continuing the one-interval E9.5->E10.5 lineage
    trend, scored mmd_u 66 against 84+ for entries that keep the latest stage's myocardial share.)"""
    pred, limit = blood_share(prediction), blood_share(last_input)
    cm, cm_floor = cardiomyocyte_share(prediction), CM_TOLERANCE * chamber_cardiomyocyte_share(last_input)
    failures = (['blood'] if pred > limit else []) + (['cardiomyocytes'] if cm < cm_floor else [])
    return dict(prediction=dict(blood=pred, cardiomyocytes=cm), blood_limit=limit, cardiomyocyte_floor=cm_floor,
                failures=failures)


def compare(prediction, reference, blood_reference):
    """Compatibility shim for agentic_scientist/tools/calibrate.py (historical analysis): blood rule only."""
    return blood_guard(prediction, blood_reference)
