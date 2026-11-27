"""Final phase (pre-registered in PROTOCOL.md): guard and validation scoring of every checkpoint, selection,
test export, evidence packaging. Runs automatically after the last round; no human input."""
import json
import re
import shutil
import subprocess
import zipfile
from pathlib import Path

from fm import score as S
from fm.common import (FM, HELDOUT, HELDOUT_SCORING_SEEDS, MIN_CELLS, PANELS, PRED_SEED, PY, TEST_MAX_CELLS,
                       now, panel_genes, sha256, write_json)
from fm.evaluation import content_hash, run_program, score_snapshot

PRED_SEEDS = [PRED_SEED, 101]
GUARD_GAIN = 1.0
DIRECTION_TOLERANCE = 1.0
BLOOD = ('Hba-a1', 'Hba-a2', 'Hbb-bs', 'Hbb-bt')


def blood_like(stage):
    import numpy as np
    expression = np.asarray(stage[:, list(BLOOD)].X.mean(axis=1)).ravel()
    if not expression.size or not np.isfinite(expression).all():
        raise ValueError('invalid blood-marker expression')
    return float((expression > 3).mean())


def finalize(run):
    fd = run.dir / 'final'
    fd.mkdir(exist_ok=True)
    sel_path = fd / 'selection.json'
    if not sel_path.exists():
        select(run, fd, sel_path)
    sel = json.loads(sel_path.read_text())
    if not (fd / 'submission/manifest.json').exists():
        export(run, fd, sel)
    package(run, fd)


def passes_guard(candidate, reference):
    if any('pred_seed_scores' not in item for item in (candidate, reference)):
        return False
    gains = [a - b for a, b in zip(candidate['pred_seed_scores'], reference['pred_seed_scores'], strict=True)]
    return (min(gains) >= 0 and sum(gains) / len(gains) >= GUARD_GAIN
            and candidate['metrics']['de_direction'] >= reference['metrics']['de_direction'] - DIRECTION_TOLERANCE)


def select(run, fd, sel_path):
    seed = fd / 'seed'
    seed.mkdir(exist_ok=True)
    shutil.copy2(FM / 'kit/program.py', seed / 'program.py')
    reference = dict(round=-1, rounds=[], snapshot='final/seed', hash=content_hash(seed), model='empirical seed')
    cps, by_hash = [reference], {reference['hash']: reference}
    for k, r in sorted(run.state['rounds'].items(), key=lambda x: int(x[0])):
        c = r.get('checkpoint')
        if not c:
            continue
        if c['hash'] in by_hash:
            by_hash[c['hash']]['rounds'].append(int(k))
            continue
        e = dict(c, rounds=[int(k)])
        by_hash[c['hash']] = e
        cps.append(e)
    run.log(f'final: scoring {len(cps)} distinct snapshots on the late two-day guard')
    for c in cps:
        work = fd / 'work' / f"guard_{c['hash']}"
        c['guard'] = score_snapshot(run.dir / c['snapshot'], HELDOUT, PRED_SEEDS, HELDOUT_SCORING_SEEDS, work)['guard']
        run.log(f"final: {c['snapshot']} guard={c['guard'].get('score')} validation={c.get('validation')}")
    passed = [c for c in cps[1:] if passes_guard(c['guard'], reference['guard'])]
    passed.sort(key=lambda c: (-c['guard']['score'], c['round']))
    write_json(sel_path, dict(time=now(), rule=(
        'Use one nominated checkpoint per round. Rank by the independent late whole-heart guard after a '
        'paired win of at least one mean point with no prediction-seed loss and no more than one point of '
        'DE direction loss. Require the composition veto and valid output for two test-configuration draws. '
        'Fall back to the original empirical seed. The validation target supplies diagnostics only.'),
        ranking=[c['snapshot'] for c in [*passed, reference]], checkpoints=cps,
        shortlisted=[c['snapshot'] for c in passed]))


