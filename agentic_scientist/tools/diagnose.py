"""Explain WHY a program scores what it does on one DEV split (holdout splits are refused).

  python <ROOT>/agentic_scientist/tools/diagnose.py <dev_split> [--workspace .] [--out diag] [--score]

Runs your predict() on the split, compares the prediction with the dev target and the reference stage, prints:
  1. composition: predicted vs target vs reference cell-type fractions (prediction labelled by kNN on the target)
  2. pseudobulk DE: corr / sign agreement / severity slope (β, R²) on the target's top DE genes + worst genes
  3. spatial (T2/T3): rms size ratio, occupancy Dice in the rms frame, neighbourhood-composition error
and writes PNG plots (PCA overlay, spatial projections, composition bars) you can open with your Read tool.
--score also runs the real scorer (one seed) for the per-metric skills.
"""
import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from agentic_scientist.evaluate import SETS, load, load_params, screen_workspace  # noqa: E402
from shinka_ve import harness  # noqa: E402
from src.data import load_stage  # noqa: E402

RNG = np.random.default_rng(0)


def dense(a, n=3000):
    idx = np.sort(RNG.choice(a.n_obs, min(n, a.n_obs), replace=False))
    sub = a[idx]
    X = sub.X.toarray() if hasattr(sub.X, 'toarray') else np.asarray(sub.X)
    return sub, X.astype(np.float32)


def knn_labels(Xr, labels, Xq, k=15):
    from sklearn.neighbors import KNeighborsClassifier
    return KNeighborsClassifier(k).fit(Xr, labels).predict(Xq)


def fractions(lab):
    u, c = np.unique(lab, return_counts=True)
    return dict(zip(u, c / c.sum()))


def rms_frame(C):
    C = C - C.mean(0)
    return C / np.sqrt((C ** 2).sum(1).mean()), np.sqrt((C ** 2).sum(1).mean())


