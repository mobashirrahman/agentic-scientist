"""Export a test-board bundle from a program produced by a locked Shinka (Agent Team) run.

Local artifacts only: never uploads, never consumes an official attempt.

  .venv/bin/python scripts/export_agent_submission.py --run shinka_ve/runs/<lock>_<name> [--program-id ID]

Default selection rule (fixed before the run's results were inspected): the correct
program with the highest run combined_score. The program's predict() is applied to the
test-time inputs below, with the same context contract as the locked harness.
"""
import argparse
import gc
import importlib.util
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'vendor/vec-community-kit'))
import anndata as ad  # noqa: E402
import numpy as np  # noqa: E402
from src.data import load_stage  # noqa: E402
from shinka_ve.harness import external_context  # noqa: E402
from agentic_scientist.artifacts import digest, file_sha, workspace_manifest  # noqa: E402

# Test boards: all released + officially unlocked stages before/around each target.
BOARDS = {
    'T1:test': dict(board='temporal', inputs=['T1/E8.5_RNA.h5ad', 'T1/E9.5_RNA.h5ad', 'T1/E10.5_RNA.h5ad'],
                    times=[8.5, 9.5, 10.5], time=12.5),
    'T2:heart:test_extrap': dict(board='heart', inputs=['T2/E8.25_late.h5ad', 'T2/E8.5.h5ad', 'T2/E8.75.h5ad',
                                                       'T2/E9.5.h5ad', 'T2/E10.5.h5ad'],
                                 times=[8.25, 8.5, 8.75, 9.5, 10.5], time=12.5),
    'T2:embryo:test_interp': dict(board='embryo', inputs=['T2/E7.5.h5ad', 'T2/E8.0.h5ad'],
                                  times=[7.5, 8.0], time=7.75),
    'T3:bcatenin': dict(board='perturbation', inputs=['T2/E8.0.h5ad', 'T2/E8.25_late.h5ad', 'T2/E8.5.h5ad', 'T2/E8.75.h5ad'],
                        times=[8.0, 8.25, 8.5, 8.75], time=8.75, knockout='Ctnnb1'),
}


def sha(path):
    return file_sha(path)


def pick(run, program_id=None):
    con = sqlite3.connect(run / 'programs.sqlite')
    q = 'select id, generation, combined_score, code, public_metrics from programs where correct=1'
    q += ' and id=?' if program_id else ' order by combined_score desc limit 1'
    row = con.execute(q, (program_id,) if program_id else ()).fetchone()
    if row is None:
        raise SystemExit('no matching correct program in run')
    return dict(id=row[0], generation=row[1], score=row[2], code=row[3], public=json.loads(row[4] or '{}'))


