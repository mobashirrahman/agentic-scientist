"""Snapshot the public P3 test leaderboards (overall + every board, with model names) into docs/leaderboard/<date>/.
Public data only (the same JSON the website renders). Run: .venv/bin/python -I scripts/leaderboard_snapshot.py [--top 60]
"""
import argparse
import json
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API = 'https://api.virtualembryo.ai/challenge'
BOARDS = {'T1_test': ('T1', 'T1:test'), 'T2_heart_test': ('T2', 'T2:heart:test_extrap'),
          'T2_embryo_test': ('T2', 'T2:embryo:test_interp'), 'T3_bcatenin_test': ('T3', 'T3:bcatenin')}
SHORT = {'de_score': 'DE', 'de_direction': 'dir', 'mmd_u': 'mmd', 'variogram': 'vario', 'd2_shape': 'shape',
         'occupancy_dice': 'occ', 'scale_log_ratio': 'scale', 'neighborhood_mmd': 'nbr', 'severity_slope': 'sev'}


def get(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'leaderboard-snapshot'})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def cell(x):
    return '' if x is None else (f'{x:.1f}' if isinstance(x, float) else str(x).replace('|', '/'))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--top', type=int, default=60)
    a = ap.parse_args()
    out = ROOT / 'docs/leaderboard' / time.strftime('%Y-%m-%d')
    out.mkdir(parents=True, exist_ok=True)
    data = {'overall_test': get(f'{API}/overall?split=test')}
    for name, (task, board) in BOARDS.items():
        data[name] = get(f'{API}/leaderboard?task={task}&split=test&board={board}')
    for k, v in data.items():
        (out / f'{k}.json').write_text(json.dumps(v, indent=1, ensure_ascii=False))
    md = [f"# P3 test leaderboard snapshot ({data['overall_test'].get('updated_at')})", '',
          'Public standings with submitted model names, captured for reference. Raw JSON alongside.', '']
    rows = data['overall_test']['rows']
    for track in ('agent', 'human'):
        tr = [r for r in rows if r.get('track') == track]
        md += [f'## Overall, {track} track ({len(tr)} teams)', '',
               '| # | Team | Total | T1 | T2 | T3 | T2 heart | T2 embryo |', '|---|---|---|---|---|---|---|---|']
        for i, r in enumerate(tr[:a.top], 1):
            t, b = r.get('tasks') or {}, r.get('boards') or {}
            md.append(f"| {i} | {cell(r['team'])} | {cell(r.get('total'))} | {cell(t.get('T1'))} | {cell(t.get('T2'))} | "
                      f"{cell(t.get('T3'))} | {cell(b.get('T2:heart:test_extrap'))} | {cell(b.get('T2:embryo:test_interp'))} |")
        md.append('')
    for name in BOARDS:
        d = data[name]
        rs = d['rows']
        mets = list(rs[0].get('metrics', {})) if rs else []
        md += [f"## Board {d.get('board')} ({len(rs)} entries)", '',
               '| # | Team | Track | Model | Score | ' + ' | '.join(SHORT.get(m, m) for m in mets) + ' | Scored |',
               '|---|---|---|---|---|' + '---|' * len(mets) + '---|']
        for r in rs[:a.top]:
            md.append(f"| {cell(r.get('rank'))} | {cell(r['team'])} | {r.get('track', '')} | {cell(r.get('model') or '—')} | "
                      f"{cell(r.get('headline'))} | " + ' | '.join(cell((r.get('metrics') or {}).get(m)) for m in mets)
                      + f" | {str(r.get('scored_at', ''))[:10]} |")
        md.append('')
    (out / 'README.md').write_text('\n'.join(md) + '\n')
    print(out, {k: len(v.get('rows', [])) for k, v in data.items()})


if __name__ == '__main__':
    main()
