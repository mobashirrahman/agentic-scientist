"""Fleet dispatcher for ShinkaEvolve evaluations. NOT evolvable.

Shinka calls this exactly like evaluate.py. It claims one free host from
shinka_ve/fleet_hosts.txt (one evaluation per host at a time, via flock), copies
the candidate program to that host's mirror of this repo (same absolute path,
deployed by scripts/deploy_shinka_fleet.py), runs the frozen evaluate.py there, and
copies results_dir back. If no host succeeds it evaluates locally.
The API key (.env) is never copied to workers.
"""
import argparse
import fcntl
import os
import random
import shlex
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TASK = ROOT / 'shinka_ve'
SLOTS = TASK / 'fleet' / 'slots'
COOLDOWN = TASK / 'fleet' / 'cooldown'
COOLDOWN_S = 1800  # a host that failed is skipped for 30 min
REMOTE_LIMIT_S = 5000  # below the 1.5 h Shinka eval limit
LOG = TASK / 'fleet' / 'dispatch.log'
SSH = ['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=10', '-o', 'ServerAliveInterval=30']
ENV_KEYS = ('VE_SCORING_SEEDS', 'VE_EVAL_WORKERS', 'VE_SPLITS', 'VE_ROOT')


def hosts():
    lines = (l.split('#')[0].strip() for l in (TASK / 'fleet_hosts.txt').read_text().splitlines())
    return [h for h in lines if h]


def log(msg):
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open('a') as f:
        f.write(f"{time.strftime('%F %T')} pid={os.getpid()} {msg}\n")


def cooling(host):
    f = COOLDOWN / host
    return f.exists() and time.time() - f.stat().st_mtime < COOLDOWN_S


def mark_failed(host):
    COOLDOWN.mkdir(parents=True, exist_ok=True)
    (COOLDOWN / host).touch()


def claim(max_wait=1800):
    """Return (host, open lock file). Waits until any host slot is free."""
    SLOTS.mkdir(parents=True, exist_ok=True)
    deadline = time.time() + max_wait
    while time.time() < deadline:
        order = [h for h in hosts() if not cooling(h)]
        random.shuffle(order)
        for host in order:
            fh = open(SLOTS / f'{host}.lock', 'w')
            try:
                fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
                return host, fh
            except BlockingIOError:
                fh.close()
        time.sleep(5)
    return None, None


def remote_eval(host, program, results):
    tag = f'{os.getpid()}_{int(time.time())}'
    rdir = f'/scratch/user/ve-shinka-jobs/{tag}'
    rprog, rres = f'{rdir}/program.py', f'{rdir}/results'
    subprocess.run(SSH + [host, f'mkdir -p {rres}'], check=True, timeout=60)
    subprocess.run(['rsync', '-a', '-e', ' '.join(SSH), str(program), f'{host}:{rprog}'], check=True, timeout=120)
    env = ' '.join(f'{k}={shlex.quote(os.environ[k])}' for k in ENV_KEYS if k in os.environ)
    cmd = (f'cd {ROOT} && timeout -k 60 {REMOTE_LIMIT_S} env OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2 {env} '
           f'.venv/bin/python shinka_ve/evaluate.py --program_path {rprog} --results_dir {rres}')
    proc = subprocess.run(SSH + [host, cmd], capture_output=True, text=True)
    sys.stdout.write(proc.stdout[-4000:])
    sys.stderr.write(proc.stderr[-4000:])
    subprocess.run(['rsync', '-a', '-e', ' '.join(SSH), f'{host}:{rres}/', f'{results}/'], check=True, timeout=300)
    subprocess.run(SSH + [host, f'rm -rf {rdir}'], timeout=60)
    if not (Path(results) / 'metrics.json').exists():
        raise RuntimeError(f'no metrics.json from {host} (exit {proc.returncode})')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--program_path', required=True)
    ap.add_argument('--results_dir', required=True)
    a = ap.parse_args()
    program, results = Path(a.program_path).resolve(), Path(a.results_dir).resolve()
    results.mkdir(parents=True, exist_ok=True)
    for attempt in range(3):
        host, fh = claim()
        if host is None:
            break
        try:
            t0 = time.time()
            log(f'start {host} {program.parent.name}')
            remote_eval(host, program, results)
            log(f'done {host} {program.parent.name} {time.time() - t0:.0f}s')
            return
        except Exception as e:  # host failure: retry elsewhere, keep this host locked briefly
            log(f'fail {host} attempt={attempt} {e!r}')
            mark_failed(host)
        finally:
            fh.close()
    log(f'local fallback {program.parent.name}')
    # Local fallback on the workspace host: cap parallel splits so memory stays well under 31 GB.
    env = dict(os.environ, VE_EVAL_WORKERS='2')
    subprocess.run([sys.executable, str(TASK / 'evaluate.py'), '--program_path', str(program),
                    '--results_dir', str(results)], check=True, env=env)


if __name__ == '__main__':
    main()
