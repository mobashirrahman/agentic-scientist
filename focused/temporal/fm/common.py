"""Shared paths, stage definitions, split definitions and small helpers for the focused T1 run."""
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

STAGES = {
    'E8.5': dict(file=TRAIN / 'E8.5_RNA.h5ad', time=8.5, role='train',
                 sha256='8eab2d0ccaa89f92861b09816b76b6a731b8ed6b5995e4af196d9ed8ff76e504'),
    'E9.5': dict(file=TRAIN / 'E9.5_RNA.h5ad', time=9.5, role='train',
                 sha256='0296e0043842f944a663f3c11ac1542d1bbee733c1cd657bd56f75af65958361'),
    'E10.5': dict(file=PROTECTED / 'E10.5_RNA.h5ad', time=10.5, role='protected',
                  sha256='974e04e7fe64fb96142f17994a9678d4cebd4f1868dec4de034eda4245b7dd6c'),
}
for name, digest in json.loads((PANELS / 'guard_sha256.json').read_text()).items():
    STAGES[name] = dict(file=PROTECTED / f'guard_{name}.h5ad', time=float(name[1:]),
                        role='protected', sha256=digest)

TEST_MAX_CELLS = 5118
MIN_CELLS = 638
PRED_SEED = 42
SPLITS = {
    'val': dict(role='validation', inputs=['E8.5', 'E9.5'], target='E10.5', reference='E9.5',
                sampling='heart_with_surroundings', min_cells=1000, max_cells=TEST_MAX_CELLS, weight=1.0),
    'shape': dict(role='test', inputs=['E8.5', 'E9.5'], target=None, time=11.5,
                  sampling='heart_chambers', max_cells=TEST_MAX_CELLS),
    'guard': dict(role='heldout', inputs=['E14.5', 'E16.5'], target='E18.5', reference='E16.5',
                  sampling='heart_chambers', max_cells=TEST_MAX_CELLS, weight=1.0),
    'test': dict(role='test', inputs=['E8.5', 'E9.5', 'E10.5'], target=None, time=12.5,
                 sampling='heart_chambers', max_cells=TEST_MAX_CELLS),
}
VALIDATION = ['val']
HELDOUT = ['guard']
VAL_SCORING_SEEDS = [101, 102, 103]
HELDOUT_SCORING_SEEDS = [201, 202, 203]


def target_time(split):
    spec = SPLITS[split]
    return spec['time'] if 'time' in spec else STAGES[spec['target']]['time']


def panel_genes(split='test'):
    name = 'guard.genes.txt' if split == 'guard' else 'T1__test.genes.txt'
    return (PANELS / name).read_text().split()


def load_expression(name, genes):
    """Read only X and the model/scorer annotations, keeping protected layers out of memory."""
    import anndata as ad
    import numpy as np
    from scipy import sparse

    source = ad.read_h5ad(STAGES[name]['file'], backed='r')
    try:
        columns = source.var_names.get_indexer(genes)
        if (columns < 0).any():
            raise ValueError(f'{name} is missing {int((columns < 0).sum())} panel genes')
        # Backed sparse indexing cannot apply both arbitrary axes in one read.
        x = source.X
        x = x.to_memory() if hasattr(x, 'to_memory') else np.asarray(x)
        if list(source.var_names) != genes:
            x = x[:, columns]
        x = sparse.csr_matrix(x, dtype=np.float32)
        obs = source.obs[['celltype']].copy()
        return ad.AnnData(x, obs=obs, var=source.var.iloc[columns, :0].copy())
    finally:
        source.file.close()


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
