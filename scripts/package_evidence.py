"""Agent Team evidence for a finished AgenticScientist run (Rules section 9), built automatically by final.sh after the export.

Packages ORIGINAL run files only (nothing is edited or reconstructed), one archive set per evidence kind:
  trajectory  every agent transcript (cycles/*/*.jsonl), the run log, per-cycle hypothesis/outcome/evaluation records,
              the knowledge bank and lab notebook, state.json, the final-selection log and records, and the code each
              cycle produced (workspace text files)
  prompts     the locked prompt templates and skills, plus the exact rendered prompt of every agent call
  harness     every file of the configuration lock (orchestrator, tools, evaluator, config, final/export scripts, data
              manifests), verified against the lock hashes, plus the lock record itself
  other       the export manifest and the submitted files' hashes, the selected program, external-data disclosure and
              provenance, and README.md (framework, models, timeline, human actions)
Archives larger than the per-file cap are split into numbered parts. A secret scan runs over every text file first;
a hit aborts packaging (nothing is redacted silently). Output: <export dir>/evidence/ with MANIFEST.json (sha256 and
size of every archive) and README.md.

  .venv/bin/python -I scripts/package_evidence.py --run agentic_scientist/runs/<lock>_<name> --export <export dir>
"""
import argparse
import hashlib
import io
import json
import re
import sys
import tarfile
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CAP = 190 * 2 ** 20          # stay under the 200 MiB per-file limit
TOTAL_CAP = 2 * 2 ** 30      # 2 GiB per submission
CHUNK = 1 << 20
BOARD = r'(?:temporal|perturbation|heart|embryo)'
CYCLE = r'cycles/(?:w\d+_(?:c\d+|tune)|merge)'
WORKSPACE = rf'(?:program\.py|{BOARD}(?:_\w+)?\.py|{BOARD}_(?:knobs|tuned)\.json|CHANGES\.md|PROVENANCE\.json)'
ROLE = r'(?:ideate(?:_r)?|implement|critic_plan|critic_code|distill|curate|review_fix|debug\d+)'
CALL = rf'(?:{CYCLE}/{ROLE}|planner/p\d+/plan)\.\d+'
CANDIDATE = r'(?:w\d+_c\d+|init_w\d+_\d+|seed|merge|final_ws|composed|w\d+_tune)'
RUN_FILES = [re.compile(p) for p in (
    r'state\.json|seed_dev\.(?:json|log)|(?:run|final)\.log|(?:notebook|plan|brief)\.md',
    r'knowledge/(?:entries\.jsonl|knowledge\.md|history/\d+\.md)',
    r'planner/p\d+/plan\.md', rf'{CALL}\.jsonl',
    rf'{CYCLE}/(?:hypothesis|outcome|critique|code_review|eval(?:_sub)?|sanity|noharm)\.json',
    rf'{CYCLE}/(?:implemented|ideate_retry|tune/tune\.json)',
    rf'{CYCLE}/tune/trial\d+/(?:params|eval_\d+_\d+)\.json',
    rf'(?:seed_ws|final/(?:selected|final_ws)|init_w\d+_\d+/ws|{CYCLE}/(?:ws|tuned_ws))/{WORKSPACE}',
    rf'(?:seed_ws|{CYCLE}/ws|init_w\d+_\d+/ws)_evals/pair\d+_(?:{BOARD}|eval_{BOARD}(?:-{BOARD})*)\.json',
    rf'final/(?:(?:unseen|holdout)_{CANDIDATE}|guard_{CANDIDATE}_{BOARD})_pair\d+(?:_sub)?\.json',
    r'final/(?:final|final_ws_dev(?:_sub)?)\.json',
    rf'monitor/(?:late_anchor\.jsonl|{CANDIDATE}_(?:heart|temporal)\.json)',
)]
SECRETS = [
    (re.compile(rb'sk-ant-[A-Za-z0-9_\-]{20,}'), 'Anthropic API key'),
    (re.compile(rb'\bsk-(?:proj-)?[A-Za-z0-9_\-]{32,}'), 'OpenAI-style API key'),
    (re.compile(rb'(?<!Credential=)\bAKIA[0-9A-Z]{16}\b'), 'AWS access key'),  # not public key IDs in pre-signed URLs fetched by agents
    (re.compile(rb'\bgh[pousr]_[A-Za-z0-9]{30}'), 'GitHub token'),
    (re.compile(rb'-----BEGIN [A-Z ]*PRIVATE KEY-----'), 'private key'),
    (re.compile(rb'\b(?:VE_API_KEY|VEC_API_KEY|OPENAI_API_KEY|ANTHROPIC_API_KEY|OPENCODE_API_KEY)\s*[=:]\s*["\']?[A-Za-z0-9_\-]{16,}'),
     'API key assignment'),
]


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def collect(run, export, lock):
    """Collect only known records from their producer's directory."""
    kinds = {k: [] for k in ('trajectory', 'prompts', 'harness', 'other')}
    for p in sorted(run.rglob('*')):
        rel = p.relative_to(run).as_posix()
        if p.is_symlink() or not p.is_file():
            continue
        if re.fullmatch(rf'{CALL}\.prompt\.json', rel):
            kinds['prompts'].append((f'rendered/{rel}', p))
        elif any(rx.fullmatch(rel) for rx in RUN_FILES):
            kinds['trajectory'].append((f'run/{rel}', p))
    name = run.name.removeprefix(lock['lock_id'] + '_')
    for suffix in ('.log', '.supervisor.log'):
        log = run.parent / (name + suffix)
        if log.is_file() and not log.is_symlink():
            kinds['trajectory'].append((f'logs/{log.name}', log))
    for f in sorted(lock['files']):
        p = ROOT / f
        if not p.is_file() or p.is_symlink():
            raise FileNotFoundError(f'Missing regular locked file: {f}')
        kinds['harness'].append((f'code/{f}', p))
        if f.startswith(('agentic_scientist/prompts/', 'agentic_scientist/skills/')):
            kinds['prompts'].append((f'templates/{f}', p))
    lock_path = ROOT / 'agentic_scientist/locks' / f"{lock['lock_id']}.json"
    kinds['harness'].append((f'lock/{lock_path.name}', lock_path))
    for p in sorted(export.rglob('*')):
        rel = p.relative_to(export).as_posix()
        if p.is_file() and not p.is_symlink() and re.fullmatch(rf'manifest\.json|program\.py|ws/{WORKSPACE}', rel):
            kinds['other'].append((f'export/{p.relative_to(export)}', p))
    for f in ('docs/EXTERNAL_SOURCES.md', 'docs/external_provenance.json'):
        if (ROOT / f).exists():
            kinds['other'].append((f, ROOT / f))
    return kinds


