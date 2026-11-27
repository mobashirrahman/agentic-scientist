"""Long-horizon check against ALLOWED late data (after E13.5): does the program's far forecast look like a real late heart?

Rules §10 forbid any use of measured data from after E9.5 up to and including E13.5, but anything after E13.5 is allowed
(and disclosed in docs/EXTERNAL_SOURCES.md). This check runs the workspace's heart program from the released heart stages
(E8.25_late ... E9.5, never E10.5) to E14.5 with sampling='heart_dissected', and compares it with:
  - Feulner et al. 2024 wild-type dissected hearts at E14.5 (context['external'] for the heart board),
  - GSE282547 Slide-seq wild-type heart sections at E14.5 (context['external_spatial']).
Different platforms (Drop-seq, Slide-seq vs MERFISH), so absolute expression is not compared. Only platform-robust
quantities are: the fraction of each heart compartment (marker-defined identically on both sides) and which compartments
neighbour which (spatial kNN co-occurrence). It is a diagnostic for long-horizon behaviour, not a score.
For T1 it runs E8.5+E9.5 -> E16.5 and compares cardiac compartment fractions with the Qiu 2024 late anchor (TS24-25).

  .venv/bin/python agentic_scientist/tools/late_anchor_check.py <workspace> [--board heart|temporal|both] [--json out.json]
"""
import argparse
import importlib.util
import json
import sys

import numpy as np

from mgcheck import harness, load_stage
from agentic_scientist.evaluate import load_params
from heavy_slot import acquire

from agentic_scientist.tools.feulner_forecast import COMPARTMENTS


def dense(x):
    return np.asarray(x.toarray() if hasattr(x, 'toarray') else x, dtype=np.float32)


def compartments(adata):
    names, scores = [], []
    for name, genes in COMPARTMENTS.items():
        g = [x for x in genes if x in set(adata.var_names)]
        if not g:
            continue
        X = dense(adata[:, g].X)
        Z = (X - X.mean(0)) / (X.std(0) + 1e-6)
        names.append(name)
        scores.append(Z.mean(1))
    S = np.vstack(scores).T
    lab = np.array(names, dtype=object)[S.argmax(1)]
    lab[S.max(1) <= 0.25] = 'other'
    return lab


def fractions(lab):
    keys = list(COMPARTMENTS) + ['other']
    return {k: round(float(np.mean(lab == k)), 4) for k in keys}


def l1(a, b):
    return round(sum(abs(a[k] - b[k]) for k in a) / 2, 4)


def neighbours(coords, lab, k=10):
    """Row-normalised compartment co-occurrence among each cell's k nearest spatial neighbours."""
    from sklearn.neighbors import NearestNeighbors
    keys = list(COMPARTMENTS) + ['other']
    idx = NearestNeighbors(n_neighbors=k + 1).fit(coords).kneighbors(coords, return_distance=False)[:, 1:]
    M = np.zeros((len(keys), len(keys)))
    pos = {c: i for i, c in enumerate(keys)}
    for i, row in enumerate(idx):
        for j in row:
            M[pos[lab[i]], pos[lab[j]]] += 1
    return M / np.maximum(M.sum(1, keepdims=True), 1)


def load_program(ws):
    sys.path.insert(0, str(ws))
    spec = importlib.util.spec_from_file_location('mg_prog', f'{ws}/program.py')
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def rms(c):
    c = c - c.mean(0)
    return float(np.sqrt((c ** 2).sum(1).mean()))


