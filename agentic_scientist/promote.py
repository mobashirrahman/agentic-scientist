"""Promote a run's holdout-selected program to the seed of the next run (pre-registered rule, run by a human).

  .venv/bin/python agentic_scientist/promote.py <run_dir>

Promote the program named by final/final.json. Dev-only boards can change
without changing the holdout score. The old seed is archived in agentic_scientist/seed_history/.
"""
import json
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
run = Path(sys.argv[1]).resolve()
fin = json.loads((run / 'final/final.json').read_text())
if fin['chosen'] == 'seed':
    sys.exit(f"no promotion: the seed won the holdout check in {run.name}")
row = next(r for r in fin['candidates'] if r['id'] == fin['chosen'])
seed_row = fin['candidates'][0]
hist = ROOT / 'agentic_scientist/seed_history' / time.strftime('%Y%m%d_%H%M%S')
shutil.copytree(ROOT / 'agentic_scientist/seed', hist)
shutil.rmtree(ROOT / 'agentic_scientist/seed')
shutil.copytree(run / 'final/selected', ROOT / 'agentic_scientist/seed', ignore=shutil.ignore_patterns('__pycache__', '.quick_eval_runs'))
(ROOT / 'agentic_scientist/seed/PROVENANCE.json').write_text(json.dumps(dict(
    from_run=run.name, program=fin['chosen'], holdout=row['holdout'], previous_seed_holdout=seed_row['holdout'],
    previous_seed_archived=str(hist.relative_to(ROOT)), promoted_at=time.strftime('%F %T')), indent=1))
print(f"promoted {fin['chosen']} (holdout {row['holdout']:.2f}, seed {seed_row['holdout']:.2f}); old seed -> {hist}")
