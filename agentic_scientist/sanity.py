"""Frozen plausibility checks for 3-day forecasts (no ground truth). Part of the AgenticScientist lock.

The real tests extrapolate 2-3 days (T1 and heart E12.5); no released data reaches that far, so we cannot score it.
We can still reject forecasts that are obviously broken. Every bound is generous on purpose: a plausible
forecast must pass easily; only blow-ups fail. Calibrated on the seed (see checks/sanity_calib.json).
"""
import numpy as np
from scipy import sparse

from shinka_ve import harness

BOUNDS = dict(gene_blowup_frac=0.02,   # share of genes whose mean exceeds 3x the inputs' max mean + 0.5
              dominate=0.6,            # one cell type may not exceed max(0.6, 2x its largest input share)
              drift_ratio=2.5,         # pseudobulk drift vs the inputs' drift scaled linearly to the horizon
              collapse=0.1,            # median per-gene variance ratio (pred / last input) below this = collapsed
              radius=(0.7, 4.0))       # heart RMS radius ratio vs the last input


def dense(x):
    return np.asarray(x.toarray() if sparse.issparse(x) else x, dtype=np.float64)


def plausibility(pred, split):
    spec = harness.SPLITS[split]
    ins = [harness.load_stage(p) for p in spec['inputs']]
    genes = [g for g in ins[-1].var_names if g in set(pred.var_names)]
    if len(genes) > 3000:  # T1 whole transcriptome: keep the 3000 most variable genes of the last input
        X = ins[-1][:, genes].X
        X = X.tocsc() if sparse.issparse(X) else X
        m = np.asarray(X.mean(0)).ravel()
        v = np.asarray(X.multiply(X).mean(0)).ravel() - m ** 2 if sparse.issparse(X) else X.var(0)
        genes = [genes[i] for i in np.argsort(-v)[:3000]]
    F, L = dense(ins[0][:, genes].X), dense(ins[-1][:, genes].X)
    P = dense(pred[:, genes].X)
    out, fails = {}, []
    if not np.isfinite(P).all() or (P < 0).any():
        fails.append('non-finite or negative expression')
        return dict(metrics=out, fails=fails)
    im = np.maximum(F.mean(0), L.mean(0))
    out['gene_blowup_frac'] = float((P.mean(0) > 3 * im + .5).mean())
    if out['gene_blowup_frac'] > BOUNDS['gene_blowup_frac']:
        fails.append(f"{out['gene_blowup_frac']:.1%} of genes blow up (>3x the inputs' max mean)")
    var_l = L.var(0)
    ok = var_l > 1e-6
    out['var_ratio'] = float(np.median(P.var(0)[ok] / var_l[ok]))
    if out['var_ratio'] < BOUNDS['collapse']:
        fails.append(f"collapsed population (median variance ratio {out['var_ratio']:.2f})")
    interval = spec['times'][-1] - spec['times'][-2]
    horizon = spec['time'] - spec['times'][-1]
    d_in = np.linalg.norm(L.mean(0) - F.mean(0)) * horizon / interval
    out['drift_ratio'] = float(np.linalg.norm(P.mean(0) - L.mean(0)) / max(d_in, 1e-9))
    if out['drift_ratio'] > BOUNDS['drift_ratio']:
        fails.append(f"runaway drift ({out['drift_ratio']:.1f}x the linear trend)")
    # cell-type domination: nearest centroid of the last input's annotated types (top-variance genes)
    lab = np.asarray(ins[-1].obs['celltype']).astype(str)
    top = np.argsort(-var_l)[:500]
    types = sorted(set(lab))
    C = np.stack([L[lab == t][:, top].mean(0) for t in types])
    rng = np.random.default_rng(0)
    idx = rng.choice(len(P), min(len(P), 4000), replace=False)
    d = ((P[idx][:, top, None] - C.T[None]) ** 2).sum(1)
    share = np.bincount(d.argmin(1), minlength=len(types)) / len(idx)
    in_share = np.zeros(len(types))
    for a in ins:
        la = np.asarray(a.obs['celltype']).astype(str)
        in_share = np.maximum(in_share, np.array([(la == t).mean() for t in types]))
    j = int(share.argmax())
    out['max_type_share'], out['max_type'], out['max_type_input_share'] = float(share[j]), types[j], float(in_share[j])
    if share[j] > max(BOUNDS['dominate'], 2 * in_share[j]):
        fails.append(f"{types[j]} takes {share[j]:.0%} of cells (max {in_share[j]:.0%} in the inputs)")
    if spec['board'] == 'heart' and 'spatial_3D' in pred.obsm:
        r = lambda X: float(np.sqrt(((X - X.mean(0)) ** 2).sum(1).mean()))  # noqa: E731
        out['radius_ratio'] = r(np.asarray(pred.obsm['spatial_3D'], float)) / r(np.asarray(ins[-1].obsm['spatial_3D'], float))
        lo, hi = BOUNDS['radius']
        if not lo <= out['radius_ratio'] <= hi:
            fails.append(f"heart size ratio {out['radius_ratio']:.2f} outside [{lo}, {hi}]")
    return dict(metrics=out, fails=fails)
