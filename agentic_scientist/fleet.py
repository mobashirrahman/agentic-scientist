"""Evaluate a AgenticScientist workspace on a bio fleet host (shares slot locks/cooldown with Shinka's dispatcher)."""
import json
import os
import shlex
import subprocess
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from shinka_ve.fleet_evaluate import SSH, claim, log, mark_failed  # noqa: E402
from agentic_scientist.tools.heavy_slot import reserve  # noqa: E402

REMOTE_LIMIT_S = 5000


class DeadlineReached(TimeoutError):
    """The run's wall-clock research budget has elapsed."""


def remaining(deadline, cap):
    if deadline is None:
        return cap
    seconds = deadline - time.time()
    if seconds <= 0:
        raise DeadlineReached('research wall-clock deadline reached')
    return min(cap, seconds)


def _remote(host, ws: Path, set_name: str, out: Path, extra='', deadline=None):
    tag = f'bra_{os.getpid()}_{uuid.uuid4().hex}'
    rdir = f'/scratch/user/ve-shinka-jobs/{tag}'
    rsh = ' '.join(SSH)
    try:
        subprocess.run(SSH + [host, f'mkdir -m 700 -p {rdir}'], check=True, timeout=remaining(deadline, 60))
        subprocess.run(['rsync', '-a', '--exclude', '__pycache__', '-e', rsh, f'{ws}/', f'{host}:{rdir}/ws/'],
                       check=True, timeout=remaining(deadline, 300))
        limit = remaining(deadline, REMOTE_LIMIT_S)
        cmd = (f'cd {shlex.quote(str(ROOT))} && timeout -k 60 {limit} '
               f'.venv/bin/python agentic_scientist/evaluate.py --workspace {rdir}/ws --set {set_name} --out {rdir}/result.json '
               f'--workers 4 {extra} > {rdir}/eval.log 2>&1')
        proc = subprocess.run(SSH + [host, cmd], timeout=limit + 120)
        subprocess.run(['rsync', '-a', '-e', rsh, f'{host}:{rdir}/eval.log', str(out.with_suffix('.log'))],
                       timeout=remaining(deadline, 120))
        proc.check_returncode()
        subprocess.run(['rsync', '-a', '-e', rsh, f'{host}:{rdir}/result.json', str(out)], check=True,
                       timeout=remaining(deadline, 120))
    finally:
        subprocess.run(SSH + [host, f'rm -rf {shlex.quote(rdir)}'], timeout=60)


def evaluate(ws: Path, set_name: str, out: Path, pred_seed=None, fit_seed=0, splits=None, deadline=None) -> dict:
    """Blocking. Fleet first (3 hosts), then local fallback."""
    ws, out = Path(ws).resolve(), Path(out).resolve()
    extra = f'--pred-seed {pred_seed} --fit-seed {fit_seed}' if pred_seed is not None else ''
    if splits:
        extra += ' --splits ' + ','.join(splits)
    out.unlink(missing_ok=True)
    for attempt in range(3):
        host, fh = claim(max_wait=remaining(deadline, 3600))
        if host is None:
            break
        try:
            t0 = time.time()
            log(f'mg start {host} {set_name} {ws}')
            _remote(host, ws, set_name, out, extra, deadline)
            log(f'mg done {host} {set_name} {time.time() - t0:.0f}s')
            return json.loads(out.read_text())
        except Exception as e:  # noqa: BLE001
            log(f'mg fail {host} attempt={attempt} {e!r}')
            remaining(deadline, 1)  # a run deadline is not a host failure
            mark_failed(host)
        finally:
            fh.close()
    log(f'mg local fallback {ws}')
    with reserve('fleet fallback', deadline):
        subprocess.run([str(ROOT / '.venv/bin/python'), str(ROOT / 'agentic_scientist/evaluate.py'), '--workspace', str(ws),
                        '--set', set_name, '--out', str(out), '--workers', '1'] + extra.split(), check=False,
                       stdout=subprocess.DEVNULL, timeout=remaining(deadline, REMOTE_LIMIT_S + 600))
    return json.loads(out.read_text()) if out.exists() else dict(correct=False, error='evaluation produced no result')
