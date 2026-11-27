"""Final phase (pre-registered in PROTOCOL.md): guard and validation scoring of every checkpoint, selection,
test export, evidence packaging. Runs automatically after the last round; no human input."""
import json
import re
import shutil
import subprocess
import zipfile
from pathlib import Path

from fm import score as S
from fm.common import (FM, HELDOUT, HELDOUT_SCORING_SEEDS, MIN_CELLS, NATIVE_OCCUPANCY_MIN, PY, TEST_MAX_CELLS,
                       VALIDATION, VAL_SCORING_SEEDS, now, panel_genes, sha256, write_json)
from fm.evaluation import run_program

PRED_SEEDS = [0, 1]
GUARD_TOL = 1.0  # a candidate may not lose more than this to the round-0 starting model on the guard split


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


def select(run, fd, sel_path):
    cps, by_hash = [], {}
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
    run.log(f'final: {len(cps)} distinct checkpoints')
    from concurrent.futures import ThreadPoolExecutor

    def both(c):
        snap = run.dir / c['snapshot']
        w = fd / 'work' / Path(c['snapshot']).as_posix().replace('/', '_')
        return (run.fleet.score(snap, HELDOUT, PRED_SEEDS, HELDOUT_SCORING_SEEDS, w / 'ho'),
                run.fleet.score(snap, VALIDATION, PRED_SEEDS, VAL_SCORING_SEEDS, w / 'va'))

    with ThreadPoolExecutor(max(1, min(len(cps), 2 * max(1, len(run.fleet.hosts))))) as ex:
        scored = list(ex.map(both, cps))
    for c, (ho, va) in zip(cps, scored):
        c['heldout'] = S.combine(ho, HELDOUT)
        c['heldout_splits'] = ho
        c['validation_2seeds'] = S.combine(va, VALIDATION)
        c['validation_splits_2seeds'] = va
        c['native_occupancy'] = ((va.get('val') or {}).get('native_occupancy'))
        run.log(f"final: round {c['round']} {c['snapshot']} heldout={c['heldout']} "
                f"validation={c['validation_2seeds']} occupancy={c['native_occupancy']}")
    reference = cps[0]['heldout'] if cps and cps[0].get('heldout') is not None else None

    def eligible(c):
        if c.get('heldout') is None or c.get('validation_2seeds') is None:
            return False
        if c.get('native_occupancy') is None or c['native_occupancy'] < NATIVE_OCCUPANCY_MIN:
            return False
        if reference is not None and c['heldout'] < reference - GUARD_TOL:
            return False
        return True

    elig = [c for c in cps if eligible(c)]
    ranked = sorted(elig, key=lambda c: (-c['validation_2seeds'], -c['round']))
    if not ranked:
        ranked = sorted((c for c in cps if c.get('heldout') is not None),
                        key=lambda c: (-(c.get('validation_2seeds') or -1e9), -c['round']))
    write_json(sel_path, dict(time=now(), rule=(
        'highest validation (2 prediction seeds x 3 scoring seeds) among checkpoints that (a) pass the native-occupancy '
        f'gate >= {NATIVE_OCCUPANCY_MIN}, and (b) lose <= {GUARD_TOL} to the round-0 starting model on the guard split; '
        'ties -> later round; if none qualifies, highest validation among checkpoints that completed the guard'),
        ranking=[c['snapshot'] for c in ranked], checkpoints=cps,
        selected=ranked[0]['snapshot'] if ranked else None))


