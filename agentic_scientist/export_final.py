"""Export a workspace to the four P3 TEST files, gate the exact files, and package evidence.

Local artifacts only: never uploads. Used by the AgenticScientist final run for 6-hourly checkpoints and the final
export (orchestrator), and by hand for inspection:

  .venv/bin/python -I agentic_scientist/export_final.py --workspace W --out DIR [--boards T1:test,...]
  .venv/bin/python -I agentic_scientist/export_final.py --package RUN_DIR --out ZIP

Gates run on the exact exported file:
  * official format check (vendor/vec-community-kit vec_submit_check: panel genes and order, row limits, obsm);
  * finite, non-negative expression; row count within the official limit;
  * embryo geometry: occupancy Dice of the output against its nearer input embryo must reach >= 97% of what a plain
    random subsample of that embryo (same size, same scorer seeds) reaches. The reference is midpoint geometry (agentic_scientist/native.py);
  * T1 blood guard: the forecast's blood-like share may not exceed the last input's.
"""
import argparse
import gc
import hashlib
import json
import sys
import time
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT, ROOT / 'vendor/vec-community-kit', ROOT / 'vendor/veckit'):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import numpy as np  # noqa: E402

GEOMETRY_RATIO_MIN = 0.97
GEOMETRY_SEEDS = (0, 1, 2, 3, 4)


