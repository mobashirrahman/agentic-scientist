"""Agent sandbox for the AgenticScientist final run (Linux Landlock, no user namespaces).

Every agent CLI session (Codex, Claude Code, OpenCode) and every command it starts runs inside a Landlock allowlist:
  * read-only: system paths, the CLIs, the Python environment, the repository's code, docs, panels and external data,
    the run's shared files (brief, knowledge, plan), and the released stage files EXCEPT the protected local
    holdout targets (T2 E10.5 heart, T2 E7.5 embryo, T1 late guards);
  * read-write: the session's own home and tmp, its cycle directory, /tmp, /dev, /proc.
Codex and Claude get an isolated HOME / CODEX_HOME / CLAUDE_CONFIG_DIR per session (no access to the operator's other
transcripts, memories, MCP servers or plugins); credentials are copied in and synced back both ways while the session
runs, so token refreshes are never lost. Session homes live outside the run directory and are never packaged.

The protected files are also what the human-only per-cycle holdout monitor scores, so agents cannot see them by any
route; the orchestrator itself (not sandboxed) reads them.
"""
import json
import os
import shutil
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOME = Path.home()
VENV_REAL = Path('/scratch/user/virtual-embryo/.venv')
SHINKA_SRC = Path('/scratch/user/virtual-embryo/vendor/ShinkaEvolve')
PROTECTED = ('T2/E10.5.h5ad', 'T2/E7.5.h5ad', 'T1/guard_E14.5.h5ad', 'T1/guard_E16.5.h5ad', 'T1/guard_E18.5.h5ad',
             'T3/unseen_wt_a.h5ad', 'T3/unseen_wt_b.h5ad', 'T3/unseen_ko.h5ad', 'T3/unseen_spec.json')
SYSTEM_RO = ['/usr', '/lib', '/lib64', '/lib32', '/bin', '/sbin', '/etc', '/opt', '/run', '/sys', '/snap']
SYSTEM_RW = ['/dev', '/proc', '/tmp']
# Only what the agents' tools and programs need. Run history (earlier runs' programs, plans, archives, submission
# bundles) is deliberately NOT readable: agents learn from the curated library and the public leaderboard.
REPO_RO = ['agentic_scientist/tools', 'agentic_scientist/skills', 'agentic_scientist/library', 'agentic_scientist/data',
           'agentic_scientist/seed_final', 'agentic_scientist/seed_final_v2', 'agentic_scientist/config.json', 'src', 'shinka_ve', 'vendor',
           'docs/leaderboard', 'docs/papers', 'data/panels', 'data/external', 'data/checkpoints',
           'data/staged_inventory.json', 'opencode.json']
HEAVY_SLOTS = ROOT.parent / '.agentic_scientist-heavy-slots'  # quick_eval's machine-wide lock files
CLI_RO = [HOME / '.local', HOME / '.opencode', HOME / '.npm', HOME / '.nvm']
# OpenCode gets an isolated XDG home too: with the operator's XDG dirs, `opencode run` attaches to the operator's
# long-running `opencode serve --service` daemon and its tools would execute OUTSIDE the sandbox. Only auth.json is
# copied in; the downloaded helper binaries are linked read-only.
OC_DATA = Path(os.environ.get('XDG_DATA_HOME', HOME / '.local/share')) / 'opencode'
OC_CACHE = Path(os.environ.get('XDG_CACHE_HOME', HOME / '.cache')) / 'opencode'
# Antigravity (agy) and Command Code also get an isolated HOME: only their credential file (and Command Code's model
# settings) is copied in, so the operator's hooks, MCP servers, plugins and conversation history never load.
AGY_DIR = HOME / '.gemini/antigravity-cli'
CC_DIR = HOME / '.commandcode'
CRED = {'claude': (HOME / '.claude/.credentials.json', '.claude/.credentials.json'),
        'codex': (HOME / '.codex/auth.json', '.codex/auth.json'),
        'agy': (AGY_DIR / 'antigravity-oauth-token', '.gemini/antigravity-cli/antigravity-oauth-token'),
        'commandcode': (CC_DIR / 'auth.json', '.commandcode/auth.json')}
ISOLATED = ('claude', 'codex', 'fake', 'opencode', 'agy', 'commandcode')
_SYNC_LOCK = threading.Lock()


def protected_paths():
    return [ROOT / 'data/raw' / p for p in PROTECTED]


