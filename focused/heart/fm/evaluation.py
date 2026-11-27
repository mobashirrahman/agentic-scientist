"""Evaluation service: runs workspace programs in Landlock and scores them with the official scorer.

The program never shares a process with any answer file: it runs in a sandboxed child that can read only its
snapshot and its split's INPUT stages; the parent (this service) loads the target, scores, and returns numbers.

Agents talk to it through a spool directory (round/evalq/req/*.json -> round/evalq/res/*.json) with tools/evaluate.py
and tools/testcheck.py. Validation requests return full scores and full error traces (validation runs only receive
training stages). Test-configuration checks return pass/fail and an error class only, never a message, because
those runs receive the protected stages.
"""
import hashlib
import json
import os
import re
import shutil
import signal
import stat
import subprocess
import threading
import time
import traceback
from pathlib import Path

from fm import score as S
from fm.common import FM, PY, SPLITS, STAGES, VALIDATION, VAL_SCORING_SEEDS, VENV, now, read_json, write_json

SNAP_MAX_FILE = 50 << 20
SNAP_MAX_TOTAL = 300 << 20
SNAP_SKIP_DIRS = {'tools', 'history', 'prior_knowledge', '__pycache__', '.git', '.ipynb_checkpoints', 'scratch', 'tmp'}
RUN_TIMEOUT = {'validation': 1800, 'heldout': 1800, 'test': 2700}
RSS_LIMIT = 20 << 30
RUNNER_THREADS = '4'


def snapshot(ws, dest):
    """Copy the program files of a workspace (code and small assets; not tools/, history/, caches)."""
    ws, dest = Path(ws), Path(dest)
    total = 0
    for folder, dirs, names, folder_fd in os.fwalk(ws, follow_symlinks=False):
        dirs[:] = sorted(d for d in dirs if d not in SNAP_SKIP_DIRS and not d.startswith('.'))
        relative = Path(folder).relative_to(ws)
        for name in sorted(names):
            if name.startswith('.') or Path(name).suffix in ('.h5ad', '.log', '.jsonl'):
                continue
            try:
                fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=folder_fd)
            except OSError:
                continue
            with os.fdopen(fd, 'rb') as source:
                entry = os.fstat(source.fileno())
                if not stat.S_ISREG(entry.st_mode) or entry.st_size > SNAP_MAX_FILE:
                    continue
                out = dest / relative / name
                out.parent.mkdir(parents=True, exist_ok=True)
                with out.open('wb') as stream:
                    copied = 0
                    while chunk := source.read(1 << 20):
                        copied += len(chunk)
                        if copied > SNAP_MAX_FILE or total + copied > SNAP_MAX_TOTAL:
                            raise RuntimeError('workspace snapshot exceeds the file or total size limit')
                        stream.write(chunk)
                total += copied
    if not (dest / 'program.py').is_file():
        raise RuntimeError('program.py missing from the workspace')
    return content_hash(dest)


def content_hash(d):
    h = hashlib.sha256()
    for p in sorted(Path(d).rglob('*')):
        if p.is_file() and p.suffix != '.md':  # notes do not change the program
            h.update(str(p.relative_to(d)).encode())
            h.update(p.read_bytes())
    return h.hexdigest()[:16]


def _rss(pid):
    total, stack = 0, [pid]
    while stack:
        p = stack.pop()
        try:
            for line in open(f'/proc/{p}/status'):
                if line.startswith('VmRSS:'):
                    total += int(line.split()[1]) * 1024
            for t in os.listdir(f'/proc/{p}/task'):
                stack += [int(c) for c in open(f'/proc/{p}/task/{t}/children').read().split()]
        except (OSError, ValueError):
            pass
    return total


