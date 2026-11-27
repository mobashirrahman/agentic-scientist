"""Public P3 TEST leaderboard for the agents: every public entry with its full per-metric test scores and model name.

All public leaderboard data is fair game: model names (including numbers in them), scores, per-metric results, and
live fetches of the same public JSON the website renders (no key needed). Try to REPLICATE the strongest recipes the
names describe, then build on them. The one rule (live rules, section 10, last bullet): "Returned scores may be used
to choose among predictions, not to compute them" - do not solve for a hidden target property by inverting the skill
map or differencing scores. Reading names and trying recipes/parameter values is ordinary leaderboard work.

  leaderboard.py [--live] gaps <board> [--ws W | --eval E]   per metric: weight, best / top-10 / median test value, where
                                                             the field separates, and our current DEV value
  leaderboard.py [--live] top <board> [--metric m] [-n 25]   entries by headline or one metric, all metrics + model name
  leaderboard.py [--live] entry <board> <rank|team regex>    one entry in full (all metrics, model, team, time)
  leaderboard.py [--live] families <board>                   naming schemes (shared code) and their mean metric profile
  leaderboard.py [--live] sweeps <board>                     knob-like name tokens (d230, k150, N25179, tilt075 ...) that
                                                             vary across entries, and how headline/metrics move (Spearman)
  leaderboard.py [--live] search <regex>                     matching model names on every board
  leaderboard.py recipes <board>                             curated decoding of the top public names (what to replicate)
  leaderboard.py ours [<board>]                              OUR earlier test entries: per-metric scores + what each did,
                                                             next to the public top-10 mean of every metric
  leaderboard.py diff [<board>]                              changes between the two latest snapshots
<board>: T1 | heart | embryo | T3.  --live fetches the current public board instead of the latest snapshot.
"""
import argparse
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SNAP_DIRS = [ROOT / 'docs/leaderboard'] + ([Path(os.environ['MG_RUN']) / 'leaderboard'] if os.environ.get('MG_RUN') else [])
API = 'https://api.virtualembryo.ai/challenge'
FILES = {'T3': 'T3_bcatenin_test', 'heart': 'T2_heart_test', 'embryo': 'T2_embryo_test', 'T1': 'T1_test'}
API_BOARD = {'T1': ('T1', 'T1:test'), 'heart': ('T2', 'T2:heart:test_extrap'), 'embryo': ('T2', 'T2:embryo:test_interp'),
             'T3': ('T3', 'T3:bcatenin')}
HIDDEN_SHA = {'b655d06928cbca9d','598427034543b344','134a21710ca600b3'}  # operator entries (sha256 prefix of the lower-cased team name, spaces removed): not shown


def hidden(team):
    import hashlib
    key = re.sub(r'\s+', '', str(team or '')).lower()
    return hashlib.sha256(key.encode()).hexdigest()[:16] in HIDDEN_SHA
WEIGHTS = {
    'T1': {'de_score': .25, 'de_direction': .25, 'mmd_u': .30, 'variogram': .20},
    'T3': {'de_score': .30, 'de_direction': .25, 'severity_slope': .25, 'mmd_u': .12, 'variogram': .08},
    'heart': {'de_score': .125, 'de_direction': .125, 'mmd_u': .15, 'variogram': .10, 'neighborhood_mmd': .25,
              'd2_shape': 1 / 12, 'occupancy_dice': 1 / 12, 'scale_log_ratio': 1 / 12},
}
WEIGHTS['embryo'] = WEIGHTS['heart']
TOTAL_W = {'T1': 1.0, 'T3': 1.0, 'heart': .5, 'embryo': .5}  # weight of the board in the total score
DEV_BOARD = {'T1': 'temporal', 'T3': 'perturbation', 'heart': 'heart', 'embryo': 'embryo'}
KNOB = re.compile(r'^([a-z]+?)(\d+(?:\.\d+)?)$', re.I)
NOTE = ("NOTE: scores are each team's best of many test submissions (selected, optimistic) and validation predicts test "
        "poorly; a replicated recipe must still win the paired dev race. Test conditions: T1 E8.5/E9.5/E10.5 -> E12.5 "
        "heart chambers; heart E8.25..E10.5 -> dissected E12.5 heart; embryo E7.5 + E8.0 -> E7.75; T3 Ctnnb1 KO at E8.75.")