def released_files():
    """Every stage file under data/raw except the protected holdout targets."""
    prot = {p.resolve() for p in protected_paths()}
    return sorted(p for p in (ROOT / 'data/raw').rglob('*') if p.is_file() and p.resolve() not in prot)


def _fresh(path):
    try:
        d = json.loads(Path(path).read_text())
        o = d.get('claudeAiOauth') or {}
        if o.get('expiresAt'):
            return float(o['expiresAt']) / 1000
        from datetime import datetime
        if d.get('last_refresh'):
            return datetime.fromisoformat(d['last_refresh'].replace('Z', '+00:00')).timestamp()
        exp = (d.get('token') or {}).get('expiry')  # agy (Go time: nanoseconds, offset)
        if isinstance(exp, str):
            import re
            exp = re.sub(r'(\.\d{6})\d+', r'\1', exp.replace('Z', '+00:00'))
            return datetime.fromisoformat(exp).timestamp()
    except (OSError, ValueError, TypeError, AttributeError):
        pass
    try:
        return Path(path).stat().st_mtime
    except OSError:
        return -1


def _copy_atomic(src, dst):
    dst = Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_name(f'.{dst.name}.{os.getpid()}.{threading.get_ident()}.sync')
    shutil.copy2(src, tmp)
    os.chmod(tmp, 0o600)
    tmp.replace(dst)


def sync_credentials(cli, home):
    """Copy whichever credential file is fresher over the other (operator <-> session)."""
    if cli not in CRED:
        return
    main, rel = CRED[cli]
    sess = Path(home) / rel
    with _SYNC_LOCK:
        if not main.exists() and not sess.exists():
            return
        if not sess.exists() or (main.exists() and _fresh(main) > _fresh(sess) and main.read_bytes() != sess.read_bytes()):
            _copy_atomic(main, sess)
        elif not main.exists() or (_fresh(sess) > _fresh(main) and main.read_bytes() != sess.read_bytes()):
            _copy_atomic(sess, main)


