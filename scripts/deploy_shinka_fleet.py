"""Mirror the Shinka evaluation environment to every host in shinka_ve/fleet_hosts.txt.

Same absolute path as here, so the venv and editable installs work unchanged.
Copies code, venv, released + officially unlocked stages and vetted external data.
Never copies .env, submissions, git history or run outputs.
"""
import subprocess, sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
ITEMS = ['.venv', 'vendor', 'src', 'shinka_ve', 'data/raw', 'data/external', 'requirements.txt']
EXCLUDE = ['.env', 'shinka_ve/runs', 'shinka_ve/fleet', 'shinka_ve/.scratch', '*.part', '__pycache__']
SSH = 'ssh -o BatchMode=yes -o ConnectTimeout=10'

def deploy(host):
    subprocess.run(SSH.split() + [host, f'mkdir -p {ROOT}'], check=True, timeout=60)
    cmd = ['rsync', '-aR', '--delete', '-e', SSH] + [f'--exclude={e}' for e in EXCLUDE] + ITEMS + [f'{host}:{ROOT}/']
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    if r.returncode:
        return host, 'rsync failed: ' + r.stderr[-300:]
    t = subprocess.run(SSH.split() + [host, f'cd {ROOT} && test ! -e .env && .venv/bin/python -c "import shinka, vec_local_score, anndata, torch; print(1)"'],
                       capture_output=True, text=True, timeout=300)
    return host, 'ok' if t.stdout.strip() == '1' else 'check failed: ' + (t.stderr or t.stdout)[-300:]

if __name__ == '__main__':
    hosts = [l.split('#')[0].strip() for l in (ROOT / 'shinka_ve/fleet_hosts.txt').read_text().splitlines()]
    hosts = [h for h in hosts if h]
    hosts = [h for h in hosts if not sys.argv[1:] or h in sys.argv[1:]]
    with ThreadPoolExecutor(5) as ex:
        for host, status in ex.map(deploy, hosts):
            print(host, status, flush=True)
