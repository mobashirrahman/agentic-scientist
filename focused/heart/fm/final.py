"""Final phase (pre-registered in PROTOCOL.md): held-out scoring of every checkpoint, selection, test export,
evidence packaging. Runs automatically after the last round; no human input."""
import json
import re
import shutil
import subprocess
import zipfile
from pathlib import Path

from fm import score as S
from fm.common import (FM, HELDOUT, HELDOUT_SCORING_SEEDS, MIN_CELLS, PY, TEST_MAX_CELLS, VALIDATION,
                       VAL_SCORING_SEEDS, now, panel_genes, sha256, write_json)
from fm.evaluation import content_hash, run_program, snapshot
from fm.pilot import stage_control

PRED_SEEDS = [0, 1]


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
    for mode in ('copy_last', 'crop', 'crop_scale'):
        snap = fd / 'controls' / mode
        stage_control(mode, snap)
        cps.append(dict(round=-1, rounds=[], snapshot=str(snap.relative_to(run.dir)),
                        hash=content_hash(snap), model=mode, control=True))
    reference = fd / 'controls' / 'historical_focused'
    snapshot(FM.parents[1] / 'models/historical/heart', reference)
    cps.append(dict(round=-1, rounds=[], snapshot=str(reference.relative_to(run.dir)),
                    hash=content_hash(reference), model='historical_focused', control=True, comparison_only=True))
    for control in cps:
        by_hash[control['hash']] = control
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
        c['heldout'] = ho.get('ho_long', {}).get('score')
        c['heldout_splits'] = ho
        c['validation_2seeds'] = S.combine(va, VALIDATION)
        c['validation_splits_2seeds'] = va
        run.log(f"final: round {c['round']} {c['snapshot']} heldout={c['heldout']} validation={c['validation_2seeds']}")
    def control_ok(c):
        return all('score' in c[key].get(split, {}) for key, split in (
            ('heldout_splits', 'ho_long'), ('heldout_splits', 'ho_heart'),
            ('validation_splits_2seeds', 'val_heart'),
        ))

    controls = sorted((c for c in cps if c.get('control') and control_ok(c)), key=lambda c: -c['heldout'])
    if len(controls) != 4:
        raise RuntimeError('A registered heart control or the archived comparator failed')

    baseline = controls[0]

    def eligible(c):
        if c.get('control') or not control_ok(c):
            return False
        trial, control = c['heldout_splits'], baseline['heldout_splits']
        deltas = [a - b for a, b in zip(trial['ho_long']['pred_seed_scores'],
                                        control['ho_long']['pred_seed_scores'], strict=True)]
        return (min(deltas) >= 0 and c['heldout'] - baseline['heldout'] >= 0.75
                and trial['ho_heart']['score'] >= control['ho_heart']['score'] - 0.50
                and c['validation_splits_2seeds']['val_heart']['score']
                >= baseline['validation_splits_2seeds']['val_heart']['score'] - 0.50)

    challengers = sorted((c for c in cps if eligible(c)), key=lambda c: (-c['heldout'], -c['validation_2seeds'], c['round']))
    ranked = challengers + [c for c in controls if not c.get('comparison_only')]
    write_json(sel_path, dict(time=now(), rule='Beat the strongest fixed control on the two-day chamber replay by '
                              '0.75 mean points with no paired seed loss and <=0.50 loss on each shorter replay.',
                              evidence='Retrospective replays; one E10.5 target shared by short and long forecasts.',
                              reference=baseline['snapshot'], challenger_promoted=bool(challengers),
                              ranking=[c['snapshot'] for c in ranked],
                              checkpoints=cps, selected=ranked[0]['snapshot']))