def scan(kinds):
    hits = []
    for files in kinds.values():
        for arc, p in files:
            found = set()
            tail = b''
            with p.open('rb') as stream:
                for block in iter(lambda: stream.read(CHUNK), b''):
                    # Normalize whitespace so arbitrarily padded assignments fit the overlap.
                    data = re.sub(rb'\s+', b' ', tail + block)
                    for rx, what in SECRETS:
                        if rx.search(data):
                            found.add(what)
                    tail = data[-128:]
                    # A long PEM label can span many reads, including a partial closing delimiter.
                    header = re.search(rb'-----BEGIN [A-Z ]*(?:PRIVATE KEY-{1,4})?$', data)
                    if header and len(data) - header.start() > 128:
                        tail = b'-----BEGIN ' + data[-64:]

            hits.extend(f'{arc}: {what}' for what in sorted(found))
    return hits


def verify_harness(kinds, lock):
    packaged = {arc.removeprefix('code/') for arc, _ in kinds['harness'] if arc.startswith('code/')}
    bad = sorted(set(lock['files']) - packaged)
    for arc, p in kinds['harness']:
        f = arc.split('/', 1)[1]
        if arc.startswith('code/') and lock['files'].get(f) and sha256(p) != lock['files'][f]:
            bad.append(f)
    return bad


