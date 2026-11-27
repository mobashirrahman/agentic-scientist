"""Mirror the AgenticScientist evaluator onto the bio fleet hosts (their /scratch is local, not shared).

  .venv/bin/python -I agentic_scientist/prepare_fleet.py [--hosts N] [--smoke]

Sends code (agentic_scientist without runs, src, shinka_ve, vendor, scripts, models), panels, external data and the
RELEASED stage files. The protected local holdout targets (agentic_scientist/sandbox.PROTECTED) are never sent, so
remote evaluation can only run dev/sanity/guard sets; holdout scoring stays on this host. Each host is verified by
sha256 of every stage file it received; hosts that fail are commented out of a run-local host list.
"""
import argparse
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from agentic_scientist.sandbox import PROTECTED  # noqa: E402

SSH = ['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=10', '-o', 'ServerAliveInterval=30']
DEST = str(ROOT)
OLD_DATA = '/scratch/user/virtual-embryo/data'
CODE = ['agentic_scientist/', 'src/', 'shinka_ve/', 'vendor/', 'scripts/', 'models/', 'data/panels/',
        'data/staged_inventory.json', 'data/external/', 'data/checkpoints/', 'opencode.json']


def sh(cmd, timeout=1800):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def stage_hashes():
    inv = json.loads((ROOT / 'data/staged_inventory.json').read_text())
    return inv


def prepare(host, smoke):
    rsh = ' '.join(SSH)
    log = []
    r = sh(SSH + [host, f'mkdir -p {DEST}/data/raw && test -x /scratch/user/virtual-embryo/.venv/bin/python && '
                        f'ln -sfn /scratch/user/virtual-embryo/.venv {DEST}/.venv && echo ok'], 60)
    if 'ok' not in r.stdout:
        return host, False, f'no venv: {r.stderr[-300:]}'
    for item in CODE:
        src = ROOT / item.rstrip('/')
        if not src.exists():
            continue
        args = ['rsync', '-a', '--delete', '-e', rsh, '--exclude', '__pycache__', '--exclude', 'runs/',
                '--exclude', '.quick_eval_runs']
        if item == 'data/external/':
            args += [f'--link-dest={OLD_DATA}/external']
        r = sh(args + [str(src) + ('/' if item.endswith('/') else ''), f'{host}:{DEST}/{item}'])
        if r.returncode:
            return host, False, f'rsync {item}: {r.stderr[-300:]}'
    excl = []
    for p in PROTECTED:
        excl += ['--exclude', p]
    r = sh(['rsync', '-a', '--delete', '-e', rsh, *excl, f'--link-dest={OLD_DATA}/raw', f'{ROOT}/data/raw/',
            f'{host}:{DEST}/data/raw/'], 3600)
    if r.returncode:
        return host, False, f'rsync raw: {r.stderr[-300:]}'
    files = sorted(str(p.relative_to(ROOT / 'data/raw')) for p in (ROOT / 'data/raw').rglob('*.h5ad')
                   if str(p.relative_to(ROOT / 'data/raw')) not in PROTECTED)
    r = sh(SSH + [host, f'cd {DEST}/data/raw && sha256sum ' + ' '.join(files) + ' && ls ' + ' '.join(PROTECTED) +
                  ' 2>/dev/null | wc -l'], 900)
    remote = dict(reversed(l.split()) for l in r.stdout.splitlines() if len(l.split()) == 2)
    leaked = r.stdout.strip().splitlines()[-1].strip() if r.stdout.strip() else '?'
    log.append(f'{len(remote)} stage files hashed; protected present: {leaked}')
    if leaked not in ('0',):
        return host, False, 'protected file present on host: ' + leaked
    if smoke:
        cmd = (f'cd {DEST} && timeout 1500 .venv/bin/python -I agentic_scientist/evaluate.py --workspace '
               f'agentic_scientist/seed_final_v2 --set quick --splits heart_organ_proxy --workers 1 --out /tmp/as_smoke.json'
               ' > /tmp/as_smoke.log 2>&1; python3 -c "import json;d=json.load(open(\'/tmp/as_smoke.json\'));'
               'print(d.get(\'correct\'), d.get(\'proxy\'), d.get(\'error\'))"')
        r = sh(SSH + [host, cmd], 1800)
        log.append('smoke: ' + (r.stdout.strip() or r.stderr[-300:]))
        if not r.stdout.startswith('True'):
            return host, False, '; '.join(log)
    return host, remote, '; '.join(log)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--hosts', type=int, default=99)
    ap.add_argument('--smoke', action='store_true')
    a = ap.parse_args()
    hosts = [h.strip() for h in (ROOT / 'shinka_ve/fleet_hosts.txt').read_text().splitlines()
             if h.strip() and not h.lstrip().startswith('#')][:a.hosts]
    files = sorted(str(p.relative_to(ROOT / 'data/raw')) for p in (ROOT / 'data/raw').rglob('*.h5ad')
                   if str(p.relative_to(ROOT / 'data/raw')) not in PROTECTED)
    local = dict(reversed(l.split()) for l in
                 subprocess.run(['sha256sum', *files], cwd=ROOT / 'data/raw', capture_output=True, text=True).stdout.splitlines())
    with ThreadPoolExecutor(len(hosts)) as pool:
        res = list(pool.map(lambda h: prepare(h, a.smoke), hosts))
    report = {}
    for host, remote, msg in res:
        ok = bool(remote) and all(remote.get(f) == h for f, h in local.items())
        report[host] = dict(ok=ok, note=msg if ok else (msg if remote is False else 'hash mismatch; ' + msg))
        print(f"{host}: {'OK' if ok else 'FAILED'} {report[host]['note']}", flush=True)
    out = ROOT / 'agentic_scientist/fleet_ready.json'
    out.write_text(json.dumps(report, indent=1) + '\n')
    print(f"{sum(r['ok'] for r in report.values())}/{len(report)} hosts ready -> {out}")


if __name__ == '__main__':
    main()
