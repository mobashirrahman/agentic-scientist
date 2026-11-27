"""Export Codex's T2 heart and embryo test predictions with the official export's exact inputs, context and
format checker (scripts/export_agent_submission.py). Local only: never uploads.
Needs the decrypted test inputs data/raw/T2/E10.5.h5ad and data/raw/T2/E7.5.h5ad (run via codex_t2_export.sh)."""
import gc
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path('/scratch/user/virtual-embryo')
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(ROOT / 'vendor/vec-community-kit'))
import anndata as ad  # noqa: E402
import numpy as np  # noqa: E402
from src.data import load_stage  # noqa: E402
from shinka_ve.harness import external_context  # noqa: E402
from export_agent_submission import BOARDS, TrackedContext  # noqa: E402
from vec_submit_check.checker import check  # noqa: E402

OUT = Path('/scratch/user/codex_t2_submission_bundle')
WS = {'T2:heart:test_extrap': Path('/scratch/user/ve-next/humantrack/t2_heart'),
      'T2:embryo:test_interp': Path('/scratch/user/ve-next/humantrack/t2_embryo')}


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def load(ws):
    spec = importlib.util.spec_from_file_location(f'prog_{ws.name}', ws / 'program.py')
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


OUT.mkdir(parents=True, exist_ok=True)
panels = json.loads((ROOT / 'data/panels/index.json').read_text())
manifest = dict(source='Codex human-track T2 models (ve-next/humantrack), seed 42, fit_seed 0', boards={})
for key, ws in WS.items():
    spec = BOARDS[key]
    module = load(ws)
    stages = [load_stage(p) for p in spec['inputs']]
    if spec['board'] == 'embryo':
        genes = stages[0].var_names[stages[0].var_names.isin(stages[1].var_names)]
        stages = [s[:, genes].copy() for s in stages]
    context = TrackedContext(seed=42, fit_seed=0, n=3000, knockout=None,
                             **external_context(spec['board'], list(stages[-1].var_names), stages, spec['times']),
                             sampling={'heart': 'heart_dissected'}.get(spec['board']), params={})
    pred = module.predict(spec['board'], stages, list(spec['times']), spec['time'], context)
    board = panels[key]
    panel = (ROOT / 'data/panels' / board['genes_file']).read_text().split()
    missing = [g for g in panel if g not in set(pred.var_names)]
    if missing:
        raise SystemExit(f'{key}: prediction lacks {len(missing)} panel genes')
    pred = pred[:, panel].copy()
    X = pred.X.toarray() if hasattr(pred.X, 'toarray') else np.asarray(pred.X)
    clean = ad.AnnData(X.astype(np.float32), var=pred.var.iloc[:, :0].copy())
    clean.obs_names = [f'historical-entry_{i}' for i in range(clean.n_obs)]
    for k in board['obsm_required']:
        clean.obsm[k] = np.asarray(pred.obsm[k])[:, :3].astype(np.float32)
    path = OUT / (key.replace(':', '__') + '.h5ad')
    clean.write_h5ad(path, compression='gzip')
    report = check(str(path), key, panels=str(ROOT / 'data/panels'))
    ok = report.get('ok', report.get('valid'))
    manifest['boards'][key] = dict(file=path.name, cells=clean.n_obs, genes=clean.n_vars, sha256=sha(path),
                                   workspace=str(ws), program_sha256=sha(ws / 'program.py'),
                                   target_time=spec['time'], format_check=report)
    print(key, clean.shape, 'format ok' if ok else f'FORMAT FAIL {report}', flush=True)
    if not ok:
        raise SystemExit(1)
    del stages, pred, clean, X
    gc.collect()
(OUT / 'manifest.json').write_text(json.dumps(manifest, indent=2, default=str) + '\n')
print(OUT)
