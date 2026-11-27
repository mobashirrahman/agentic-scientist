"""Artifact identity and atomic JSON writes shared by evaluation and export."""
import hashlib
import json
import os
import tempfile
from pathlib import Path


def file_sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def run_config(root, lock, requested=None, state=None):
    """Validate the startup binding and parse the exact bytes it identifies."""
    saved = (state or {}).get('effective_config') or {}
    name = requested if requested is not None else saved.get('path', 'agentic_scientist/config.json')
    path = (root / name).resolve()
    relative = path.relative_to(root).as_posix()
    if relative not in lock['files']:
        raise SystemExit(f'Config absent from lock: {relative}')
    data = path.read_bytes()
    binding = dict(path=relative, sha256=hashlib.sha256(data).hexdigest())
    if binding['sha256'] != lock['files'][relative] or (state is not None and saved != binding):
        raise SystemExit('Effective config path or digest differs from startup or lock')
    return binding, json.loads(data)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


# Files the harness or its tools write into a workspace; never program content.
HARNESS_FILES = ('CHANGES.md', 'PROVENANCE.json', '.quick_eval_runs')
HARNESS_DIRS = ('__pycache__',)


def workspace_manifest(ws):
    ws = Path(ws)
    return {
        p.relative_to(ws).as_posix(): file_sha(p)
        for p in sorted(ws.rglob('*'))
        if p.is_file() and not set(HARNESS_DIRS) & set(p.relative_to(ws).parts)
        and p.name not in HARNESS_FILES
    }


def write_text(path, text):
    path = Path(path)
    with tempfile.NamedTemporaryFile(mode='w', dir=path.parent, delete=False) as stream:
        tmp = Path(stream.name)
        try:
            stream.write(text)
            stream.close()
            os.replace(tmp, path)
        finally:
            tmp.unlink(missing_ok=True)


def write_json(path, value):
    write_text(path, json.dumps(value, indent=1, default=float) + '\n')


def read_cached(path, key):
    try:
        value = json.loads(Path(path).read_text())
    except (FileNotFoundError, ValueError):
        return None
    return value if isinstance(value, dict) and value.get('correct') and value.get('cache_key') == key else None
