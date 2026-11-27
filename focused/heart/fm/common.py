"""Shared paths, split definitions and small helpers for focused_morphogen_t2_heart."""
import hashlib
import json
import os
import re
import time
from pathlib import Path

FM = Path(__file__).resolve().parents[1]
VENV = FM.parents[1] / '.venv'  # fixed Python environment (read-only for agents and programs)
PY = str(VENV / 'bin/python')
DATA = FM / 'data'
TRAIN, PROTECTED, PANELS = DATA / 'train', DATA / 'protected', DATA / 'panels'
RUNS = FM / 'runs'

# Official T2 heart stages. Training stages are readable by agents; E8.5 and E10.5 (P2 validation answers, obtained
# through the official P3 opt-in) are protected: only the evaluation service and the final phase read them.
STAGES = {
    'E8.25': dict(file=TRAIN / 'E8.25_late.h5ad', time=8.25, role='train',
                  sha256='d56f94d3e2d719ed3074d86c03eae457ccf90b24145d33300f9958f0e8078593'),
    'E8.5': dict(file=PROTECTED / 'E8.5.h5ad', time=8.5, role='protected',
                 sha256='41c76db18bfaa92c1d66f8220ec5fbb6d6acccb0a6b78241f40080a3096d37db'),
    'E8.75': dict(file=TRAIN / 'E8.75.h5ad', time=8.75, role='train',
                  sha256='149ab6df7c99ad85046c8aebebcf0c43689b3720c59ffb7cc550edcf2f13a83c'),
    'E9.5': dict(file=TRAIN / 'E9.5.h5ad', time=9.5, role='train',
                 sha256='371ca6530e084de2b6cd6703b49d95f4bb59546c9291659809575382a630ee9a'),
    'E10.5': dict(file=PROTECTED / 'E10.5.h5ad', time=10.5, role='protected',
                  sha256='d6b37967f9cf3533091964cd07421c48a5c7c04628e9321123a426cb2a9c7e8b'),
}

# Heart-chambers-only target (the E12.5 test is dissected as "the heart chambers only" per the organisers):
# cardiomyocytes of every chamber, endocardium, cushion / valve EndoMT mesenchyme, (pro)epicardium and the dorsal
# mesenchymal protrusion. Surrounding tissue (pharyngeal mesoderm, body wall, pericardium, liver, foregut/bronchus,
# neural crest, surface ectoderm, extra-cardiac vessels) is excluded. One rule for every stage.
HEART_CHAMBERS = re.compile(r'CM$|^Chamber-Endo$|EndoMT|^Epi$|^Proepi$|^DMP$')

TEST_MAX_CELLS = 3000  # fixed output size across paired controls and safely inside the live portal bounds
VAL_MAX_CELLS = TEST_MAX_CELLS
MIN_CELLS = 1000

SPLITS = {
    # Validation (agents see these scores through tools/evaluate.py): the official T2:heart:val_extrap board
    # (training stages -> E10.5, reference = last training stage E9.5) and its heart-chambers-only twin.
    'val_all': dict(role='validation', inputs=['E8.25', 'E8.75', 'E9.5'], target='E10.5', reference='E9.5',
                    dissection='heart_with_surroundings', max_cells=VAL_MAX_CELLS, weight=0.0),
    'val_heart': dict(role='validation', inputs=['E8.25', 'E8.75', 'E9.5'], target='E10.5', reference='E9.5',
                      target_filter='heart_chambers', dissection='heart_chambers_only', max_cells=VAL_MAX_CELLS,
                      weight=1.0),
    # Held-out (never shown to agents; final selection only): backcast E8.25 + E8.5 + E8.75 -> E9.5. E8.5 is a
    # validation file agents never receive, and agents never see this configuration or its scores.
    'ho_all': dict(role='heldout', inputs=['E8.25', 'E8.5', 'E8.75'], target='E9.5', reference='E8.75',
                   dissection='heart_with_surroundings', max_cells=VAL_MAX_CELLS, weight=0.5),
    'ho_heart': dict(role='heldout', inputs=['E8.25', 'E8.5', 'E8.75'], target='E9.5', reference='E8.75',
                     target_filter='heart_chambers', dissection='heart_chambers_only', max_cells=VAL_MAX_CELLS,
                     weight=0.5),
    'ho_long': dict(role='heldout', inputs=['E8.25', 'E8.5'], target='E10.5', reference='E8.5',
                    target_filter='heart_chambers', dissection='heart_chambers_only', max_cells=VAL_MAX_CELLS,
                    weight=1.0),
    # Test configuration (no truth): every released and unlocked stage -> E12.5, heart chambers only.
    'test': dict(role='test', inputs=['E8.25', 'E8.5', 'E8.75', 'E9.5', 'E10.5'], target=None, time=12.5,
                 dissection='heart_chambers_only', max_cells=TEST_MAX_CELLS),
}
VALIDATION = ['val_all', 'val_heart']
HELDOUT = ['ho_long', 'ho_heart']
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


def panel_genes(board='test_extrap'):
    return (PANELS / f'T2__heart__{board}.genes.txt').read_text().split()


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