LIVE = False


def snapshots():
    out = []
    for d in SNAP_DIRS:
        if d.is_dir():
            out += [s for s in d.iterdir() if s.is_dir() and (s / 'T1_test.json').exists()]
    return sorted(out, key=lambda s: s.name)


def _get(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'leaderboard-reader'})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def rows(board, snap=None):
    if LIVE and snap is None:
        task, b = API_BOARD[board]
        data = _get(f'{API}/leaderboard?task={task}&split=test&board={b}')
    else:
        snap = snap or snapshots()[-1]
        data = json.loads((snap / f'{FILES[board]}.json').read_text())
    return [r for r in data['rows'] if not hidden(r.get('team'))]


def tokens(name):
    return [t for t in re.split(r'[\s_\-:,;()/|]+', name or '') if t]


def clean(name, width=160):
    return (name or '(no name)')[:width]


def family(name):
    sk = [re.sub(r'[\d.]+', '', t).lower() for t in tokens(name)]
    sk = [t for t in sk if t]
    return '_'.join(sk[:2]) if sk else '(unnamed)'


def mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else float('nan')


def median(xs):
    xs = sorted(x for x in xs if x is not None)
    return xs[len(xs) // 2] if xs else float('nan')


def spearman(a, b):
    def rank(v):
        o = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v)
        i = 0
        while i < len(o):
            j = i
            while j + 1 < len(o) and v[o[j + 1]] == v[o[i]]:
                j += 1
            for k in range(i, j + 1):
                r[o[k]] = (i + j) / 2
            i = j + 1
        return r
    ra, rb = rank(a), rank(b)
    ma, mb = mean(ra), mean(rb)
    num = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    den = (sum((x - ma) ** 2 for x in ra) * sum((y - mb) ** 2 for y in rb)) ** .5
    return num / den if den else float('nan')


def dev_metrics(eval_path, board):
    ev = json.loads(Path(eval_path).read_text())
    per = {}
    for r in ev.get('splits', {}).values():
        if r.get('board') == DEV_BOARD[board]:
            for k, v in (r.get('metrics') or {}).items():
                per.setdefault(k, []).append(v)
    return {k: mean(v) for k, v in per.items()}


def eval_of(ws):
    ws = Path(ws)
    for f in (ws.parent / 'eval.json', ws.parent / 'dev.json', ws.parent / 'seed_dev.json'):
        if f.exists():
            return f
    return None


def cmd_gaps(a):
    if a.ws and not a.eval:
        a.eval = eval_of(a.ws)
    rs = rows(a.board)
    top = rs[:10]
    dev = dev_metrics(a.eval, a.board) if a.eval else {}
    print(f'{a.board}: {len(rs)} public entries; best {rs[0]["headline"]:.1f}, top-10 mean '
          f'{mean([r["headline"] for r in top]):.1f}, median {median([r["headline"] for r in rs]):.1f}')
    print(f'{"metric":18s} {"weight":>6s} {"best":>6s} {"top10":>6s} {"median":>6s} {"sep@board":>9s} {"head@board":>10s}'
          + ('  dev(parent)' if dev else ''))
    out = []
    for m, w in WEIGHTS[a.board].items():
        b = max((r['metrics'].get(m) or 0) for r in rs)
        t = mean([r['metrics'].get(m) for r in top])
        md = median([r['metrics'].get(m) for r in rs])
        out.append(((t - md) * w, m, w, b, t, md, (100 - t) * w))
    for sep, m, w, b, t, md, head in sorted(out, key=lambda x: -x[0]):
        d = f'  {dev[m]:10.1f}' if m in dev else ''
        print(f'{m:18s} {w:6.3f} {b:6.1f} {t:6.1f} {md:6.1f} {sep:9.2f} {head:10.2f}{d}')
    print('sep@board = weight x (top-10 mean - median): where the leading recipes separate from the field. '
          'head@board = weight x (100 - top-10 mean): headroom left even for the leaders.')
    if a.board in ('heart', 'embryo'):
        print('T2: d2_shape/occupancy/scale count only x min(1, neighborhood_mmd/50): neighbourhoods come first.')
    print(NOTE)


