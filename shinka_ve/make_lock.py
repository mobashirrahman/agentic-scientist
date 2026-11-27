"""Record an Agent-track configuration lock: hashes of every file that defines the run."""
import hashlib, json, subprocess, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
FILES = ['shinka_ve/task_prompt.md', 'shinka_ve/initial.py', 'shinka_ve/evaluate.py', 'shinka_ve/harness.py',
         'shinka_ve/limit_wrapper.py', 'shinka_ve/run_evo.py', 'shinka_ve/config.json',
         'shinka_ve/fleet_evaluate.py', 'shinka_ve/fleet_hosts.txt', 'scripts/deploy_shinka_fleet.py', 'shinka_ve/supervise.sh',
         'src/data.py', 'src/v2/transport.py', 'src/v2/complexity.py', 'src/v2/anchor.py',
         'data/external/qiu2024/manifest.json']
lock_id = time.strftime('lock_%Y%m%d_%H%M%S')
shinka_commit = subprocess.run(['git', '-C', str(ROOT / 'vendor/ShinkaEvolve'), 'rev-parse', 'HEAD'],
                               capture_output=True, text=True).stdout.strip()
record = dict(lock_id=lock_id, created=time.strftime('%Y-%m-%dT%H:%M:%S%z'), shinka_commit=shinka_commit,
              config=json.loads((ROOT / 'shinka_ve/config.json').read_text()),
              files={f: hashlib.sha256((ROOT / f).read_bytes()).hexdigest() for f in FILES},
              note=sys.argv[1] if len(sys.argv) > 1 else '')
out = ROOT / 'shinka_ve/locks' / f'{lock_id}.json'
out.parent.mkdir(exist_ok=True)
out.write_text(json.dumps(record, indent=2) + '\n')
print(out)