def sha(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def geometry_gate(pred_xyz, inputs, times, target_time):
    """Occupancy of the output vs a bracket embryo in MIDPOINT geometry (per-native-axis spread interpolated at the
    elapsed-time fraction, see agentic_scientist/native.py), relative to a plain subsample of that reference.
    Best bracket counts. (Previously the reference was the unstretched nearer input; that geometry scored
    occupancy 3.7 on the test.)"""
    from common.shape_metrics import occupancy_dice
    from agentic_scientist.native import midpoint_cloud
    frac = float(np.clip((target_time - times[0]) / max(times[-1] - times[0], 1e-9), 0.0, 1.0))
    clouds = [np.asarray(a.obsm['spatial_3D'], float) for a in inputs]
    p = np.asarray(pred_xyz, float)
    best = None
    for k in (0, len(inputs) - 1):
        q = midpoint_cloud(k, clouds, frac)
        n = min(len(p), len(q))
        got, ref = [], []
        for s in GEOMETRY_SEEDS:
            got.append(occupancy_dice(p, q, seed=s)[0])
            sub = q[np.random.default_rng(1000 + s).choice(len(q), n, replace=False)]
            ref.append(occupancy_dice(sub, q, seed=s)[0])
        ratio = float(np.mean(got) / max(np.mean(ref), 1e-9))
        if best is None or ratio > best['ratio']:
            best = dict(ratio=ratio, dice=float(np.mean(got)), ref=float(np.mean(ref)), k=k)
    return dict(passed=bool(best['ratio'] >= GEOMETRY_RATIO_MIN), ratio=round(best['ratio'], 4), dice=round(best['dice'], 4),
                plain_subsample_dice=round(best['ref'], 4), reference_input_index=best['k'], reference='midpoint geometry',
                min_ratio=GEOMETRY_RATIO_MIN,
                unique_positions=int(len(np.unique(np.round(p, 3), axis=0))), n=int(len(p)))


def predict_board(module, key, spec, seed, n, tuned):
    from scripts.export_agent_submission import TrackedContext, external_read
    from shinka_ve.harness import external_context
    from src.data import load_stage
    stages = [load_stage(p) for p in spec['inputs']]
    if spec['board'] == 'embryo':
        genes = stages[0].var_names[stages[0].var_names.isin(stages[1].var_names)]
        stages = [s[:, genes].copy() for s in stages]
    context = TrackedContext(seed=seed, fit_seed=0, n=n, knockout=spec.get('knockout'),
                             **external_context(spec['board'], list(stages[-1].var_names), stages, spec['times']),
                             sampling={'temporal': 'heart_chambers', 'heart': 'heart_dissected'}.get(spec['board']),
                             params=dict(tuned.get(spec['board'], {})))
    pred = module.predict(spec['board'], [s.copy() for s in stages], list(spec['times']), spec['time'], context)
    return pred, stages, context, external_read(spec['board'], context)


def export(ws, out, boards=None, seed=42, n=3000, log=print):
    """Predict, write and gate every requested test board. Returns the manifest (also written to out/manifest.json)."""
    import anndata as ad
    from vec_submit_check.checker import check
    from scripts.export_agent_submission import BOARDS, load_program
    from agentic_scientist.artifacts import digest, workspace_manifest
    from agentic_scientist.evaluate import load_params, screen_workspace
    ws, out = Path(ws).resolve(), Path(out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    err = screen_workspace(ws)
    if err:
        raise SystemExit(f'workspace fails the program screen: {err}')
    for m in [m for m in sys.modules if m in ('program', 'temporal', 'heart', 'embryo', 'perturbation')
              or m.split('_')[0] in ('temporal', 'heart', 'embryo', 'perturbation')]:
        del sys.modules[m]
    sys.path.insert(0, str(ws))
    try:
        module = load_program(ws / 'program.py')
        tuned = load_params(ws)
        panels = json.loads((ROOT / 'data/panels/index.json').read_text())
        manifest = dict(workspace=str(ws), workspace_sha256=digest(workspace_manifest(ws)), seed=seed, n=n,
                        created=time.strftime('%F %T %z'), tuned_params=tuned, boards={})
        for key, spec in BOARDS.items():
            if boards and key not in boards:
                continue
            t0 = time.time()
            row = dict(gates={})
            try:
                pred, stages, context, ext = predict_board(module, key, spec, seed, n, tuned)
                board = panels[key]
                panel = (ROOT / 'data/panels' / board['genes_file']).read_text().split()
                missing = [g for g in panel if g not in set(pred.var_names)]
                if missing:
                    raise ValueError(f'prediction lacks {len(missing)} panel genes, e.g. {missing[:3]}')
                pred = pred[:, panel].copy()
                X = pred.X.toarray() if hasattr(pred.X, 'toarray') else np.asarray(pred.X)
                X = X.astype(np.float32)
                row['gates']['finite_nonnegative'] = bool(np.isfinite(X).all() and (X >= 0).all())
                clean = ad.AnnData(X, var=pred.var.iloc[:, :0].copy())
                clean.obs_names = [f'cell_{i}' for i in range(clean.n_obs)]
                for k in board['obsm_required']:
                    if k not in pred.obsm:
                        raise ValueError(f'program output lacks required obsm[{k!r}]')
                    clean.obsm[k] = np.asarray(pred.obsm[k])[:, :3].astype(np.float32)
                path = out / (key.replace(':', '__') + '.h5ad')
                clean.write_h5ad(path, compression='gzip')
                report = check(str(path), key, panels=str(ROOT / 'data/panels'))
                row['gates']['format'] = bool(report.get('ok', report.get('valid')))
                if spec['board'] == 'embryo':
                    g = geometry_gate(clean.obsm['spatial_3D'], stages, spec['times'], spec['time'])
                    row['gates']['embryo_geometry'] = g['passed']
                    row['geometry'] = g
                if spec['board'] == 'temporal':
                    from agentic_scientist.composition import blood_guard
                    bg = blood_guard(pred, stages[-1])
                    row['gates']['t1_blood_guard'] = not bg.get('failures')
                    row['blood_guard'] = bg
                row.update(file=path.name, cells=int(clean.n_obs), genes=int(clean.n_vars), sha256=sha(path),
                           inputs={p: sha(ROOT / 'data/raw' / p) for p in spec['inputs']}, target_time=spec['time'],
                           knockout=spec.get('knockout'), format_check=report, context_read=sorted(context.read),
                           external_data_read=ext)
                del stages, pred, clean, X
            except Exception as e:  # noqa: BLE001 - a failing board is reported, never silently skipped
                row.update(error=f'{type(e).__name__}: {e}'[:2000])
                row['gates']['ran'] = False
            row['ok'] = 'error' not in row and all(row['gates'].values())
            row['seconds'] = round(time.time() - t0, 1)
            manifest['boards'][key] = row
            log(f"export {key}: {'ok' if row['ok'] else 'FAILED'} {row.get('error') or row['gates']}")
            gc.collect()
        manifest['ok'] = all(r['ok'] for r in manifest['boards'].values())
        (out / 'manifest.json').write_text(json.dumps(manifest, indent=1, default=str) + '\n')
        return manifest
    finally:
        sys.path.remove(str(ws))


MAX_ZIP_BYTES = 3_000_000_000  # uncompressed input cap for the combined archive
PORTAL_PART_LIMIT = 185 * 1024 * 1024  # stay comfortably below the 200 MiB portal per-file cap
EVIDENCE_GLOBS = ('lock.json', 'brief.md', 'plan.md', 'notebook.md', 'state.json', 'run.log', 'final.log',
                  'sandbox_probe.json', 'agent_calls.jsonl',
                  'seed_dev.json', 'knowledge/**/*', 'planner/**/*', 'cycles/**/*.json', 'cycles/**/*.jsonl',
                  'cycles/**/*.md', 'cycles/**/*.txt', 'cycles/**/ws/*', 'final/**/*', 'checkpoints/**/*',
                  'monitor/**/*', 'init_*/**/*.json', 'seed_ws/*')
HARNESS_GLOBS = ('agentic_scientist/*.py', 'agentic_scientist/*.sh', 'agentic_scientist/config_final*.json', 'agentic_scientist/config_dday.json', 'agentic_scientist/config_normandy.json', 'agentic_scientist/config_overlord.json', 'agentic_scientist/seed_overlord/*', 'agentic_scientist/seed_dday/*', 'agentic_scientist/seed_normandy/*',
                 'agentic_scientist/prompts/*.md', 'agentic_scientist/tools/*.py', 'agentic_scientist/skills/**/*.md',
                 'agentic_scientist/seed_final/*', 'agentic_scientist/seed_final_v2/*', 'agentic_scientist/library/*',
                 'agentic_scientist/data/*', 'shinka_ve/harness.py', 'shinka_ve/dynamics.py',
                 'scripts/export_agent_submission.py', 'scripts/build_coexpr_prior.py', 'scripts/package_evidence.py',
                 'src/**/*.py', 'docs/external_provenance.json', 'data/external/*/manifest*.json', 'agentic-scientist')

_CRED_FILES = {'auth.json', 'mcp-auth.json', '.env', 'credentials.json', 'id_rsa', 'id_ed25519'}
_CRED_SUFFIXES = {'.pem', '.key', '.db', '.db-wal', '.db-shm', '.sqlite', '.sqlite3', '.p12', '.pfx'}
_SKIP_PARTS = {'home', '.codex', '.claude', '__pycache__', '.quick_eval_runs', 'upload_ready'}


def _secret_patterns():
    import re
    pats = []
    try:
        from vec_agent_evidence.common import SECRET_PATTERNS
        pats.extend(SECRET_PATTERNS)
    except Exception:
        pass
    pats.extend([
        ('aws_access_key', re.compile(rb'(?<!Credential=)\bAKIA[0-9A-Z]{16}\b')),
        ('github_token', re.compile(rb'\bgh[pousr]_[A-Za-z0-9]{30}')),
        ('private_key_pem', re.compile(rb'-----BEGIN [A-Z ]*PRIVATE KEY-----')),
        ('api_key_assignment', re.compile(
            rb'\b(?:VE_API_KEY|VEC_API_KEY|OPENAI_API_KEY|ANTHROPIC_API_KEY|OPENCODE_API_KEY|GEMINI_API_KEY)\s*[=:]\s*["\']?[A-Za-z0-9_\-]{16,}')),
    ])
    return pats


def _scan_files_for_secrets(file_pairs):
    """Scan text-like files for credential patterns (official vec_agent_evidence + extra regexes)."""
    import re
    pats = _secret_patterns()
    text_ext = {'.json', '.jsonl', '.md', '.txt', '.log', '.py', '.sh', '.sha256', '.yaml', '.yml', '.toml', '.cfg', '.tsv', '.csv'}
    hits, scanned = [], 0
    for arc, p in file_pairs:
        p = Path(p)
        if p.name in _CRED_FILES or p.suffix.lower() in _CRED_SUFFIXES:
            hits.append(f'{arc}: disallowed credential filename')
            continue
        if p.suffix.lower() not in text_ext or not p.is_file():
            continue
        scanned += 1
        found, tail = set(), b''
        with p.open('rb') as stream:
            for block in iter(lambda: stream.read(1 << 20), b''):
                buf = tail + block
                for label, rx in pats:
                    if rx.search(buf):
                        found.add(label)
                tail = buf[-256:]
        hits.extend(f'{arc}: {label}' for label in sorted(found))
    return dict(clean=not hits, files_scanned=scanned, hits=hits)


def _write_split_zips(out_dir, kind, file_pairs, part_limit=PORTAL_PART_LIMIT):
    """Write `<kind>.zip` (or `<kind>.part01.zip`, `<kind>.part02.zip`, ...) keeping every zip <= part_limit bytes."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    if not file_pairs:
        return []
    parts, part_idx, z, cur_path, cur_files = [], 0, None, None, 0

    def open_part():
        nonlocal part_idx, z, cur_path, cur_files
        part_idx += 1
        cur_path = out_dir / f'{kind}.part{part_idx:02d}.zip'
        z = zipfile.ZipFile(cur_path, 'w', zipfile.ZIP_DEFLATED, allowZip64=True)
        cur_files = 0

    def close_part():
        nonlocal z
        if z is not None:
            z.close()
            parts.append(cur_path)
            z = None

    open_part()
    seen = set()
    for arc, p in file_pairs:
        p = Path(p)
        if arc in seen or not p.is_file() or p.is_symlink():
            continue
        if p.name in _CRED_FILES or p.suffix.lower() in _CRED_SUFFIXES:
            continue
        seen.add(arc)
        # Flush to a new part before crossing part_limit (estimate compressed size conservatively)
        if cur_files > 0 and z.fp.tell() > part_limit - 16 * 1024 * 1024:
            close_part()
            open_part()
        z.write(p, arc)
        cur_files += 1
    close_part()
    if len(parts) == 1:
        single = out_dir / f'{kind}.zip'
        parts[0].replace(single)
        parts = [single]
    return parts


def package_upload_ready(run_dir, out_dir=None, lock=None):
    """Build a portal-ready upload directory with:
      - submission/ (4 official vec_submit_check-verified .h5ad files + manifest.json + SUBMISSION.md + final.json)
      - submission_files.zip (convenience zip of the submission files)
      - prompts.zip, harness.zip, trajectory.zip (auto-split <=185 MiB/part), other.zip
      - EVIDENCE_MANIFEST.json + README.md (SHA-256s, lock verification, secret scan, API format checks).
    Never uploads anything and never packages credentials or private holdout files.
    """
    import shutil
    from vec_submit_check.checker import check
    run_dir = Path(run_dir).resolve()
    fdir = run_dir / 'final'
    out_dir = Path(out_dir).resolve() if out_dir else (fdir / 'upload_ready')
    tmp_dir = out_dir.with_name(f'.{out_dir.name}.partial')
    shutil.rmtree(tmp_dir, ignore_errors=True)
    tmp_dir.mkdir(parents=True, exist_ok=True)

    # 1. Resolve lock JSON
    lock_path = Path(lock).resolve() if lock else None
    if lock_path is None:
        lid = '_'.join(run_dir.name.split('_')[:3])
        cand = ROOT / 'agentic_scientist/locks' / f'{lid}.json'
        if cand.is_file():
            lock_path = cand
    lock_data = json.loads(lock_path.read_text()) if lock_path and lock_path.is_file() else {}

    # 2. Copy and re-verify final submission files (official vec_submit_check + SHA-256)
    sub_src = fdir / 'submission'
    if not sub_src.is_dir() and (fdir / 'submission_fallback').is_dir():
        sub_src = fdir / 'submission_fallback'
    sub_dst = tmp_dir / 'submission'
    sub_dst.mkdir(parents=True, exist_ok=True)
    sub_manifest = json.loads((sub_src / 'manifest.json').read_text()) if (sub_src / 'manifest.json').is_file() else {}
    sub_checks, sub_pairs = {}, []
    for key, row in (sub_manifest.get('boards') or {}).items():
        fname = row.get('file')
        if not fname or not (sub_src / fname).is_file():
            sub_checks[key] = dict(ok=False, error='missing file')
            continue
        dst = sub_dst / fname
        shutil.copy2(sub_src / fname, dst)
        actual_sha = sha(dst)
        expected_sha = row.get('sha256')
        rep = check(str(dst), key, panels=str(ROOT / 'data/panels'))
        fmt_ok = bool(rep.get('ok', rep.get('valid')))
        sha_ok = (expected_sha is None) or (actual_sha == expected_sha)
        sub_checks[key] = dict(ok=bool(fmt_ok and sha_ok and row.get('ok', True)), file=fname,
                               sha256=actual_sha, sha_matches_manifest=sha_ok, format_ok=fmt_ok,
                               cells=row.get('cells'), bytes=dst.stat().st_size, gates=row.get('gates'))
        sub_pairs.append((f'submission/{fname}', dst))
    for extra_name, src_p in [('manifest.json', sub_src / 'manifest.json'),
                              ('SUBMISSION.md', fdir / 'SUBMISSION.md'),
                              ('final.json', fdir / 'final.json')]:
        if src_p.is_file():
            shutil.copy2(src_p, sub_dst / extra_name)
            sub_pairs.append((f'submission/{extra_name}', sub_dst / extra_name))

    # 3. Collect evidence into the 4 official portal kinds: prompts, harness, trajectory, other
    kinds = dict(prompts=[], harness=[], trajectory=[], other=[])
    seen_rel = set()

    def ok_run_file(p):
        if not p.is_file() or p.is_symlink() or p.suffix in ('.zip', '.partial', '.pyc', '.h5ad'):
            return False
        if p.name in _CRED_FILES or p.suffix.lower() in _CRED_SUFFIXES:
            return False
        rel_parts = p.relative_to(run_dir).parts
        if any(part in _SKIP_PARTS for part in rel_parts):
            return False
        return True

    for pat in EVIDENCE_GLOBS:
        for p in sorted(run_dir.glob(pat)):
            if not ok_run_file(p):
                continue
            rel = p.relative_to(run_dir).as_posix()
            if rel in seen_rel:
                continue
            seen_rel.add(rel)
            if rel.endswith('.prompt.json') or rel in ('brief.md', 'plan.md') or (rel.startswith('planner/') and rel.endswith('.md')):
                kinds['prompts'].append((f'rendered/{rel}', p))
            elif rel.startswith('final/selected/') or rel in ('final/SUBMISSION.md', 'final/final.json', 'final/submission/manifest.json'):
                kinds['other'].append((f'final/{rel.removeprefix("final/")}', p))
            else:
                kinds['trajectory'].append((f'trajectory/{rel}', p))

    # Include top-level run + supervisor logs alongside trajectory
    run_name = run_dir.name
    if lock_data.get('lock_id'):
        short_name = run_name.removeprefix(lock_data['lock_id'] + '_')
        for suf in ('.log', '.supervisor.log'):
            lp = run_dir.parent / (short_name + suf)
            if lp.is_file() and not lp.is_symlink():
                kinds['trajectory'].append((f'logs/{lp.name}', lp))

    # Harness & prompt templates from lock (with SHA-256 verification!)
    lock_mismatches, lock_checked = [], 0
    if lock_data.get('files'):
        for f, expected in sorted(lock_data['files'].items()):
            p = ROOT / f
            if not p.is_file() or p.is_symlink():
                lock_mismatches.append(f'{f} (missing)')
                continue
            lock_checked += 1
            if expected and sha(p) != expected:
                lock_mismatches.append(f'{f} (sha mismatch)')
            kinds['harness'].append((f'harness/{f}', p))
            if f.startswith(('agentic_scientist/prompts/', 'agentic_scientist/skills/')):
                kinds['prompts'].append((f'templates/{f}', p))
    else:
        for pat in HARNESS_GLOBS:
            for p in sorted(ROOT.glob(pat)):
                if p.is_file() and not p.is_symlink():
                    rel = p.relative_to(ROOT).as_posix()
                    kinds['harness'].append((f'harness/{rel}', p))
                    if rel.startswith(('agentic_scientist/prompts/', 'agentic_scientist/skills/')):
                        kinds['prompts'].append((f'templates/{rel}', p))
    if lock_path and lock_path.is_file():
        kinds['harness'].append((f'lock/{lock_path.name}', lock_path))

    # External provenance & manifests go into other/
    for f in ('docs/external_provenance.json', 'docs/EXTERNAL_SOURCES.md'):
        if (ROOT / f).is_file():
            kinds['other'].append((f, ROOT / f))
    for mp in sorted((ROOT / 'data/external').glob('*/manifest*.json')):
        if mp.is_file():
            kinds['other'].append((mp.relative_to(ROOT).as_posix(), mp))

    # 4. Run full secret scan across every evidence file BEFORE zipping
    all_ev_pairs = [pair for files in kinds.values() for pair in files]
    sec = _scan_files_for_secrets(all_ev_pairs)

    # 5. Write split portal-ready zips + submission_files.zip
    archives = {}
    if sub_pairs:
        sub_zip = tmp_dir / 'submission_files.zip'
        with zipfile.ZipFile(sub_zip, 'w', zipfile.ZIP_DEFLATED, allowZip64=True) as z:
            for arc, p in sub_pairs:
                z.write(p, arc)
        archives['submission_files.zip'] = dict(kind='submission', bytes=sub_zip.stat().st_size,
                                                mb=round(sub_zip.stat().st_size / (1024 * 1024), 2),
                                                sha256=sha(sub_zip))
    ev_total_bytes = 0
    for kind in ('prompts', 'harness', 'trajectory', 'other'):
        for zp in _write_split_zips(tmp_dir, kind, kinds[kind]):
            sz = zp.stat().st_size
            ev_total_bytes += sz
            archives[zp.name] = dict(kind=kind, bytes=sz, mb=round(sz / (1024 * 1024), 2),
                                     under_200mb=bool(sz <= 200 * 1024 * 1024), sha256=sha(zp),
                                     file_count=len(kinds[kind]))

    # 6. Write EVIDENCE_MANIFEST.json + README.md
    lock_integrity = dict(ok=(len(lock_mismatches) == 0 and lock_checked > 0),
                          lock_id=lock_data.get('lock_id'), checked=lock_checked, mismatches=lock_mismatches[:20])
    all_sub_ok = bool(sub_checks) and all(v.get('ok') for v in sub_checks.values())
    all_under_200 = all(v.get('under_200mb', True) for v in archives.values() if v['kind'] != 'submission')
    ev_manifest = dict(
        run=run_dir.name,
        created=time.strftime('%F %T %z'),
        ready_for_upload=bool(all_sub_ok and sec['clean'] and lock_integrity['ok'] and all_under_200),
        submission_all_ok=all_sub_ok,
        submission_checks=sub_checks,
        lock_integrity=lock_integrity,
        secret_scan=sec,
        evidence_total_mb=round(ev_total_bytes / (1024 * 1024), 2),
        all_evidence_parts_under_200mb=all_under_200,
        archives=archives,
    )
    (tmp_dir / 'EVIDENCE_MANIFEST.json').write_text(json.dumps(ev_manifest, indent=1) + '\n')
    lines = [
        f'# Portal-Ready Submission & Evidence Package ({run_dir.name})', '',
        f"- Created: {ev_manifest['created']}",
        f"- Ready for upload: `{ev_manifest['ready_for_upload']}`",
        f"- Official `vec_submit_check` + SHA-256 verification: `{all_sub_ok}`",
        f"- Lock integrity (`{lock_data.get('lock_id')}`): `{lock_integrity['ok']}` ({lock_checked} locked files checked, {len(lock_mismatches)} mismatches)",
        f"- Secret scan (`vec_agent_evidence` + API key regexes): clean=`{sec['clean']}` ({sec['files_scanned']} files scanned, {len(sec['hits'])} hits)",
        f"- Total evidence size: `{ev_manifest['evidence_total_mb']} MiB` (all parts <= 200 MiB: `{all_under_200}`)", '',
        '## Submission files (`submission/` and `submission_files.zip`)',
        '| board | file | cells | vec_submit_check | sha256 |', '|---|---|---|---|---|',
    ]
    for k, v in sub_checks.items():
        lines.append(f"| {k} | `{v.get('file')}` | {v.get('cells')} | `{v.get('ok')}` | `{str(v.get('sha256'))[:16]}` |")
    lines += ['', '## Portal evidence archives (upload by kind)', '| archive | kind | MiB | files | sha256 |', '|---|---|---|---|---|']
    for name, info in archives.items():
        if info['kind'] == 'submission':
            continue
        lines.append(f"| `{name}` | `{info['kind']}` | {info['mb']} | {info.get('file_count', '')} | `{info['sha256'][:16]}` |")
    (tmp_dir / 'README.md').write_text('\n'.join(lines) + '\n')

    shutil.rmtree(out_dir, ignore_errors=True)
    tmp_dir.replace(out_dir)
    return ev_manifest


def package(run_dir, out_zip, lock=None, extra=()):
    """Zip the run's prompts, trajectories, outcomes, knowledge, selection and submission plus the harness source.
    Session homes (credentials) are never included; they live outside the run directory."""
    run_dir, out_zip = Path(run_dir).resolve(), Path(out_zip).resolve()
    out_zip.parent.mkdir(parents=True, exist_ok=True)
    sums, budget = [], [MAX_ZIP_BYTES]
    tmp = out_zip.with_name(f'.{out_zip.name}.partial')
    with zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED, allowZip64=True) as z:
        seen = set()

        def add(path, arc):
            path = Path(path)
            if arc in seen or not path.is_file() or path.suffix in ('.zip', '.partial', '.pyc'):
                return  # never the archive itself (it lives under final/) or any other archive
            if path.resolve() in (out_zip, tmp.resolve()):
                return
            size = path.stat().st_size
            if size > 400_000_000 or size > budget[0]:
                return
            if any(part in ('home', '.codex', '.claude', '__pycache__', '.quick_eval_runs')
                   for part in path.parts[len(run_dir.parts):]):
                return
            seen.add(arc)
            budget[0] -= size
            z.write(path, arc)
            sums.append(f'{sha(path)}  {arc}')
        for pat in EVIDENCE_GLOBS:
            for p in sorted(run_dir.glob(pat)):
                rel = p.relative_to(run_dir).parts
                if p.suffix == '.h5ad' and not (rel[0] == 'final' and len(rel) > 1 and rel[1].startswith('submission')):
                    continue  # prediction files: only the final submission (checkpoint files are reproducible)
                add(p, f'trajectory/{p.relative_to(run_dir)}')
        for pat in HARNESS_GLOBS:
            for p in sorted(ROOT.glob(pat)):
                add(p, f'harness/{p.relative_to(ROOT)}')
        if lock:
            add(Path(lock), f'harness/{Path(lock).relative_to(ROOT)}')
        for p in extra:
            add(Path(p), f'other/{Path(p).name}')
        z.writestr('SHA256SUMS', '\n'.join(sums) + '\n')
        z.writestr('README.md', README.format(run=run_dir.name, n=len(sums), t=time.strftime('%F %T %z')))
    tmp.replace(out_zip)
    return out_zip


README = """# AgenticScientist evidence: {run}

Packaged {t}; {n} files (SHA256SUMS lists each).

- `trajectory/`: the run as it happened. `brief.md` (the agents' brief), `cycles/<worker>_c<NN>/` per cycle:
  `*.prompt.json` (every rendered prompt with the model and CLI that received it), `*.jsonl` (the CLI's own
  event stream = full transcript), `hypothesis.json`, `outcome.json`, evaluations, `ws/` (the candidate program).
  `agent_calls.jsonl` logs every agent call (role, intended and actual model, seconds, exit, quota events).
  `knowledge/` is the knowledge bank, `planner/` the run planner, `checkpoints/` the 6-hourly automated exports,
  `final/` the selection record and the submission files with their manifest and gate results.
- `harness/`: the locked harness source, configuration, prompts, tools, seeds and the lock file.

All prediction files were produced by the programs in `trajectory/` without human edits. Agents could read the
public P3 leaderboard (model names, scores, per-metric results; snapshots plus hourly refreshes of the public JSON).
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--workspace')
    ap.add_argument('--package')
    ap.add_argument('--upload-ready')
    ap.add_argument('--out', required=True)
    ap.add_argument('--boards')
    ap.add_argument('--seed', type=int, default=42)
    a = ap.parse_args()
    if a.upload_ready:
        print(json.dumps(package_upload_ready(a.upload_ready, a.out), indent=1))
        return
    if a.package:
        print(package(a.package, a.out))
        return
    m = export(a.workspace, a.out, a.boards.split(',') if a.boards else None, seed=a.seed)
    print(json.dumps({k: dict(ok=v['ok'], gates=v['gates'], error=v.get('error')) for k, v in m['boards'].items()},
                     indent=1))


if __name__ == '__main__':
    main()