def export(run, fd, sel):
    genes = panel_genes('test_extrap')
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
            problems.append('gene order differs from T2__heart__test_extrap.genes.txt')
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
        out = sub / 'T2__heart__test_extrap.h5ad'
        shutil.copy2(m['pred'], out)
        c = next(x for x in sel['checkpoints'] if x['snapshot'] == snap_rel)
        write_json(sub / 'manifest.json', dict(
            board='T2:heart:test_extrap', file=out.name, sha256=sha256(out), n_cells=int(a.n_obs), n_genes=len(genes),
            selected_snapshot=snap_rel, selected_round=c['round'], rounds=c['rounds'], model=c['model'],
            research_control=bool(c.get('control')), selection_reference=sel.get('reference'),
            validation=c['validation_2seeds'], heldout=c['heldout'], fallback_used=snap_rel != sel['selected'],
            configuration='inputs E8.25,E8.5,E8.75,E9.5,E10.5 -> 12.5, dissection heart_chambers_only, seed 0',
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
                 (rd / 'home/.claude/projects', f'{n}/claude_session_files'),
                 (rd / 'home/.codex/sessions', f'{n}/codex_session_files')]
        prompts += [(rd / 'TASK.md', f'{n}/TASK.md')] + [(p, f'{n}/{p.name}') for p in sorted((rd / 'transcripts').glob('*.prompt.md'))]
    prompts += [(FM / 'prompts', 'prompt_templates')]
    harness = [(FM / d, d) for d in ('fm', 'kit', 'prompts', 'tests')] + \
              [(FM / f, f) for f in ('config.json', 'PROTOCOL.md', 'README.md', 'run.sh')] + \
              [(run.dir / 'lock.json', 'lock.json'),
               (FM / 'data/panels', 'gene_panels'),
               (fd / 'controls/historical_focused', 'archived_reference')]
    env = fd / 'environment.txt'
    lines = []
    for cmd in (['codex', '--version'], ['claude', '--version'], [PY, '-m', 'pip', 'freeze'], ['uname', '-a']):
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
    full = run.dir / f'focused_t2_heart_{run.id}_agent_full.zip'
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
    crow = '\n'.join(f"| {c['rounds']} | {c['snapshot']} | {c.get('validation_2seeds')} | {c.get('heldout')} |"
                     for c in sel.get('checkpoints', []))
    return f"""# AgenticScientist heart evidence for run {run.id}

Agent Team entry, T2:heart:test_extrap. Framework: AgenticScientist.

## Models
- Builder (round 0): {cfg['builder']['model']} (reasoning effort {cfg['builder']['effort']}) via Codex CLI.
- Improvers (rounds 1-{cfg['improve_rounds']}): {cfg['improver']['model']} (effort {cfg['improver']['effort']}) via {cfg['improver']['cli']} CLI.
- Fallback (used only when the scheduled model was unavailable): {cfg['fallback']['model']} (effort {cfg['fallback']['effort']}) via Codex CLI.
- Model actually used per session: state.json -> rounds -> sessions (also listed below).
- CLI versions: see environment.txt.

## Human involvement
The team wrote the harness, prompts and protocol (PROTOCOL.md), fixed them by a sha256 lock (lock.json) and launched
the run once. No human edited code, chose among intermediate outputs, or intervened in agent sessions. The final
checkpoint was picked by the pre-registered held-out rule and exported automatically.

## Data
Official T2 heart stages only: training E8.25 (E8.25_late), E8.75, E9.5; P2 validation answers E8.5 and E10.5
(obtained through the official P3 opt-in). Agents had web search/fetch for literature research under the organisers'
external-data rules; every external source they used is listed in each round's NOTES.md (workspace_final). They also
received the team's earlier experiments as kit/prior_knowledge (in harness.zip).
Validation (agent-visible): E8.25+E8.75+E9.5 -> E10.5, all cells and heart-chambers-only target.
Selection: E8.25+E8.5 -> E10.5 chamber replay; E8.25+E8.5+E8.75 -> E9.5 chamber replay for regression. The E10.5 replays share a target.
Agents and programs ran under Linux Landlock: E8.5 and E10.5 were unreadable to agents; programs could read only
their own snapshot and their configuration's input stages, with TCP disabled.

## Rounds
| round | agent | started | ended | active h | evaluations | checkpoint validation |
|---|---|---|---|---|---|---|
{rows}

Sessions: {'; '.join(f"r{k}:{x['model']}({x['kind']},{x['seconds']}s)" for k, r in sorted(st['rounds'].items(), key=lambda x: int(x[0])) for x in r.get('sessions', []))}

## Final selection
Rule: {sel.get('rule')}

| rounds | snapshot | validation | held-out |
|---|---|---|---|
{crow}

Selected: {sel.get('selected')}. Submission: {man.get('file')} sha256 {man.get('sha256')} ({man.get('n_cells')} cells),
fallback used: {man.get('fallback_used')}.

## Files
trajectory.zip (CLI event streams, CLI session files, evaluation ledger, every evaluated program snapshot, final
workspaces, run log, state), prompts.zip (every prompt sent, rendered task briefs, templates), harness.zip (harness
code, kit, prompts, config, protocol, lock), other.zip (selection, submission manifest, environment). Credential
files are excluded and token-like strings redacted.
"""