def export(run, fd, sel):
    genes = panel_genes('test_interp')
    sub = fd / 'submission'
    sub.mkdir(exist_ok=True)
    tried = []
    import anndata as ad
    import numpy as np
    for snap_rel in sel['ranking']:
        m = run_program(run.dir / snap_rel, 'test', 0, fd / 'work/test_export')
        tried.append(dict(snapshot=snap_rel, ok=m.get('ok'), error_type=m.get('error_type'), error=m.get('error')))
        if not m.get('ok'):
            continue
        a = ad.read_h5ad(m['pred'])
        problems = []
        if list(a.var_names) != genes:
            problems.append('gene order differs from T2__embryo__test_interp.genes.txt')
        if not MIN_CELLS <= a.n_obs <= TEST_MAX_CELLS:
            problems.append(f'n_cells {a.n_obs} outside [{MIN_CELLS}, {TEST_MAX_CELLS}]')
        sp = np.asarray(a.obsm.get('spatial_3D'))
        if sp.shape != (a.n_obs, 3) or not np.isfinite(sp).all():
            problems.append('spatial_3D invalid')
        X = a.X.toarray() if hasattr(a.X, 'toarray') else np.asarray(a.X)
        if not np.isfinite(X).all() or (X < 0).any():
            problems.append('expression not finite/non-negative')
        if problems:
            tried[-1].update(ok=False, problems=problems)
            continue
        out = sub / 'T2__embryo__test_interp.h5ad'
        shutil.copy2(m['pred'], out)
        c = next(x for x in sel['checkpoints'] if x['snapshot'] == snap_rel)
        write_json(sub / 'manifest.json', dict(
            board='T2:embryo:test_interp', file=out.name, sha256=sha256(out), n_cells=int(a.n_obs), n_genes=len(genes),
            selected_snapshot=snap_rel, selected_round=c['round'], rounds=c['rounds'], model=c['model'],
            framework='Command Code CLI (headless cmd -p)', harness='focused AgenticScientist',
            effort=run.cfg.get('builder', {}).get('effort'),
            validation=c['validation_2seeds'], heldout=c['heldout'], native_occupancy=c.get('native_occupancy'),
            fallback_used=snap_rel != sel['selected'],
            configuration='inputs E7.5,E8.0 -> 7.75, seed 0',
            tried=tried, time=now()))
        shutil.copytree(run.dir / snap_rel, sub / 'program', dirs_exist_ok=True)
        run.log(f'final: exported {out} from {snap_rel} ({a.n_obs} cells)')
        return
    write_json(sub / 'export_failed.json', dict(tried=tried))
    run.attention('test export failed for every checkpoint; see final/submission/export_failed.json')


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
    full = run.dir / f'focused_t2_embryo_{run.id}_agent_full.zip'
    with zipfile.ZipFile(full, 'w', zipfile.ZIP_DEFLATED) as z:
        for p in sorted(ev.iterdir()):
            z.write(p, f'evidence/{p.name}')
        for p in sorted((fd / 'submission').glob('*')):
            if p.is_file():
                z.write(p, f'submission/{p.name}')
    run.log(f'final: evidence packaged -> {full}')