class Session:
    """One sandboxed CLI invocation: env, Landlock prefix, credential sync."""

    def __init__(self, cli, session_dir, cwd, run_dir, extra_ro=(), extra_rw=()):
        self.cli = cli
        self.dir = Path(session_dir)
        self.home = self.dir / 'home'
        self.tmp = self.dir / 'tmp'
        for d in (self.home, self.tmp, self.home / '.codex', self.home / '.claude', self.home / '.config',
                  self.home / '.cache'):
            d.mkdir(parents=True, exist_ok=True)
        (self.home / '.gitconfig').write_text('[user]\n\tname = agent\n\temail = agent@localhost\n')
        self.cwd = Path(cwd)
        self.run_dir = Path(run_dir)
        self.extra_ro = [Path(p) for p in extra_ro]
        self.extra_rw = [Path(p) for p in extra_rw]
        self._stop = threading.Event()
        self._thread = None

    def env(self, base):
        e = dict(base)
        if self.cli in ISOLATED:
            e.update(HOME=str(self.home), CODEX_HOME=str(self.home / '.codex'),
                     CLAUDE_CONFIG_DIR=str(self.home / '.claude'), XDG_CACHE_HOME=str(self.home / '.cache'),
                     XDG_CONFIG_HOME=str(self.home / '.config'), XDG_DATA_HOME=str(self.home / '.local-share'),
                     XDG_STATE_HOME=str(self.home / '.local-state'))
        for k in [k for k in e if k.startswith('CLAUDE_CODE_') or k in ('CLAUDECODE', 'CLAUDE_PID', 'CLAUDE_EFFORT',
                                                                      'MG_PRIVATE_FINAL', 'SSH_AUTH_SOCK')]:
            e.pop(k)  # never inherit the operator's own Claude Code session
        e.update(TMPDIR=str(self.tmp), MPLCONFIGDIR=str(self.tmp), NUMBA_CACHE_DIR=str(self.tmp), IS_SANDBOX='1',
                 DISABLE_AUTOUPDATER='1', CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC='1',
                 PATH=f'{ROOT}/.venv/bin:{HOME}/.local/bin:{HOME}/.opencode/bin:/usr/local/bin:/usr/bin:/bin')
        return e

    def allow(self):
        ro = list(SYSTEM_RO) + [str(p) for p in CLI_RO] + [str(ROOT / '.venv'), str(VENV_REAL), str(SHINKA_SRC)]
        ro += [str(ROOT / p) for p in REPO_RO if (ROOT / p).exists()]
        ro += [str(p) for p in (ROOT / 'agentic_scientist').glob('*.py')]
        ro += [str(p) for p in released_files()]
        ro += [str(self.run_dir / n) for n in ('brief.md', 'plan.md', 'knowledge', 'seed_ws', 'cycles', 'notebook.md',
                                               'seed_dev.json', 'leaderboard') if (self.run_dir / n).exists()]
        ro += [str(p) for p in self.extra_ro]
        HEAVY_SLOTS.mkdir(parents=True, exist_ok=True)
        rw = list(SYSTEM_RW) + [str(self.home), str(self.tmp), str(self.cwd), str(HEAVY_SLOTS)]
        rw += [str(p) for p in self.extra_rw]
        if self.cli == 'opencode':
            ro += [str(p) for p in (OC_CACHE / 'bin', OC_CACHE / 'packages', OC_CACHE / 'npm') if p.exists()]
        return ro, rw

    def prefix(self):
        ro, rw = self.allow()
        args = [str(ROOT / '.venv/bin/python'), '-I', str(ROOT / 'agentic_scientist/landlock.py'), '--no-system',
                '--scope-signals']
        for p in ro:
            args += ['--ro', p]
        for p in rw:
            args += ['--rw', p]
        # Listing (names only) of the whole repository: Python's import system must list each sys.path directory
        # (the repo root for agentic_scientist / shinka_ve / src), and agents navigate with ls. File CONTENTS
        # stay limited to the ro/rw paths above; the protected holdout files remain unreadable.
        for p in (ROOT, self.run_dir):
            args += ['--list', str(p)]
        return args + ['--']

    def _opencode_home(self):
        data = self.home / '.local-share' / 'opencode'
        data.mkdir(parents=True, exist_ok=True)
        if (OC_DATA / 'auth.json').exists():
            _copy_atomic(OC_DATA / 'auth.json', data / 'auth.json')
        cache = self.home / '.cache' / 'opencode'
        cache.mkdir(parents=True, exist_ok=True)
        for sub in ('bin', 'packages', 'npm'):
            if (OC_CACHE / sub).exists() and not (cache / sub).exists():
                (cache / sub).symlink_to(OC_CACHE / sub)
        for f in ('models.json',):
            if (OC_CACHE / f).exists():
                shutil.copy2(OC_CACHE / f, cache / f)

    def _agy_home(self):
        d = self.home / '.gemini/antigravity-cli'
        d.mkdir(parents=True, exist_ok=True)
        if (AGY_DIR / 'installation_id').exists() and not (d / 'installation_id').exists():
            shutil.copy2(AGY_DIR / 'installation_id', d / 'installation_id')

    def _commandcode_home(self):
        d = self.home / '.commandcode'
        d.mkdir(parents=True, exist_ok=True)
        if (CC_DIR / 'config.json').exists():  # onboarding flags and per-model reasoning effort; no hooks
            shutil.copy2(CC_DIR / 'config.json', d / 'config.json')

    def __enter__(self):
        sync_credentials(self.cli, self.home)
        if self.cli == 'opencode':
            self._opencode_home()
        elif self.cli == 'agy':
            self._agy_home()
        elif self.cli == 'commandcode':
            self._commandcode_home()

        def loop():
            while not self._stop.wait(60):
                try:
                    sync_credentials(self.cli, self.home)
                except OSError:
                    pass
        self._thread = threading.Thread(target=loop, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *exc):
        self._stop.set()
        try:
            sync_credentials(self.cli, self.home)
        except OSError:
            pass
        return False


def probe(run_dir, cli_cmds=None):
    """Preflight: a sandboxed shell must fail to read every protected file and succeed on a released one."""
    import subprocess
    import tempfile
    out = {}
    with tempfile.TemporaryDirectory(dir=str(Path(run_dir))) as d:
        s = Session('fake', Path(d) / 'sess', Path(d), run_dir)
        for p in protected_paths() + released_files()[:1]:
            r = subprocess.run(s.prefix() + ['/bin/sh', '-c', f'head -c 16 {p} > /dev/null'], env=s.env(os.environ),
                               capture_output=True, text=True)
            out[str(p.relative_to(ROOT))] = 'readable' if r.returncode == 0 else 'blocked'
    bad = [k for k, v in out.items() if (v == 'readable') == any(k.endswith(x) for x in PROTECTED)]
    return dict(results=out, ok=not bad, problems=bad)