def write_archives(out, kind, files):
    """Pack files into <kind>.tar.gz, starting a new part whenever the compressed size nears the cap."""
    paths, part, tar, buf = [], 0, None, None

    def open_part():
        nonlocal tar, buf, part
        part += 1
        buf = io.BytesIO()
        tar = tarfile.open(fileobj=buf, mode='w:gz', compresslevel=6)

    def close_part():
        tar.close()
        name = f'{kind}.tar.gz' if part == 1 else f'{kind}.part{part:02d}.tar.gz'
        (out / name).write_bytes(buf.getvalue())
        paths.append(out / name)

    open_part()
    for arc, p in files:
        if buf.tell() > CAP - 32 * 2 ** 20 and tar.getmembers():
            close_part()
            open_part()
        tar.add(p, arcname=arc, recursive=False)
    close_part()
    if len(paths) > 1:  # rename the first part consistently
        first = out / f'{kind}.tar.gz'
        first.rename(out / f'{kind}.part01.tar.gz')
        paths[0] = out / f'{kind}.part01.tar.gz'
    return paths


def models_used(run):
    c = Counter()
    rx = re.compile(r'agent (\w+) (\w+)\.?\d* exit=(\S+) \d+s model=(\S+)')
    log = run / 'run.log'
    for line in (log.read_text(errors='ignore').splitlines() if log.exists() else []):
        m = rx.search(line)
        if m:
            c[(m.group(1), m.group(4), m.group(2))] += 1
    return c