def export(run, fd, sel):
    import anndata as ad
    from scipy import sparse
    import numpy as np

    genes = panel_genes()
    sub = fd / 'submission'
    sub.mkdir(exist_ok=True)
    tried = []
    cardiac = set(json.loads((PANELS / 't1_celltype_map.json').read_text())['cardiac']) | {'Blood'}
    last = S.load_stage('E10.5', genes)
    limit = blood_like(last[last.obs['celltype'].isin(cardiac).to_numpy()])
    for snap_rel in sel['ranking']:
        c = next(x for x in sel['checkpoints'] if x['snapshot'] == snap_rel)
        info = dict(snapshot=snap_rel, checks=[])
        tried.append(info)
        for seed in PRED_SEEDS:
            m = run_program(run.dir / snap_rel, 'test', seed, fd / 'work' / f'test_export_{seed}')
            check = dict(seed=seed, ok=m.get('ok'), error_type=m.get('error_type'))
            info['checks'].append(check)
            if not m.get('ok'):
                break
            a = ad.read_h5ad(m['pred'])
            blood = blood_like(a)
            x = a.X.data if sparse.issparse(a.X) else np.asarray(a.X)
            check.update(blood_like=blood, ok=(list(a.var_names) == genes and MIN_CELLS <= a.n_obs <= TEST_MAX_CELLS
                         and not a.obsm and not len(a.obs.columns) and np.isfinite(x).all() and (x >= 0).all()
                         and blood <= limit))
            if not check['ok']:
                break
            if seed == PRED_SEED:
                artifact, n_cells = Path(m['pred']), a.n_obs
        else:
            out = sub / 'T1__test.h5ad'
            shutil.copy2(artifact, out)
            write_json(sub / 'manifest.json', dict(
                board='T1:test', file=out.name, sha256=sha256(out), n_cells=int(n_cells), n_genes=len(genes),
                selected_snapshot=snap_rel, selected_round=c['round'], rounds=c['rounds'], model=c['model'],
                framework='Command Code CLI (headless cmd -p)', harness='focused AgenticScientist',
                validation=c.get('validation'), late_guard=c['guard'].get('score'), blood_like_limit=limit,
                research_candidate=c['round'] >= 0, input_stages=['E8.5', 'E9.5', 'E10.5'],
                target_stage='E12.5', sampling='heart_chambers', seed=PRED_SEED, tried=tried, time=now()))
            shutil.copytree(run.dir / snap_rel, sub / 'program', dirs_exist_ok=True)
            run.log(f'final: exported {out} from {snap_rel} ({n_cells} cells)')
            return
    write_json(sub / 'export_failed.json', dict(tried=tried))
    run.attention('T1 test export failed for every snapshot; see final/submission/export_failed.json')


SECRET = re.compile(r'(sk-ant-[A-Za-z0-9_\-]{10,}|eyJ[A-Za-z0-9_\-]{20,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}|'
                    r'"(?:accessToken|refreshToken|access_token|refresh_token|id_token|api_key|OPENAI_API_KEY)"\s*:\s*"[^"]+")')
SKIP_NAMES = {'.credentials.json', 'auth.json', '.claude.json'}


def _add(z, path, arc):
    if path.name in SKIP_NAMES or path.stat().st_size > 200 << 20 or path.suffix == '.h5ad':
        return
    if path.suffix in ('.json', '.jsonl', '.md', '.log', '.txt', '.py', '.tsv', '.sh', '.toml'):
        text = path.read_text(errors='replace')
        z.writestr(arc, SECRET.sub('[REDACTED]', text))
    else:
        z.write(path, arc)


def _zip(dest, items):
    with zipfile.ZipFile(dest, 'w', zipfile.ZIP_DEFLATED) as z:
        for src, arc in items:
            src = Path(src)
            if src.is_file():
                _add(z, src, arc)
            elif src.is_dir():
                for p in sorted(src.rglob('*')):
                    if p.is_file() and '__pycache__' not in p.parts:
                        _add(z, p, f'{arc}/{p.relative_to(src)}')


