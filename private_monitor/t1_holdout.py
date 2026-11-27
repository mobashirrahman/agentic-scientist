"""Private per-cycle T1 held-out score for the humans' dashboard (never shown to agents, never used by the run).

  .venv/bin/python -I private_monitor/t1_holdout.py --run agentic_scientist/runs/<lock>_final --watch

For the seed and every evaluated T1 cycle, the cycle's program makes its TEST-MODE T1 prediction (E8.5/E9.5/E10.5 ->
E12.5, sampling='heart_chambers', exactly the file a submission would contain) INSIDE the agents' Landlock sandbox
(released inputs only; output to a private temp dir). The prediction is then scored outside the sandbox against the
protected dissected-heart E14.5 scRNA (data/raw/T1/guard_E14.5.h5ad, 15k cells) on the shared genes (19,320), with
the same T1 metrics and scoring seeds as the other held-out boards. E14.5 is two days past the test target, so this
is a proxy: use it to see whether cycles move the test file toward a real later heart, not as a test estimate.

Results: /scratch/user/as_private/<run>/t1_holdout.jsonl (the dashboard merges them with holdout.jsonl).
Lives outside every agent-readable path and outside the run lock, so it can change while the run is going.
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
PY = str(ROOT / '.venv/bin/python')
PRIVATE_ROOT = Path('/scratch/user/as_private')
TARGET = 'T1/guard_E14.5.h5ad'
SPLIT = 't1_hold_e145'
TEST_SPEC = dict(board='temporal', task='T1', inputs=['T1/E8.5_RNA.h5ad', 'T1/E9.5_RNA.h5ad', 'T1/E10.5_RNA.h5ad'],
                 times=[8.5, 9.5, 10.5], time=12.5, sampling='heart_chambers')

# Runs inside the sandbox (passed with -c because this file is not readable there): test-mode prediction only.
PREDICT = r'''
import sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import agentic_scientist.evaluate as E
H = E.harness
H.SPLITS[sys.argv[4]] = dict(SPEC, target=None)
ws = Path(sys.argv[2])
mod = E.load(ws)
pred, ref = H.run_split(mod, sys.argv[4], SEED, 0, E.load_params(ws))
pred.write_h5ad(sys.argv[3])
print('ok', pred.shape)
'''


def predict_in_sandbox(ws, run_dir, out_h5ad, seed):
    from agentic_scientist.sandbox import Session
    tmp = Path(out_h5ad).parent
    code = f'SPEC = {TEST_SPEC!r}\nSEED = {int(seed)}\n' + PREDICT
    with tempfile.TemporaryDirectory(dir=str(tmp)) as sd:
        s = Session('fake', Path(sd) / 'sess', tmp, run_dir, extra_rw=[tmp])
        env = dict(s.env(os.environ), OMP_NUM_THREADS='2', OPENBLAS_NUM_THREADS='2', MKL_NUM_THREADS='2')
        r = subprocess.run(s.prefix() + [PY, '-I', '-c', code, str(ROOT), str(ws), str(out_h5ad), SPLIT],
                           cwd=str(tmp), env=env, capture_output=True, text=True, timeout=3600)
    if r.returncode != 0 or not Path(out_h5ad).exists():
        raise RuntimeError(f'prediction failed (exit {r.returncode}): {(r.stderr or r.stdout)[-1500:]}')


def score(pred_path, scoring_seeds):
    import anndata as ad
    import agentic_scientist.evaluate as E
    H = E.harness
    H.SPLITS[SPLIT] = dict(TEST_SPEC, target=TARGET, time=14.5)
    tgt_genes = list(ad.read_h5ad(ROOT / 'data/raw' / TARGET, backed='r').var_names)
    pred = ad.read_h5ad(pred_path)
    ref = H.load_stage(TEST_SPEC['inputs'][-1])  # copy-last floor reference (E10.5), as on every T1 split
    shared = [g for g in ref.var_names if g in set(tgt_genes) and g in set(pred.var_names)]
    pred, ref = pred[:, shared].copy(), ref[:, shared].copy()
    per, mets = [], []
    for s in scoring_seeds:
        sc, m = H.score_split(pred, ref, SPLIT, [s])
        per.append(sc)
        mets.append(m)
    return dict(score=sum(per) / len(per), seed_scores=per, n_genes=len(shared), n_pred=int(pred.n_obs),
                metrics={k: sum(m.get(k, 0) for m in mets) / len(mets) for k in mets[0]})


def candidates(run_dir):
    """Seed first, then every T1 cycle with a correct dev evaluation, in finishing order."""
    out = [dict(id='seed', ws=run_dir / 'seed_ws', verdict='seed', parent=None, researcher=None, t=0)]
    for c in sorted((run_dir / 'cycles').glob('*_c*')):
        o = c / 'outcome.json'
        if not o.exists():
            continue
        try:
            oc = json.loads(o.read_text())
        except ValueError:
            continue
        if oc.get('board') != 'temporal' or oc.get('dev_board') is None:
            continue
        out.append(dict(id=c.name, ws=Path(oc.get('ws') or c / 'ws'), verdict=oc.get('verdict'), parent=oc.get('parent_id'),
                        researcher=oc.get('researcher'), t=oc.get('finished') or o.stat().st_mtime))
    return out


def score_one(run_dir, cand, out_jsonl):
    import agentic_scientist.evaluate as E
    rec = dict(t=time.time(), id=cand['id'], board='temporal', ws=str(cand['ws']), verdict=cand['verdict'],
               researcher=cand['researcher'], parent=cand['parent'], target=TARGET, mode='test-mode E12.5 prediction')
    t0 = time.time()
    try:
        err = E.screen_workspace(Path(cand['ws']))
        if err:
            raise RuntimeError(f'screen: {err}')
        seed = E.SETS['holdout']['seed']
        sys.path.insert(0, str(ROOT / 'agentic_scientist/tools'))
        import heavy_slot  # same machine-wide slots as the agents' quick_eval (a T1 run holds several GB)
        with tempfile.TemporaryDirectory(dir=str(out_jsonl.parent)) as tmp, heavy_slot.reserve(f"t1 held-out {cand['id']}"):
            pred = Path(tmp) / 'pred.h5ad'
            predict_in_sandbox(cand['ws'], run_dir, pred, seed)
            rec.update(score(pred, E.SETS['holdout']['scoring_seeds']), correct=True)
    except Exception as ex:  # noqa: BLE001 - monitor only
        rec.update(correct=False, error=f'{type(ex).__name__}: {ex}'[:1500], trace=traceback.format_exc()[-1500:])
    rec['seconds'] = round(time.time() - t0, 1)
    with out_jsonl.open('a') as f:
        f.write(json.dumps(rec, default=float) + '\n')
    return rec


def done_ids(out_jsonl):
    ids = set()
    if out_jsonl.exists():
        for line in out_jsonl.read_text().splitlines():
            try:
                ids.add(json.loads(line)['id'])
            except (ValueError, KeyError):
                pass
    return ids


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--run', required=True)
    ap.add_argument('--watch', action='store_true', help='keep scoring new T1 cycles until --until (ISO time)')
    ap.add_argument('--until', default='2026-11-26T09:59:00+01:00')
    a = ap.parse_args()
    run_dir = Path(a.run).resolve()
    out_dir = PRIVATE_ROOT / run_dir.name
    out_dir.mkdir(parents=True, exist_ok=True)
    out_jsonl = out_dir / 't1_holdout.jsonl'
    from datetime import datetime
    stop = datetime.fromisoformat(a.until).timestamp()
    while True:
        todo = [c for c in candidates(run_dir) if c['id'] not in done_ids(out_jsonl)]
        for c in todo:
            r = score_one(run_dir, c, out_jsonl)
            print(time.strftime('%F %T'), c['id'], r.get('score'), r.get('error', '')[:200], flush=True)
        if not a.watch or time.time() > stop:
            break
        time.sleep(60)


if __name__ == '__main__':
    main()
