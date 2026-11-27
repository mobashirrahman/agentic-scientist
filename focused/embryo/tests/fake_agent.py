"""Fake agent for the end-to-end harness test: edits program.py, calls the real tools, emits JSON events."""
import json
import os
import subprocess
import sys

mode = sys.argv[1]
print(json.dumps({'type': 'start', 'mode': mode}), flush=True)
# prove the sandbox: protected data and the operator's home must be unreadable
for p in ['/scratch/user/focused_morphogen_t2_embryo/data/protected/E7.5.h5ad',
          os.path.expanduser('~') + '/../../user/.claude/.credentials.json']:
    try:
        open(p, 'rb').read(1)
        print(json.dumps({'type': 'LEAK', 'path': p}), flush=True)
    except OSError:
        print(json.dumps({'type': 'denied', 'path': p}), flush=True)
# the builder fails twice (exercises wait -> retry -> switch to the fallback model)
if mode == 'builder':
    n = int(open('.fails').read()) if os.path.exists('.fails') else 0
    if n < 2:
        open('.fails', 'w').write(str(n + 1))
        print(json.dumps({'type': 'error', 'message': 'simulated failure'}), flush=True)
        sys.exit(1)
open('knobs.json', 'w').write(json.dumps({'keep_frac': {'low': 0.3, 'high': 1.0, 'default': 1.0}}))
src = open('program.py').read()
if 'FAKE_SHRINK' not in src:
    src = src.replace('    return result', """    result = result[: max(1000, int(result.n_obs * context['params'].get('keep_frac', 1.0)))].copy()  # FAKE_SHRINK
    return result""")
    open('program.py', 'w').write(src)
for cmd in (['python', 'tools/evaluate.py', '--note', f'fake {mode}'], ['python', 'tools/testcheck.py']):
    r = subprocess.run(cmd, capture_output=True, text=True)
    print(json.dumps({'type': 'tool', 'cmd': cmd, 'out': r.stdout[-1500:], 'err': r.stderr[-800:]}), flush=True)
open('NOTES.md', 'a').write(f'\nfake {mode} round done\n')
print(json.dumps({'type': 'done'}), flush=True)