def run_program(snap, split, seed, out, timeout=None):
    """Run the snapshot's predict() for one split in Landlock. Returns the runner's meta dict (+ 'pred' path)."""
    out = Path(out)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    tmp = out / 'tmp'
    tmp.mkdir()
    inputs = [str(STAGES[n]['file']) for n in SPLITS[split]['inputs']]
    cmd = [PY, '-I', str(FM / 'fm/landlock.py'), '--ro', str(FM / 'fm'), '--ro', str(FM / 'data/panels'), '--ro', str(FM.parents[1] / 'data/panels'),
           '--ro', str(VENV), '--ro', str(Path(snap).resolve()), '--rw', str(out), '--no-tcp', '--scope-signals']
    for f in inputs:
        cmd += ['--ro', f]
    cmd += ['--', PY, '-I', str(FM / 'fm/runner.py'), '--snapshot', str(Path(snap).resolve()), '--split', split,
            '--seed', str(seed), '--out', str(out)]
    env = dict(PATH='/usr/bin:/bin', HOME=str(tmp), TMPDIR=str(tmp), LANG='C.UTF-8', OMP_NUM_THREADS=RUNNER_THREADS,
               OPENBLAS_NUM_THREADS=RUNNER_THREADS, MKL_NUM_THREADS=RUNNER_THREADS, NUMBA_NUM_THREADS=RUNNER_THREADS,
               NUMBA_CACHE_DIR=str(tmp), MPLCONFIGDIR=str(tmp), PYTHONHASHSEED='0')
    timeout = timeout or RUN_TIMEOUT[SPLITS[split]['role']]
    t0, killed = time.time(), None
    with open(out / 'stdout.log', 'wb') as log:
        proc = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, env=env,
                                start_new_session=True)
        while proc.poll() is None:
            time.sleep(2)
            if time.time() - t0 > timeout:
                killed = 'timeout'
            elif _rss(proc.pid) > RSS_LIMIT:
                killed = 'memory'
            if killed:
                os.killpg(proc.pid, signal.SIGKILL)
                proc.wait()
    meta = read_json(out / 'meta.json') or {}
    if killed:
        meta = dict(ok=False, error_type='Timeout' if killed == 'timeout' else 'MemoryLimit',
                    error=f'run exceeded the {timeout} s limit' if killed == 'timeout' else
                    f'run exceeded the {RSS_LIMIT >> 30} GB memory limit', seconds=round(time.time() - t0, 1))
    elif not meta:
        tail = (out / 'stdout.log').read_text(errors='replace')[-3000:]
        meta = dict(ok=False, error_type='RunnerCrash', error=f'runner exited {proc.returncode}', trace=tail)
    meta['pred'] = str(out / 'pred.h5ad') if meta.get('ok') else None
    shutil.rmtree(tmp, ignore_errors=True)
    return meta


def score_snapshot(snap, splits, seeds, scoring_seeds, work, parallel=2):
    """Run and score a snapshot on splits for each prediction seed. Returns {split: result} (seed-averaged)."""
    import anndata as ad
    jobs = [(sp, sd) for sd in seeds for sp in splits]
    metas = {}

    def worker(chunk):
        for sp, sd in chunk:
            metas[(sp, sd)] = run_program(snap, sp, sd, Path(work) / f'{sp}_s{sd}')

    chunks = [jobs[i::parallel] for i in range(parallel)]
    threads = [threading.Thread(target=worker, args=(c,)) for c in chunks if c]
    [t.start() for t in threads]
    [t.join() for t in threads]
    results = {}
    for sp in splits:
        per = []
        for sd in seeds:
            m = metas[(sp, sd)]
            if not m.get('ok'):
                results[sp] = dict(error_type=m.get('error_type'), error=m.get('error'), trace=m.get('trace'),
                                   seconds=m.get('seconds'), seed=sd)
                break
            try:
                r = S.score(ad.read_h5ad(m['pred']), sp, scoring_seeds)
            except Exception as e:  # noqa: BLE001
                results[sp] = dict(error_type='ScoringError', error=f'{type(e).__name__}: {e}',
                                   trace=traceback.format_exc()[-3000:], seed=sd)
                break
            r.update(n_cells=m.get('n_cells'), seconds=m.get('seconds'), predict_seconds=m.get('predict_seconds'))
            per.append(r)
        else:
            res = dict(score=sum(r['score'] for r in per) / len(per), pred_seed_scores=[r['score'] for r in per],
                       seed_sd=per[0]['seed_sd'] if len(per) == 1 else None, n_cells=per[0]['n_cells'],
                       seconds=max(r['seconds'] or 0 for r in per),
                       metrics={k: sum(r['metrics'][k] for r in per) / len(per) for k in per[0]['metrics']})
            results[sp] = res
    for sd in seeds:  # predictions are not kept (disk); scores are
        for sp in splits:
            p = Path(work) / f'{sp}_s{sd}' / 'pred.h5ad'
            p.unlink(missing_ok=True)
    return results


def format_check(snap, splits, work):
    """Run a snapshot on splits without scoring; returns {split: (ok, error_type)}."""
    out = {}
    for sp in splits:
        m = run_program(snap, sp, 0, Path(work) / f'check_{sp}')
        out[sp] = dict(ok=bool(m.get('ok')), error_type=m.get('error_type'), seconds=m.get('seconds'),
                       n_cells=m.get('n_cells'))
        shutil.rmtree(Path(work) / f'check_{sp}', ignore_errors=True)
    return out


