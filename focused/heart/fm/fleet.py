"""bio fleet: parallel scoring of program snapshots (Optuna trials, final held-out scoring). One job per host at a
time; failing hosts are benched for 30 min; local fallback. Agents never reach the fleet (no ssh keys in their
sandbox). The harness and data are mirrored to the same path on each host and checked against the lock."""
from concurrent.futures import ThreadPoolExecutor
import json
import queue
import shlex
import subprocess
import threading
import time
import uuid
from pathlib import Path

from fm.common import FM, PY, sha256
from fm.evaluation import score_snapshot
from fm.prepare_worker import runtime

SSH = ['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=10', '-o', 'ServerAliveInterval=30']
RSH = ' '.join(SSH)


class Fleet:
    def __init__(self, hosts, log, job_timeout=3600):
        self.log, self.job_timeout = log, job_timeout
        self.bench = {}
        self.q = queue.Queue()
        self.hosts = []
        if hosts:
            with ThreadPoolExecutor(max_workers=min(len(hosts), 6)) as pool:
                accepted = list(pool.map(self._deploy, hosts))
            for host, ready in zip(hosts, accepted, strict=True):
                if ready:
                    self.hosts.append(host)
                    self.q.put(host)
        self.log(f'fleet: {len(self.hosts)} hosts ready: {self.hosts}')

    def _deploy(self, host):
        root = FM.parents[1]
        legacy_env = root.with_name('virtual-embryo') / '.venv'
        directories = (FM / 'fm', FM / 'runs', root / 'data' / 'panels')
        q = shlex.quote
        try:
            prepare = ('umask 077; mkdir -p -- ' + ' '.join(q(str(p)) for p in directories)
                       + f' && if [ ! -e {q(str(root / ".venv"))} ]; then '
                       + f'ln -s -- {q(str(legacy_env))} {q(str(root / ".venv"))}; fi')
            subprocess.run(SSH + [host, prepare], check=True, timeout=60, capture_output=True)
            for path in (FM / 'fm', root / 'data' / 'panels'):
                subprocess.run(['rsync', '-a', '--exclude', '__pycache__', '-e', RSH, f'{path}/',
                                f'{host}:{path}/'], check=True, timeout=120, capture_output=True)
            cmd = f'{q(PY)} -I {q(str(FM / "fm" / "prepare_worker.py"))}'
            out = subprocess.run(SSH + [host, cmd], check=True, timeout=180, capture_output=True,
                                 text=True).stdout
            observed = json.loads(out)
            expected = {
                'runtime': runtime(),
                'panel': sha256(FM / 'data/panels/T2__heart__test_extrap.genes.txt'),
                'code': {p.name: sha256(p) for p in sorted((FM / 'fm').glob('*.py'))},
            }
            if observed != expected:
                raise ValueError('worker panel, scoring runtime, or source fingerprint differs')
            return True
        except (OSError, ValueError, subprocess.SubprocessError) as exc:
            detail = getattr(exc, 'stderr', '') or str(exc)
            if isinstance(detail, bytes):
                detail = detail.decode(errors='replace')
            self.log(f'fleet: worker {host} unavailable: {detail.strip()}'[:310])
            return False

    def _take(self, wait=900):
        t0 = time.time()
        while time.time() - t0 < wait:
            if all(self.bench.get(host, 0) > time.time() for host in self.hosts):
                return None
            try:
                h = self.q.get(timeout=10)
            except queue.Empty:
                continue
            if self.bench.get(h, 0) > time.time():
                threading.Timer(60, self.q.put, args=(h,)).start()
                continue
            return h
        return None

    def score(self, snap, splits, seeds, scoring, work):
        """Blocking: score a snapshot on a fleet host (local fallback). Same result format as score_snapshot."""
        work = Path(work)
        work.mkdir(parents=True, exist_ok=True)
        for attempt in range(3):
            h = self._take() if self.hosts else None
            if h is None:
                break
            tag = f'{FM}/runs/_remote/{uuid.uuid4().hex}'
            try:
                subprocess.run(SSH + [h, f'mkdir -p {tag}'], check=True, timeout=60)
                subprocess.run(['rsync', '-a', '-e', RSH, f'{Path(snap).resolve()}/', f'{h}:{tag}/snap/'], check=True,
                               timeout=300)
                cmd = (f'timeout -k 60 {self.job_timeout} {PY} -I {FM}/fm/remote_eval.py --snap {tag}/snap '
                       f'--splits {",".join(splits)} --seeds {",".join(map(str, seeds))} '
                       f'--scoring {",".join(map(str, scoring))} --out {tag}/res.json > {tag}/log 2>&1')
                subprocess.run(SSH + [h, cmd], check=True, timeout=self.job_timeout + 180)
                out = subprocess.run(SSH + [h, f'cat {tag}/res.json'], check=True, timeout=120, capture_output=True,
                                     text=True).stdout
                result = json.loads(out)
                if not isinstance(result, dict) or any('score' not in result.get(split, {}) for split in splits):
                    raise ValueError('one or more replay scores missing from worker')
                self.log(f'fleet: {h} completed {",".join(splits)}')
                return result
            except Exception as e:  # noqa: BLE001
                self.log(f'fleet: job failed on {h} (attempt {attempt}): {e!r}'[:300])
                self.bench[h] = time.time() + 1800
            finally:
                try:
                    subprocess.run(SSH + [h, f'rm -rf {shlex.quote(tag)}'], timeout=20, capture_output=True)
                except (OSError, subprocess.TimeoutExpired):
                    self.log(f'fleet: scratch cleanup timed out on {h}')
                self.q.put(h)
        self.log('fleet: local fallback')
        return score_snapshot(snap, splits, seeds, scoring, work)
