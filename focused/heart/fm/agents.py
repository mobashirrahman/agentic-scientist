"""Headless agent sessions (Codex CLI, Claude Code) inside Landlock, with full transcripts.

Each session gets its own HOME / CODEX_HOME / CLAUDE_CONFIG_DIR inside the round directory (no access to the operator's
other transcripts, memories, MCP servers, plugins or skills) and a Landlock allowlist: read-only system paths, the
Python environment, the CLIs, the training stages; read-write only its workspace, its home, its tmp and its eval
spool. Credentials are copied in and synced back both ways while the session runs (token refreshes are never lost).

Transcript = the CLI's own JSON event stream (codex exec --json / claude -p --output-format stream-json --verbose),
saved verbatim, plus the CLI's own session files under the session home.
"""
import json
import os
import re
import shutil
import signal
import subprocess
import threading
import time
from pathlib import Path

from fm.common import FM, PY, STAGES, TRAIN, VENV, now, write_json

HOME = Path.home()
CLI_RO = [str(HOME / '.local')]  # node, codex, claude binaries
CRED = {'claude': (HOME / '.claude/.credentials.json', '.claude/.credentials.json'),
        'codex': (HOME / '.codex/auth.json', '.codex/auth.json')}
STALL_S = 1800  # no event from the CLI for 30 min = not responding
CODEX_DISABLE = ['apps', 'plugins', 'browser_use', 'computer_use', 'in_app_browser', 'memories']
LIMIT_PAT = re.compile(r"usage limit|rate limit|quota|too many requests|\b429\b|overloaded|try again at", re.I)
AUTH_PAT = re.compile(r'\b401\b|unauthorized|authentication_error|invalid api key|not logged in|oauth token|'
                      r'please run /login|login required|missing bearer', re.I)


def _fresh(path):
    """Freshness of a credential file: token expiry / refresh time if present, else mtime."""
    try:
        d = json.loads(Path(path).read_text())
        o = d.get('claudeAiOauth') or {}
        if o.get('expiresAt'):
            return float(o['expiresAt']) / 1000
        if d.get('last_refresh'):
            from datetime import datetime
            return datetime.fromisoformat(d['last_refresh'].replace('Z', '+00:00')).timestamp()
    except (OSError, ValueError, TypeError):
        return -1
    return Path(path).stat().st_mtime


def _copy_atomic(src, dst):
    dst = Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_name(f'.{dst.name}.sync')
    shutil.copy2(src, tmp)
    os.chmod(tmp, 0o600)
    tmp.replace(dst)


def sync_credentials(cli, home):
    """Copy whichever credential file is fresher over the other (operator <-> session)."""
    if cli not in CRED:
        return
    main, rel = CRED[cli]
    sess = Path(home) / rel
    if not main.exists() and not sess.exists():
        return
    if not sess.exists() or (main.exists() and _fresh(main) > _fresh(sess) and main.read_bytes() != sess.read_bytes()):
        _copy_atomic(main, sess)
    elif not main.exists() or (_fresh(sess) > _fresh(main) and main.read_bytes() != sess.read_bytes()):
        _copy_atomic(sess, main)


def kill_marked(marker):
    """Kill every process carrying FM_SESSION=<marker> (stragglers started with nohup/setsid by an agent)."""
    me = os.getpid()
    for pid in os.listdir('/proc'):
        if not pid.isdigit() or int(pid) == me:
            continue
        try:
            env = open(f'/proc/{pid}/environ', 'rb').read()
        except OSError:
            continue
        if f'FM_SESSION={marker}'.encode() in env.split(b'\0'):
            try:
                os.kill(int(pid), signal.SIGKILL)
            except OSError:
                pass


class Result:
    def __init__(self, **kw):
        self.kind = 'error'  # done | timeout | limited | auth | error | stopped
        self.session_id = None
        self.reset_at = None
        self.elapsed = 0.0
        self.final_text = ''
        self.detail = ''
        self.__dict__.update(kw)

    def as_dict(self):
        return dict(self.__dict__)