def evidence_readme(run, fd):
    st, cfg = run.state, run.cfg
    sel = json.loads((fd / 'selection.json').read_text()) if (fd / 'selection.json').exists() else {}
    man = json.loads((fd / 'submission/manifest.json').read_text()) if (fd / 'submission/manifest.json').exists() else {}
    rows = '\n'.join(f"| {k} | {r.get('cli')}:{r.get('model')} | {r.get('started')} | {r.get('ended')} | "
                     f"{round(r.get('active_s', 0) / 3600, 2)} | {r.get('evaluations')} | "
                     f"{(r.get('checkpoint') or {}).get('validation')} |" for k, r in sorted(st['rounds'].items(), key=lambda x: int(x[0])))
    crow = '\n'.join(f"| {c['rounds']} | {c['snapshot']} | {c.get('validation_2seeds')} | {c.get('heldout')} | "
                     f"{c.get('native_occupancy')} |" for c in sel.get('checkpoints', []))
    return f"""# Focused T2 embryo agent run: evidence for run {run.id}

Agent Team entry, T2:embryo:test_interp.

## Framework and harness
- Framework (runtime): **Command Code CLI**, headless `cmd -p`; an off-the-shelf runtime, selected as Custom on the
  portal. No framework code is attached because we did not write the runtime.
- Harness (written for this Challenge): **focused AgenticScientist**, attached as `harness.zip` (episode runner, evaluation
  service, sandboxed program runner, exact scoring wrapper, selection, export, packaging).
- Framework and harness are separate; the harness code is the only code we wrote.

## Models
- Builder (round 0): {cfg['builder']['model']} (effort {cfg['builder'].get('effort', 'max')}) via the Command Code CLI.
- Improvers (rounds 1-{cfg['improve_rounds']}): {cfg['improver']['model']} (effort {cfg['improver'].get('effort', 'max')}) via the Command Code CLI.
- Fallback (used only when the scheduled model was unavailable): {cfg['fallback']['model']} (effort {cfg['fallback'].get('effort', 'max')}).
- Model actually used per session: state.json -> rounds -> sessions (also listed below).
- CLI versions: see environment.txt.

## Evidence map (portal fields)
- Trajectory: `trajectory.zip` — raw Command Code JSON event streams per session (`rounds/r*/transcripts/*.jsonl`),
  the CLI's own session files (`rounds/r*/home/.commandcode/projects`), the evaluation ledger, every program
  snapshot, final workspaces, `run.log` and `state.json`. Not a summary or reconstruction.
- Prompts: `prompts.zip` — every prompt sent (`rounds/r*/transcripts/*.prompt.md`), each round's rendered `TASK.md`,
  and the prompt templates.
- Harness: `harness.zip` — `fm/`, `kit/`, `prompts/`, `tests/`, `config.json`, `PROTOCOL.md`, `README.md`, `run.sh`,
  and the run `lock.json` (sha256 of every harness, prompt, kit, test, config and data file).

## Human involvement
The team wrote the harness, prompts and protocol (PROTOCOL.md), fixed them by a sha256 lock (lock.json) and launched
the run once. No human edited code, chose among intermediate outputs, or intervened in agent sessions. The final
checkpoint was picked by the pre-registered rule and exported automatically.

## Data
Official T2 embryo stages only. Training inputs E6.75 and E8.0 (agent-readable). Validation target E7.5 (P2 answer,
protected). Guard target E7.25 (withheld from agents). Agents had web search/fetch for literature research under the
organisers' external-data rules; every external source they used is listed in each round's NOTES.md.
Validation (agent-visible): E7.25+E8.0 -> E7.5.
Guard (never visible to agents): E6.75+E8.0 -> E7.25; final veto only.
Test configuration: E7.5+E8.0 -> 7.75.
Agents and programs ran under Linux Landlock: E7.5 and E7.25 were unreadable to agents; programs could read only
their own snapshot and their configuration's input stages, with no network.

## Rounds
| round | agent | started | ended | active h | evaluations | checkpoint validation |
|---|---|---|---|---|---|---|
{rows}

Sessions: {'; '.join(f"r{k}:{x['model']}({x['kind']},{x['seconds']}s)" for k, r in sorted(st['rounds'].items(), key=lambda x: int(x[0])) for x in r.get('sessions', []))}

## Final selection
Rule: {sel.get('rule')}

| rounds | snapshot | validation | guard | native occupancy |
|---|---|---|---|---|
{crow}

Selected: {sel.get('selected')}. Submission: {man.get('file')} sha256 {man.get('sha256')} ({man.get('n_cells')} cells),
fallback used: {man.get('fallback_used')}.

## Files
trajectory.zip (CLI event streams, CLI session files, evaluation ledger, every evaluated program snapshot, final
workspaces, run log, state), prompts.zip (every prompt sent, rendered task briefs, templates), harness.zip (harness
code, kit, prompts, config, protocol, lock), other.zip (selection, submission manifest, environment). Credential
files are excluded and token-like strings redacted.
"""