def package(run, fd):
    ev = fd / 'evidence'
    ev.mkdir(exist_ok=True)
    rounds = sorted((run.dir / 'rounds').glob('r*'))
    traj, prompts = [(run.dir / 'run.log', 'run.log'), (run.dir / 'state.json', 'state.json')], []
    for rd in rounds:
        n = rd.name
        traj += [(rd / 'transcripts', f'{n}/transcripts'), (rd / 'evals.jsonl', f'{n}/evals.jsonl'),
                 (rd / 'snapshots', f'{n}/snapshots'), (rd / 'workspace', f'{n}/workspace_final'),
                 (rd / 'home/.commandcode/projects', f'{n}/commandcode_session_files')]
        prompts += [(rd / 'TASK.md', f'{n}/TASK.md')] + [(p, f'{n}/{p.name}') for p in sorted((rd / 'transcripts').glob('*.prompt.md'))]
    prompts += [(FM / 'prompts', 'prompt_templates')]
    harness = [(FM / d, d) for d in ('fm', 'kit', 'prompts', 'tests')] + \
              [(FM / f, f) for f in ('config.json', 'PROTOCOL.md', 'README.md', 'run.sh')] + \
              [(run.dir / 'lock.json', 'lock.json')]
    env = fd / 'environment.txt'
    lines = []
    for cmd in (['cmd', '--version'], [PY, '-m', 'pip', 'freeze'], ['uname', '-a']):
        try:
            lines.append('$ ' + ' '.join(cmd) + '\n' + subprocess.run(cmd, capture_output=True, text=True, timeout=60).stdout)
        except Exception as e:  # noqa: BLE001
            lines.append(f'$ {cmd}: {e}')
    env.write_text('\n'.join(lines))
    readme = ev / 'README.md'
    readme.write_text(evidence_readme(run, fd))
    other = [(fd / 'selection.json', 'selection.json'), (fd / 'submission/manifest.json', 'submission_manifest.json'),
             (env, 'environment.txt'), (readme, 'README.md')]
    _zip(ev / 'trajectory.zip', traj)
    _zip(ev / 'prompts.zip', prompts)
    _zip(ev / 'harness.zip', harness)
    _zip(ev / 'other.zip', other)
    sums = [f'{sha256(p)}  {p.name}' for p in sorted(ev.glob('*.zip'))]
    (ev / 'SHA256SUMS').write_text('\n'.join(sums) + '\n')
    full = run.dir / f'focused_t1_{run.id}_agent_full.zip'
    with zipfile.ZipFile(full, 'w', zipfile.ZIP_DEFLATED) as z:
        for p in sorted(ev.iterdir()):
            z.write(p, f'evidence/{p.name}')
        for p in sorted((fd / 'submission').glob('*')):
            if p.is_file():
                z.write(p, f'submission/{p.name}')
    run.log(f'final: evidence packaged -> {full}')


def evidence_readme(run, fd):
    sel = json.loads((fd / 'selection.json').read_text())
    man = json.loads((fd / 'submission/manifest.json').read_text()) if (fd / 'submission/manifest.json').exists() else {}
    rows = '\n'.join(f"| {k} | {r.get('model')} | {r.get('evaluations')} | "
                     f"{(r.get('checkpoint') or {}).get('validation')} |"
                     for k, r in sorted(run.state['rounds'].items(), key=lambda x: int(x[0])))
    return f"""# Focused AgenticScientist T1 research evidence

Local export for the T1:test board. See PROTOCOL.md for the locked selection and data definitions.

- Runtime: Command Code CLI in headless mode.
- Harness: focused AgenticScientist with sandboxed prediction and separate scoring.
- Prior work: the team-authored empirical donor sampler in kit/program.py.
- Data: released T1 E8.5 and E9.5, officially unlocked T1 E10.5, and strictly post-E13.5
  wild-type whole-heart Drop-seq from Feulner et al. (GSE150817), used only for the final evaluation.
- The selection is automatic. Checkpoints and exports are research artifacts for local review.

| round | model | evaluations | local validation |
|---|---|---|---|
{rows}

Final rule: {sel.get('rule')}
Exported snapshot: {man.get('selected_snapshot')}. File: {man.get('file')}. SHA256: {man.get('sha256')}.
"""