def _line(r, ms):
    return (f'{r.get("rank", 0):4d} {str(r["team"])[:16]:16s} {str(r.get("track", ""))[:5]:5s} {r["headline"]:5.1f} '
            + ' '.join(f'{(r["metrics"].get(m) or 0):5.1f}' for m in ms) + '  ' + clean(r.get('model')))


def cmd_top(a):
    rs = rows(a.board)
    key = (lambda r: -(r['metrics'].get(a.metric) or -1e9)) if a.metric else (lambda r: r['rank'])
    ms = list(WEIGHTS[a.board])
    print(f'{"rank":>4s} {"team":16s} {"track":5s} {"head":>5s} ' + ' '.join(f'{m[:5]:>5s}' for m in ms) + '  model')
    for r in sorted(rs, key=key)[:a.n]:
        print(_line(r, ms))
    print(NOTE)


def cmd_entry(a):
    rs = rows(a.board)
    if a.which.isdigit():
        hit = [r for r in rs if r.get('rank') == int(a.which)]
    else:
        rx = re.compile(a.which, re.I)
        hit = [r for r in rs if rx.search(str(r['team'])) or rx.search(str(r.get('model') or ''))]
    for r in hit[:10]:
        print(json.dumps(r, indent=1, ensure_ascii=False))
    if not hit:
        print('no matching public entry')


def cmd_families(a):
    rs = [r for r in rows(a.board) if r.get('model')]
    fam = {}
    for r in rs:
        fam.setdefault(family(r['model']), []).append(r)
    ms = list(WEIGHTS[a.board])
    print(f'{"family":24s} {"n":>2s} {"best":>5s} {"mean":>5s} ' + ' '.join(f'{m[:5]:>5s}' for m in ms) + '  examples')
    for f, rr in sorted(fam.items(), key=lambda x: -max(r['headline'] for r in x[1])):
        if len(rr) < a.min and max(r['headline'] for r in rr) < a.show_single_above:
            continue
        print(f'{f[:24]:24s} {len(rr):2d} {max(r["headline"] for r in rr):5.1f} {mean([r["headline"] for r in rr]):5.1f} '
              + ' '.join(f'{mean([r["metrics"].get(m) for r in rr]):5.1f}' for m in ms) + '  '
              + ' | '.join(clean(r['model'], 60) for r in sorted(rr, key=lambda r: -r['headline'])[:3]))
    print('Families group names with the same leading tokens (digits ignored); teams sharing a scheme often share code.')
    print(NOTE)


def cmd_sweeps(a):
    rs = [r for r in rows(a.board) if r.get('model')]
    groups = {}
    for r in rs:
        for t in tokens(r['model']):
            m = KNOB.match(t)
            if not m or m.group(1).lower() in ('p', 't', 'e', 'v'):
                continue
            key = (m.group(1).lower(), len(m.group(2).split('.')[0]))
            groups.setdefault(key, []).append((float(m.group(2)), r))
    ms = list(WEIGHTS[a.board])
    shown = 0
    for (pre, nd), vs in sorted(groups.items(), key=lambda x: -len(x[1])):
        vals = [v for v, _ in vs]
        if len(vs) < 3 or len(set(vals)) < 3:
            continue
        shown += 1
        print(f'\nknob "{pre}" ({nd}-digit values), {len(vs)} entries, values {sorted(set(vals))}')
        print('  Spearman with headline {:+.2f}; '.format(spearman(vals, [r['headline'] for _, r in vs]))
              + ', '.join(f'{m[:5]} {spearman(vals, [r["metrics"].get(m) or 0 for _, r in vs]):+.2f}' for m in ms))
        for v, r in sorted(vs, key=lambda x: x[0]):
            print(f'    {v:8g}  head {r["headline"]:5.1f}  ' + ' '.join(f'{m[:5]} {(r["metrics"].get(m) or 0):5.1f}' for m in ms)
                  + f'  {str(r["team"])[:12]}: {clean(r["model"], 80)}')
    if not shown:
        print('no knob token varies across >= 3 entries on this board')
    print('\nA trend over few entries from different teams is weak evidence (different code, selected maxima): a '
          'direction or range to test on dev. ' + NOTE)


