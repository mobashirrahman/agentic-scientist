"""Score the CURRENT workspace program on the validation configurations (counts against your budget).

  python tools/evaluate.py --note "what changed"      # snapshot + run + score (about 1-10 min)
  python tools/evaluate.py --history                  # your evaluations so far (free)
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _client import Q, request  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument('--note', default='')
ap.add_argument('--history', action='store_true')
ap.add_argument('--json', action='store_true')
a = ap.parse_args()
if a.history:
    led = Q / 'evals.jsonl'
    rows = [json.loads(x) for x in led.read_text().splitlines()] if led.exists() else []
    for r in rows:
        if r['kind'] == 'validate':
            s = r.get('splits') or {}
            v = s.get('val') or {}
            print(f"#{r['n']:3d} {r['snapshot']} validation={r.get('validation')} val={v.get('score')} "
                  f"native_occupancy={v.get('native_occupancy')}  {r.get('note', '')}")
    sys.exit(0)
r = request('validate', a.note)
if a.json:
    print(json.dumps(r, indent=1))
    sys.exit(0)
if not r.get('ok'):
    print('EVALUATION FAILED:', r.get('error') or '')
    for sp, v in (r.get('splits') or {}).items():
        if 'score' not in v:
            print(f'--- {sp}: {v.get("error_type")}: {v.get("error")}\n{v.get("trace") or ""}')
else:
    print(f"validation = {r['validation']:.3f}   (eval #{r['eval_no']}, snapshot {r['snapshot']}, {r['seconds']:.0f}s)")
    pb = r.get('previous_best')
    if pb:
        print(f"previous best = {pb['validation']:.3f} ({pb['snapshot']})")
    for sp, v in r['splits'].items():
        m = ' '.join(f'{k}={x:.1f}' for k, x in v['metrics'].items())
        occ = v.get('native_occupancy')
        print(f"  {sp}: {v['score']:.3f}  n_cells={v['n_cells']}  native_occupancy={occ}  run={v['seconds']}s\n     {m}")
print(f"evaluations left: {r.get('evaluations_left')}   time left: {r.get('remaining_seconds', 0) // 60} min")
