"""Shared paths, stage definitions, split definitions and small helpers for the focused T2 embryo run."""
import hashlib
import json
import os
import time
from pathlib import Path

FM = Path(__file__).resolve().parents[1]
VENV = FM.parents[1] / '.venv'  # fixed Python environment (read-only for agents and programs)
PY = str(VENV / 'bin/python')
DATA = FM / 'data'
TRAIN, PROTECTED, PANELS = DATA / 'train', DATA / 'protected', DATA / 'panels'
RUNS = FM / 'runs'

# Official T2 embryo stages used by this run.
# Training stages are readable by agents; E7.25 (guard target) and E7.5 (validation target and a test input) are
# protected: only the evaluation service and the final export read them.
STAGES = {
    'E6.75': dict(file=TRAIN / 'E6.75.h5ad', time=6.75, role='train',
                  sha256='ab58b9217d1b9a18b0181f498475a9eb821ac2c92ab2b7e45a623da0e4fffe70'),
    'E7.25': dict(file=PROTECTED / 'E7.25.h5ad', time=7.25, role='protected',
                  sha256='c34192a31036b783b97ce1877ac50fc920b39faa3e00dc3c637b3e7e04255ee6'),
    'E7.5': dict(file=PROTECTED / 'E7.5.h5ad', time=7.5, role='protected',
                 sha256='e8e47255ddeca96d5604c7cd4923bbf27765c24bc6a3cd44e800cd6ea05a7d54'),
    'E8.0': dict(file=TRAIN / 'E8.0.h5ad', time=8.0, role='train',
                 sha256='17530e23fbfa6a139ff68d0353a489d83790f5b60f036b7d2f58303a1ff8a810'),
}

TEST_MAX_CELLS = 5000   # official T2:embryo:test_interp upper bound (data/panels/index.json)
MIN_CELLS = 1000
NATIVE_OCCUPANCY_MIN = 0.90   # official occupancy Dice against the best input stage; 1 = one native cloud

SPLITS = {
    # Validation (agents see these scores): the official T2:embryo:val_interp board.
    'val': dict(role='validation', inputs=['E7.25', 'E8.0'], target='E7.5', reference='E8.0',
                max_cells=5000, weight=1.0),
    # Guard (never shown to agents; final veto): backcast through a stage withheld from agents.
    'guard': dict(role='heldout', inputs=['E6.75', 'E8.0'], target='E7.25', reference='E8.0',
                  max_cells=5000, weight=1.0),
    # Test configuration (no truth): both released/unlocked inputs of the official board.
    'test': dict(role='test', inputs=['E7.5', 'E8.0'], target=None, time=7.75, max_cells=TEST_MAX_CELLS),
}
VALIDATION = ['val']
HELDOUT = ['guard']
VAL_SCORING_SEEDS = [101, 102, 103]
HELDOUT_SCORING_SEEDS = [201, 202, 203]


def target_time(split):
    s = SPLITS[split]
    return s.get('time') or STAGES[s['target']]['time']


def split_files(split):
    """Every stage file a split touches (inputs, target, reference)."""
    s = SPLITS[split]
    names = list(s['inputs']) + [n for n in (s.get('target'), s.get('reference')) if n]
    return sorted({str(STAGES[n]['file']) for n in names})


def panel_genes(board='test_interp'):
    return (PANELS / f'T2__embryo__{board}.genes.txt').read_text().split()


def now():
    return time.strftime('%Y-%m-%d %H:%M:%S')


def sha256(path, chunk=1 << 22):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        while b := f.read(chunk):
            h.update(b)
    return h.hexdigest()


def write_json(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f'.{path.name}.{os.getpid()}.tmp')
    tmp.write_text(json.dumps(obj, indent=1, default=float) + '\n')
    tmp.replace(path)


def read_json(path, default=None):
    try:
        return json.loads(Path(path).read_text())
    except (FileNotFoundError, ValueError):
        return default