def check_heart(mod, seed, params):
    paths = ['T2/E8.25_late.h5ad', 'T2/E8.5.h5ad', 'T2/E8.75.h5ad', 'T2/E9.5.h5ad']
    times = [8.25, 8.5, 8.75, 9.5]
    inputs = [load_stage(p) for p in paths]
    genes = list(inputs[-1].var_names)
    ctx = dict(seed=seed, fit_seed=0, n=5000, knockout=None, sampling='heart_dissected', params=params,
               **harness.external_context('heart', genes, inputs, times))
    pred = mod.predict('heart', [a.copy() for a in inputs], times, 14.5, ctx)
    out = dict(horizon='E9.5 -> E14.5', n_pred=int(pred.n_obs))
    plab = compartments(pred)
    out['pred_fractions'] = fractions(plab)
    ext, sp = ctx.get('external'), ctx.get('external_spatial')
    if ext is not None:
        a = ext[np.isclose(np.asarray(ext.obs['stage_days'], float), 14.5)]
        out['feulner_e14.5_fractions'] = fractions(compartments(a))
        out['fraction_distance_vs_feulner'] = l1(out['pred_fractions'], out['feulner_e14.5_fractions'])
    if sp is not None:
        s = sp[np.isclose(np.asarray(sp.obs['stage_days'], float), 14.5)]
        slab = compartments(s)
        out['slideseq_e14.5_fractions'] = fractions(slab)
        out['fraction_distance_vs_slideseq'] = l1(out['pred_fractions'], out['slideseq_e14.5_fractions'])
        Mp = neighbours(np.asarray(pred.obsm['spatial_3D'])[:, :2], plab)
        Ms = neighbours(np.asarray(s.obsm['spatial'])[:, :2], slab)
        out['neighbourhood_corr_vs_slideseq'] = round(float(np.corrcoef(Mp.ravel(), Ms.ravel())[0, 1]), 3)
    out['growth_rms_ratio_vs_E9.5'] = round(rms(np.asarray(pred.obsm['spatial_3D'])[:, :2]) /
                                             rms(np.asarray(inputs[-1].obsm['spatial_3D'])[:, :2]), 3)
    return out


def check_temporal(mod, seed, params):
    paths, times = ['T1/E8.5_RNA.h5ad', 'T1/E9.5_RNA.h5ad'], [8.5, 9.5]
    inputs = [load_stage(p) for p in paths]
    genes = list(inputs[-1].var_names)
    ctx = dict(seed=seed, fit_seed=0, n=5000, knockout=None, sampling='heart_chambers', params=params,
               **harness.external_context('temporal', genes, inputs, times))
    pred = mod.predict('temporal', [a.copy() for a in inputs], times, 16.5, ctx)
    plab, ilab = compartments(pred), compartments(inputs[-1])
    out = dict(horizon='E9.5 -> E16.5', n_pred=int(pred.n_obs), pred_fractions=fractions(plab))
    # Qiu late cells are a per-cell-type subset of the whole embryo (not a heart dissection), so their composition is
    # meaningless here. Compare the maturation DIRECTION instead, within one compartment and one platform: Qiu late
    # (TS24-25) minus Qiu early (TS12-13) versus prediction minus the latest input, over the genes Qiu says change most.
    ext = ctx.get('external')
    if ext is not None and 'group' in ext.obs and 'cell_type' in ext.obs:
        grp, ct = ext.obs['group'].astype(str).to_numpy(), ext.obs['cell_type'].astype(str).str.lower().to_numpy()
        for comp, key in (('myocardium', 'cardi'), ('endocardium_endothelium', 'endothel')):
            hit = np.char.find(ct.astype(str), key) >= 0
            early, late = (grp == 'calibration') & hit, (grp == 'anchor_late') & hit
            if early.sum() < 30 or late.sum() < 30 or (plab == comp).sum() < 30 or (ilab == comp).sum() < 30:
                continue
            g = [x for x in ext.var_names if x in set(pred.var_names) and x in set(inputs[-1].var_names)]
            d_ref = dense(ext[late][:, g].X).mean(0) - dense(ext[early][:, g].X).mean(0)
            d_pred = dense(pred[plab == comp][:, g].X).mean(0) - dense(inputs[-1][ilab == comp][:, g].X).mean(0)
            top = np.argsort(-np.abs(d_ref))[:500]
            out[f'{comp}_maturation_corr_vs_qiu'] = round(float(np.corrcoef(d_pred[top], d_ref[top])[0, 1]), 3)
            out[f'{comp}_maturation_sign_agreement'] = round(float(np.mean(np.sign(d_pred[top]) == np.sign(d_ref[top]))), 3)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('workspace')
    ap.add_argument('--board', default='both', choices=['heart', 'temporal', 'both'])
    ap.add_argument('--seed', type=int, default=101)
    ap.add_argument('--json')
    a = ap.parse_args()
    acquire('late anchor check')
    mod = load_program(a.workspace)
    params = load_params(a.workspace)
    res = {}
    if a.board in ('heart', 'both'):
        res['heart'] = check_heart(mod, a.seed, params.get('heart', {}))
    if a.board in ('temporal', 'both'):
        res['temporal'] = check_temporal(mod, a.seed, params.get('temporal', {}))
    print(json.dumps(res, indent=1))
    if a.json:
        with open(a.json, 'w') as f:  # noqa: PTH123 - tool, not a program
            json.dump(res, f, indent=1)


if __name__ == '__main__':
    main()
