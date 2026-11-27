"""Head-node memory guard: at most SLOTS heavy local evaluations (diagnose, quick_eval) at once across all agents.
A T1 diagnosis holds 7-8 GB; five agents diagnosing together exhausted the 31 GB head node in full6."""
import fcntl
import os
import time
from contextlib import contextmanager
from pathlib import Path

SLOTS = int(os.environ.get('MG_HEAVY_SLOTS', '2'))
_held = []


def _claim(what, deadline=None):
    d = Path(__file__).resolve().parents[3] / '.agentic_scientist-heavy-slots'
    d.mkdir(parents=True, exist_ok=True)
    said = False
    while True:
        if deadline is not None and time.time() >= deadline:
            raise TimeoutError('head-node slot deadline reached')
        for k in range(SLOTS):
            f = open(d / f'.heavy_slot{k}.lock', 'w')
            try:
                fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
                return f
            except OSError:
                f.close()
        if not said:
            print(f'waiting for a free head-node slot ({SLOTS} heavy local runs at once){" for " + what if what else ""}...', flush=True)
            said = True
        time.sleep(5)


def acquire(what=''):
    _held.append(_claim(what))


@contextmanager
def reserve(what, deadline=None):
    with _claim(what, deadline):
        yield