def load_program(path):
    spec = importlib.util.spec_from_file_location('agent_program', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# Where each context key's data comes from (shinka_ve/harness.py EXTERNAL / EXTERNAL_SPATIAL / expression_prior)
SOURCES = {('temporal', 'external'): 'Qiu et al. 2024 JAX atlas anchors (data/external/qiu2024)',
           ('heart', 'external'): 'Feulner et al. 2024 perinatal heart (data/external/heart_anchor)',
           ('heart', 'external_spatial'): 'Slide-seq developing heart atlas GSE282547 (data/external/heart_spatial)',
           ('embryo', 'external'): 'Extended Mouse Atlas, Imaz-Rosshandler et al. 2024 (data/external/embryo_anchor)',
           ('perturbation', 'external'): 'Gene Ontology prior (data/external/go_prior)',
           ('perturbation', 'expression_prior'): 'Qiu et al. 2024-derived expression prior (data/external/expression_prior)',
           ('perturbation', 'gene_embeddings'): 'Geneformer-V2-104M WT <=E9.0 gene embeddings (data/external/gene_embeddings)',
           ('perturbation', 'coexpr_prior'): 'Qiu et al. 2024 WT <=E9.0 signed gene-to-panel co-expression prior (data/external/coexpr_prior)'}


class TrackedContext(dict):
    """The context dict handed to predict(); records which keys the program actually read (provenance of the
    external data a submitted prediction used). A whole-dict copy counts as reading every key."""
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.read = set()

    def __getitem__(self, k):
        self.read.add(k)
        return super().__getitem__(k)

    def get(self, k, default=None):
        self.read.add(k)
        return super().get(k, default)

    def __contains__(self, k):
        self.read.add(k)
        return super().__contains__(k)

    def _all(self):
        self.read.update(super().keys())

    def __iter__(self):
        self._all()
        return super().__iter__()

    def keys(self):
        self._all()
        return super().keys()

    def items(self):
        self._all()
        return super().items()

    def values(self):
        self._all()
        return super().values()

    def copy(self):
        self._all()
        return dict(super().items())


def external_read(board, ctx):
    """[(key, source, non-empty)] for every external key the program read."""
    out = []
    for key in ('external', 'external_spatial', 'expression_prior', 'gene_embeddings', 'coexpr_prior'):
        if key in ctx.read:
            val = dict.get(ctx, key)
            out.append(dict(key=key, source=SOURCES.get((board, key), key), provided=val is not None))
    return out


def external(genes):
    files = sorted((ROOT / 'data/external/qiu2024').glob('*.h5ad'))
    if not files:
        return None
    from src.v2.anchor import load_external
    return load_external(files, genes)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--run', required=True)
    ap.add_argument('--workspace', help='AgenticScientist run: workspace dir (default <run>/final/selected)')
    ap.add_argument('--program-id')
    ap.add_argument('--seed', type=int, default=42)
    ap.add_argument('--n', type=int, default=3000)
    a = ap.parse_args()
    run = (ROOT / a.run).resolve()
    lockdir = 'agentic_scientist/locks' if run.name.startswith('mglock') else 'shinka_ve/locks'
    lock = json.loads((ROOT / lockdir / ('_'.join(run.name.split('_')[:3]) + '.json')).read_text())
    if lockdir == 'agentic_scientist/locks':  # free-form AgenticScientist workspace chosen by the run's frozen holdout rule
        import shutil
        ws = Path(a.workspace).resolve() if a.workspace else run / 'final/selected'
        final = json.loads((run / 'final/final.json').read_text()) if (run / 'final/final.json').exists() else {}
        if final.get('eligible_for_export') is False:
            raise SystemExit('calibrated finalization produced no eligible T3 promotion')
        if 'evaluator' in lock:
            if final.get('lock_id') != lock['lock_id'] or 'selected_sha256' not in final:
                raise SystemExit('the locked run has no completed final selection')
            changed = [f for f, expected in lock['files'].items() if file_sha(ROOT / f) != expected]
            if changed:
                raise SystemExit(f'lock violation during export: {changed[0]}')
        workspace_hash = digest(workspace_manifest(ws))
        if 'selected_sha256' in final and workspace_hash != final['selected_sha256']:
            raise SystemExit('prediction workspace differs from the selected artifact')
        prog = dict(id=final.get('chosen', ws.name) + '_' + workspace_hash[:8],
                    generation=None, score=None, public=final)
        out = ROOT / 'submissions/agent' / run.name / prog['id']
        shutil.rmtree(out / 'ws', ignore_errors=True)
        shutil.copytree(ws, out / 'ws', ignore=shutil.ignore_patterns('__pycache__'))
        sys.path.insert(0, str(out / 'ws'))
        module = load_program(out / 'ws/program.py')
        from agentic_scientist.evaluate import load_params  # the evaluator's own loader: <board>_tuned.json (+ legacy file)
        tuned = load_params(out / 'ws')
        (out / 'program.py').write_text((out / 'ws/program.py').read_text())
    else:
        prog = pick(run, a.program_id)
        out = ROOT / 'submissions/agent' / run.name / prog['id'][:8]
        out.mkdir(parents=True, exist_ok=True)
        (out / 'program.py').write_text(prog['code'])
        module = load_program(out / 'program.py')
    panels = json.loads((ROOT / 'data/panels/index.json').read_text())
    from vec_submit_check.checker import check
    manifest = dict(run=run.name, lock_id=lock['lock_id'], program_id=prog['id'], generation=prog['generation'],
                    run_combined_score=prog['score'], run_public_metrics=prog['public'],
                    program_sha256=sha(out / 'program.py'), seed=a.seed, n=a.n, boards={})
    if lockdir == 'agentic_scientist/locks':
        manifest['workspace_sha256'] = workspace_hash
        manifest['tuned_params'] = tuned
    for key, spec in BOARDS.items():
        stages = [load_stage(p) for p in spec['inputs']]
        if spec['board'] == 'embryo':  # same gene intersection as the locked harness
            genes = stages[0].var_names[stages[0].var_names.isin(stages[1].var_names)]
            stages = [s[:, genes].copy() for s in stages]
        context = TrackedContext(seed=a.seed, fit_seed=0, n=a.n, knockout=spec.get('knockout'),
                       **external_context(spec['board'], list(stages[-1].var_names), stages, spec['times']),
                       sampling={'temporal': 'heart_chambers', 'heart': 'heart_dissected'}.get(spec['board']),
                       params=dict(tuned.get(spec['board'], {})) if lockdir == 'agentic_scientist/locks' else {})
        pred = module.predict(spec['board'], stages, list(spec['times']), spec['time'], context)
        board = panels[key]
        panel = (ROOT / 'data/panels' / board['genes_file']).read_text().split()
        missing = [g for g in panel if g not in set(pred.var_names)]
        if missing:
            raise SystemExit(f'{key}: prediction lacks {len(missing)} panel genes, e.g. {missing[:3]}')
        pred = pred[:, panel].copy()
        X = pred.X.toarray() if hasattr(pred.X, 'toarray') else np.asarray(pred.X)
        clean = ad.AnnData(X.astype(np.float32), var=pred.var.iloc[:, :0].copy())
        clean.obs_names = [f'historical-entry_{i}' for i in range(clean.n_obs)]
        for k in board['obsm_required']:
            if k not in pred.obsm:
                raise SystemExit(f'{key}: program output lacks required obsm[{k!r}]')
            clean.obsm[k] = np.asarray(pred.obsm[k])[:, :3].astype(np.float32)
        path = out / (key.replace(':', '__') + '.h5ad')
        clean.write_h5ad(path, compression='gzip')
        report = check(str(path), key, panels=str(ROOT / 'data/panels'))
        manifest['boards'][key] = dict(file=path.name, cells=clean.n_obs, genes=clean.n_vars, sha256=sha(path),
                                       inputs={p: sha(ROOT / 'data/raw' / p) for p in spec['inputs']},
                                       target_time=spec['time'], knockout=spec.get('knockout'),
                                       format_check=report, context_read=sorted(context.read),
                                       external_data_read=external_read(spec['board'], context))
        if not report.get('ok', report.get('valid')):
            raise SystemExit(f'{key}: format check failed: {report}')
        print(key, clean.shape, 'format ok', flush=True)
        del stages, pred, clean, X
        gc.collect()
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2, default=str) + '\n')
    print(out)


if __name__ == '__main__':
    main()
