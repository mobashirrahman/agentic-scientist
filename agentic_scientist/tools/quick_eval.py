"""Fast local check of your workspace on ONE dev split, one scoring seed (a few minutes).
Usage (from the workspace): python <ROOT>/agentic_scientist/tools/quick_eval.py <split>
dev splits: temporal_val temporal_heartonly heart_early heart_late heart_long heart_e875 heart_organ_proxy
            embryo_early gata4_1 gata4_2 mab21l2_e95 hand2_e825 hand2_e925
Budget: at most 3 runs per workspace (the full multi-split evaluation happens on the fleet afterwards)."""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LIMIT = 3
args = [a for a in sys.argv[1:] if not a.startswith('-')]
split = args[0] if args else 'gata4_1'
sys.path.insert(0, str(ROOT))
from agentic_scientist.evaluate import SETS, harness  # noqa: E402
board = os.environ.get('MG_QUICK_BOARD')
allowed = [name for name in SETS['quick']['splits']
           if not board or harness.SPLITS[name]['board'] == board]
if split not in allowed:
    sys.exit(f"unsupported split {split!r}; available splits: {' '.join(allowed)}")
if ',' in split:
    sys.exit('one split per run; the fleet evaluates all splits afterwards')
counter = Path('.quick_eval_runs')
n = int(counter.read_text()) if counter.exists() else 0
if n >= LIMIT:
    sys.exit(f'quick_eval budget used ({LIMIT} runs). Stop testing and finish: write CHANGES.md; the fleet evaluates all splits.')
counter.write_text(str(n + 1))
print(f'quick_eval run {n + 1}/{LIMIT}', flush=True)
sys.path.insert(0, str(ROOT / 'agentic_scientist/tools'))
import heavy_slot  # noqa: E402
heavy_slot.acquire(f'quick_eval {split}')
sys.exit(subprocess.call([str(ROOT / '.venv/bin/python'), '-I', str(ROOT / 'agentic_scientist/evaluate.py'), '--workspace', '.',
                          '--set', 'quick', '--splits', split, '--workers', '1'],
                         env=dict(os.environ, OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1'),
                         timeout=1800))
