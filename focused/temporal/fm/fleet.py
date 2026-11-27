"""bio fleet: parallel scoring of program snapshots (Optuna trials, final held-out scoring). One job per host at a
time; failing hosts are benched for 30 min; local fallback. Agents never reach the fleet (no ssh keys in their
sandbox). The harness and data are mirrored to the same path on each host and checked against the lock."""
import json
import queue
import shlex
import subprocess
import threading
import time
import uuid
from pathlib import Path

from fm.common import FM, PY, STAGES, sha256
from fm.evaluation import score_snapshot

SSH = ['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=10', '-o', 'ServerAliveInterval=30']
RSH = ' '.join(SSH)


class Fleet:
    def __init__(self, hosts, log, job_timeout=3600):
        self.log, self.job_timeout = log, job_timeout
        self.bench = {}
        self.q = queue.Queue()
        self.hosts = []
        for h in hosts:
            if self._deploy(h):
                self.hosts.append(h)
                self.q.put(h)
        self.log(f'fleet: {len(self.hosts)} hosts ready: {self.hosts}')

    def _deploy(self, h):
        try:
            subprocess.run(SSH + [h, f'mkdir -p {FM}/runs'], check=True, timeout=60, capture_output=True)
            for d in ('fm', 'data'):
                subprocess.run(['rsync', '-a', '--delete', '--exclude', '__pycache__', '-e', RSH, f'{FM}/{d}/',
                                f'{h}:{FM}/{d}/'], check=True, timeout=1800, capture_output=True)
            want = {str(s['file']): s['sha256'] for s in STAGES.values()}
            out = subprocess.run(SSH + [h, 'sha256sum ' + ' '.join(want)], check=True, timeout=600,
                                 capture_output=True, text=True).stdout
            got = {l.split()[1]: l.split()[0] for l in out.splitlines()}
            if got != want:
                raise RuntimeError('data checksum mismatch')
            local = {p.name: sha256(p) for p in (FM / 'fm').glob('*.py')}
            out = subprocess.run(SSH + [h, f'cd {FM}/fm && sha256sum *.py'], check=True, timeout=60,
                                 capture_output=True, text=True).stdout
            if {l.split()[1]: l.split()[0] for l in out.splitlines()} != local:
                raise RuntimeError('harness mismatch')
            return True
        except Exception as e:  # noqa: BLE001
            self.log(f'fleet: host {h} unavailable: {e!r}'[:300])
            return False

    def _take(self, wait=900):
        t0 = time.time()
        while time.time() - t0 < wait:
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
                return json.loads(out)
            except Exception as e:  # noqa: BLE001
                self.log(f'fleet: job failed on {h} (attempt {attempt}): {e!r}'[:300])
                self.bench[h] = time.time() + 1800
            finally:
                subprocess.run(SSH + [h, f'rm -rf {shlex.quote(tag)}'], timeout=60, capture_output=True)
                self.q.put(h)
        self.log('fleet: local fallback')
        return score_snapshot(snap, splits, seeds, scoring, work)