def readme(run, export, lock, state, final, models, archives):
    frameworks = {'codex': 'OpenAI Codex CLI (codex exec)', 'claude': 'Claude Code CLI (claude -p)',
                  'opencode': 'OpenCode CLI (opencode run)'}
    by_model = Counter()
    for (cli, model, _role), n in models.items():
        by_model[(cli, model)] += n
    roles = {}
    for (cli, model, role), n in models.items():
        roles.setdefault((cli, model), Counter())[role] += n
    log = (run / 'run.log').read_text(errors='ignore').splitlines() if (run / 'run.log').exists() else []
    pauses = [l for l in log if 'usage-limited' in l or 'paused' in l.lower()]
    acc = state.get('accepted', [])
    lines = [
        f'# Evidence for AgenticScientist run {run.name}', '',
        '## What ran the agent',
        '- Framework: **AgenticScientist**, our own research-agent harness (Python; agentic_scientist/orchestrator.py). It drives the',
        '  agent CLIs below in headless mode, evaluates every candidate on the dev splits with the official metrics,',
        '  accepts by a paired multi-seed test, and selects the final program by a frozen holdout rule.',
        '- Agent CLIs: ' + ', '.join(sorted({frameworks.get(cli, cli) for cli, _ in by_model})),
        '- Model strings actually run (agent calls, by role):',
    ]
    for (cli, model), n in by_model.most_common():
        lines.append(f'  - `{model}` via {cli}: {n} calls (' + ', '.join(f'{r} {k}' for r, k in roles[(cli, model)].most_common()) + ')')
    lines += [
        '', '## Lock and run',
        f"- Configuration lock: `{lock['lock_id']}` created {lock.get('created')}; {len(lock['files'])} files hashed "
        '(prompts, harness, evaluator, config, tools, seed program, data manifests, final and export scripts).',
        f"- Research started {time.strftime('%Y-%m-%d %H:%M', time.localtime(state.get('research_started', 0)))}; "
        f"{sum(w.get('cycle', 0) for w in state.get('workers', {}).values())} cycles; {len(acc)} accepted changes; "
        f"agent calls {state.get('calls')}; API-equivalent cost ${state.get('cost_usd', 0):.2f}.",
        f"- Final selection (automatic, frozen rule): chosen `{final.get('chosen')}`, workspace sha256 "
        f"`{final.get('selected_sha256')}`.",
        '', '## Human actions after the lock',
        '- One: a team member entered the holdout passphrase to start agentic_scientist/final.sh (decrypts the held-out',
        '  evaluation data so the frozen selection rule can run; agents never see it). Selection, export, format check',
        '  and this evidence package then ran automatically.',
        f'- Automatic harness events (no human involvement): {len(pauses)} usage-limit pauses/route-arounds logged in run.log.',
        '', '## Archives (evidence kinds)',
        '| file | kind | contents |', '|---|---|---|',
    ]
    desc = dict(trajectory='agent transcripts, run log, per-cycle records, knowledge bank, final selection log, code per cycle',
                prompts='locked prompt templates and skills + every rendered prompt sent to an agent',
                harness='all locked files (verified against the lock hashes) + the lock record',
                other='export manifest (submitted file hashes, inputs, format checks, external data read), selected program, external-data disclosure')
    for kind, ps in archives.items():
        for p in ps:
            lines.append(f'| {p.name} | {kind} | {desc[kind]} |')
    lines += ['', 'MANIFEST.json lists the sha256 and size of every archive. Nothing in these archives was edited after',
              'the run; files are copied verbatim from the run directory and the locked repository state.']
    return '\n'.join(lines) + '\n'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--run', required=True)
    ap.add_argument('--export', required=True)
    a = ap.parse_args()
    run, export = (ROOT / a.run).resolve(), (ROOT / a.export).resolve()
    lock = json.loads((ROOT / 'agentic_scientist/locks' / ('_'.join(run.name.split('_')[:3]) + '.json')).read_text())
    state = json.loads((run / 'state.json').read_text())
    final = json.loads((run / 'final/final.json').read_text()) if (run / 'final/final.json').exists() else {}
    kinds = collect(run, export, lock)
    bad = verify_harness(kinds, lock)
    if bad:
        raise SystemExit(f'harness files differ from the lock: {bad[:5]}')
    hits = scan(kinds)
    if hits:
        raise SystemExit('secret scan found possible credentials; evidence NOT packaged (fix by hand, then rerun):\n  '
                         + '\n  '.join(hits[:20]))
    out = export / 'evidence'
    if out.exists():
        for p in out.iterdir():
            p.unlink()
    out.mkdir(parents=True, exist_ok=True)
    archives = {kind: write_archives(out, kind, files) for kind, files in kinds.items() if files}
    (out / 'README.md').write_text(readme(run, export, lock, state, final, models_used(run), archives))
    man = {p.name: dict(sha256=sha256(p), bytes=p.stat().st_size, kind=k) for k, ps in archives.items() for p in ps}
    man['README.md'] = dict(sha256=sha256(out / 'README.md'), bytes=(out / 'README.md').stat().st_size, kind='other')
    total = sum(v['bytes'] for v in man.values())
    if total > TOTAL_CAP or any(v['bytes'] > 200 * 2 ** 20 for v in man.values()):
        raise SystemExit(f'evidence exceeds the caps (total {total / 2**20:.0f} MiB)')
    (out / 'MANIFEST.json').write_text(json.dumps(dict(run=run.name, lock_id=lock['lock_id'], created=time.strftime('%F %T'),
                                                       files=man, counts={k: len(v) for k, v in kinds.items()}), indent=1) + '\n')
    for p in out.iterdir():
        p.chmod(0o444)
    print(f'evidence: {out} ({total / 2**20:.1f} MiB; ' + ', '.join(f'{k} {len(v)} files' for k, v in kinds.items()) + ')')


if __name__ == '__main__':
    sys.exit(main())