class Agent:
    def __init__(self, role, round_dir, log, extra_ro=()):
        self.role = role  # dict(cli, model, effort)
        self.dir = Path(round_dir)
        self.ws = self.dir / 'workspace'
        self.home = self.dir / 'home'
        self.tmp = self.dir / 'tmp'
        self.tdir = self.dir / 'transcripts'
        for d in (self.home, self.tmp, self.tdir, self.home / '.codex', self.home / '.claude'):
            d.mkdir(parents=True, exist_ok=True)
        (self.home / '.gitconfig').write_text('[user]\n\tname = agent\n\temail = agent@localhost\n'
                                              '[init]\n\tdefaultBranch = main\n')
        self.log = log
        self.extra_ro = list(extra_ro)
        self.marker = f'{self.dir.parent.parent.name}-{self.dir.name}'

    def env(self):
        e = dict(PATH=f'{VENV}/bin:{HOME}/.local/bin:/usr/local/bin:/usr/bin:/bin',
                 HOME=str(self.home), TMPDIR=str(self.tmp), LANG='C.UTF-8', LC_ALL='C.UTF-8', TERM='dumb',
                 USER=os.environ.get('USER', 'agent'), SHELL='/bin/bash', VIRTUAL_ENV=str(VENV),
                 CODEX_HOME=str(self.home / '.codex'), CLAUDE_CONFIG_DIR=str(self.home / '.claude'),
                 XDG_CACHE_HOME=str(self.home / '.cache'), XDG_CONFIG_HOME=str(self.home / '.config'),
                 XDG_DATA_HOME=str(self.home / '.local-share'), MPLCONFIGDIR=str(self.tmp),
                 NUMBA_CACHE_DIR=str(self.tmp), FM_EVALQ=str(self.dir / 'evalq'), FM_SESSION=self.marker,
                 OMP_NUM_THREADS='4', OPENBLAS_NUM_THREADS='4', MKL_NUM_THREADS='4',
                 DISABLE_AUTOUPDATER='1', CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC='1',
                 CLAUDE_CODE_SUBAGENT_MODEL=self.role['model'] if self.role['cli'] == 'claude' else '',
                 IS_SANDBOX='1')
        return {k: v for k, v in e.items() if v != ''}

    def landlock(self):
        ro = CLI_RO + [str(VENV), str(TRAIN), str(FM / 'tests/fake_agent.py'), str(self.dir / 'evalq')] + self.extra_ro
        ro.extend(str(stage['file']) for stage in STAGES.values() if stage['role'] == 'train')
        rw = [str(self.ws), str(self.home), str(self.tmp), str(self.dir / 'evalq/req')]
        args = [PY, '-I', str(FM / 'fm/landlock.py'), '--scope-signals']
        for p in ro:
            args += ['--ro', p]
        for p in rw:
            args += ['--rw', p]
        return args + ['--']

    def command(self, prompt, resume_id=None):
        r = self.role
        if r['cli'] == 'fake':  # end-to-end harness test only (tests/fake_agent.py), never in a real config
            return [PY, '-I', str(FM / 'tests/fake_agent.py'), r['model'], prompt[:200]]
        if r['cli'] == 'claude':
            cmd = ['claude', '-p', prompt, '--model', r['model'], '--effort', r.get('effort', 'high'),
                   '--output-format', 'stream-json', '--verbose', '--dangerously-skip-permissions',
                   '--setting-sources', 'project', '--strict-mcp-config', '--disable-slash-commands']
            if resume_id:
                cmd += ['--resume', resume_id]
            return cmd
        common = ['--json', '-m', r['model'], '-c', f'model_reasoning_effort="{r.get("effort", "high")}"',
                  '--dangerously-bypass-approvals-and-sandbox', '--skip-git-repo-check', '--ignore-user-config',
                  '-c', 'web_search="live"']
        for f in CODEX_DISABLE:
            common += ['--disable', f]
        if resume_id:
            return ['codex', 'exec', *common, 'resume', resume_id, prompt]
        return ['codex', 'exec', *common, '-C', str(self.ws), prompt]

    def run(self, prompt, budget_s, label, resume_id=None, stop_event=None):
        """Run one CLI invocation until it exits or budget_s elapses. Never raises on agent failure."""
        idx = len(list(self.tdir.glob('*.jsonl'))) + 1
        base = self.tdir / f'{idx:02d}_{label}'
        (base.with_suffix('.prompt.md')).write_text(prompt)
        cmd = self.command(prompt, resume_id)
        write_json(base.with_suffix('.cmd.json'), dict(cmd=[c if c != prompt else '<prompt.md>' for c in cmd],
                                                       role=self.role, resume=resume_id, started=now(),
                                                       budget_s=round(budget_s)))
        sync_credentials(self.role['cli'], self.home)
        res = Result(session_id=resume_id)
        t0 = time.time()
        out = base.with_suffix('.jsonl')
        err = base.with_suffix('.stderr.log')
        with out.open('w') as fo, err.open('w') as fe:
            proc = subprocess.Popen(self.landlock() + cmd, cwd=self.ws, env=self.env(), stdout=subprocess.PIPE,
                                    stderr=fe, stdin=subprocess.DEVNULL, start_new_session=True, text=True,
                                    bufsize=1)
            stop_sync = threading.Event()

            def syncer():
                while not stop_sync.wait(60):
                    try:
                        sync_credentials(self.role['cli'], self.home)
                    except OSError:
                        pass

            last = dict(t=time.time())

            def watchdog():
                while proc.poll() is None:
                    if time.time() - last['t'] > STALL_S:
                        res.kind = 'stalled'
                    if time.time() - t0 > budget_s:
                        res.kind = 'timeout'
                    elif stop_event is not None and stop_event.is_set():
                        res.kind = 'stopped'
                    if res.kind in ('timeout', 'stopped', 'stalled'):
                        try:
                            os.killpg(proc.pid, signal.SIGTERM)
                            time.sleep(20)
                            os.killpg(proc.pid, signal.SIGKILL)
                        except OSError:
                            pass
                        return
                    time.sleep(5)

            threading.Thread(target=syncer, daemon=True).start()
            threading.Thread(target=watchdog, daemon=True).start()
            for line in proc.stdout:
                last['t'] = time.time()
                fo.write(line)
                fo.flush()
                self._parse(line, res)
            proc.wait()
            stop_sync.set()
        kill_marked(self.marker)
        sync_credentials(self.role['cli'], self.home)
        res.elapsed = time.time() - t0
        res.exit_code = proc.returncode
        if res.kind == 'stalled':
            res.kind, res.detail = 'error', f'no output for {STALL_S} s (not responding); killed'
        elif res.kind not in ('timeout', 'stopped'):
            tail = (out.read_text(errors='replace')[-6000:] + err.read_text(errors='replace')[-3000:])
            if res.kind == 'done' and proc.returncode == 0:
                pass
            elif res.reset_at or (LIMIT_PAT.search(tail) and not res.final_text):
                res.kind = 'limited'
                res.reset_at = res.reset_at or self._reset_from_text(tail)
            elif AUTH_PAT.search(tail):
                res.kind = 'auth'
            elif res.kind != 'done':
                res.kind = 'error'
            res.detail = tail[-1500:]
        self.log(f'agent {self.role["cli"]}:{self.role["model"]} {self.dir.name}/{base.name} kind={res.kind} '
                 f'exit={proc.returncode} {res.elapsed:.0f}s session={res.session_id}')
        write_json(base.with_suffix('.result.json'), dict(res.as_dict(), ended=now()))
        return res

    def _parse(self, line, res):
        try:
            ev = json.loads(line)
        except ValueError:
            return
        if not isinstance(ev, dict):
            return
        t = ev.get('type')
        if self.role['cli'] == 'fake':
            if t == 'done':
                res.kind = 'done'
            return
        if self.role['cli'] == 'claude':
            if ev.get('session_id'):
                res.session_id = ev['session_id']
            if t == 'rate_limit_event':
                info = ev.get('rate_limit_info') or {}
                if info.get('status') == 'rejected' and info.get('resetsAt'):
                    res.reset_at = float(info['resetsAt'])
            elif t == 'result':
                res.final_text = str(ev.get('result') or '')
                if ev.get('subtype') == 'success' and not ev.get('is_error'):
                    res.kind = 'done'
                    res.reset_at = None
        else:
            if t == 'thread.started' and ev.get('thread_id'):
                res.session_id = ev['thread_id']
            elif t == 'item.completed' and (ev.get('item') or {}).get('type') == 'agent_message':
                res.final_text = str(ev['item'].get('text') or '')
            elif t == 'turn.completed':
                res.kind = 'done'
            elif t == 'turn.failed':
                res.kind = 'error'
                msg = str((ev.get('error') or {}).get('message', ''))
                if LIMIT_PAT.search(msg):
                    res.reset_at = self._reset_from_text(msg)

    @staticmethod
    def _reset_from_text(text):
        """'try again at 4:40 AM' / 'resets in 2h 5m' -> epoch seconds; default 30 minutes."""
        m = re.search(r'try again at (\d{1,2}):(\d{2})\s*([AP]M)?', text, re.I)
        if m:
            h, mi = int(m.group(1)), int(m.group(2))
            if m.group(3):
                h = h % 12 + (12 if m.group(3).upper() == 'PM' else 0)
            t = time.localtime()
            cand = time.mktime((t.tm_year, t.tm_mon, t.tm_mday, h, mi, 0, 0, 0, -1)) + 60
            return cand if cand > time.time() else cand + 86400
        m = re.search(r'(?:in|after)\s+(?:(\d+)\s*d(?:ays?)?\s*)?(?:(\d+)\s*h(?:ours?)?\s*)?(?:(\d+)\s*m(?:in)?)?', text,
                      re.I)
        if m and any(m.groups()):
            d, h, mi = (int(x or 0) for x in m.groups())
            return time.time() + d * 86400 + h * 3600 + mi * 60 + 60
        return time.time() + 1800
