"""Field-wide calibration: how does a team's P2 validation score (targets we now hold locally) translate into its P3 test
score (hidden targets)? Public leaderboard data only. For each board pair it fits test = a + b * val over the teams
that appear on both boards (robust: Theil-Sen), reports the fit, and maps our local scores through it.

Board pairs (P2 val target == our local split):
  T1      T1:val (E8.5+E9.5 -> E10.5)            == local temporal_val          -> T1:test (E10.5 -> E12.5 chambers)
  heart   T2:heart:val_extrap (-> E10.5)         == local holdout heart_e105    -> T2:heart:test_extrap (-> E12.5)
  embryo  T2:embryo:val_interp (E7.5 / E7.75)    == local holdout embryo_late   -> T2:embryo:test_interp
  T3      T3:gata4 (Gata4 KO E8.75)              == local dev gata4_1/gata4_2   -> T3:bcatenin (Ctnnb1 KO)

  .venv/bin/python -I scripts/calibration_map.py [--local T1=59.3 heart=51.3 embryo=74 T3=55.6] [--out docs/leaderboard/<date>]
"""
import argparse
import json
import time
import urllib.request
from pathlib import Path

import numpy as np

API = 'https://api.virtualembryo.ai/challenge'
PAIRS = {'T1': (('T1', 'T1:val'), ('T1', 'T1:test')),
         'heart': (('T2', 'T2:heart:val_extrap'), ('T2', 'T2:heart:test_extrap')),
         'embryo': (('T2', 'T2:embryo:val_interp'), ('T2', 'T2:embryo:test_interp')),
         'T3': (('T3', 'T3:gata4'), ('T3', 'T3:bcatenin'))}


def get(task, split, board):
    url = f'{API}/leaderboard?task={task}&split={split}&board={board}'
    req = urllib.request.Request(url, headers={'User-Agent': 'leaderboard-snapshot'})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def theil_sen(x, y):
    from scipy.stats import theilslopes
    b, a, lo, hi = theilslopes(y, x)
    return a, b, lo, hi


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--local', nargs='*', default=[], help='board=score, our local score on the matching split')
    ap.add_argument('--out', default=f"docs/leaderboard/{time.strftime('%Y-%m-%d')}")
    a = ap.parse_args()
    local = {k: float(v) for k, v in (s.split('=') for s in a.local)}
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    report, md = {}, ['# Local-to-test calibration (public P2 validation vs P3 test boards)', '',
                      f'Fetched {time.strftime("%Y-%m-%d %H:%M %Z")}. One point per team on both boards (each its best).', '',
                      '| board | teams | fit test = a + b*val | Spearman | test at val 50/60/70/80 | our local | our expected test |',
                      '|---|---|---|---|---|---|---|']
    for name, ((tv, bv), (tt, bt)) in PAIRS.items():
        val, test = get(tv, 'val', bv), get(tt, 'test', bt)
        (out / f'p2_{bv.replace(":", "_")}.json').write_text(json.dumps(val, indent=1))
        V = {r['team']: r['headline'] for r in val.get('rows', []) if r.get('headline') is not None}
        T = {r['team']: r['headline'] for r in test.get('rows', []) if r.get('headline') is not None}
        both = sorted(set(V) & set(T))
        x, y = np.array([V[t] for t in both]), np.array([T[t] for t in both])
        keep = (x > 30) & (y > 30)  # drop broken submissions on either side
        x, y = x[keep], y[keep]
        ia, ib, lo, hi = theil_sen(x, y)
        from scipy.stats import spearmanr
        rho = spearmanr(x, y).correlation
        grid = {g: round(ia + ib * g, 1) for g in (50, 60, 70, 80)}
        resid = y - (ia + ib * x)
        mine = local.get(name)
        exp = round(ia + ib * mine, 1) if mine is not None else None
        band = (round(exp + np.percentile(resid, 10), 1), round(exp + np.percentile(resid, 90), 1)) if exp is not None else None
        report[name] = dict(val_board=bv, test_board=bt, teams=int(len(x)), a=ia, b=ib, b_ci=(lo, hi), spearman=rho,
                            grid=grid, resid_p10_p90=(float(np.percentile(resid, 10)), float(np.percentile(resid, 90))),
                            local=mine, expected_test=exp, expected_band_p10_p90=band)
        md.append(f"| {name} | {len(x)} | {ia:.1f} + {ib:.2f}*val (b {lo:.2f}..{hi:.2f}) | {rho:.2f} | "
                  f"{grid[50]}/{grid[60]}/{grid[70]}/{grid[80]} | {mine if mine is not None else '-'} | "
                  f"{exp if exp is not None else '-'}{f' ({band[0]}..{band[1]})' if band else ''} |")
    if all(report[k]['expected_test'] is not None for k in report):
        e = {k: report[k]['expected_test'] for k in report}
        total = e['T1'] + (e['heart'] + e['embryo']) / 2 + e['T3']
        md += ['', f"Expected total = T1 + (heart + embryo)/2 + T3 = **{total:.1f}**"]
        report['expected_total'] = total
    md += ['', 'Caveats: P2 headlines are each team\'s best over many submissions (selected on the board, so optimistic);',
           'the official scorer subsamples differently from our local wrapper; T3 moves from Gata4 to Ctnnb1 (different gene).',
           'Use the fit for orders of magnitude, not decimals.']
    (out / 'calibration.json').write_text(json.dumps(report, indent=1, default=float))
    (out / 'CALIBRATION.md').write_text('\n'.join(md) + '\n')
    print('\n'.join(md))


if __name__ == '__main__':
    main()