class EvalService(threading.Thread):
    """Per-round spool service. status_fn() -> dict(remaining_s=..., ...) supplied by the orchestrator."""

    def __init__(self, round_dir, max_evals, max_testchecks, status_fn, log):
        super().__init__(daemon=True)
        self.dir = Path(round_dir)
        self.q = self.dir / 'evalq'
        (self.q / 'req').mkdir(parents=True, exist_ok=True)
        (self.q / 'res').mkdir(parents=True, exist_ok=True)
        self.max_evals, self.max_testchecks = max_evals, max_testchecks
        self.status_fn, self.log = status_fn, log
        self.stop_flag = threading.Event()
        self.ledger = self.dir / 'evals.jsonl'
        self.lock = threading.Lock()

    def records(self):
        if not self.ledger.exists():
            return []
        return [json.loads(x) for x in self.ledger.read_text().splitlines() if x.strip()]

    def mirror(self):
        """Agent-readable copy of the ledger (the real ledger is outside the agent's sandbox)."""
        if self.ledger.exists():
            shutil.copy2(self.ledger, self.q / 'evals.jsonl')

    def counts(self):
        r = self.records()
        return (sum(1 for x in r if x['kind'] == 'validate' and x.get('counted', True)),
                sum(1 for x in r if x['kind'] == 'testcheck'))

    def best(self):
        v = [x for x in self.records() if x['kind'] == 'validate' and x.get('validation') is not None]
        return max(v, key=lambda x: x['validation']) if v else None

    def run(self):
        while not self.stop_flag.is_set():
            reqs = sorted((self.q / 'req').glob('*.json'))
            if not reqs:
                time.sleep(2)
                continue
            for p in reqs:
                if self.stop_flag.is_set():
                    return
                rid = p.stem
                try:
                    if not re.fullmatch(r'[0-9]{10,}_[a-f0-9]{8}', rid):
                        raise ValueError('invalid request name')
                    fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
                    with os.fdopen(fd, 'rb') as stream:
                        req = json.loads(stream.read(4096))
                    if not isinstance(req, dict) or req.get('id') != rid:
                        raise ValueError('invalid request identity')
                except (OSError, ValueError):
                    p.unlink(missing_ok=True)
                    continue
                try:
                    res = self.handle(req, rid)
                except Exception as e:  # noqa: BLE001 - never kill the service
                    res = dict(id=rid, ok=False, error=f'evaluation service error: {type(e).__name__}: {e}')
                    self.log(f'eval service error {rid}: {traceback.format_exc()[-1500:]}')
                write_json(self.q / 'res' / f'{rid}.json', res)
                p.unlink(missing_ok=True)
                self.mirror()

    def evaluate_workspace(self, kind='validate', note='', counted=True):
        """Snapshot + validate the current workspace (also used by the orchestrator, uncounted)."""
        with self.lock:
            n = len(self.records()) + 1
            snap = self.dir / 'snapshots' / f's{n:03d}'
            h = snapshot(self.dir / 'workspace', snap)
            t0 = time.time()
            res = score_snapshot(snap, VALIDATION, [0], VAL_SCORING_SEEDS, self.dir / 'work')
            val = S.combine(res, VALIDATION)
            rec = dict(n=n, kind=kind, counted=counted, time=now(), snapshot=snap.name, hash=h, note=note[:500],
                       validation=val, splits=res, seconds=round(time.time() - t0, 1))
            with self.ledger.open('a') as f:
                f.write(json.dumps(rec, default=float) + '\n')
            return rec

    def handle(self, req, rid):
        kind = req.get('kind', 'validate')
        used_v, used_t = self.counts()
        st = self.status_fn()
        base = dict(id=rid, kind=kind, remaining_seconds=int(st.get('remaining_s', 0)))
        if kind == 'validate':
            if used_v >= self.max_evals:
                return dict(base, ok=False, error=f'validation budget exhausted ({self.max_evals} evaluations)')
            prev = self.best()
            rec = self.evaluate_workspace('validate', str(req.get('note', '')))
            self.log(f"eval {self.dir.name} #{rec['n']} {rec['snapshot']} validation={rec['validation']} "
                     f"note={rec['note'][:80]!r}")
            out = dict(base, ok=rec['validation'] is not None, eval_no=rec['n'], snapshot=rec['snapshot'],
                       validation=rec['validation'], splits=rec['splits'], seconds=rec['seconds'],
                       previous_best=prev and dict(validation=prev['validation'], snapshot=prev['snapshot']),
                       evaluations_left=self.max_evals - used_v - 1)
            return out
        if kind == 'testcheck':
            if used_t >= self.max_testchecks:
                return dict(base, ok=False, error=f'test-configuration check budget exhausted ({self.max_testchecks})')
            with self.lock:
                n = len(self.records()) + 1
                snap = self.dir / 'snapshots' / f's{n:03d}'
                h = snapshot(self.dir / 'workspace', snap)
                m = run_program(snap, 'test', 0, self.dir / 'work' / f'testcheck_{n:03d}')
                shutil.rmtree(self.dir / 'work' / f'testcheck_{n:03d}', ignore_errors=True)
                rec = dict(n=n, kind='testcheck', time=now(), snapshot=snap.name, hash=h, ok=bool(m.get('ok')),
                           error_type=m.get('error_type'), seconds=m.get('seconds'))
                with self.ledger.open('a') as f:
                    f.write(json.dumps(rec) + '\n')
            self.log(f"testcheck {self.dir.name} #{n} ok={rec['ok']} {rec['error_type'] or ''}")
            return dict(base, ok=rec['ok'], error_type=rec['error_type'],
                        seconds=None if rec['seconds'] is None else int(round(rec['seconds'], -1)),
                        checks_left=self.max_testchecks - used_t - 1,
                        note='Messages are withheld for this configuration because it reads protected stages.')
        return dict(base, ok=False, error=f'unknown request kind {kind!r}')
