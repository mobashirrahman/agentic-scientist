"""Lock: sha256 of every harness, prompt, kit and config file plus the data files, taken at the first launch.
Every later (re)start of the same run refuses to continue if any locked file changed."""
import subprocess

from fm.common import FM, STAGES, now, read_json, sha256, write_json

LOCKED_DIRS = ['fm', 'kit', 'prompts', 'tests', 'data/panels']
LOCKED_FILES = ['config.json', 'PROTOCOL.md', 'run.sh', 'README.md']


def current():
    files = {}
    for d in LOCKED_DIRS:
        for p in sorted((FM / d).rglob('*')):
            if p.is_file() and '__pycache__' not in p.parts:
                files[str(p.relative_to(FM))] = sha256(p)
    for f in LOCKED_FILES:
        if (FM / f).exists():
            files[f] = sha256(FM / f)
    workspace = FM.parents[1]
    reference = workspace / 'models/historical/heart'
    for candidate in sorted(reference.glob('*')):
        if candidate.is_file():
            files[f'archived_reference/{candidate.name}'] = sha256(candidate)
    for p in sorted((workspace / 'vendor').glob('*')):
        if p.name in {'veckit', 'vec-community-kit'}:
            for source in sorted(p.rglob('*.py')):
                files[f'vendor/{source.relative_to(workspace / "vendor")}'] = sha256(source)
    return files


def ensure(run_dir):
    for name, s in STAGES.items():
        if sha256(s['file']) != s['sha256']:
            raise SystemExit(f'data file {s["file"]} does not match its official sha256')
    path = run_dir / 'lock.json'
    lk = read_json(path)
    cur = current()
    if lk is None:
        try:
            commit = subprocess.run(['git', '-C', str(FM), 'rev-parse', 'HEAD'], capture_output=True, text=True).stdout.strip()
            dirty = subprocess.run(['git', '-C', str(FM), 'status', '--porcelain', '--', *LOCKED_DIRS, *LOCKED_FILES],
                                   capture_output=True, text=True).stdout.strip()
        except OSError:
            commit, dirty = '', 'git unavailable'
        write_json(path, dict(created=now(), git_commit=commit, git_dirty=bool(dirty), files=cur,
                              data={n: s['sha256'] for n, s in STAGES.items()}))
        return
    changed = sorted(k for k in set(cur) | set(lk['files']) if cur.get(k) != lk['files'].get(k))
    if changed:
        raise SystemExit(f'lock violation: files changed since the run was locked: {changed}')