def cmd_search(a):
    rx = re.compile(a.regex, re.I)
    for b in FILES:
        for r in rows(b):
            if r.get('model') and rx.search(r['model']):
                print(f'{b:6s} rank {r["rank"]:3d} {r["headline"]:5.1f} {str(r["team"])[:16]:16s} {clean(r["model"])}')
    print(NOTE)


def cmd_recipes(a):
    f = ROOT / 'agentic_scientist/data/leaderboard_recipes.md'
    text = f.read_text()
    parts = re.split(r'(?m)^## ', text)
    want = {'T1': 'T1', 'heart': 'T2 heart', 'embryo': 'T2 embryo', 'T3': 'T3'}[a.board]
    print(parts[0].strip())
    for p in parts[1:]:
        if p.startswith(want):
            print('\n## ' + p.strip())


def cmd_ours(a):
    d = json.loads((ROOT / 'agentic_scientist/data/our_test_history.json').read_text())
    print(d['_about'])
    for b in ([a.board] if a.board else FILES):
        top = rows(b)[:10]
        ms = list(WEIGHTS[b])
        print(f'\n== {b}: public top-10 mean ' + ' '.join(f'{m[:5]} {mean([r["metrics"].get(m) for r in top]):.1f}'
                                                     for m in ms))
        for e in d['entries']:
            if e['board'] != b:
                continue
            met = ' '.join(f'{m[:5]} {e["metrics"][m]:.1f}' for m in ms if m in (e.get('metrics') or {})) or '(metrics n/a)'
            print(f'  {e["entry"]:9s} {e["date"]} test {e["headline"]:5.2f} | {met}\n            {e["program"]}')


def cmd_diff(a):
    ss = snapshots()
    if len(ss) < 2:
        print('only one snapshot')
        return
    old, new = ss[-2], ss[-1]
    print(f'{old.name} -> {new.name}')
    for b in ([a.board] if a.board else FILES):
        o = {r['team']: r for r in rows(b, old)}
        for r in rows(b, new)[:80]:
            p = o.get(r['team'])
            if p is None or abs(r['headline'] - p['headline']) > .3 or r.get('model') != p.get('model'):
                print(f'{b:6s} {str(r["team"])[:16]:16s} {p["headline"] if p else float("nan"):5.1f} -> {r["headline"]:5.1f} '
                      f'(rank {r["rank"]})  {clean(r.get("model"))}')


def main():
    global LIVE
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--live', action='store_true', help='fetch the current public board (no key needed)')
    sp = ap.add_subparsers(dest='cmd', required=True)
    g = sp.add_parser('gaps')
    g.add_argument('board', choices=FILES)
    g.add_argument('--eval', help='eval.json of a program (e.g. the parent) to show our dev metric values')
    g.add_argument('--ws', help="a workspace; its evaluation (../eval.json or the run's seed_dev.json) is used")
    t = sp.add_parser('top')
    t.add_argument('board', choices=FILES)
    t.add_argument('--metric')
    t.add_argument('-n', type=int, default=25)
    e = sp.add_parser('entry')
    e.add_argument('board', choices=FILES)
    e.add_argument('which')
    f = sp.add_parser('families')
    f.add_argument('board', choices=FILES)
    f.add_argument('--min', type=int, default=2)
    f.add_argument('--show-single-above', type=float, default=70.0)
    s = sp.add_parser('sweeps')
    s.add_argument('board', choices=FILES)
    q = sp.add_parser('search')
    q.add_argument('regex')
    r = sp.add_parser('recipes')
    r.add_argument('board', choices=FILES)
    o = sp.add_parser('ours')
    o.add_argument('board', nargs='?', choices=FILES)
    d = sp.add_parser('diff')
    d.add_argument('board', nargs='?', choices=FILES)
    a = ap.parse_args()
    LIVE = a.live
    {'gaps': cmd_gaps, 'top': cmd_top, 'entry': cmd_entry, 'families': cmd_families, 'sweeps': cmd_sweeps,
     'search': cmd_search, 'recipes': cmd_recipes, 'ours': cmd_ours, 'diff': cmd_diff}[a.cmd](a)


if __name__ == '__main__':
    sys.exit(main())