def occupancy_dice(P, T, bins=16):
    P, _ = rms_frame(P)
    T, _ = rms_frame(T)
    edges = np.linspace(-3, 3, bins + 1)

    def occ(X):
        H, _ = np.histogramdd(np.clip(X, -2.999, 2.999), bins=[edges] * 3)
        return H > 0
    t = occ(T)
    best = 0
    for f in ([1, 1, 1], [-1, -1, 1], [-1, 1, -1], [1, -1, -1]):
        p = occ(P * np.array(f))
        best = max(best, 2 * (p & t).sum() / max(p.sum() + t.sum(), 1))
    return best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('split')
    ap.add_argument('--workspace', default='.')
    ap.add_argument('--out')
    ap.add_argument('--score', action='store_true')
    a = ap.parse_args()
    if a.split not in SETS['dev']['splits']:
        sys.exit(f'refused: {a.split} is not a dev split ({", ".join(SETS["dev"]["splits"])})')
    spec = harness.SPLITS[a.split]
    if spec['board'] == 'temporal':
        sys.exit('T1 offers aggregate scores through quick_eval.py')
    ws = Path(a.workspace).resolve()
    err = screen_workspace(ws)
    if err:
        sys.exit(f'static screen failed: {err}')
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import heavy_slot
    heavy_slot.acquire(f'diagnose {a.split}')
    out = Path(a.out or ws.parent / f'diag_{a.split}')  # outside the workspace: artifacts are not program files
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    pred, ref = harness.run_split(load(ws), a.split, 101, 0, params=load_params(ws))
    target = load_stage(spec['target'])[:, list(ref.var_names)].copy()
    print(f'# {a.split} ({spec["board"]}): predict {time.time() - t0:.0f}s | pred {pred.n_obs} cells, target {target.n_obs}, '
          f'reference {ref.n_obs}, genes {ref.n_vars}')
    report = dict(split=a.split, board=spec['board'])

    # ---- shared low-dim space (top-variance genes, PCA) ----
    from sklearn.decomposition import PCA
    T, Xt = dense(target)
    R, Xr = dense(ref)
    P, Xp = dense(pred)
    var = np.argsort(-np.vstack([Xt, Xr]).var(0))[:2000]
    pca = PCA(30, random_state=0).fit(np.vstack([Xt[:, var], Xr[:, var]]))
    Zt, Zr, Zp = (pca.transform(X[:, var]) for X in (Xt, Xr, Xp))

    # ---- 1. composition ----
    if 'celltype' in T.obs:
        lt = T.obs['celltype'].astype(str).to_numpy()
        lp = knn_labels(Zt, lt, Zp)
        lr = knn_labels(Zt, lt, Zr)  # reference cells mapped to target types, comparable vocabulary
        ft, fp, fr = fractions(lt), fractions(lp), fractions(lr)
        rows = sorted(set(ft) | set(fp), key=lambda c: -abs(fp.get(c, 0) - ft.get(c, 0)))
        print('\n## 1. Composition (fraction; prediction and reference labelled by kNN on target types)')
        print(f'{"cell type":38s} {"pred":>7s} {"target":>7s} {"ref":>7s} {"pred-tgt":>9s}')
        for c in rows[:15]:
            print(f'{c[:38]:38s} {fp.get(c, 0):7.3f} {ft.get(c, 0):7.3f} {fr.get(c, 0):7.3f} {fp.get(c, 0) - ft.get(c, 0):+9.3f}')
        tv = .5 * sum(abs(fp.get(c, 0) - ft.get(c, 0)) for c in set(ft) | set(fp))
        tv_ref = .5 * sum(abs(fr.get(c, 0) - ft.get(c, 0)) for c in set(ft) | set(fr))
        print(f'total variation distance: prediction {tv:.3f} vs copying the reference {tv_ref:.3f} (lower is better)')
        report['composition'] = dict(tv_pred=tv, tv_ref=tv_ref, worst=[(c, fp.get(c, 0), ft.get(c, 0)) for c in rows[:10]])

    # ---- 2. pseudobulk DE ----
    genes = np.asarray(ref.var_names)
    mt, mr, mp = Xt.mean(0), Xr.mean(0), Xp.mean(0)
    dt, dp = mt - mr, mp - mr
    top = np.argsort(-np.abs(dt))[:200]
    sign = float(np.mean(np.sign(dp[top]) == np.sign(dt[top])))
    corr = float(np.corrcoef(dp[top], dt[top])[0, 1]) if dp[top].std() > 0 else float('nan')
    beta = float(np.polyfit(dt[top], dp[top], 1)[0]) if dp[top].std() > 0 else 0.0
    r2 = corr ** 2 if np.isfinite(corr) else 0.0
    print('\n## 2. Pseudobulk change vs reference on the target\'s top-200 changed genes')
    print(f'sign agreement {sign:.2f} | corr {corr:.3f} | slope β {beta:.3f} (R² {r2:.3f}); severity needs β>0 and R²>0.01, '
          f'|log β| small; magnitude ratio |Δpred|/|Δtrue| = {np.abs(dp[top]).mean() / max(np.abs(dt[top]).mean(), 1e-9):.2f}')
    wrong = [i for i in top if np.sign(dp[i]) != np.sign(dt[i])]
    print('wrong-direction genes (true Δ, predicted Δ):', ', '.join(f'{genes[i]}({dt[i]:+.2f},{dp[i]:+.2f})' for i in wrong[:15]) or 'none')
    under = sorted(top, key=lambda i: -(abs(dt[i]) - abs(dp[i])) * (np.sign(dp[i]) == np.sign(dt[i])))[:10]
    print('most under-predicted genes:', ', '.join(f'{genes[i]}({dt[i]:+.2f},{dp[i]:+.2f})' for i in under))
    report['de'] = dict(sign=sign, corr=corr, beta=beta, r2=r2, wrong=[str(genes[i]) for i in wrong[:30]])
    # The scorer's own response metrics on the same matrices (exact definitions, no subsampling split).
    try:
        from vec_local_score.veckit_loader import load_veckit
        load_veckit()._load_task_metrics({'temporal': 'T1', 'perturbation': 'T3'}.get(spec['board'], 'T2'))
        from common import core_metrics as cm
        up, dn, _ = cm.de_genes(Xt, Xr)
        sev = cm.severity_slope(Xp, Xt, Xr)
        def fmt(v):
            if isinstance(v, dict):
                return '{' + ', '.join(f'{k}={x:.3f}' if isinstance(x, float) else f'{k}={x}' for k, x in v.items()
                                       if isinstance(x, (int, float))) + '}'
            return f'{v:.3f}' if isinstance(v, float) else str(v)
        print(f'scorer definitions: truth DE genes {len(up)} up / {len(dn)} down (|Δmean| ≥ {cm.MIN_LFC}) | '
              f'de_score {fmt(cm.de_score(Xp, Xt, Xr))} | de_direction {fmt(cm.de_direction(Xp, Xt, Xr))} | '
              f'severity log β {sev[0]:.3f} (R² {sev[1]:.3f}; worst {cm.SEVERITY_LOG_WORST:.2f} = no/unrelated response, 0 = ideal)')
        dp_all, dt_all = Xp.mean(0) - Xr.mean(0), Xt.mean(0) - Xr.mean(0)
        print(f'response size: std(Δpred) / std(Δtrue) over all genes = {dp_all.std() / max(dt_all.std(), 1e-12):.3f} '
              f'(< 0.01 counts as "no response" → severity at the floor)')
        report['scorer_raw'] = dict(de_up=len(up), de_dn=len(dn), severity_log_beta=sev[0], severity_r2=sev[1])
    except Exception as e:  # noqa: BLE001
        print(f'(scorer metric functions unavailable: {e!r})')

    # ---- 3. spatial ----
    if 'spatial_3D' in pred.obsm and 'spatial_3D' in target.obsm:
        Cp, Ct = np.asarray(P.obsm['spatial_3D'], float), np.asarray(T.obsm['spatial_3D'], float)
        Cr = np.asarray(R.obsm['spatial_3D'], float) if 'spatial_3D' in R.obsm else None
        rp, rt = rms_frame(Cp)[1], rms_frame(Ct)[1]
        print('\n## 3. Spatial')
        print(f'rms radius: pred {rp:.1f}, target {rt:.1f}' + (f', reference {rms_frame(Cr)[1]:.1f}' if Cr is not None else '')
              + f' | scale_log_ratio ≈ {np.log(rp / rt):+.3f} (0 is ideal)')
        dice = occupancy_dice(Cp, Ct)
        dref = occupancy_dice(Cr, Ct) if Cr is not None else float('nan')
        print(f'occupancy Dice (16³ rms frame, best flip): pred {dice:.3f} vs reference {dref:.3f}')
        report['spatial'] = dict(scale_log_ratio=float(np.log(rp / rt)), occupancy_pred=dice, occupancy_ref=dref)
        if 'celltype' in T.obs:
            from sklearn.neighbors import NearestNeighbors
            types = sorted(set(lt))

            def niche(C, lab):
                nn = NearestNeighbors(n_neighbors=16).fit(C)
                idx = nn.kneighbors(C, return_distance=False)[:, 1:]
                M = np.zeros((len(C), len(types)))
                ti = {t: i for i, t in enumerate(types)}
                for r, row in enumerate(idx):
                    for j in row:
                        if lab[j] in ti:
                            M[r, ti[lab[j]]] += 1 / 15
                return M
            Np, Nt = niche(Cp, lp), niche(Ct, lt)
            gap = []
            for i, t in enumerate(types):
                a_, b_ = lp == t, lt == t
                if a_.sum() > 10 and b_.sum() > 10:
                    gap.append((t, float(np.abs(Np[a_].mean(0) - Nt[b_].mean(0)).sum() / 2)))
            gap.sort(key=lambda x: -x[1])
            print('neighbourhood-composition error per type (0 = same neighbours as in the target; drives neighborhood_mmd):')
            print('  ' + ', '.join(f'{t}={g:.2f}' for t, g in gap[:10]))
            report['neighbourhood_gap'] = gap[:15]

    # ---- plots ----
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(1, 2, figsize=(12, 5))
    ax[0].scatter(Zr[:, 0], Zr[:, 1], s=2, c='#bbbbbb', label='reference')
    ax[0].scatter(Zt[:, 0], Zt[:, 1], s=2, c='#2b8cbe', label='target', alpha=.6)
    ax[0].scatter(Zp[:, 0], Zp[:, 1], s=2, c='#e34a33', label='prediction', alpha=.6)
    ax[0].legend(markerscale=4)
    ax[0].set_title(f'{a.split}: PCA 1-2')
    ax[1].scatter(Zt[:, 2], Zt[:, 3], s=2, c='#2b8cbe', alpha=.6)
    ax[1].scatter(Zp[:, 2], Zp[:, 3], s=2, c='#e34a33', alpha=.6)
    ax[1].set_title('PCA 3-4')
    fig.tight_layout()
    fig.savefig(out / 'pca.png', dpi=90)
    plt.close(fig)
    if report.get('spatial'):
        fig, ax = plt.subplots(2, 3, figsize=(14, 9))
        for row, (C, name) in enumerate(((Ct, 'target'), (Cp, 'prediction'))):
            Cn, _ = rms_frame(C)
            for k, (i, j) in enumerate(((0, 1), (0, 2), (1, 2))):
                ax[row, k].scatter(Cn[:, i], Cn[:, j], s=1, c='#2b8cbe' if row == 0 else '#e34a33')
                ax[row, k].set_title(f'{name}: axes {i}-{j} (rms frame)')
                ax[row, k].set_xlim(-3, 3)
                ax[row, k].set_ylim(-3, 3)
        fig.tight_layout()
        fig.savefig(out / 'spatial.png', dpi=80)
        plt.close(fig)
    if report.get('composition'):
        rows = rows[:15]
        fig, ax = plt.subplots(figsize=(10, 6))
        y = np.arange(len(rows))
        ax.barh(y - .2, [ft.get(c, 0) for c in rows], .4, label='target', color='#2b8cbe')
        ax.barh(y + .2, [fp.get(c, 0) for c in rows], .4, label='prediction', color='#e34a33')
        ax.set_yticks(y, [c[:40] for c in rows])
        ax.invert_yaxis()
        ax.legend()
        ax.set_title('cell-type fractions (largest mismatches first)')
        fig.tight_layout()
        fig.savefig(out / 'composition.png', dpi=90)
        plt.close(fig)

    if a.score:
        sc, metrics = harness.score_split(pred, ref, a.split, [101])
        print(f'\n## Scorer (seed 101): {sc:.2f}')
        print('  ' + ', '.join(f'{k}={v:.1f}' for k, v in sorted(metrics.items(), key=lambda kv: kv[1])))
        report['score'] = dict(score=sc, metrics=metrics)
    (out / 'report.json').write_text(json.dumps(report, indent=1, default=float))
    print(f'\nplots: {", ".join(str(p) for p in sorted(out.glob("*.png")))}\nreport: {out / "report.json"}')


if __name__ == '__main__':
    main()
