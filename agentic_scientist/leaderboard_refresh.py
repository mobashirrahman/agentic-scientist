"""Public P3 test leaderboard snapshots for the agents (operator entries removed).

  .venv/bin/python -I agentic_scientist/leaderboard_refresh.py --out docs/leaderboard/<date>     # fetch live
  .venv/bin/python -I agentic_scientist/leaderboard_refresh.py --filter SRC_DIR --out DST_DIR     # filter a copy

Same public JSON the website renders (no key). Rows of our own teams are dropped so agents never see our entries.
"""
import argparse
import json
import re
import time
import urllib.request
from pathlib import Path

API = 'https://api.virtualembryo.ai/challenge'
BOARDS = {'T1_test': ('T1', 'T1:test'), 'T2_heart_test': ('T2', 'T2:heart:test_extrap'),
          'T2_embryo_test': ('T2', 'T2:embryo:test_interp'), 'T3_bcatenin_test': ('T3', 'T3:bcatenin')}
HIDDEN_SHA = {'b655d06928cbca9d','598427034543b344','134a21710ca600b3'}  # operator entries (sha256 prefix of the lower-cased team name, spaces removed): not shown


def hidden(team):
    import hashlib
    key = re.sub(r'\s+', '', str(team or '')).lower()
    return hashlib.sha256(key.encode()).hexdigest()[:16] in HIDDEN_SHA


def _get(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'leaderboard-reader'})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def scrub(data):
    data = dict(data)
    if isinstance(data.get('rows'), list):
        data['rows'] = [r for r in data['rows'] if not hidden(r.get('team'))]
    for k in ('note', 'partners', 'counts'):
        data.pop(k, None)
    return data


def write(out, data):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    for k, v in data.items():
        tmp = out / f'.{k}.json.tmp'
        tmp.write_text(json.dumps(scrub(v), indent=1, ensure_ascii=False))
        tmp.replace(out / f'{k}.json')
    return out


def fetch():
    data = {'overall_test': _get(f'{API}/overall?split=test')}
    for name, (task, board) in BOARDS.items():
        data[name] = _get(f'{API}/leaderboard?task={task}&split=test&board={board}')
    return data


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True)
    ap.add_argument('--filter', help='copy and filter an existing snapshot directory instead of fetching')
    a = ap.parse_args()
    if a.filter:
        src = Path(a.filter)
        data = {p.stem: json.loads(p.read_text()) for p in src.glob('*.json')}
    else:
        data = fetch()
    print(write(a.out, data), time.strftime('%F %T'))


if __name__ == '__main__':
    main()
