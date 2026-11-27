"""AgenticScientist orchestrator. Locked; no human steering during a run.

  .venv/bin/python agentic_scientist/orchestrator.py --lock agentic_scientist/locks/<lock>.json --run-name NAME

Workers run IDEATE -> IMPLEMENT -> EVALUATE(dev, fleet) -> [DEBUG] -> ACCEPT? -> DISTILL cycles.
Final pick = one qualified program per board, composed on top of the seed.
Resumable: every step leaves a marker file in its cycle directory.
"""
import argparse
import fcntl
import hashlib
import json
import math
import os
import shutil
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from string import Template

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from agentic_scientist import fleet  # noqa: E402
from agentic_scientist.artifacts import digest, file_sha, read_cached, run_config, workspace_manifest, write_json, write_text  # noqa: E402
from agentic_scientist.knowledge import SECTIONS, Bank, classify, line, signature  # noqa: E402

MG = ROOT / 'agentic_scientist'
PY = str(ROOT / '.venv/bin/python')
LIT_MCP = dict(command=PY, args=['-I', str(ROOT / 'agentic_scientist/tools/lit_mcp.py')])  # literature MCP for every agent
BOARDS_ALL = ('temporal', 'heart', 'embryo', 'perturbation')
LOCK = threading.RLock()
# Quota detection in the tail of a failed transcript (any CLI). HARD keys mark the CLI limited at once.
LIMIT_KEYS = ('rate limit', 'rate_limit', 'usage limit', 'quota', '429', 'overloaded', 'try again at', 'too many requests',
              'resource_exhausted', 'resource exhausted', 'insufficient credit', 'out of credits', 'credit balance',
              'exceeded your')
HARD_LIMIT_KEYS = ('usage limit', 'resource_exhausted', 'resource exhausted', 'insufficient credit', 'out of credits',
                   'credit balance', 'exceeded your')
PREMIUM_CLIS = ('codex', 'claude', 'agy')


def now():
    return time.strftime('%F %T')


def harness_splits():
    from shinka_ve import harness
    return harness.SPLITS


class Run:
    def __init__(self, lock_path, name, config=None, final_only=False):
        self.final_only = final_only
        self.lock = json.loads(Path(lock_path).read_text())
        self.eval_revision = digest(self.lock)
        self.verify_lock()
        if 'evaluator' in self.lock:
            from agentic_scientist.preflight import fingerprint, versions

            if fingerprint() != self.lock['evaluator'] or versions(('optuna', 'torch')) != self.lock['tuner']:
                raise SystemExit('Lock violation: evaluator inputs, vendor code, or runtime versions changed')
        self.dir = MG / 'runs' / f"{self.lock['lock_id']}_{name}"
        self.dir.mkdir(parents=True, exist_ok=True)
        self.state_path = self.dir / 'state.json'
        fd = os.open(self.dir, os.O_RDONLY)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            state = json.loads(self.state_path.read_text()) if self.state_path.exists() else None
            if final_only and state is None:
                raise SystemExit('finalization requires an existing run')
            binding, self.cfg = run_config(ROOT, self.lock, config, state)
            if state is None:
                state = dict(calls=0, cost_usd=0.0, impl_stats={}, global_best=None, stale=0,
                             accepted=[], workers={}, effective_config=binding)
                write_json(self.state_path, state)
            self.state = state
        finally:
            os.close(fd)
        self.notebook = self.dir / 'notebook.md'
        if not self.notebook.exists():
            self.notebook.write_text('# Lab notebook (raw log; the curated synthesis is knowledge/knowledge.md)\n')
        self.bank = Bank(self.dir)
        self.curate_lock = threading.Lock()
        self.pair_locks = {}
        self.stop = False

    # ---------- bookkeeping ----------
    def verify_lock(self):
        for f, h in self.lock['files'].items():
            if file_sha(ROOT / f) != h:
                raise SystemExit(f'Lock violation: {f} changed since {self.lock["lock_id"]}')

    def save(self):
        with LOCK:
            write_json(self.state_path, self.state)

    def log(self, msg):
        with LOCK, (self.dir / 'run.log').open('a') as f:
            f.write(f'{now()} {msg}\n')
        print(f'{now()} {msg}', flush=True)

    # ---------- agents ----------
    PROVIDER_SEMS = {}

    def provider_slot(self, cli):
        """At most cfg['provider_concurrency'][cli] simultaneous sessions per CLI (quota pacing)."""
        cap = (self.cfg.get('provider_concurrency') or {}).get(cli)
        if not cap:
            return threading.Semaphore(1000)
        with LOCK:
            return self.PROVIDER_SEMS.setdefault(cli, threading.BoundedSemaphore(int(cap)))

    def log_call(self, rec):
        with LOCK, (self.dir / 'agent_calls.jsonl').open('a') as f:
            f.write(json.dumps(rec, default=str) + '\n')

    def session_dir(self, transcript, attempt):
        """Sandbox session homes live outside the run directory (credentials are never packaged)."""
        base = Path(self.cfg.get('session_root', '/scratch/user/as_sessions')) / self.dir.name
        rel = Path(transcript).resolve().relative_to(self.dir.resolve())
        return base / rel.parent / f'{rel.name}.{attempt}'

    def agent(self, role, prompt, cwd, transcript, allowed=None, add_dirs=(), fresh_output=None):
        """Run a headless agent CLI in the Landlock sandbox. Retries with backoff; when a CLI is usage-limited the call
        goes to another role with quota (ideation: the other premium researcher, then the overflow model)."""
        role = dict(role)
        orig = dict(role)
        intended = self.key(role)
        transcript = Path(transcript)
        prior = list(transcript.parent.glob(f'{transcript.name}.*.jsonl'))
        offset = max((int(p.name.split('.')[-2]) for p in prior), default=-1) + 1
        ideation = transcript.name in ('ideate', 'ideate_r', 'ideate_rescue')
        env = dict(os.environ, MG_RUN=str(self.dir), MG_ROOT=str(ROOT))
        if self.cfg.get('scope_quick_eval') and transcript.parent.parent == self.dir / 'cycles':
            worker = transcript.parent.name.split('_c', 1)[0]
            if worker in self.state['workers']:
                env['MG_QUICK_BOARD'] = self.home_board(worker)
        for attempt in range(6):
            fleet.remaining(self.research_deadline(), 1)
            if self.unavailable(role['cli']):
                role = self.unlimited_role(orig, ideation)
            if transcript.name == 'ideate':  # slower researchers keep their longer limit when standing in for another
                role['timeout_s'] = max(role['timeout_s'], self.research_timeout(role))
            with LOCK:
                if self.state['calls'] >= self.cfg['max_agent_calls']:
                    raise RuntimeError('agent call budget exhausted')
                self.state['calls'] += 1
                self.save()
            if role['cli'] == 'claude':
                cmd = ['claude', '-p', prompt, '--model', role['model'], '--output-format', 'stream-json', '--verbose',
                       '--dangerously-skip-permissions', '--strict-mcp-config',  # inside the Landlock sandbox
                       '--setting-sources', 'project', '--disable-slash-commands',
                       '--mcp-config', json.dumps({'mcpServers': {'lit': LIT_MCP}})]  # only our literature server
                if 'effort' in role:
                    cmd += ['--effort', role['effort']]
                if allowed:
                    cmd += ['--allowedTools', *allowed, 'mcp__lit']
                for d in add_dirs:
                    cmd += ['--add-dir', str(d)]
            elif role['cli'] == 'opencode':
                # OpenCode Go models; inside the Landlock sandbox; lit MCP from the repo-root opencode.json
                cmd = ['opencode', 'run', '--model', role['model'], '--format', 'json', '--auto', '--archived',
                       '--title', Path(transcript).name, prompt]
            elif role['cli'] == 'agy':
                # Antigravity CLI (Opus 4.6); inside the Landlock sandbox with an isolated HOME (no operator hooks/MCP)
                cmd = ['agy', '-p', prompt, '--model', role['model'], '--output-format', 'stream-json',
                       '--dangerously-skip-permissions', '--disable-slash-commands']
                if 'effort' in role:
                    cmd += ['--effort', role['effort']]
                for d in add_dirs:
                    cmd += ['--add-dir', str(d)]
            elif role['cli'] == 'commandcode':
                # Command Code; inside the Landlock sandbox with an isolated HOME; built-in mods only, no skills
                cmd = ['cmd', '-p', prompt, '-m', role['model'], '--output-format', 'json', '--yolo', '-t',
                       '--skip-onboarding', '--no-auto-update', '--no-session', '--safe-mode', '--no-skills',
                       '--config', 'artifacts=false', '--config', 'taste-learning=false',  # no publishing, no code upload
                       '--max-turns', str(role.get('max_turns', 300))]
                if 'effort' in role:
                    cmd += ['--effort', role['effort']]
                for d in add_dirs:
                    cmd += ['--add-dir', str(d)]
            elif role['cli'] == 'fake':  # harness smoke test only (tools/fake_agent.py), never in a real config
                cmd = [PY, '-I', str(MG / 'tools/fake_agent.py'), str(cwd), str(transcript.name)]
                env['FAKE_PROMPT'] = prompt[:20000]
            else:
                cmd = ['codex', 'exec', '-C', str(cwd), '-m', role['model'], '-c',
                       f'model_reasoning_effort="{role.get("effort", "high")}"', '--dangerously-bypass-approvals-and-sandbox',  # inside the Landlock sandbox
                       '--skip-git-repo-check', '--json', '-c', 'web_search="live"', '--ignore-user-config',
                       *[x for f in ('apps', 'plugins', 'browser_use', 'computer_use', 'in_app_browser', 'memories')
                         for x in ('--disable', f)],
                       '-c', f'mcp_servers.lit.command={json.dumps(LIT_MCP["command"])}',
                       '-c', f'mcp_servers.lit.args={json.dumps(LIT_MCP["args"])}']
                for d in add_dirs:
                    cmd += ['--add-dir', str(d)]
                cmd.append(prompt)
            tpath = Path(f'{transcript}.{offset + attempt}.jsonl')
            write_json(tpath.with_suffix('.prompt.json'), dict(role=role, intended=intended, prompt=prompt))
            if fresh_output is not None:
                fresh_output.unlink(missing_ok=True)
            t0 = time.time()
            sandboxed = self.cfg.get('sandbox', True)
            from agentic_scientist.sandbox import Session
            sess = Session(role['cli'], self.session_dir(tpath.with_suffix(''), attempt), cwd, self.dir,
                           extra_rw=[Path(cwd), transcript.parent] + ([Path(fresh_output).parent] if fresh_output is not None else []))
            run_env = sess.env(env) if sandboxed else env
            full = (sess.prefix() + cmd) if sandboxed else cmd
            slot = self.provider_slot(role['cli'])
            waited = time.time()
            with slot:
                waited = time.time() - waited
                t0 = time.time()
                try:
                    with sess, tpath.open('w') as out:
                        proc = subprocess.run(full, cwd=cwd, stdout=out, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                              env=run_env, timeout=fleet.remaining(self.research_deadline(), role['timeout_s']))
                    code = proc.returncode
                except subprocess.TimeoutExpired:
                    code = 'timeout'
            text = tpath.read_text(errors='replace')
            if code == 0 and (bad := self.result_failure(text)):
                code = bad
            self._cost(text)
            if role['cli'] == 'claude':
                self._claude_budget(text)
            low = text[-5000:].lower()
            limited = code != 0 and any(k in low for k in LIMIT_KEYS)
            self.log_call(dict(t=t0, seconds=round(time.time() - t0, 1), queue_s=round(waited, 1),
                               cycle=transcript.parent.name, label=transcript.name, attempt=offset + attempt,
                               cli=role['cli'], model=role['model'], role=self.key(role), intended=intended,
                               substitute=self.key(role) != intended, exit=code, limited=limited,
                               transcript=str(tpath.relative_to(self.dir)) if tpath.is_relative_to(self.dir) else str(tpath)))
            self.log(f'agent {role["cli"]} {transcript.name} exit={code} {time.time() - t0:.0f}s model={role["model"]}')
            if code == 'timeout':
                fleet.remaining(self.research_deadline(), 1)
            if code == 0:
                return tpath
            low = text[-5000:].lower()
            if limited:
                if any(k in low for k in HARD_LIMIT_KEYS) or attempt >= 1:  # a quota window or a repeat limit
                    self.mark_limited(role['cli'], text[-5000:])
                    role = self.unlimited_role(orig, ideation)
                else:
                    time.sleep(fleet.remaining(self.research_deadline(), 120))
                continue
            if code == 'timeout':
                return tpath if fresh_output is None else None  # partial work may still be usable; evaluation decides
            time.sleep(fleet.remaining(self.research_deadline(), 30))
        return None

    def limited(self, cli):
        return self.state.get('limited_until', {}).get(cli, 0) > time.time()

    def mark_limited(self, cli, tail, until=None):
        """Remember a CLI's quota window: Claude's rate_limit_event resetsAt, codex's 'try again at 4:40 AM',
        otherwise 30 minutes."""
        import re
        if until is None:
            until = time.time() + 1800
            m = re.search(r'try again at (\d{1,2}):(\d{2})\s*([AP]M)?', tail, re.I)
            if m:
                h, mi = int(m.group(1)), int(m.group(2))
                if m.group(3):
                    h = h % 12 + (12 if m.group(3).upper() == 'PM' else 0)
                t = time.localtime()
                cand = time.mktime((t.tm_year, t.tm_mon, t.tm_mday, h, mi, 0, 0, 0, -1)) + 60
                until = cand if cand > time.time() else cand + 86400
        with LOCK:
            old = self.state.setdefault('limited_until', {}).get(cli, 0)
            self.state['limited_until'][cli] = max(old, until)
            self.save()
        if until > old:
            self.log(f'{cli} usage-limited until {time.strftime("%a %H:%M", time.localtime(until))}')

    @staticmethod
    def at(value):
        """Epoch seconds of an ISO-8601 time with offset (config deadlines), or None."""
        if not value:
            return None
        from datetime import datetime
        return datetime.fromisoformat(value).timestamp()

    def research_deadline(self):
        """Research ends at the earlier of start + max_research_seconds and cfg['research_kill_at'] (absolute):
        every agent call and evaluation is bounded by it, so in-flight cycles are cut there."""
        if getattr(self, 'final_only', False):
            return None
        cands = []
        start = self.state.get('research_started')
        limit = self.cfg.get('max_research_seconds')
        if start is not None and limit is not None:
            cands.append(start + limit)
        if self.at(self.cfg.get('research_kill_at')):
            cands.append(self.at(self.cfg['research_kill_at']))
        return min(cands) if cands else None

    def evaluate(self, ws, set_name, out, pred_seed=None, fit_seed=0, splits=None):
        # fleet_research: agents' dev/sanity/tuning evaluations use the fleet; finalization (private data) stays local.
        if set_name != 'composition' and (not self.cfg.get('local_evaluation_only')
                                          or (self.cfg.get('fleet_research') and not self.final_only)):
            return fleet.evaluate(ws, set_name, out, pred_seed, fit_seed, splits,
                                  deadline=self.research_deadline())
        cmd = [PY, '-I', str(MG / 'evaluate.py'), '--workspace', str(ws), '--set', set_name,
               '--out', str(out), '--workers', '1', '--fit-seed', str(fit_seed)]
        if pred_seed is not None:
            cmd.extend(['--pred-seed', str(pred_seed)])
        if splits:
            cmd.extend(['--splits', ','.join(splits)])
        if set_name == 'composition' and self.cfg.get('scope_quick_eval'):
            cmd.append('--verdict-only')
        with fleet.reserve('local evaluator', self.research_deadline()):
            out.unlink(missing_ok=True)
            subprocess.run(cmd, env=dict(os.environ, OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1'),
                           stdout=subprocess.DEVNULL, check=True,
                           timeout=fleet.remaining(self.research_deadline(), 1800))
        return json.loads(out.read_text())

    def unavailable(self, cli):
        return self.limited(cli) or (cli == 'claude' and bool(self.state.get('claude_off')))

    def fallback_chain(self, role, ideation):
        """Roles that stand in for `role` while its CLI is out of quota, in order. Premium roles (codex/claude/agy):
        cfg['quota_fallback'] (agy Opus 4.6, then OpenCode DeepSeek, then Command Code DeepSeek), then for ideation the
        other researcher of the schedule. Cheap roles: cfg['cheap_fallback']. Legacy cfg['overflow'] last."""
        premium = role['cli'] in PREMIUM_CLIS
        chain = list(self.cfg.get('quota_fallback' if premium else 'cheap_fallback') or [])
        if ideation:
            chain += list(self.cfg.get('ideator_cycle') or [])
        if self.cfg.get('overflow'):
            chain.append(self.cfg['overflow'])
        seen, out = {self.key(role)}, []
        for r in chain:
            if self.key(r) not in seen:
                seen.add(self.key(r))
                out.append(r)
        return out

    def unlimited_role(self, role, ideation):
        """The intended role if its CLI has quota, else the first role of its fallback chain that has quota.
        When none has quota the worker pauses until the earliest reset (bounded by the research deadline)."""
        pool = [role] + self.fallback_chain(role, ideation)
        while True:
            fleet.remaining(self.research_deadline(), 1)
            for r in pool:
                if not self.unavailable(r['cli']):
                    if self.key(r) != self.key(role):
                        self.log(f'quota fallback: {self.key(role)} unavailable, using {self.key(r)}')
                    return dict(r, timeout_s=role['timeout_s'])
            lim = self.state.get('limited_until', {})
            wakes = [lim[r['cli']] for r in pool if r['cli'] in lim]
            wake = min(wakes) if wakes else time.time() + 1800
            if (deadline := self.research_deadline()) is not None:
                wake = min(wake, deadline)
            self.log(f'paused: no quota for {sorted({r["cli"] for r in pool})} until '
                     f'{time.strftime("%a %H:%M", time.localtime(wake))}')
            with LOCK:
                self.state['paused_until'] = wake
                self.save()
            t0 = time.time()
            while time.time() < wake and not self.stop:
                time.sleep(min(60, max(0, wake - time.time())))
            with LOCK:
                self.state['paused_s'] = self.state.get('paused_s', 0) + (time.time() - t0) / max(1, self.cfg['workers'])
                self.state.pop('paused_until', None)
                self.save()
            if self.stop:
                return role

    def _claude_budget(self, text):
        """The Claude ideator shares the operator's subscription. Once its 7-day utilization reaches
        cfg['claude_max_week_util'], every later Claude role call goes to cfg['claude_fallback'] for the rest of the run."""
        util = None
        for line in text.splitlines():
            if '"rate_limit_event"' not in line:
                continue
            try:
                info = json.loads(line).get('rate_limit_info') or {}
            except ValueError:
                continue
            if info.get('status') == 'rejected' and info.get('resetsAt'):
                self.mark_limited('claude', '', until=float(info['resetsAt']))
            u = ((info.get('unifiedWindows') or {}).get('seven_day') or {}).get('utilization')
            if u is None and info.get('rateLimitType') == 'seven_day':
                u = info.get('utilization')
            if isinstance(u, (int, float)):
                util = u
        if util is None:
            return
        with LOCK:
            self.state['claude_week_util'] = util
            if util >= self.cfg.get('claude_max_week_util', 0.92) and not self.state.get('claude_off'):
                self.state['claude_off'] = True
                self.log(f'claude 7-day utilization {util:.2f} >= cap; Claude roles now use the quota fallback chain')

    @staticmethod
    def result_failure(text):
        """agy / commandcode report some failures in the result event with exit code 0."""
        for line in reversed(text.splitlines()[-50:]):
            try:
                ev = json.loads(line)
            except ValueError:
                continue
            if not isinstance(ev, dict):
                continue
            if ev.get('event') == 'result' and isinstance(ev.get('result'), dict):
                st = str(ev['result'].get('status', 'SUCCESS'))
                return None if st == 'SUCCESS' else f'agy-{st.lower()}'
            if ev.get('type') == 'result' and 'finalText' in ev:
                st = str(ev.get('subtype', 'success'))
                return None if st == 'success' else f'cc-{st}'
        return None

    @staticmethod
    def final_text(tpath):
        """Last assistant text from a claude / codex / opencode JSON transcript."""
        out = ''
        if not tpath:
            return out
        for line in Path(tpath).read_text(errors='replace').splitlines():
            try:
                ev = json.loads(line)
            except ValueError:
                continue
            if not isinstance(ev, dict):
                continue
            if ev.get('type') == 'result' and isinstance(ev.get('result'), str):
                out = ev['result']
            if ev.get('type') == 'result' and isinstance(ev.get('finalText'), str):  # commandcode
                out = ev['finalText']
            if ev.get('event') == 'result' and isinstance(ev.get('result'), dict):  # agy
                out = ev['result'].get('response') or out
            item = ev.get('item') or {}
            if ev.get('type') == 'item.completed' and item.get('type') == 'agent_message':
                out = item.get('text', '')
            part = ev.get('part') or {}
            if part.get('type') == 'text' and part.get('text'):
                out = part['text']
        return out

    @staticmethod
    def parse_json(text):
        import re
        m = re.search(r'```(?:json)?\s*(\{.*\})\s*```', text, re.S) or re.search(r'(\{.*\})', text, re.S)
        try:
            return json.loads(m.group(1)) if m else None
        except ValueError:
            return None

    @staticmethod
    def code(ws, limit=40000):
        parts = []
        for f in sorted(Path(ws).rglob('*.py')):
            if '__pycache__' not in f.parts:
                parts.append(f'### {f.relative_to(ws)}\n{f.read_text(errors="replace")}')
        return '\n\n'.join(parts)[:limit]

    @staticmethod
    def diff(a, b, limit=30000):
        import difflib
        out = []
        names = {p.relative_to(a) for p in Path(a).rglob('*.py')} | {p.relative_to(b) for p in Path(b).rglob('*.py')}
        for n in sorted(names):
            if '__pycache__' in n.parts:
                continue
            x = (Path(a) / n).read_text().splitlines() if (Path(a) / n).exists() else []
            y = (Path(b) / n).read_text().splitlines() if (Path(b) / n).exists() else []
            out += difflib.unified_diff(x, y, f'parent/{n}', f'candidate/{n}', lineterm='', n=3)
        return '\n'.join(out)[:limit]

    def _cost(self, text):
        for line in text.splitlines()[-5:]:
            try:
                ev = json.loads(line)
            except ValueError:
                continue
            if isinstance(ev, dict) and ev.get('type') == 'result' and 'total_cost_usd' in ev:
                with LOCK:
                    self.state['cost_usd'] += float(ev['total_cost_usd'])

    def audit(self, cycle_dir):
        """Held-out data is encrypted and absent during research, so mentions in transcripts cannot leak anything:
        they are logged as warnings (audit_warnings.txt). Only program code that references held-out files
        disqualifies (it would try to read them at evaluation time)."""
        bad = [s.lower() for s in self.cfg['holdout_forbidden']]
        warns, hits = [], []

        def walk(x):
            if isinstance(x, dict):
                for k, v in x.items():
                    if k in ('input', 'command', 'arguments') and any(b in json.dumps(v).lower() for b in bad):
                        warns.append(json.dumps(v)[:300])
                    walk(v)
            elif isinstance(x, list):
                for v in x:
                    walk(v)
        for t in Path(cycle_dir).glob('*.jsonl'):
            for line in t.read_text(errors='replace').splitlines():
                try:
                    walk(json.loads(line))
                except ValueError:
                    pass
        for f in Path(cycle_dir, 'ws').rglob('*.py'):
            src = f.read_text(errors='replace').lower()
            if any(b in src for b in bad if '/' in b or b.endswith(('.h5ad', '_ko')) or 'holdout' in b):
                hits.append(f'program file {f.name} references a held-out data file')
        if warns:
            Path(cycle_dir, 'audit_warnings.txt').write_text('\n'.join(warns) + '\n')
            self.log(f'{Path(cycle_dir).name} audit: {len(warns)} transcript mentions of held-out names (warning only; holdout files Landlock-protected)')
        return hits

    # ---------- evaluation helpers ----------
    @staticmethod
    def describe(ev):
        if not ev or not ev.get('correct'):
            return f"INVALID: {(ev or {}).get('error')}"
        lines = [f"proxy {ev['proxy']:.2f} | " + ', '.join(f'{b} {s:.2f}' for b, s in sorted(ev['boards'].items()))]
        for name, r in ev['splits'].items():
            if r.get('board') == 'temporal' or name.startswith('temporal_'):
                lines.append(f"  {name}: {r.get('score', 0):.2f}")
                continue
            worst = sorted(r.get('metrics', {}).items(), key=lambda kv: kv[1])[:5]
            lines.append(f"  {name}: {r.get('score', 0):.2f}; weakest " + ', '.join(f'{k}={v:.1f}' for k, v in worst))
        return '\n'.join(lines)

    # ---------- noise control: paired, repeated evaluation with racing ----------
    SEED_PAIRS = [(101, 0), (202, 1), (303, 2), (404, 3), (505, 4), (606, 5), (707, 6), (808, 7), (909, 8)]

    def evaluation_key(self, ws, set_name, pair=None, splits=None):
        return digest([self.eval_revision, workspace_manifest(ws), set_name, pair, splits])

    def evaluate_cached(self, ws, set_name, out, pair=None, splits=None):
        key = self.evaluation_key(ws, set_name, pair, splits)
        cached = read_cached(out, key)
        if cached is not None:
            return cached
        args = () if pair is None else pair
        ev = self.evaluate(Path(ws), set_name, out, *args, splits=splits)
        write_json(out, dict(ev, cache_key=key))
        return ev

    def pair_key(self, manifest, board, j):
        files = {n: v for n, v in manifest.items() if self.board_of(n) in (board, None)}
        return digest([self.eval_revision, files, 'dev', board, self.SEED_PAIRS[j]])

    def pair_evals(self, ws, first_eval, n, boards=None):
        """Dev evaluations of `ws` under the first n (prediction, fit) seed pairs, all launched at once on the fleet;
        pair 0 = `first_eval`. Per task: only the splits of `boards` (default: every board) are evaluated, and each
        (pair, board) result is cached next to the workspace (`pair<j>_<board>.json`), so a parent is evaluated once
        per pair and board and reused by every child. Boards not requested keep their pair-0 results (their files are
        identical between a candidate and its parent, so their paired difference is exactly zero)."""
        cache = Path(str(ws) + '_evals')
        cache.mkdir(exist_ok=True)
        boards = sorted(b for b in (boards or self.BOARDS) if self.board_splits('dev', [b]))
        path = lambda j, b: cache / f'pair{j}_{b}.json'  # noqa: E731
        manifest = workspace_manifest(ws)

        def load(j, b):
            return read_cached(path(j, b), self.pair_key(manifest, b, j))

        def run(j):
            with LOCK:
                slot = self.pair_locks.setdefault((cache.resolve(), j), threading.Lock())
            with slot:
                return score(j)

        def score(j):
            miss = [b for b in boards if load(j, b) is None]
            if miss:
                sub = self.evaluate(Path(ws), 'dev', cache / f"pair{j}_eval_{'-'.join(miss)}.json", *self.SEED_PAIRS[j],
                                     splits=self.board_splits('dev', miss))
                if not sub.get('correct'):
                    return sub
                for b in miss:
                    part = dict(correct=True, boards={b: sub['boards'][b]}, board_se={b: (sub.get('board_se') or {}).get(b)},
                                splits={k: r for k, r in sub['splits'].items() if r.get('board') == b},
                                cache_key=self.pair_key(manifest, b, j))
                    write_json(path(j, b), part)
            parts = [load(j, b) for b in boards]
            return self.splice(first_eval, dict(correct=True, splits={k: r for e in parts for k, r in e['splits'].items()}))

        out = [first_eval] + [None] * (n - 1)
        if n > 1:
            with ThreadPoolExecutor(n - 1) as pool:
                out[1:] = list(pool.map(run, range(1, n)))
        return out

    def prefetch_parent(self, ws, ev, boards=None):
        """Evaluate a newly accepted program on all seed pairs in the background (only the boards its children will
        change, i.e. the owning worker's) so its children race fast."""
        n = 1 + max(self.cfg['acceptance']['batches'])
        threading.Thread(target=self.pair_evals, args=(ws, ev, n, boards), daemon=True).start()

    @classmethod
    def board_of(cls, name):
        return next((b for b in cls.BOARDS if name == f'{b}.py' or name.startswith(f'{b}_')), None)

    @staticmethod
    def board_files(ws, b):
        """Every file a board owns: <b>.py and <b>_* of any type (code, <b>_knobs.json, <b>_tuned.json, data)."""
        return sorted(q for q in Path(ws).iterdir() if q.is_file() and (q.name == f'{b}.py' or q.name.startswith(f'{b}_')))

    @classmethod
    def copy_board(cls, src_ws, dst_ws, b):
        """Replace dst's files of board b with src's (used by every composition)."""
        for q in cls.board_files(dst_ws, b):
            q.unlink()
        for q in cls.board_files(src_ws, b):
            shutil.copy(q, Path(dst_ws) / q.name)

    def diff_boards(self, a_ws, b_ws):
        """Boards whose files differ between two workspaces; None if not both per-board layouts or if program.py or a
        file owned by no board differs (then nothing can be scoped)."""
        if not (self.forked(a_ws) and self.forked(b_ws)):
            return None
        a, b = workspace_manifest(a_ws), workspace_manifest(b_ws)
        out = set()
        for n in a.keys() | b.keys():
            if a.get(n) == b.get(n):
                continue
            owner = self.board_of(n) if '/' not in n else None
            if owner is None:
                return None
            out.add(owner)
        return out

    @staticmethod
    def board_splits(set_name, boards):
        from agentic_scientist.evaluate import SETS, harness as H
        return [s for s in SETS[set_name]['splits'] if H.SPLITS[s]['board'] in set(boards)]

    def eval_scoped(self, ws, parent, out):
        """Pair-0 dev evaluation of a candidate on the boards it changed only. The scope rule keeps every other board's
        files byte-identical to the parent's, so their results are the parent's (spliced in). Falls back to the full
        dev set when scoping is impossible (unforked layout, program.py/unowned file changed, parent eval invalid)."""
        par0 = parent['eval']
        boards = self.diff_boards(parent['ws'], ws) if self.cfg.get('scoped_eval', True) else None
        if boards is None or not par0.get('correct'):
            return self.evaluate_cached(ws, 'dev', out)
        if not boards:  # nothing changed: identical to the parent (the race reports "no effect")
            ev = dict(par0, scoped=[])
        else:
            sub = self.evaluate_cached(ws, 'dev', out.with_name(out.stem + '_sub.json'), splits=self.board_splits('dev', boards))
            ev = self.splice(par0, sub)
            if ev.get('correct'):
                ev = dict(ev, error=None, set='dev', scoped=sorted(boards))
        write_json(out, ev)
        return ev

    def inherit_pairs(self, src_ws, dst_ws):
        """Copy src's cached per-board seed-pair results for every board whose files dst shares with src."""
        different = self.diff_boards(src_ws, dst_ws)
        if different is None:
            return
        same = set(self.BOARDS) - different
        sc, dc = Path(str(src_ws) + '_evals'), Path(str(dst_ws) + '_evals')
        dc.mkdir(exist_ok=True)
        for b in same:
            for f in sc.glob(f'pair[0-9]_{b}.json'):
                if not (dc / f.name).exists():
                    shutil.copy(f, dc / f.name)

    @staticmethod
    def changed_splits(cand, par, tol=1e-9):
        cs, ps = cand.get('splits') or {}, par.get('splits') or {}
        return [s for s in cs if abs(cs[s].get('score', 0) - ps.get(s, {}).get('score', 0)) > tol
                or cs[s].get('seed_scores') != ps.get(s, {}).get('seed_scores')]

    @staticmethod
    def splice(par_ev, sub_ev):
        """Full-set evaluation = parent's evaluation with the re-evaluated (changed) splits replaced."""
        from agentic_scientist.evaluate import aggregate
        if not sub_ev.get('correct'):
            return sub_ev
        splits = {**par_ev['splits'], **sub_ev['splits']}
        return dict(aggregate(splits), correct=True, splits=splits)

    @classmethod
    def screen_stats(cls, cand, parent, alpha):
        """Pair the scoring draws in locked dev-seed order before estimating uncertainty."""
        from agentic_scientist.evaluate import SETS, aggregate
        changed = cls.changed_splits(cand, parent)
        zero = {s: dict(board=row['board'], score=0.) for s, row in parent['splits'].items()}
        draws = []
        n = len(SETS['dev']['scoring_seeds'])
        for i in range(n):
            delta = dict(zero)
            for s in changed:
                c = cand['splits'][s].get('seed_scores') or []
                p = parent['splits'][s].get('seed_scores') or []
                if len(c) != n or len(p) != n:
                    return None  # insufficient matched draws: proceed to fresh confirmation pairs
                delta[s] = dict(zero[s], score=c[i] - p[i])
            draws.append(aggregate(delta))
        return cls.paired_stats(draws, [aggregate(zero)] * n, alpha)

    @staticmethod
    def paired_stats(cand, par, alpha):
        """Mean paired difference, one-sided (1 - alpha) bounds, for the proxy and each board."""
        from scipy.stats import t as tdist
        keys = ['proxy'] + sorted(par[0]['boards'])
        get = lambda e, k: e['proxy'] if k == 'proxy' else e['boards'].get(k, 0.0)  # noqa: E731
        st = {}
        for k in keys:
            d = [get(c, k) - get(p, k) for c, p in zip(cand, par)]
            n = len(d)
            mean = sum(d) / n
            if n > 1:
                sd = (sum((x - mean) ** 2 for x in d) / (n - 1)) ** .5
                se = sd / n ** .5
                q = float(tdist.ppf(1 - alpha, n - 1))
            else:  # single pair: fall back to scoring-seed noise of both evaluations
                bse = lambda e: (e.get('proxy_se') if k == 'proxy' else (e.get('board_se') or {}).get(k)) or .3  # noqa: E731
                se, q = (bse(cand[0]) ** 2 + bse(par[0]) ** 2) ** .5, 1.645
            st[k] = dict(n=n, mean=mean, se=se, lb=mean - q * se, ub=mean + q * se, z=mean / max(se, 1e-9), diffs=d)
        return st

    def race(self, ws, ev, parent):
        """Accept / reject a candidate against its parent with a paired, repeated test (racing).

        1. Screen on pair 0. Invalid -> reject. Clear loss (z <= reject_z) -> reject without more compute.
        2. Otherwise evaluate both on more (prediction, fit) seed pairs, in batches, and stop as soon as the
           decision is clear. Paired differences cancel the noise both share.
        3. Accept if the proxy's lower bound > margin and no board drops significantly, OR a board improves
           significantly (lower bound > 0) while the proxy's mean gain is >= 0 and no board drops significantly.
        """
        A = self.cfg['acceptance']
        if not ev.get('correct'):
            return False, 'invalid', None
        par0 = parent['eval']
        st = self.screen_stats(ev, par0, A['alpha'])
        if st and st['proxy']['z'] <= A['reject_z']:
            return False, f"clear loss on screen: Δ{st['proxy']['mean']:+.2f} (z {st['proxy']['z']:+.1f})", st
        changed = self.changed_splits(ev, par0)
        if not changed:
            return False, 'no effect: every dev split scores exactly as the parent', st
        diff = self.diff_boards(parent['ws'], ws)
        cb = sorted(diff) if diff else None  # evaluate every board if scoping is impossible
        cand, par = [ev], [par0]
        for n in A['batches']:  # all pairs of a batch, candidate and parent, run concurrently
            with ThreadPoolExecutor(2) as pool:
                fp = pool.submit(self.pair_evals, parent['ws'], par0, n + 1, cb)
                fc = pool.submit(self.pair_evals, ws, ev, n + 1, cb)
                par, cand = fp.result()[1:], fc.result()[1:]
            if not all(p.get('correct') for p in par):
                return False, 'parent failed a seed pair (cannot compare)', st
            bad = [c for c in cand if not c.get('correct')]
            if bad:
                return False, f"crashes under another seed: {str(bad[0].get('error'))[:200]}", st
            st = self.paired_stats(cand, par, A['alpha'])
            decision = self.decide(st, A)
            if decision[0] is not None:
                return self.condition_rules(decision, cand, par, changed, st)
        ok, why = self.decide(st, A, final=True)
        return self.condition_rules((ok, why), cand, par, changed, st)

    def condition_rules(self, decision, cand, par, changed, st):
        """Guard gains against meaningful regressions on a stage, gene, or assay."""
        from agentic_scientist.evaluate import HEART_TARGETS
        ok, why = decision
        if not ok:
            return ok, why, st
        groups = dict(HEART_TARGETS)
        groups.update(gata4=['gata4_1', 'gata4_2'], mab21l2=['mab21l2_e95'],
                      hand2=['hand2_e825', 'hand2_e925'], mef2c=['mef2c_e90', 'mef2c_e85'],
                      embryo_e725=['embryo_early'], embryo_e80=['guard_embryo_e80'])
        from agentic_scientist.evaluate import harness as H
        touched = {H.SPLITS[s]['board'] for s in changed}
        floor = self.cfg.get('group_floor')
        for name, splits in groups.items():
            if not {H.SPLITS[s]['board'] for s in splits} & touched:
                continue
            def group_score(ev):
                return sum(ev['splits'][s]['score'] for s in splits) / len(splits)
            result = self.paired_stats([dict(proxy=group_score(c), boards={}) for c in cand],
                                       [dict(proxy=group_score(p), boards={}) for p in par],
                                       self.cfg['acceptance']['alpha'])['proxy']
            if result['ub'] < -self.cfg.get('condition_drop', 0.5):
                return False, f'{name} regressed ({result["mean"]:+.2f}); {why}', st
            if floor is not None and result['mean'] < -float(floor):
                return False, f'{name} mean change {result["mean"]:+.2f} below -{floor}; {why}', st
        return ok, why, st

    @staticmethod
    def decide(st, A, final=False):
        boards = [k for k in st if k != 'proxy']
        P = st['proxy']
        drops = [b for b in boards if st[b]['ub'] < 0 and st[b]['mean'] < -A['board_drop']]
        bm = A.get('board_margin') or {}
        up = [b for b in boards if st[b]['lb'] > bm.get(b, A['margin'])]
        tag = f"Δproxy {P['mean']:+.2f} [{P['lb']:+.2f}, {P['ub']:+.2f}] n={P['n']}"
        if drops:
            return False, f"{tag}; significant drop on {', '.join(drops)}"
        # boards with few distinct targets (heart, embryo) must clear their own, higher margin
        strict = [b for b in boards if b in bm and st[b]['mean'] != 0 and st[b]['lb'] <= bm[b]]
        if strict:
            if final or st[strict[0]]['ub'] < bm[strict[0]]:
                return False, f"{tag}; {strict[0]} lower bound {st[strict[0]]['lb']:+.2f} not above {bm[strict[0]]}"
            return None, tag
        if P['lb'] > A['margin']:
            return True, f"{tag}; significant gain"
        if up and P['mean'] >= 0:
            return True, f"{tag}; significant gain on {', '.join(up)}"
        if P['ub'] < A['margin']:
            return False, f"{tag}; no gain (upper bound below margin)"
        return (False, f"{tag}; inconclusive after {P['n']} seed pairs") if final else (None, tag)

    @staticmethod
    def key(role):
        return f"{role['cli']}:{role['model']}"

    def pick_implementer(self):
        stats = self.state['impl_stats']
        total = sum(s[0] for s in stats.values()) + 1
        best, best_v = None, -1
        for i, role in enumerate(self.cfg['implementers']):
            n, wins = stats.get(self.key(role), [0, 0])
            v = float('inf') if n == 0 else wins / n + math.sqrt(2 * math.log(total) / n)
            if v > best_v:
                best, best_v = i, v
        return dict(self.cfg['implementers'][best])

    # ---------- the cycle ----------
    def cycle(self, w, i):
        ws_state = self.state['workers'][w]
        cdir = self.dir / 'cycles' / f'{w}_c{i:02d}'
        cdir.mkdir(parents=True, exist_ok=True)
        if (cdir / 'outcome.json').exists():
            outcome = json.loads((cdir / 'outcome.json').read_text())
            self.commit_outcome(w, cdir, outcome)
            return outcome
        self.verify_lock()
        if not (cdir / 'started').exists():
            (cdir / 'started').write_text(str(time.time()))
        parent, alt_note = self.choose_parent(w, i)
        self.state['workers'][w]['cur_parent'] = parent.get('id', 'seed')
        complexity = min(5, 2 + ws_state['fails'] // 2)
        sibs = '\n'.join(f"- {o['title']}: {o['verdict']} ({o['reason']})" for o in ws_state['history'][-5:]) or '(none)'
        cross_run = self.cfg.get('use_cross_run_history', True)
        display_eval = parent['eval']
        if self.cfg.get('scope_quick_eval'):
            board = self.home_board(w)
            display_eval = dict(display_eval, boards={board: display_eval['boards'][board]},
                                splits={name: row for name, row in display_eval['splits'].items()
                                        if row.get('board') == board})
        sub = dict(root=ROOT, brief_path=self.dir / 'brief.md', worker=w, cycle=i, cycle_dir=cdir, best_ws=parent['ws'], best_eval=self.describe(display_eval),
                   knowledge=self.bank.synthesis() + '\n\n### Records (all boards, recent first is last)\n' + self.bank.relevant(BOARDS_ALL, 30),
                   library=self.library() if cross_run else '',
                   pitfalls=self.bank.pitfalls(), siblings=sibs, complexity=complexity,
                   lessons=self.lessons() if cross_run else '')
        plan = self.dir / 'plan.md'
        sub['focus'] = self.focus_text(w) + alt_note + (
            f"\n\n## Run planner's current priorities (all boards; read before choosing)\n{plan.read_text()[:4000]}"
            if plan.exists() else '')
        rimpl = bool(self.cfg.get('researcher_implements'))
        ws = cdir / 'ws'
        if not (cdir / 'hypothesis.json').exists():
            (cdir / 'analysis').mkdir(exist_ok=True)
            if rimpl:  # the researcher designs AND implements: it works in a fresh copy of the parent
                shutil.rmtree(ws, ignore_errors=True)
                shutil.copytree(parent['ws'], ws, ignore=shutil.ignore_patterns('__pycache__', '.quick_eval_runs'))
                sub['ws'] = ws
            intended = self.role(w, 'ideator')  # a quota substitute never gets less time than this (agent())
            limit = max(intended['timeout_s'], self.research_timeout(intended))
            prompt = self.role_prompt('researcher' if rimpl else 'ideator').safe_substitute(
                sub, time_limit_min=limit // 60, draft_by_min=limit // 120)
            self.agent(intended, prompt, ws if rimpl else cdir, cdir / 'ideate',
                       allowed=None if rimpl else ['WebSearch', 'WebFetch', 'Read', 'Grep', 'Glob', 'Write', 'Edit',
                                                   f'Bash({PY}:*)', 'Bash(ls:*)', 'Bash(head:*)'], add_dirs=[ROOT])
        if rimpl and not (cdir / 'hypothesis.json').exists():
            self.rescue_hypothesis(w, cdir, parent, sub)
        if not (cdir / 'hypothesis.json').exists():
            return self.finish(w, cdir, dict(title='(no hypothesis)', verdict='skipped', reason='researcher wrote no hypothesis.json'))
        try:
            hyp = json.loads((cdir / 'hypothesis.json').read_text())
        except ValueError as e:
            return self.finish(w, cdir, dict(title='(invalid hypothesis)', verdict='skipped', reason=f'hypothesis.json is not valid JSON: {e}'))
        if rimpl and not (cdir / 'implemented').exists():
            (cdir / 'implemented').write_text(self.ran_role(cdir, 'ideate') or self.key(self.role(w, 'ideator')))
            if not ws.exists() or not self.diff_boards(parent['ws'], ws):
                return self.finish(w, cdir, dict(title=hyp.get('title'), verdict='skipped',
                                                 reason='the researcher did not change the program'), hyp)
        urls = [e for e in hyp.get('evidence', []) if 'http' in str(e.get('source', ''))]
        if len(urls) < 2 and not (cdir / 'ideate_retry').exists() and self.cfg.get('evidence_retry', True):
            (cdir / 'ideate_retry').write_text('thin evidence')
            prompt = self.role_prompt('ideator').safe_substitute(sub) + (
                '\n\nYour previous hypothesis.json cited fewer than 2 external sources. Do the literature step '
                'properly now (lit MCP tools or lit.py: pubmed/search/fulltext), then revise hypothesis.json in place.')
            self.agent(self.role(w, 'ideator'), prompt, cdir, cdir / 'ideate_r',
                       allowed=['WebSearch', 'WebFetch', 'Read', 'Grep', 'Glob', 'Write', 'Edit', f'Bash({PY}:*)',
                                'Bash(ls:*)', 'Bash(head:*)'], add_dirs=[ROOT])
            hyp = json.loads((cdir / 'hypothesis.json').read_text())
        brief = (self.dir / 'brief.md').read_text()
        if not (cdir / 'critique.json').exists() and self.critic(w, 'plan') is None:
            (cdir / 'critique.json').write_text(json.dumps(dict(verdict='go', issues=['plan critic disabled by config'])))
        if not (cdir / 'critique.json').exists():
            prompt = Template((MG / 'prompts/critic_plan.md').read_text()).safe_substitute(
                sub, brief=brief, program=self.code(parent['ws']), hypothesis=json.dumps(hyp, indent=1),
                knowledge=self.bank.synthesis() + '\n\n### Records on the targeted boards\n' + self.bank.relevant(hyp.get('target_boards'), 40))
            crit = self.parse_json(self.final_text(self.agent(self.critic(w, 'plan'), prompt, cdir, cdir / 'critic_plan'))) \
                or dict(verdict='go', issues=['critic unavailable'])
            (cdir / 'critique.json').write_text(json.dumps(crit, indent=1))
        crit = json.loads((cdir / 'critique.json').read_text())
        if crit.get('verdict') == 'reject':
            return self.finish(w, cdir, dict(title=hyp.get('title'), verdict='vetoed',
                                             reason='critic: ' + '; '.join(map(str, crit.get('issues', [])))[:400]), hyp)
        if crit.get('verdict') == 'revise' and isinstance(crit.get('hypothesis'), dict):
            hyp = dict(crit['hypothesis'], critic_issues=crit.get('issues', []))
        impl_role = None
        if not (cdir / 'implemented').exists():
            shutil.rmtree(ws, ignore_errors=True)
            shutil.copytree(parent['ws'], ws, ignore=shutil.ignore_patterns('__pycache__', '.quick_eval_runs'))
            impl_role = self.pick_implementer()
            prompt = self.role_prompt('implementer').safe_substitute(
                sub, ws=ws, hypothesis=json.dumps(hyp, indent=1))
            self.agent(impl_role, prompt, ws, cdir / 'implement',
                       allowed=['Read', 'Grep', 'Glob', 'Write', 'Edit', 'MultiEdit', f'Bash({PY}:*)', 'Bash(ls:*)',
                                'Bash(cat:*)', 'Bash(head:*)', 'Bash(grep:*)', 'Bash(cp:*)', 'Bash(mkdir:*)'])
            (cdir / 'implemented').write_text(self.key(impl_role))
        impl_cli = (cdir / 'implemented').read_text().strip()
        if not (cdir / 'code_review.json').exists() and self.critic(w, 'code') is None:
            (cdir / 'code_review.json').write_text(json.dumps(dict(verdict='pass', issues=['code critic disabled by config'])))
        if not (cdir / 'code_review.json').exists():
            prompt = Template((MG / 'prompts/critic_code.md').read_text()).safe_substitute(
                sub, brief=brief, hypothesis=json.dumps(hyp, indent=1), diff=self.diff(parent['ws'], ws))
            rev = self.parse_json(self.final_text(self.agent(self.critic(w, 'code'), prompt, cdir, cdir / 'critic_code'))) \
                or dict(verdict='pass', issues=['critic unavailable'])
            (cdir / 'code_review.json').write_text(json.dumps(rev, indent=1))
            if rev.get('verdict') == 'fix':
                prompt = self.role_prompt('debugger').safe_substitute(
                    sub, ws=ws, attempt='review', title=hyp.get('title'), history='(none)',
                    error='Code review (GPT critic) requires fixes before evaluation:\n' + json.dumps(rev.get('issues'), indent=1))
                self.agent(self.pick_implementer(), prompt, ws, cdir / 'review_fix',
                           allowed=['Read', 'Grep', 'Glob', 'Write', 'Edit', f'Bash({PY}:*)', 'Bash(ls:*)', 'Bash(cat:*)'])
        hits = self.audit(cdir)
        if hits:
            return self.finish(w, cdir, dict(title=hyp.get('title'), verdict='disqualified', reason='audit: ' + hits[0]), hyp)
        history = []
        bad_scope = self.scope(w, parent['ws'], ws)
        if bad_scope:
            return self.finish(w, cdir, dict(title=hyp.get('title'), verdict='rejected', reason='scope: ' + bad_scope), hyp)
        self.reset_tuned(parent['ws'], ws)
        ev = self.eval_scoped(ws, parent, cdir / 'eval.json')
        for attempt in range(self.cfg['max_debug_attempts']):
            if ev.get('correct'):
                break
            history.append(str(ev.get('error'))[:1500])
            prompt = self.role_prompt('debugger').safe_substitute(
                sub, ws=ws, attempt=attempt, error=ev.get('error'), title=hyp.get('title'), history='\n'.join(history))
            self.agent(self.debug_role(w, cdir), prompt, ws, cdir / f'debug{attempt}',
                       allowed=None if rimpl else ['Read', 'Grep', 'Glob', 'Write', 'Edit', f'Bash({PY}:*)', 'Bash(ls:*)', 'Bash(cat:*)'])
            hits = self.audit(cdir)
            if hits:
                return self.finish(w, cdir, dict(title=hyp.get('title'), verdict='disqualified', reason='audit: ' + hits[0]), hyp)
            bad_scope = self.scope(w, parent['ws'], ws)
            if bad_scope:
                return self.finish(w, cdir, dict(title=hyp.get('title'), verdict='rejected', reason='scope: ' + bad_scope), hyp)
            self.reset_tuned(parent['ws'], ws)
            ev = self.eval_scoped(ws, parent, cdir / 'eval.json')
        bad_scope = self.scope(w, parent['ws'], ws)
        if (not bad_scope and ev.get('correct') and self.cfg.get('require_calibrated_final')
                and self.cfg.get('t1_research_only', True)
                and 'temporal' in self.diff_boards(parent['ws'], ws)):
            passed = (not self.cfg.get('t1_composition_veto', True)
                      or self.evaluate(ws, 'composition', cdir / 'composition.json').get('plausible'))
            return self.finish(w, cdir, dict(title=hyp.get('title'),
                                             verdict='research_only' if passed else 'rejected',
                                             reason='T1 diagnostic only' if passed else 'T1 composition veto',
                                             ws=str(ws), boards=ev.get('boards')), hyp, parent['eval'], ev)
        if not bad_scope and ev.get('correct'):  # slow programs are tuned and raced like any other (no runtime gate)
            ev = self.maybe_tune(w, cdir, ws, parent, ev)
        if not bad_scope and ev.get('correct') and self.cfg.get('sanity', True):
            from agentic_scientist.evaluate import SETS
            ch = self.changed_splits(ev, parent['eval'])
            if any(s in ch for s in ['temporal_val', 'temporal_heartonly', 'temporal_matched', 'heart_early', 'heart_late', 'heart_long',
                                     'heart_e875', 'heart_organ_proxy', 'heart_e875_organ', 'heart_long_organ']):
                sv = self.evaluate(ws, 'sanity', cdir / 'sanity.json')
                if not sv.get('plausible'):
                    why = '; '.join(sv.get('fails') or []) or str(sv.get('error'))[:300]
                    return self.finish(w, cdir, dict(title=hyp.get('title'), verdict='rejected',
                                                     reason='implausible 3-day forecast: ' + why), hyp)
        if bad_scope:
            return self.finish(w, cdir, dict(title=hyp.get('title'), verdict='rejected', reason='scope: ' + bad_scope), hyp)
        if (self.cfg.get('t1_composition_veto', True) and ev.get('correct')
                and 'temporal' in self.diff_boards(parent['ws'], ws)):
            guard = self.evaluate(ws, 'composition', cdir / 'composition.json')
            if not guard.get('plausible'):
                return self.finish(w, cdir, dict(title=hyp.get('title'), verdict='rejected',
                                                 reason='T1 blood guard: the E12.5 forecast has a larger blood-like '
                                                        'share than the E10.5 input'), hyp)
        native_min = self.cfg.get('embryo_native_min')
        if native_min is not None and ev.get('correct') and 'embryo' in self.diff_boards(parent['ws'], ws):
            native = [r.get('metrics', {}).get('native_occupancy') for r in ev['splits'].values()
                      if r.get('board') == 'embryo']
            if not native or any(v is None or v < native_min for v in native):
                return self.finish(w, cdir, dict(title=hyp.get('title'), verdict='rejected',
                                                 reason=f'embryo geometry is not one native embryo (native_occupancy '
                                                        f'{native} < {native_min})'), hyp)
        slow = self.too_slow(ev)
        if slow:  # advisory only: never a rejection reason
            self.log(f'{cdir.name} runtime note (not a rejection): {slow}')
        ok, reason, stats = self.race(ws, ev, parent)
        sev = self.severity_note(ev)
        if sev:
            reason = f'{reason} | {sev}'
        review = None
        if ok and self.cfg.get('promotion_review'):
            review = self.promotion_review(w, cdir, ws, parent, hyp, ev, stats, impl_cli)
            if not review['promote']:
                ok = False
                reason = f"{reason} | promotion review veto: {review['why']}"[:900]

        nh = None
        if ev.get('correct') and any(s.startswith('gata4') for s in self.changed_splits(ev, parent['eval'])):
            try:
                subprocess.run([str(ROOT / '.venv/bin/python'), str(ROOT / 'agentic_scientist/tools/noharm.py'), str(ws),
                                '--json', str(cdir / 'noharm.json')], cwd=ROOT / 'agentic_scientist/tools', capture_output=True, timeout=fleet.remaining(self.research_deadline(), 1800))
                nh = json.loads((cdir / 'noharm.json').read_text())
                nh = {k: nh[k] for k in ('gene_specific', 'median_ratio', 'gata4_global_scale', 'verdict')}
                reason_suffix = f" | gene-specificity {nh['gene_specific']:+.2f} ({nh['verdict'].split(':')[0]})"
            except Exception as e:  # noqa: BLE001
                nh, reason_suffix = dict(error=repr(e)), ''
        else:
            reason_suffix = ''
        mean_proxy = parent['eval']['proxy'] + stats['proxy']['mean'] if stats else ev.get('proxy')
        outcome = dict(title=hyp.get('title'), verdict='accepted' if ok else 'rejected', reason=reason + reason_suffix, stats=stats, noharm=nh,
                       proxy=mean_proxy, screen_proxy=ev.get('proxy'), boards=ev.get('boards'), parent_proxy=parent['eval']['proxy'],
                       implementer=impl_cli, ws=str(ws), tune=self.tune_summary(cdir), review=review)
        outcome['parent_id'] = parent.get('id', 'seed')
        return self.finish(w, cdir, outcome, hyp, parent['eval'], ev)


    # ---------- AgenticScientist final-run additions ----------
    def ran_role(self, cdir, label):
        """Key (cli:model) of the role that actually ran the latest `label` call of a cycle (after any substitution)."""
        best = None
        for f in Path(cdir).glob(f'{label}.*.prompt.json'):
            try:
                n = int(f.name.split('.')[-3])
            except ValueError:
                continue
            if best is None or n > best[0]:
                best = (n, f)
        if best is None:
            return None
        try:
            return self.key(json.loads(best[1].read_text())['role'])
        except (OSError, ValueError, KeyError):
            return None

    def role_by_key(self, key, timeout_s=None):
        pool = list(self.cfg.get('ideator_cycle') or []) + list(self.cfg.get('implementers') or [])
        pool += [self.cfg[k] for k in ('overflow', 'claude_fallback') if self.cfg.get(k)]
        pool += list(self.cfg.get('quota_fallback') or []) + list(self.cfg.get('cheap_fallback') or [])
        for r in pool:
            if self.key(r) == key:
                return dict(r, **({'timeout_s': timeout_s} if timeout_s else {}))
        return None

    def debug_role(self, w, cdir):
        """Researcher-implements mode: the model that wrote the code fixes it (substituted by agent() when limited)."""
        if self.cfg.get('researcher_implements'):
            r = self.role_by_key(self.ran_role(cdir, 'ideate') or '', self.cfg.get('debug_timeout_s', 1800))
            return r or dict(self.role(w, 'ideator'), timeout_s=self.cfg.get('debug_timeout_s', 1800))
        return self.pick_implementer()

    def research_timeout(self, role):
        """cfg['research_timeout_s'] = {"cli:model": seconds}: a longer wall-clock limit for the main research session
        of slower researchers (they run real-scorer screens before writing hypothesis.json). Applies whether the model
        is scheduled or stands in for another one; 0 = the role's own timeout_s."""
        return int((self.cfg.get('research_timeout_s') or {}).get(self.key(role), 0))

    @staticmethod
    def session_digest(tpath, limit=60000, item_chars=2500):
        """Readable record of one agent session from any CLI's JSON transcript (agy, codex, claude, opencode,
        commandcode): the agent's messages, the commands it ran and their (truncated) outputs, in order. Commands still
        running when the session ended are marked."""
        items, slots, called = [], {}, {}

        def cut(s, n=item_chars):
            s = str(s).strip()
            return s if len(s) <= n else s[:n // 2] + f'\n[... {len(s) - n} chars cut ...]\n' + s[-n // 2:]

        def tool(name, args=None, output=None, key=None, running=False):
            """One command and its output; `key` ties a still-running call to its later completion."""
            if isinstance(args, dict):
                args = args.get('CommandLine') or args.get('command') or args.get('cmd') or json.dumps(args)
            if key is not None:
                args = args if args else called.get(key, '')
                called[key] = args
            if isinstance(output, list):
                output = '\n'.join(str(c.get('text', '')) if isinstance(c, dict) else str(c) for c in output)
            text = f'$ [{name}] {cut(args, 1500)}'
            if running:
                text += '\n(no output: still running when the session ended)'
            elif output not in (None, ''):
                text += '\n' + cut(output)
            if key is not None and key in slots:
                items[slots[key]] = text
                if not running:
                    slots.pop(key)
                return
            if running and key is not None:
                slots[key] = len(items)
            items.append(text)

        def say(text, key=None):
            if key is None:
                items.append(str(text))
            elif key in slots:
                items[slots[key]] += str(text)
            else:
                slots[key] = len(items)
                items.append(str(text))

        for line in Path(tpath).read_text(errors='replace').splitlines():
            try:
                ev = json.loads(line)
            except ValueError:
                continue
            if not isinstance(ev, dict):
                continue
            su, item, msg, part, cc = (ev.get(k) for k in ('step_update', 'item', 'message', 'part', 'event'))
            if isinstance(su, dict):  # agy: streamed step updates
                kind, idx = su.get('step_type'), su.get('step_index')
                info = su.get('tool_info') or {}
                if kind == 'agent_response' and su.get('text_delta'):
                    say(su['text_delta'], ('say', idx))
                elif kind == 'tool':
                    tool(su.get('tool_name'), info.get('parameters') or {}, info.get('output'), ('tool', idx),
                         running=su.get('state') != 'DONE')
            elif isinstance(item, dict) and ev.get('type') in ('item.started', 'item.completed'):  # codex
                t, done = item.get('type'), ev['type'] == 'item.completed'
                if t == 'agent_message' and done:
                    say(item.get('text', ''))
                elif t == 'command_execution':
                    tool('shell', item.get('command', ''), item.get('aggregated_output'), item.get('id'), running=not done)
                elif t == 'file_change' and done:
                    say('[edited] ' + ', '.join(str(c.get('path')) for c in item.get('changes') or []))
                elif t == 'web_search' and done:
                    say('[web search] ' + json.dumps(item.get('action') or item.get('query'))[:500])
            elif isinstance(msg, dict) and ev.get('type') in ('assistant', 'user'):  # claude
                for c in msg.get('content') or []:
                    if not isinstance(c, dict):
                        continue
                    if c.get('type') == 'text':
                        say(c.get('text', ''))
                    elif c.get('type') == 'tool_use':
                        tool(c.get('name'), c.get('input') or {})
                    elif c.get('type') == 'tool_result':
                        out = c.get('content')
                        if isinstance(out, list):
                            out = '\n'.join(str(x.get('text', '')) if isinstance(x, dict) else str(x) for x in out)
                        say(cut(out))
            elif isinstance(part, dict):  # opencode
                if part.get('type') == 'text':
                    say(part.get('text', ''))
                elif part.get('type') == 'tool':
                    st = part.get('state') or {}
                    tool(part.get('tool'), st.get('input') or {}, st.get('output'), part.get('id'),
                         running=st.get('status') not in ('completed', 'error'))
            elif isinstance(cc, dict) and ev.get('type') == 'event':  # commandcode
                if cc.get('type') == 'message_end':
                    for c in cc.get('content') or []:
                        if isinstance(c, dict) and c.get('type') == 'text':
                            say(c.get('text', ''))
                        elif isinstance(c, dict) and c.get('type') == 'tool_use':
                            tool(c.get('name'), c.get('input') or {}, key=c.get('id'), running=True)
                elif cc.get('type') == 'tool_completed':
                    tool(cc.get('toolName'), None, cc.get('result'), cc.get('toolCallId'))
        text = '\n\n'.join(s.strip() for s in items if s and s.strip())
        if len(text) > limit:
            head = limit // 6
            text = (text[:head] + f'\n\n[... {len(text) - limit} chars from the middle of the session cut ...]\n\n'
                    + text[-(limit - head):])
        return text

    def rescue_hypothesis(self, w, cdir, parent, sub):
        """Researcher mode: a research session that ended without hypothesis.json (typically stopped at its wall-clock
        limit while a long analysis was still running) gets ONE short wrap-up call per session. The model that ran it
        (or its quota fallback) reads a digest of that session, its analysis files and the workspace diff, then writes
        hypothesis.json and finishes the implementation without new long analyses. Fully automatic."""
        rc = self.cfg.get('rescue') or {}
        if not rc.get('enabled', True):
            return
        runs = sorted(cdir.glob('ideate.*.jsonl'), key=lambda p: int(p.name.split('.')[-2]))
        if not runs:
            return
        last = runs[-1]
        marker = cdir / 'rescue_of'
        if marker.exists() and marker.read_text().strip() == last.name:
            return
        marker.write_text(last.name)
        digest = self.session_digest(last, limit=int(rc.get('digest_chars', 60000)))
        if len(digest) < int(rc.get('min_digest_chars', 400)):
            self.log(f'{cdir.name} rescue skipped: the research session {last.name} did almost nothing')
            return
        dpath = cdir / 'analysis' / 'previous_session.md'
        dpath.parent.mkdir(exist_ok=True)
        write_text(dpath, digest)
        timeout = int(rc.get('timeout_s', 1500))
        role = (self.role_by_key(self.ran_role(cdir, 'ideate') or '', timeout)
                or dict(self.role(w, 'ideator'), timeout_s=timeout))
        ws = cdir / 'ws'
        diff = self.diff(parent['ws'], ws, limit=int(rc.get('diff_chars', 12000))) if ws.exists() else ''
        prompt = self.role_prompt('rescue').safe_substitute(
            sub, ws=ws, digest_path=dpath, digest_tail=digest[-int(rc.get('inline_chars', 12000)):],
            ws_diff=diff.strip() or '(no changes yet)', minutes=timeout // 60)
        self.log(f'{cdir.name} rescue: {self.key(role)} wraps up {last.name} (no hypothesis.json yet)')
        self.agent(role, prompt, ws, cdir / 'ideate_rescue', add_dirs=[ROOT])
        ok = (cdir / 'hypothesis.json').exists()
        self.log(f"{cdir.name} rescue {'wrote hypothesis.json' if ok else 'failed: still no hypothesis.json'}")

    def review_role(self, author_key):
        """The OTHER premium researcher reviews (fallback: the same one, then overflow via agent())."""
        sched = list(self.cfg.get('ideator_cycle') or [])
        other = [r for r in sched if self.key(r) != author_key] or sched
        r = dict(other[0]) if other else dict(self.cfg['critic'])
        r['timeout_s'] = self.cfg.get('review_timeout_s', 1200)
        return r

    TEST_KEY = {'temporal': 'T1:test', 'heart': 'T2:heart:test_extrap', 'embryo': 'T2:embryo:test_interp',
                'perturbation': 'T3:bcatenin'}

    def export_gate(self, ws, board, out):
        """Export the board's TEST file with the exact submission code and run the format/geometry gates on it."""
        out = Path(out)
        man = out / 'manifest.json'
        if not man.exists():
            subprocess.run([PY, '-I', str(MG / 'export_final.py'), '--workspace', str(ws), '--out', str(out),
                            '--boards', self.TEST_KEY[board]], cwd=ROOT, stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL, timeout=fleet.remaining(self.research_deadline(), 2400))
        if not man.exists():
            return dict(ok=False, error='export produced no manifest')
        row = json.loads(man.read_text())['boards'].get(self.TEST_KEY[board], {})
        for f in out.glob('*.h5ad'):
            f.unlink()  # keep the manifest and gates, not the 20 MB file
        return dict(ok=bool(row.get('ok')), gates=row.get('gates'), error=row.get('error'), geometry=row.get('geometry'),
                    blood_guard=row.get('blood_guard'), cells=row.get('cells'))

    def promotion_review(self, w, cdir, ws, parent, hyp, ev, stats, author_key):
        """Accepted candidates only: (1) the exact test export of the board must pass the gates; (2) the other premium
        model reviews the code for rule and transfer defects. A veto needs a concrete defect with file:line evidence."""
        board = self.home_board(w)
        rfile = cdir / 'promotion_review.json'
        if rfile.exists():
            return json.loads(rfile.read_text())
        gate = self.export_gate(ws, board, cdir / 'test_export')
        if not gate['ok']:
            res = dict(promote=False, why=f"test-export gate failed: {gate.get('error') or gate.get('gates')}"
                       + (f" geometry {gate['geometry']}" if gate.get('geometry') else ''), gate=gate)
            write_json(rfile, res)
            return res
        prompt = Template((MG / 'prompts/promotion_review.md').read_text()).safe_substitute(
            root=ROOT, ws=ws, board=board, brief_path=self.dir / 'brief.md', hypothesis=json.dumps(hyp, indent=1)[:6000],
            diff=self.diff(parent['ws'], ws), stats=json.dumps(stats, default=float)[:3000],
            gate=json.dumps(gate, default=float)[:2000], cycle_dir=cdir)
        role = self.review_role(author_key)
        out = self.parse_json(self.final_text(self.agent(role, prompt, cdir, cdir / 'review'))) or {}
        verdict = str(out.get('verdict', 'promote')).lower()
        issues = out.get('issues') or []
        promote = not (verdict == 'veto' and issues)
        res = dict(promote=promote, why='; '.join(map(str, issues))[:600] if not promote else 'ok', verdict=verdict,
                   issues=issues, reviewer=self.ran_role(cdir, 'review'), gate=gate)
        write_json(rfile, res)
        return res

    def private_dir(self):
        """Human-only monitor results. Outside every agent-readable path (the sandbox allowlist excludes it)."""
        d = Path(self.cfg.get('private_root', '/scratch/user/as_private')) / self.dir.name
        d.mkdir(parents=True, exist_ok=True)
        return d

    PRIVATE_SEM = threading.Semaphore(2)

    def private_holdout(self, tag, ws, board, meta=None):
        """Per-cycle held-out score for the humans' dashboard: the candidate's board on the local holdout targets
        (dissected E10.5 heart, E7.5 embryo). Runs in the background on this host; the result is never shown to any
        agent, never written into the run directory and never used by the cycle (selection at the end of the run uses
        its own holdout evaluation)."""
        if not self.cfg.get('private_monitor', True):
            return
        from agentic_scientist.evaluate import SETS, harness as H
        set_name = 'holdout_t3' if board == 'perturbation' else 'holdout'
        splits = [x for x in SETS[set_name]['splits'] if x in H.SPLITS and H.SPLITS[x]['board'] == board]
        if set_name == 'holdout_t3' and not splits and (ROOT / 'data/raw/T3/unseen_spec.json').exists():
            splits = ['unseen_t3']

        def job():
            rec = dict(t=time.time(), id=tag, board=board, ws=str(ws), **(meta or {}))
            if not splits:
                rec['note'] = 'no local held-out target for this board (dev only)'
            else:
                with self.PRIVATE_SEM:
                    out = self.private_dir() / f'holdout_{tag}_{board}.json'
                    try:
                        if not out.exists():
                            subprocess.run([PY, '-I', str(MG / 'evaluate.py'), '--workspace', str(ws), '--set', set_name,
                                            '--splits', ','.join(splits), '--out', str(out), '--workers', str(len(splits))],
                                           env=dict(os.environ, MG_PRIVATE_FINAL='1', OMP_NUM_THREADS='2',
                                                    OPENBLAS_NUM_THREADS='2'), cwd=ROOT, stdout=subprocess.DEVNULL,
                                           stderr=subprocess.DEVNULL, timeout=3600)
                        e = json.loads(out.read_text())
                        rec.update(correct=e.get('correct'), score=(e.get('boards') or {}).get(board), error=e.get('error'),
                                   splits={k: dict(score=v.get('score'), metrics=v.get('metrics'))
                                           for k, v in (e.get('splits') or {}).items()})
                    except Exception as ex:  # noqa: BLE001 - monitor only
                        rec['error'] = repr(ex)[:500]
            with LOCK, (self.private_dir() / 'holdout.jsonl').open('a') as f:
                f.write(json.dumps(rec, default=float) + '\n')
        threading.Thread(target=job, daemon=True, name=f'private-{tag}-{board}').start()

    def compose_current(self, out_ws):
        """Seed + each worker's current dev-best program for its own board (automatic, no human choice)."""
        seed_ws = self.dir / 'seed_ws'
        shutil.rmtree(out_ws, ignore_errors=True)
        shutil.copytree(seed_ws, out_ws, ignore=shutil.ignore_patterns('__pycache__', '.quick_eval_runs'))
        parts = {}
        for w, st in sorted(self.state['workers'].items()):
            b = self.home_board(w)
            best = st.get('best') or {}
            if b and best.get('id') not in (None, 'seed'):
                self.copy_board(best['ws'], out_ws, b)
                parts[b] = dict(id=best['id'], researcher=self.ran_role(self.dir / 'cycles' / best['id'], 'ideate'))
        return parts

    def checkpoint(self, label=None):
        """Automated checkpoint: compose, export the four test files, gate them and package the evidence."""
        stamp = label or time.strftime('%Y%m%d_%H%M')
        cdir = self.dir / 'checkpoints' / stamp
        cdir.mkdir(parents=True, exist_ok=True)
        with LOCK:
            parts = self.compose_current(cdir / 'ws')
        write_json(cdir / 'composition.json', dict(t=time.time(), parts=parts))
        r = subprocess.run([PY, '-I', str(MG / 'export_final.py'), '--workspace', str(cdir / 'ws'), '--out',
                            str(cdir / 'submission')], cwd=ROOT, capture_output=True, text=True, timeout=5400)
        man = cdir / 'submission' / 'manifest.json'
        ok = man.exists() and json.loads(man.read_text()).get('ok')
        self.log(f"checkpoint {stamp}: export {'ok' if ok else 'FAILED'} parts {json.dumps(parts)}"
                 + ('' if man.exists() else f' :: {r.stderr[-400:]}'))
        with LOCK:
            self.state.setdefault('checkpoints', []).append(dict(stamp=stamp, t=time.time(), ok=bool(ok), parts=parts))
            self.save()
        return cdir, ok

    def checkpoint_loop(self):
        every = float(self.cfg.get('checkpoint_hours') or 0) * 3600
        if not every:
            return

        def loop():
            while not self.stop:
                last = self.state.get('last_checkpoint') or self.state.get('research_started') or time.time()
                if time.time() < last + every:
                    time.sleep(30)
                    continue
                with LOCK:
                    self.state['last_checkpoint'] = time.time()
                    self.save()
                try:
                    self.checkpoint()
                except Exception as e:  # noqa: BLE001 - a checkpoint must never stop research
                    self.log(f'checkpoint error {e!r}')
        self.checkpoint_thread = threading.Thread(target=loop, daemon=True, name='checkpoint')
        self.checkpoint_thread.start()

    def leaderboard_loop(self):
        """Every cfg['leaderboard_refresh_minutes'] the public P3 boards are fetched (same JSON as the website, no key) into
        <run>/leaderboard/<stamp>/ with our own teams' rows removed; tools/leaderboard.py reads the newest snapshot."""
        every = float(self.cfg.get('leaderboard_refresh_minutes') or 0) * 60
        if not every:
            return

        def loop():
            from agentic_scientist import leaderboard_refresh as lr
            while not self.stop:
                try:
                    out = lr.write(self.dir / 'leaderboard' / time.strftime('%Y-%m-%d_%H%M'), lr.fetch())
                    self.log(f'leaderboard refreshed: {out.name}')
                except Exception as e:  # noqa: BLE001 - public data is a convenience, never a dependency
                    self.log(f'leaderboard refresh failed: {e!r}')
                t0 = time.time()
                while not self.stop and time.time() < t0 + every:
                    time.sleep(30)
        threading.Thread(target=loop, daemon=True, name='leaderboard').start()

    def final_export(self):
        """After selection: export the selected program's four test files, gate them, write SUBMISSION.md, package the
        evidence. A board whose export fails falls back to the latest checkpoint's file for that board."""
        fdir = self.dir / 'final'
        sel = fdir / 'selected'
        if not sel.exists():
            raise RuntimeError('final export: no selected program')
        sub = fdir / 'submission'
        subprocess.run([PY, '-I', str(MG / 'export_final.py'), '--workspace', str(sel), '--out', str(sub)], cwd=ROOT,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5400)
        man = json.loads((sub / 'manifest.json').read_text()) if (sub / 'manifest.json').exists() else dict(boards={})
        fin = json.loads((fdir / 'final.json').read_text()) if (fdir / 'final.json').exists() else {}
        lines = [f'# AgenticScientist final submission ({self.dir.name})', '',
                 f"Lock {self.lock['lock_id']}; selection rule: {fin.get('rule')}; chosen: {fin.get('chosen')}.", '',
                 '| board | file | ok | source cycle | model that wrote it | sha256 |', '|---|---|---|---|---|---|']
        chosen = next((c for c in fin.get('candidates', []) if c.get('id') == fin.get('chosen')), {})
        src = {b: v.get('id') for b, v in (chosen.get('parts') or {}).items()}
        src.update({b: v.get('id') for b, v in (chosen.get('dev_only_parts') or {}).items()})
        for board, key in self.TEST_KEY.items():
            row = man['boards'].get(key, {})
            cyc = src.get(board, 'seed')
            model = self.ran_role(self.dir / 'cycles' / cyc, 'ideate') if cyc != 'seed' else 'seed (no agent change)'
            lines.append(f"| {key} | {row.get('file')} | {row.get('ok')} | {cyc} | {model} | {str(row.get('sha256'))[:16]} |")
        models = ', '.join(r['model'] for r in (self.cfg.get('ideator_cycle') or [self.cfg['ideator']]))
        lines += ['', f'Framework: AgenticScientist (multi-role orchestrator: researcher-implementer rotating '
                  f'{models}; diff-only promotion review by another model; DeepSeek/Sonnet/Luna/Hydrogen curation).',
                  'Files were produced by the selected program without human edits; humans only watched process health.']
        write_text(fdir / 'SUBMISSION.md', '\n'.join(lines) + '\n')
        try:
            from agentic_scientist.export_final import package, package_upload_ready
            lock = next((ROOT / 'agentic_scientist/locks').glob(f"{self.lock['lock_id']}*.json"), None)
            z = package(self.dir, fdir / f'evidence_{self.dir.name}.zip', lock=lock)
            self.log(f'final evidence packaged: {z}')
            ev = package_upload_ready(self.dir, fdir / 'upload_ready', lock=lock)
            self.log(f"portal upload_ready built: ready={ev.get('ready_for_upload')} "
                     f"secret_clean={ev.get('secret_scan', {}).get('clean')} "
                     f"lock_ok={ev.get('lock_integrity', {}).get('ok')} "
                     f"mb={ev.get('evidence_total_mb')} -> {fdir / 'upload_ready'}")
        except Exception as e:  # noqa: BLE001
            self.log(f'final evidence packaging error {e!r}')
        self.log(f"final export {'ok' if man.get('ok') else 'INCOMPLETE'}: {sub}")
        return man

    # ---------- elites: a small per-worker pool of alternative parents (borrowed from evolutionary search) ----------
    def elites(self, w):
        st = self.state['workers'][w]
        if 'elites' not in st:  # older state files: the best so far is the only elite
            b = st['best']
            st['elites'] = [dict(b, rank=b.get('rank', b['eval']['proxy']))]
        return st['elites']

    def add_elite(self, w, entry):
        """Keep the top-K accepted programs by estimated dev proxy (parent proxy + paired gain); best = the top one."""
        k = int(self.cfg.get('elites', 3))
        with LOCK:
            depth = self.state.setdefault('depth', {})
            depth.setdefault(entry['id'], depth.get(self.state['workers'][w].get('cur_parent', 'seed'), 0) + 1)
            self.state.setdefault('parent', {}).setdefault(entry['id'], self.state['workers'][w].get('cur_parent', 'seed'))
            el = [e for e in self.elites(w) if e['id'] != entry['id']] + [entry]
            el.sort(key=lambda e: -e['rank'])
            self.state['workers'][w]['elites'] = el[:k]
            top = el[0]
            self.state['workers'][w]['best'] = dict(ws=top['ws'], eval=top['eval'], id=top['id'])

    def choose_parent(self, w, i):
        """Usually the best program. An alternative elite (rotating) every third cycle, or right after two failures in a
        row, so one stalled line does not block the worker. The candidate is still tested against its own parent."""
        st, el = self.state['workers'][w], self.elites(w)
        cap = self.cfg.get('lineage_max')
        if cap:
            depth = self.state.setdefault('depth', {})
            el = [e for e in el if depth.get(e['id'], 0) < cap]
            if not el or depth.get(st['best']['id'], 0) >= cap:
                base = el[0] if el else (st.get('starting_parent') or dict(
                    ws=str(self.dir / 'seed_ws'), eval=self.seed_eval, id='seed'))
                st['cur_parent'] = base['id']
                return dict(ws=base['ws'], eval=base['eval'], id=base['id']), (
                    f"\n\nPARENT THIS CYCLE: {base['id']}. The best line ({st['best']['id']}) already stacks {cap} accepted "
                    "edits, the limit per lineage (stacked dev gains stopped transferring last run). Start a NEW line from "
                    "this parent with a mechanism DIFFERENT from that line's.")
        if int(self.cfg.get('elites', 3)) < 2 or len(el) < 2 or not (i % 3 == 2 or st['fails'] >= 2):
            return st['best'], ''
        alt = el[1 + (i // 3) % (len(el) - 1)]
        why = 'two failures in a row from the best' if st['fails'] >= 2 else 'scheduled diversity cycle'
        note = (f"\n\nPARENT THIS CYCLE: an alternative elite program ({alt['id']}, estimated dev proxy {alt['rank']:.2f}; "
                f"the best is {st['best']['id']} at {el[0]['rank']:.2f}), chosen for diversity ({why}). Build on IT: its "
                f"workspace is the parent below. Your change is tested against this parent; if accepted it joins the "
                f"worker's elites and becomes the best only if its estimated proxy is higher.")
        return dict(ws=alt['ws'], eval=alt['eval'], id=alt['id']), note

    def finish(self, w, cdir, outcome, hyp=None, parent_eval=None, cand_eval=None):
        parent_eval = parent_eval or self.state['workers'][w]['best']['eval']
        intended = self.key(self.role(w, 'ideator'))
        ran = self.ran_role(cdir, 'ideate')
        outcome.setdefault('researcher', ran)
        outcome.setdefault('researcher_intended', intended)
        outcome.setdefault('substitute', bool(ran) and ran != intended)
        outcome.setdefault('board', self.home_board(w))
        try:
            outcome.setdefault('cycle_seconds', round(time.time() - float((cdir / 'started').read_text()), 1))
        except (OSError, ValueError):
            pass
        outcome.setdefault('finished', time.time())
        if cand_eval is not None and cand_eval.get('correct'):
            outcome.setdefault('dev_board', (cand_eval.get('boards') or {}).get(self.home_board(w)))
            outcome.setdefault('parent_dev_board', (parent_eval.get('boards') or {}).get(self.home_board(w)))
        write_json(cdir / 'outcome.json', outcome)
        self.commit_outcome(w, cdir, outcome, cand_eval)
        try:
            self.record(w, cdir, outcome, hyp, parent_eval, cand_eval)
        except Exception as e:  # noqa: BLE001 - knowledge failures must not kill the run
            self.log(f'{cdir.name} knowledge error {e!r}')
        mon = cand_eval
        if mon is None and (cdir / 'eval.json').exists():
            try:
                mon = json.loads((cdir / 'eval.json').read_text())
            except ValueError:
                mon = None
        mws = outcome.get('ws') or str(cdir / 'ws')
        if mon is not None and mon.get('correct') and Path(mws).exists():
            # human-only monitors for EVERY evaluated candidate (never shown to agents, never used in the cycle)
            meta = dict(verdict=outcome['verdict'], researcher=outcome.get('researcher'),
                        dev_board=(mon.get('boards') or {}).get(self.home_board(w)), parent=outcome.get('parent_id'))
            self.private_holdout(cdir.name, mws, self.home_board(w), meta)
            self.monitor_late(cdir.name, mws, self.home_board(w))
        self.log(f"{cdir.name} {outcome['verdict']} {outcome['reason']} :: {outcome['title']}")
        self.maybe_plan()  # after the outcome is in the history, so the plan sees it
        return outcome

    def commit_outcome(self, w, cdir, outcome, cand_eval=None):
        """Replay a durable outcome if the process stopped before committing state."""
        with LOCK:
            ws_state = self.state['workers'][w]
            index = int(cdir.name.rsplit('_c', 1)[1])
            if ws_state['cycle'] > index:
                return
            if ws_state['cycle'] != index:
                raise RuntimeError(f'outcome {cdir.name} is out of sequence')
            accepted = outcome['verdict'] == 'accepted'
            if accepted:
                eval_path = cdir / 'eval.json'
                ev = cand_eval if cand_eval is not None else json.loads(eval_path.read_text())
                self.add_elite(w, dict(ws=outcome['ws'], eval=ev, id=cdir.name, rank=outcome['proxy']))
                self.state['accepted'].append(dict(id=cdir.name, ws=outcome['ws'], proxy=outcome['proxy'],
                                                   boards=outcome['boards'], eval_path=str(eval_path)))
            implementer = outcome.get('implementer')
            if implementer:
                counters = self.state['impl_stats'].setdefault(implementer, [0, 0])
                counters[0] += 1
                counters[1] += int(accepted)
            ws_state['history'].append(outcome)
            ws_state['fails'] = 0 if accepted else ws_state['fails'] + 1
            ws_state['cycle'] += 1
            gb = self.state['global_best']
            if accepted and (gb is None or outcome['proxy'] > gb):
                self.state['global_best'] = outcome['proxy']
            ws_state['stale'] = 0 if accepted else ws_state.get('stale', 0) + 1
            self.save()

    def record(self, w, cdir, outcome, hyp, parent_eval, cand_eval):
        """Distil every outcome into the knowledge bank, then let the curator re-synthesise knowledge.md."""
        status, deltas, dp, z = classify(outcome, parent_eval, cand_eval)
        try:
            from agentic_scientist.transfer import transfer
            tr = transfer(parent_eval, cand_eval).get('total') if cand_eval and cand_eval.get('correct') else None
        except Exception as e:  # noqa: BLE001 - diagnostic only, never blocks recording
            tr = None
            self.log(f'{cdir.name} transfer split failed: {e!r}')
        rd = lambda f: json.loads((cdir / f).read_text()) if (cdir / f).exists() else None  # noqa: E731
        changes = (cdir / 'ws/CHANGES.md').read_text()[-3000:] if (cdir / 'ws/CHANGES.md').exists() else ''
        try:
            sig = signature(hyp, parent_eval, cand_eval)
        except Exception as e:  # noqa: BLE001 - diagnostic only
            sig = None
            self.log(f'{cdir.name} signature check failed: {e!r}')
        if sig:
            self.log(f"{cdir.name} {sig['summary']}")
        dist = {}
        if hyp is not None:
            prompt = Template((MG / 'prompts/distiller.md').read_text()).safe_substitute(
                cycle_id=cdir.name, status=status.upper(), delta_proxy=f'{dp:+.2f}', z=f'{z:+.1f}',
                deltas=json.dumps({k: round(v, 2) for k, v in deltas.items()}) + (f' | gain by metric kind {json.dumps(tr)}' if tr else '')
                + (f" | predicted metric {sig['summary']} (did the mechanism act as intended?)" if sig else ''),
                outcome=json.dumps(outcome, default=float)[:1500],
                hypothesis=json.dumps(hyp)[:5000], critique=json.dumps(rd('critique.json'))[:3000],
                review=json.dumps(rd('code_review.json'))[:2000], changes=changes,
                error=str((cand_eval or {}).get('error') or '')[:1500])
            dist = self.parse_json(self.final_text(self.agent(self.cfg['distiller'], prompt, cdir, cdir / 'distill'))) or {}
        tags = dist.get('tags') or {}
        if not tags.get('boards'):
            tags['boards'] = [b for b in (hyp or {}).get('target_boards', []) if b in BOARDS_ALL] or \
                [b for b, d in deltas.items() if abs(d) > .5]
        entry = dict(id=cdir.name, worker=w, t=time.time(), title=outcome.get('title'), verdict=outcome.get('verdict'),
                     reason=outcome.get('reason'), status=status, delta_proxy=round(dp, 3), z=round(z, 2),
                     deltas={k: round(v, 3) for k, v in deltas.items()}, boards=(cand_eval or {}).get('boards'),
                     tags=tags, lesson=dist.get('lesson') or outcome.get('reason'), mechanism=dist.get('mechanism'),
                     retry_condition=dist.get('retry_condition'), method_lessons=dist.get('method_lessons', []),
                     impl_pitfalls=dist.get('impl_pitfalls', []), sources=dist.get('sources', []),
                     claim=(hyp or {}).get('claim'), implementer=outcome.get('implementer'),
                     portable=(hyp or {}).get('portable') if outcome.get('verdict') == 'accepted' else None,
                     transfer=tr, signature=sig, origin=(hyp or {}).get('origin'),
                     leaderboard_evidence=(hyp or {}).get('leaderboard_evidence'))
        self.bank.add(entry)
        with LOCK, self.notebook.open('a') as f:
            f.write(f"\n## {cdir.name}: {entry['title']} [{status}, {outcome.get('reason')}]\n- {entry['lesson']}\n")
        self.request_curation(cdir, entry)

    def request_curation(self, cdir, entry):
        """Curation runs in one background thread so a slow or failing curator never holds up a worker's next cycle.
        Requests coalesce: the curator always sees every record so far, and only the newest pending request is kept."""
        with LOCK:
            self.curate_pending = (cdir, entry)
            if getattr(self, 'curate_thread', None) is None:
                self.curate_thread = threading.Thread(target=self.curate_loop, daemon=True, name='curator')
                self.curate_thread.start()

    def curate_loop(self):
        while True:
            with LOCK:
                job, self.curate_pending = getattr(self, 'curate_pending', None), None
                if job is None:
                    self.curate_thread = None
                    return
            try:
                self.curate(*job)
            except Exception as e:  # noqa: BLE001 - curation is advisory; the records are already saved
                self.log(f'{job[0].name} curator error {e!r}')

    def curate(self, cdir, entry):
        with self.curate_lock:  # one curator at a time; it sees every record so far
            standing = {k: round(v['best']['eval']['proxy'], 2) for k, v in self.state['workers'].items()}
            seed = json.loads((self.dir / 'seed_dev.json').read_text())['proxy'] if (self.dir / 'seed_dev.json').exists() else None
            prompt = Template((MG / 'prompts/curator.md').read_text()).safe_substitute(
                limit=self.cfg.get('kb_chars', 9000), sections='\n'.join(f'## {s}' for s in SECTIONS),
                current=self.bank.synthesis(), all='\n'.join(line(e) for e in self.bank.entries()),
                record=json.dumps(entry, indent=1, default=float), seed_proxy=seed, standing=json.dumps(standing))
            text = self.final_text(self.agent(self.cfg['curator'], prompt, cdir, cdir / 'curate'))
            import re
            m = re.search(r'```(?:markdown|md)?\s*\n(.*?)```', text, re.S)
            if not self.bank.set_synthesis(m.group(1) if m else text, self.cfg.get('kb_chars', 9000)):
                self.log(f'{cdir.name} curator output rejected (malformed); kept previous synthesis')

    def maybe_plan(self):
        """Light planner: every `planner_every` finished cycles an agent (the curator model) rereads the accept/reject
        history of every board and rewrites plan.md: per-board priorities, lines to stop, mechanisms to try. Runs in a
        background thread; workers read the latest plan.md at ideation and never wait for it."""
        every = int(self.cfg.get('planner_every') or 0)
        if not every:
            return
        done = sum(len(v.get('history', [])) for v in self.state['workers'].values())
        with LOCK:
            due = done // every
            if due <= self.state.get('planned', 0) or getattr(self, 'plan_thread', None) and self.plan_thread.is_alive():
                return
            self.plan_thread = threading.Thread(target=self.plan, args=(due,), daemon=True, name='planner')
            self.plan_thread.start()

    def plan(self, n):
        pdir = self.dir / 'planner' / f'p{n:02d}'
        pdir.mkdir(parents=True, exist_ok=True)
        hist = '\n'.join(f"- {w} ({self.focus(w) or 'free'}): {o['title']} -> {o['verdict']} ({str(o['reason'])[:160]})"
                         for w, v in sorted(self.state['workers'].items()) for o in v.get('history', [])[-8:])
        bests = '\n'.join(f"- {w}: best {v['best']['id']} boards "
                          f"{json.dumps({k: round(x, 2) for k, x in v['best']['eval'].get('boards', {}).items()})}"
                          for w, v in sorted(self.state['workers'].items()))
        prev = (self.dir / 'plan.md').read_text() if (self.dir / 'plan.md').exists() else '(none)'
        prompt = (f"# Role: RUN PLANNER\nYou steer an autonomous research run on the Virtual Embryo Challenge. Read "
                  f"{self.dir / 'brief.md'} (the rules and evidence) and run `{PY} {MG / 'tools/leaderboard.py'} gaps <board>` "
                  f"for T1, heart, embryo and T3 (test-side headroom).\n\n## Worker bests\n{bests}\n\n## Recent cycles\n{hist}\n\n"
                  f"## Previous plan\n{prev}\n\nWrite the new plan as markdown (at most 350 words) to {pdir / 'plan.md'}: for each "
                  "board, (1) the one or two mechanisms most likely to move the TEST metrics, (2) lines to STOP (two or more "
                  "rejections, or gains that only fit the dev targets), (3) one concrete next experiment. Prefer mechanisms "
                  "that should hold at any stage. Do not invent results; cite cycle ids.")
        try:
            draft = pdir / 'plan.md'
            success = self.agent(self.cfg.get('planner') or self.cfg['curator'], prompt, pdir, pdir / 'plan',
                                 allowed=['Read', 'Grep', 'Glob', 'Write', f'Bash({PY}:*)'], add_dirs=[ROOT],
                                 fresh_output=draft)
            if success and draft.is_file() and (text := draft.read_text()).strip():
                write_text(self.dir / 'plan.md', text)
                with LOCK:
                    self.state['planned'] = n
                    self.save()
                self.log(f'planner p{n:02d} wrote plan.md')
        except Exception as e:  # noqa: BLE001 - planning is advisory
            self.log(f'planner p{n:02d} error {e!r}')

    def seed_worker_parents(self, seed_ws):
        """Start designated workers from a separately pinned board program."""
        for worker, source in self.cfg.get('worker_seed_sources', {}).items():
            state = self.state['workers'][worker]
            if state.get('starting_parent'):
                continue
            board = self.home_board(worker)
            root = self.dir / f'{worker}_starting_parent'
            workspace = root / 'ws'
            if not workspace.exists():
                shutil.copytree(seed_ws, workspace, ignore=shutil.ignore_patterns('__pycache__'))
                for path in self.board_files(workspace, board):
                    path.unlink()
                shutil.copyfile(ROOT / source, workspace / f'{board}_starting_model.py')
                write_text(workspace / f'{board}.py',
                           f'from {board}_starting_model import predict\n\n'
                           f'def predict_{board}(inputs, times, target_time, context):\n'
                           f'    return predict({board!r}, inputs, times, target_time, context)\n')
            ev = self.eval_scoped(workspace, dict(ws=str(seed_ws), eval=self.seed_eval), root / 'eval.json')
            if not ev.get('correct'):
                raise SystemExit(f'{worker} starting model failed dev evaluation: {ev.get("error")}')
            entry = dict(id=f'{worker}_starting_parent', ws=str(workspace), eval=ev, rank=ev['proxy'])
            state.update(starting_parent=entry, best=entry, elites=[entry])
            self.save()

    def seed_initial_elites(self):
        """cfg['initial_elites'] = {worker: [workspace, ...]}: accepted programs of an earlier run offered as extra
        parents (e.g. full5's heart line, whose holdout verdict was distorted by a target with surrounding tissue).
        Each is copied into the run, re-evaluated on THIS run's dev set, and enters the worker's elite archive by rank;
        if it beats the seed it becomes the worker's starting parent. Done once."""
        if self.state.get('initial_elites_done'):
            return
        for w, paths in (self.cfg.get('initial_elites') or {}).items():
            if w not in self.state['workers']:
                continue
            for k, src in enumerate(paths):
                dst = self.dir / f'init_{w}_{k}' / 'ws'
                if not dst.exists():
                    shutil.copytree(ROOT / src, dst, ignore=shutil.ignore_patterns('__pycache__', '*_evals', '.quick_eval_runs'))
                eval_path = dst.parent / 'eval.json'
                ev = self.eval_scoped(dst, dict(ws=str(self.dir / 'seed_ws'), eval=self.seed_eval), eval_path)
                if not ev.get('correct'):
                    self.log(f'initial elite {src} failed dev evaluation; skipped')
                    continue
                seed = dict(ws=str(self.dir / 'seed_ws'), eval=self.seed_eval)
                qualified, reason, stats = self.race(dst, ev, seed)
                if qualified:
                    rank = self.seed_eval['proxy'] + stats['proxy']['mean']
                    self.add_elite(w, dict(ws=str(dst), eval=ev, id=f'init_{w}_{k}', rank=rank))
                    with LOCK:
                        elite_id = f'init_{w}_{k}'
                        if not any(a['id'] == elite_id for a in self.state['accepted']):
                            self.state['accepted'].append(dict(id=elite_id, ws=str(dst), proxy=rank,
                                                               boards=ev['boards'], eval_path=str(eval_path)))
                    self.inherit_pairs(self.dir / 'seed_ws', dst)
                self.log(f'initial elite for {w}: {src} {"accepted" if qualified else "rejected"} ({reason})')
        self.state['initial_elites_done'] = True
        self.save()

    MONITOR_SEM = threading.Semaphore(1)

    def monitor_late(self, tag, ws, board):
        """Monitor only (never used for acceptance or selection, never shown to agents): run the late-anchor check
        (allowed E14.5+ data: Feulner hearts, Slide-seq sections, Qiu maturation direction) on an accepted heart/T1
        program in the background and append the result to <run>/monitor/late_anchor.jsonl."""
        if not self.cfg.get('monitor_late', True) or board not in ('heart', 'temporal'):
            return

        def job():
            with self.MONITOR_SEM:
                out = self.private_dir()
                j = out / f'{tag}_{board}.json'
                try:
                    subprocess.run([str(ROOT / '.venv/bin/python'), str(MG / 'tools/late_anchor_check.py'), str(ws),
                                    '--board', board, '--json', str(j)], cwd=ROOT, capture_output=True, timeout=fleet.remaining(self.research_deadline(), 1800))
                    res = json.loads(j.read_text()) if j.exists() else None
                except Exception as e:  # noqa: BLE001 - monitor only
                    res = dict(error=repr(e))
                with LOCK, (out / 'late_anchor.jsonl').open('a') as f:
                    f.write(json.dumps(dict(t=time.time(), id=tag, board=board, result=res), default=float) + '\n')
        threading.Thread(target=job, daemon=True).start()

    def too_slow(self, ev):
        """Runtime gate: a split may take at most max(slow_floor_s, max_slowdown x the seed's time). Slow programs make
        every paired test slow (a 2x-slower T1 program took a 90-minute paired test in full5)."""
        if self.cfg.get('max_slowdown') is None:
            return None
        factor, floor = float(self.cfg['max_slowdown']), float(self.cfg.get('slow_floor_s', 240))
        base = (getattr(self, 'seed_eval', None) or {}).get('splits', {})
        for s, r in (ev.get('splits') or {}).items():
            # CPU seconds when both sides have them (independent of fleet-host load), else wall-clock seconds
            key = 'cpu_seconds' if r.get('cpu_seconds') and (base.get(s) or {}).get('cpu_seconds') else 'seconds'
            t, b = r.get(key), (base.get(s) or {}).get(key)
            if t and b and t > max(floor, factor * b):
                return (f'{s} took {t:.0f} {key} vs the seed {b:.0f} (limit {max(floor, factor * b):.0f}); '
                        'make predict() faster (fewer cells/genes in fitting, vectorise, fewer iterations)')
        return None

    @staticmethod
    def severity_note(ev):
        """T3 response-size gate, from the evaluator's all-cell diagnostic (severity is exactly 50 below it)."""
        parts = []
        for s, r in sorted((ev.get('splits') or {}).items()):
            d = r.get('severity') or {}
            if 'r2' in d:
                parts.append(f"{s} β {d['beta']:.3g} R² {d['r2']:.2f} mag {d['magnitude_ratio']:.2f}"
                             f"{' OPEN' if d['gate_open'] else ''}")
        return ('severity gate (β>0 & R²>0.01): ' + '; '.join(parts)) if parts else ''

    def claim_cycle(self, w):
        """Work-stealing: the run has a shared budget of workers x cycles_per_worker cycles. A worker keeps taking
        cycles on its own board while budget remains (at most max_cycles_factor x cycles_per_worker), so fast
        boards are not left idle while a slow board finishes."""
        with LOCK:
            ws = self.state['workers']
            st = ws[w]
            total = self.cfg['workers'] * self.cfg['cycles_per_worker']
            cap = int(self.cfg.get('max_cycles_factor', 1.5) * self.cfg['cycles_per_worker'])
            cap = min(cap, self.cfg.get('worker_cycle_caps', {}).get(w, cap))
            board = self.home_board(w)
            board_cap = self.cfg.get('board_cycle_caps', {}).get(board)
            if board_cap is not None:
                claimed = sum(x['cycle'] + int(self.inflight.get(k) == x['cycle'])
                              for k, x in ws.items() if self.home_board(k) == board)
                if claimed >= board_cap:
                    return False
            floor = self.cfg.get('min_cycles_per_worker', 0)
            cycles = {k: x['cycle'] + int(self.inflight.get(k) == x['cycle']) for k, x in ws.items()}
            reserved = sum(max(0, floor - cycles[k]) for k in ws if k != w)
            deadline = self.research_deadline()
            expired = deadline is not None and time.time() >= deadline - self.cfg.get('cycle_drain_seconds', 0)
            no_new = self.at(self.cfg.get('no_new_cycles_at'))
            expired = expired or (no_new is not None and time.time() >= no_new)
            stale = st.get('stale', 0) >= self.cfg['patience_cycles'] and st['cycle'] >= floor
            if self.stop or expired or stale or st['cycle'] >= cap or sum(cycles.values()) + reserved >= total:
                return False
            self.inflight[w] = st['cycle']
            return True

    def worker(self, w):
        while self.claim_cycle(w):
            try:
                self.cycle(w, self.state['workers'][w]['cycle'])
            except (TimeoutError, subprocess.TimeoutExpired):
                deadline = self.research_deadline()
                if deadline is None or time.time() < deadline:
                    raise
                self.log(f'{w} stopped at the research wall-clock deadline')
                return
            except SystemExit:
                raise
            except Exception as e:  # noqa: BLE001 - keep the run alive
                self.log(f'{w} cycle error {e!r}')
                if 'budget exhausted' in str(e):
                    self.stop = True
                    return
                st = self.state['workers'][w]
                st['errors'] = st.get('errors', 0) + 1
                if st['errors'] >= 3 or not self.cfg.get('survive_cycle_errors', False):
                    self.stop = True
                    raise
                i = st['cycle']
                cdir = self.dir / 'cycles' / f'{w}_c{i:02d}'
                try:
                    if not (cdir / 'outcome.json').exists():
                        self.finish(w, cdir, dict(title='(harness error)', verdict='skipped', reason=f'harness error {e!r}'[:400]))
                except Exception as e2:  # noqa: BLE001
                    self.log(f'{w} could not close the failed cycle: {e2!r}')
                    self.stop = True
                    raise
                continue
            else:
                self.state['workers'][w]['errors'] = 0
            finally:
                with LOCK:
                    self.inflight.pop(w, None)

    # ---------- main ----------
    def run(self):
        try:
            self._run()
        except (TimeoutError, subprocess.TimeoutExpired):
            deadline = self.research_deadline()
            if deadline is None or time.time() < deadline:
                raise
            self.state['phase'] = 'awaiting_holdout'
            self.save()
            self.log('Research wall-clock deadline reached; ready for finalization.')

    def _run(self):
        if self.final_only:
            if self.state.get('phase') not in ('awaiting_holdout', 'final', 'done'):
                raise SystemExit('research must finish before finalization')
        else:
            if not self.cfg.get('research_enabled', True):
                raise SystemExit('research is disabled pending an isolated execution environment')
            if self.state.get('phase') in ('awaiting_holdout', 'final', 'done'):
                self.log(f"research already finished (phase {self.state['phase']})")
                return
            present = [r for r in self.holdout_files() if (ROOT / r).exists()]
            if present:
                raise SystemExit(f'refusing to start agents: held-out data is decrypted ({present[0]}); wipe it first')
            if self.cfg.get('sandbox', True):
                from agentic_scientist.sandbox import probe
                pr = probe(self.dir)
                write_json(self.dir / 'sandbox_probe.json', pr)
                if not pr['ok']:
                    raise SystemExit(f'sandbox probe failed: {pr}')
            self.state.setdefault('research_started', time.time())
            self.save()
            fleet.remaining(self.research_deadline(), 1)
            write_text(self.dir / 'brief.md', self.render_brief())
        seed_ws = self.dir / 'seed_ws'
        if not seed_ws.exists():
            shutil.copytree(ROOT / self.cfg.get('seed_dir', 'agentic_scientist/seed'), seed_ws,
                            ignore=shutil.ignore_patterns('__pycache__'))
        seed_eval_path = self.dir / 'seed_dev.json'
        seed_eval = self.evaluate_cached(seed_ws, 'dev', seed_eval_path)
        if not seed_eval.get('correct'):
            raise SystemExit(f'seed program fails dev evaluation: {seed_eval.get("error")}')
        self.log(f'seed dev proxy {seed_eval["proxy"]:.2f}')
        self.seed_eval, self.inflight = seed_eval, {}
        for k in range(self.cfg['workers']):
            self.state['workers'].setdefault(f'w{k}', dict(best=dict(ws=str(seed_ws), eval=seed_eval, id='seed'),
                                                           cycle=0, fails=0, history=[],
                                                           elites=[dict(ws=str(seed_ws), eval=seed_eval, id='seed', rank=seed_eval['proxy'])]))
        if not self.final_only:
            if not (self.private_dir() / 'holdout.jsonl').exists():
                for b in ('heart', 'temporal'):
                    self.monitor_late('seed', seed_ws, b)
                for b in self.BOARDS:
                    self.private_holdout('seed', seed_ws, b, dict(verdict='seed'))
            self.seed_worker_parents(seed_ws)
            boards = (set(self.BOARDS) - {'temporal'} if self.cfg.get('require_calibrated_final')
                      and self.cfg.get('t1_research_only', True) else None)
            self.prefetch_parent(seed_ws, seed_eval, boards)
            self.seed_initial_elites()
        if self.state['global_best'] is None:
            self.state['global_best'] = seed_eval['proxy']
        self.save()
        if not self.final_only:
            self.checkpoint_loop()
            self.leaderboard_loop()
            with ThreadPoolExecutor(self.cfg['workers']) as pool:
                list(pool.map(self.worker, list(self.state['workers'])))
            t = getattr(self, 'curate_thread', None)
            if t is not None:  # let the last curation finish (no orphaned curator agent)
                t.join(timeout=2 * self.cfg['curator'].get('timeout_s', 900) + 120)
            t = getattr(self, 'plan_thread', None)
            if t is not None:  # and the last plan (it is part of the run's record)
                t.join(timeout=(self.cfg.get('planner') or self.cfg['curator']).get('timeout_s', 900) + 120)
            if self.cfg.get('tune') and not self.cfg['tune'].get('on_demand') and not self.state.get('tuned_done'):
                try:
                    self.tune_phase()
                except Exception as e:  # noqa: BLE001 - a failed tuning phase must not lose the run
                    self.log(f'tune error {e!r}')
                self.state['tuned_done'] = True
                self.save()
            if self.cfg.get('merge', True) and not self.state.get('merged'):
                try:
                    self.merge(seed_ws)
                except Exception as e:  # noqa: BLE001 - a failed merge must not lose the run
                    self.log(f'merge error {e!r}')
                self.state['merged'] = True
                self.save()
        if not self.final_only and self.cfg.get('separate_final'):
            self.state['phase'] = 'awaiting_holdout'
            self.save()
            self.log('research phase complete; selection runs in the private finalization process')
            return
        missing = self.holdout_missing()
        if missing:  # phase 1 ends here: no agent may run while held-out data exists in plaintext
            if self.final_only:
                raise SystemExit(f'finalization requires decrypted holdout input: {missing[0]}')
            self.state['phase'] = 'awaiting_holdout'
            self.save()
            self.log(f'research phase complete; held-out data is encrypted ({len(missing)} files absent). '
                     f'Run: agentic_scientist/final.sh <lock> <run-name> [config] to decrypt and select.')
            return
        self.state['phase'] = 'final'
        self.save()
        try:
            self.final(seed_ws, seed_eval)
        except BaseException:
            self.state['phase'] = 'awaiting_holdout'
            self.save()
            raise
        self.state['phase'] = 'done'
        self.save()
        if self.cfg.get('final_export'):
            self.final_export()

    def reset_tuned(self, parent_ws, ws):
        """Tuned knob values are set by the harness only: a candidate's <board>_tuned.json files are the parent's."""
        from agentic_scientist import tune
        for b in self.BOARDS:
            tune.restore_tuned(parent_ws, ws, b)

    @staticmethod
    def fleet_size():
        f = ROOT / 'shinka_ve/fleet_hosts.txt'
        return max(2, sum(1 for x in f.read_text().splitlines() if x.strip() and not x.lstrip().startswith('#')))

    @staticmethod
    def tune_summary(cdir):
        f = Path(cdir) / 'tune' / 'tune.json'
        if not f.exists():
            return None
        r = json.loads(f.read_text())
        return dict(board=r.get('board'), improved=r.get('improved'), current=r.get('current'), chosen=r.get('chosen'),
                    gain=r.get('gain'), gain_se=r.get('gain_se'), settings=len(r.get('trials', [])), reason=r.get('reason'))

    def maybe_tune(self, w, cdir, ws, parent, ev):
        """On-demand knob tuning (agentic_scientist/tune.py). Deterministic trigger: the candidate's <board>_knobs.json is new or
        differs from the spec its <board>_tuned.json was tuned for. Runs on the whole fleet before the race; the outcome
        (chosen or kept values) goes to <board>_tuned.json, the candidate is re-screened with it, and the ordinary
        paired race against the parent decides."""
        from agentic_scientist import tune
        T = self.cfg.get('tune') or {}
        changed = self.diff_boards(parent['ws'], ws)
        board = next(iter(changed)) if changed and len(changed) == 1 else self.home_board(w)
        if not T.get('on_demand') or board not in T.get('boards', tune.TUNABLE_BOARDS):
            return ev
        try:
            if not tune.needs_tuning(ws, board):
                return ev
            tune.read_knobs(ws, board)
        except (ValueError, KeyError, TypeError) as e:
            self.log(f'{cdir.name} tune: invalid {board}_knobs.json ({e}); the program runs with its defaults')
            return ev
        cap = T.get('max_tunes', 24)
        with LOCK:
            used = self.state.setdefault('tunes', [])
            if cdir.name not in used and len(used) >= cap:
                self.log(f'{cdir.name} tune: all {cap} tunings of this run used; the program runs with its current values')
                return ev
            if cdir.name not in used:
                used.append(cdir.name)
        par = T.get('parallel', 'fleet')
        par = self.fleet_size() if par == 'fleet' else int(par)
        ev_fn = lambda ws_, out, ps, fs, sp: self.evaluate(ws_, 'dev', out, pred_seed=ps, fit_seed=fs, splits=sp)  # noqa: E731
        t0 = time.time()
        self.log(f'{cdir.name} tune {board}: knobs {list(tune.read_knobs(ws, board))}, {par} settings per round on the fleet')
        res = tune.Tuner(ws, board, self.board_splits('dev', [board]), cdir / 'tune', ev_fn, self.log,
                         rounds=T.get('rounds', 3), parallel=par, top=T.get('top', 3),
                         seed=T.get('seed', 0), eval_revision=self.eval_revision).run()
        tune.write_tuned(ws, board, res['chosen'], tuned_by=cdir.name, improved=res['improved'],
                         gain=res.get('gain'), gain_se=res.get('gain_se'))
        self.log(f"{cdir.name} tune {board}: {'adopted' if res['improved'] else 'kept'} {res['chosen']} "
                 f"({len(res['trials'])} settings, {time.time() - t0:.0f}s); re-screening")
        self.save()
        return self.eval_scoped(ws, parent, cdir / 'eval.json')

    def tune_phase(self):
        """After the research cycles: tune the declared knobs of each worker's best T1/heart program (agentic_scientist/tune.py),
        then accept the tuned version only through the ordinary paired test against the untuned program."""
        from agentic_scientist import tune
        from agentic_scientist.evaluate import SETS
        T = self.cfg['tune']
        boards = [b for b in T.get('boards', tune.TUNABLE_BOARDS) if b in tune.TUNABLE_BOARDS]
        self.state.setdefault('tuned', {})
        for w in sorted(self.state['workers']):
            board = self.home_board(w)
            st = self.state['workers'][w]
            if board not in boards or w in self.state['tuned'] or st['best']['id'] == 'seed':
                continue
            parent = st['best']
            try:
                knobs = tune.read_knobs(parent['ws'], board)
            except ValueError as e:
                self.log(f'tune {w}: {e}')
                self.state['tuned'][w] = dict(status='bad knob file', error=str(e))
                continue
            if not knobs:
                self.state['tuned'][w] = dict(status='no knobs declared')
                continue
            tdir = self.dir / 'cycles' / f'{w}_tune'
            splits = tune.board_splits(SETS['dev']['splits'], harness_splits(), board)
            ev_fn = lambda ws, out, ps, fs, sp: self.evaluate(ws, 'dev', out, pred_seed=ps, fit_seed=fs, splits=sp)  # noqa: E731
            cand = tdir / 'tuned_ws'
            shutil.rmtree(cand, ignore_errors=True)
            shutil.copytree(parent['ws'], cand, ignore=shutil.ignore_patterns('__pycache__', '*_evals', '.quick_eval_runs'))
            par = T.get('parallel', 'fleet')
            res = tune.Tuner(cand, board, splits, tdir, ev_fn, self.log, rounds=T.get('rounds', 3),
                             parallel=self.fleet_size() if par == 'fleet' else int(par), top=T.get('top', 3),
                             seed=T.get('seed', 0)).run()
            if res['improved']:
                tune.write_tuned(cand, board, res['chosen'], tuned_by=f'{w}_tune', gain=res.get('gain'))
            else:
                self.state['tuned'][w] = dict(status='defaults kept')
                self.save()
                continue
            ev = self.evaluate(cand, 'dev', tdir / 'eval.json')
            ok, reason, stats = self.race(cand, ev, parent)
            gain = stats['proxy']['mean'] if stats else 0.0
            self.log(f"{w}_tune {'accepted' if ok else 'rejected'} {reason} :: tuned {board} knobs")
            self.state['tuned'][w] = dict(status='accepted' if ok else 'rejected', reason=reason, ws=str(cand))
            if ok:
                self.add_elite(w, dict(ws=str(cand), eval=ev, id=f'{w}_tune', rank=parent['eval']['proxy'] + gain))
                self.state['accepted'].append(dict(id=f'{w}_tune', ws=str(cand), proxy=parent['eval']['proxy'] + gain,
                                                   boards=ev.get('boards')))
            self.save()

    def merge(self, seed_ws):
        """Combine the accepted improvements of different workers into one program (e.g. one improved heart, another
        T3). Base = the best worker program; the other workers' changes (diff vs the seed) are ported onto it by an
        implementer, then the merge must pass the same paired test against the base."""
        bests = [v['best'] for v in self.state['workers'].values() if v['best']['id'] != 'seed']
        uniq = {b['ws']: b for b in bests}
        if len(uniq) < 2:
            self.log('merge: fewer than two distinct worker improvements; skipped')
            return
        base, *others = sorted(uniq.values(), key=lambda b: -b['eval']['proxy'])
        mdir = self.dir / 'cycles' / 'merge'
        ws = mdir / 'ws'
        if ws.exists():
            shutil.rmtree(ws)
        mdir.mkdir(parents=True, exist_ok=True)
        shutil.copytree(base['ws'], ws, ignore=shutil.ignore_patterns('__pycache__', '.quick_eval_runs'))
        parts = '\n\n'.join(f"### Changes of {o['id']} (dev {o['eval']['proxy']:.2f}; boards {json.dumps({k: round(v, 2) for k, v in o['eval']['boards'].items()})}), diff vs the seed\n{self.diff(seed_ws, o['ws'])}" for o in others)
        prompt = (f"# Role: MERGER\nWorkspace {ws} holds the best program ({base['id']}, dev {base['eval']['proxy']:.2f}, boards "
                  f"{json.dumps({k: round(v, 2) for k, v in base['eval']['boards'].items()})}). Other workers improved other boards. "
                  f"Port their changes into this workspace so that every board keeps its best behaviour. Where two changes touch the "
                  f"same board, keep the base's version. Do not invent new methods. Keep predict()'s contract. You may run "
                  f"`cd {ws} && {ROOT}/.venv/bin/python {ROOT}/agentic_scientist/tools/quick_eval.py <dev split>` (max 3 runs). "
                  f"Finish with a one-paragraph summary.\n\n{parts}")
        self.agent(self.pick_implementer(), prompt, ws, mdir / 'implement')
        hits = self.audit(mdir)
        if hits:
            self.log(f'merge disqualified: {hits[0]}')
            return
        ev = self.evaluate(ws, 'dev', mdir / 'eval.json')
        parent = dict(ws=base['ws'], eval=base['eval'])
        ok, reason, stats = self.race(ws, ev, parent)
        outcome = dict(title='merge of worker improvements', verdict='accepted' if ok else 'rejected', reason=reason, stats=stats,
                       proxy=base['eval']['proxy'] + stats['proxy']['mean'] if stats else ev.get('proxy'),
                       boards=ev.get('boards'), parent_proxy=base['eval']['proxy'], ws=str(ws))
        (mdir / 'outcome.json').write_text(json.dumps(outcome, indent=1, default=float))
        self.log(f"merge {outcome['verdict']} {reason}")
        if ok:
            self.state['accepted'].append(dict(id='merge', ws=str(ws), proxy=outcome['proxy'], boards=outcome['boards']))

    BOARDS = ('temporal', 'heart', 'embryo', 'perturbation')

    @staticmethod
    def forked(ws):
        p = Path(ws) / 'program.py'
        return p.exists() and 'Frozen dispatcher' in p.read_text()

    def role_prompt(self, role):
        path = self.cfg.get('prompt_overrides', {}).get(role, f'agentic_scientist/prompts/{role}.md')
        return Template((ROOT / path).read_text())

    def render_brief(self):
        lines = []
        for i in range(self.cfg['workers']):
            w = f'w{i}'
            boards = self.worker_boards(w) or ['free choice']
            lines.append(f"- {w} — " + ' → '.join(boards))
        template = (ROOT / self.cfg.get('brief', 'agentic_scientist/prompts/brief.md')).read_text()
        roles = self.cfg.get('ideator_cycle') or [self.cfg['ideator']]
        models = ', '.join(r['model'] for r in roles)
        return template.replace('$assignments', '\n'.join(lines)).replace('$researchers', models)

    def focus(self, w):
        """The worker's own task; after 2/3 of the cycles a worker stuck for 3+ cycles may help on any one task."""
        f = (self.cfg.get('focus') or {}).get(w)
        st = self.state['workers'][w]
        if isinstance(f, list):  # per-cycle schedule, e.g. ["embryo", "temporal"]: cycle 0 embryo, then temporal
            f = f[min(st['cycle'], len(f) - 1)] if f else None
        if (f and self.cfg.get('free_roam', True) and st['cycle'] >= 2 * self.cfg['cycles_per_worker'] // 3
                and st['fails'] >= 3):
            return None
        return f

    def worker_boards(self, w):
        f = (self.cfg.get('focus') or {}).get(w)
        return None if not f else ([f] if isinstance(f, str) else list(f))

    def home_board(self, w):
        """The worker's main board (the last entry of a per-cycle focus schedule)."""
        f = (self.cfg.get('focus') or {}).get(w)
        return (f[-1] if f else None) if isinstance(f, list) else f

    def focus_text(self, w):
        f = self.focus(w)
        if f:
            note = (self.cfg.get('directives') or {}).get(w, {})
            note = note.get(f, '') if isinstance(note, dict) else note
            if isinstance(note, list):  # per-cycle schedule: build cycles first, the last entry for every later cycle
                note = note[min(self.state['workers'][w]['cycle'], len(note) - 1)] if note else ''
            return (f"YOUR TASK: you own the **{f}** board. Change only `{f}.py` and `{f}_*.py` in the workspace "
                    f"(other boards are owned by other workers; edits outside your files are rejected automatically)."
                    + (f"\n\nYOUR DIRECTION THIS CYCLE: {note}" if note else ''))
        return ("YOUR TASK: free choice. Your own board has stalled, so pick the board with the most recoverable headroom. "
                "Change the files of exactly ONE board (`<board>.py`, `<board>_*.py`).")

    def scope(self, w, parent_ws, ws):
        """Per-task layout rule: a candidate changes the files of exactly one board (its owner's), never program.py,
        and never imports another board's files. Keeps the dev combiner exact."""
        import re
        if not self.forked(parent_ws):
            return None
        for path in Path(ws).iterdir():
            if path.is_symlink() or (not path.is_file() and path.name != '__pycache__'):
                return f'workspace artifacts must be flat regular files: {path.name}'
        if (Path(ws) / 'tuned_params.json').exists():
            return 'shared tuned_params.json is unsupported in board-scoped programs'
        a, b = workspace_manifest(parent_ws), workspace_manifest(ws)
        changed = [n for n in sorted(a.keys() | b.keys()) if a.get(n) != b.get(n)]
        if 'program.py' in changed:
            return 'program.py (the frozen dispatcher) was edited'
        owner = lambda n: next((b for b in self.BOARDS if n == f'{b}.py' or n.startswith(f'{b}_')), None)  # noqa: E731
        stray = [n for n in changed if '/' in n or owner(n) is None]
        if stray:
            return f'files must be named <board>.py or <board>_*.py: {stray}'
        touched = {owner(n) for n in changed}
        if len(touched) > 1:
            return f'changes span several boards {sorted(touched)}; one board per candidate'
        f = self.focus(w)
        if f and touched and touched != {f}:
            return f'out of scope: worker owns {f}, changed {sorted(touched)}'
        for n in changed:
            if (Path(ws) / n).exists() and n.endswith('.py'):
                for b in self.BOARDS:
                    if b != owner(n) and re.search(rf'^\s*(from|import)\s+{b}(_\w+)?\b', (Path(ws) / n).read_text(), re.M):
                        return f'{n} imports another board\'s code ({b})'
        return None

    def board_means(self, ws, first_eval):
        """Mean of cached confirmation pairs, with the screen score as a display fallback."""
        if not (first_eval and first_eval.get('correct')):
            return {}
        cache = Path(str(ws) + '_evals')
        manifest = workspace_manifest(ws)
        seed_ws = self.dir / 'seed_ws'
        same_as_seed = set()
        if Path(ws).resolve() != seed_ws.resolve():
            d = self.diff_boards(seed_ws, ws)
            same_as_seed = set(self.BOARDS) - d if d is not None else set()
        seed_bm = self.board_means(seed_ws, self.seed_eval) if same_as_seed and getattr(self, 'seed_eval', None) else {}
        out = {}
        for b, v0 in first_eval['boards'].items():
            if b in same_as_seed and b in seed_bm:
                out[b] = seed_bm[b]
                continue
            vals = []
            for j in range(1, len(self.SEED_PAIRS)):
                e = read_cached(cache / f'pair{j}_{b}.json', self.pair_key(manifest, b, j))
                if e:
                    vals.append(e['boards'][b])
            out[b] = sum(vals) / len(vals) if vals else v0
        return out

    @staticmethod
    def candidate_eval_path(candidate):
        if 'eval_path' in candidate:
            return Path(candidate['eval_path'])
        directory = Path(candidate['ws']).parent
        path = directory / 'eval.json'
        return directory / 'dev.json' if candidate['id'].startswith('init_') and not path.exists() else path

    def rank_boards(self, seed_ws, seed_eval):
        """Rank distinct board programs by their gain over the same seed and dev pairs."""
        base = self.board_means(seed_ws, seed_eval)
        ranked = {b: [] for b in base}
        for candidate in self.state['accepted']:
            changed = self.diff_boards(seed_ws, candidate['ws'])
            if not changed:
                continue
            ev = json.loads(self.candidate_eval_path(candidate).read_text())
            means = self.board_means(candidate['ws'], ev)
            for board in sorted(changed & base.keys()):
                if means[board] > base[board]:
                    ranked[board].append((candidate, means[board]))
        for board, options in ranked.items():
            distinct = {}
            for candidate, score in sorted(options, key=lambda entry: (-entry[1], entry[0]['id'])):
                files = workspace_manifest(candidate['ws'])
                key = digest({n: v for n, v in files.items() if self.board_of(n) == board})
                distinct.setdefault(key, (candidate, score))
            ranked[board] = list(distinct.values())
        return ranked

    def per_board(self, rows, fdir, n_pairs):
        """Select only improvements whose paired lower bound clears the frozen margin."""
        seed = rows[0]
        margin = self.cfg.get('holdout_margin', 0.0)
        alpha = self.cfg['acceptance']['alpha']
        def read(row):
            return [json.loads((fdir / f"holdout_{row['id']}_pair{j}.json").read_text()) for j in range(n_pairs)]
        baseline = read(seed)
        passing = {}
        for row in rows[1:]:
            if row.get('holdout') is None:
                continue
            changed = self.diff_boards(seed['ws'], row['ws'])
            if not changed:
                continue
            stats = self.paired_stats(read(row), baseline, alpha)
            for board in sorted(changed & seed['holdout_boards'].keys()):
                result = stats[board]
                if result['lb'] <= margin or not math.isfinite(result['lb']):
                    continue
                guard = self.guard_ok(row, seed, board, fdir)
                if guard is not True:
                    self.log(f"final: {row['id']} {board} fails the hidden guard: {guard}")
                    continue
                passing.setdefault(board, {})[row['id']] = (row, result)
        picks = {}
        tol = float(self.cfg.get('ablation_tol', 0.25))
        parents = self.state.get('parent') or {}
        for board, eligible in passing.items():
            row, result = min(eligible.values(), key=lambda entry: (-entry[1]['mean'], entry[0]['id']))
            ancestor = parents.get(row['id'])
            while ancestor:
                if ancestor in eligible and result['mean'] - eligible[ancestor][1]['mean'] < tol:
                    self.log(f"final: ablation keeps {ancestor} over {row['id']} on {board}")
                    row, result = eligible[ancestor]
                ancestor = parents.get(ancestor)
            picks[board] = row, result
        return picks

    def guard_ok(self, row, seed, board, fdir):
        """Hidden guard (new released-stage targets no dev split predicts; never shown to workers): a T2 board change
        must not lose there versus the seed: mean >= -guard_mean and one-sided 90% lower bound >= -guard_lb."""
        from agentic_scientist.evaluate import GUARD
        G = self.cfg.get('guard') or {}
        if not G or board not in GUARD or board not in G.get('boards', list(GUARD)):
            return True
        pairs = G.get('pairs', [[301, 0], [302, 1], [303, 2], [304, 3]])
        def run(r):
            out = []
            for j, (ps, fs) in enumerate(pairs):
                p = fdir / f"guard_{r['id']}_{board}_pair{j}.json"
                e = self.evaluate_cached(r['ws'], 'guard', p, (ps, fs), GUARD[board])
                if not e.get('correct'):
                    return None
                out.append(e)
            return out
        c, s = run(row), run(seed)
        if c is None or s is None:
            return 'guard evaluation failed'
        st = self.paired_stats(c, s, 0.10)[board]
        ok = st['mean'] >= -G.get('mean', 0.25) and st['lb'] >= -G.get('lb', 0.5)
        return True if ok else f"mean {st['mean']:+.2f}, 90% lb {st['lb']:+.2f}"


    def unseen_veto(self, board, ranked, seed_ws, fdir, top=4):
        """T3 has no holdout split that selects; an unseen knockout gene (SETS['holdout_t3']) can only VETO.
        The dev-ranked T3 candidates (best first; at most `top`, one per distinct T3 code) are scored on it against the
        seed over the holdout seed pairs; a candidate whose mean paired loss is > 0.5 and > 2 SE is dropped."""
        from agentic_scientist.evaluate import SETS, harness as H
        if board != 'perturbation' or 'holdout_t3' not in SETS:
            yield from ranked
            return
        if not ranked:
            return
        missing = [s for s in SETS['holdout_t3']['splits'] if s not in H.SPLITS]  # spec not decrypted
        missing += [f for s in SETS['holdout_t3']['splits'] if s in H.SPLITS
                    for f in H.SPLITS[s]['inputs'] + [H.SPLITS[s]['target']] if not (ROOT / 'data/raw' / f).exists()]
        if missing:  # AgenticScientist final: no unseen-gene T3 data on this host; dev ranking decides
            self.log(f'final: T3 unseen-gene veto unavailable ({missing[0]}); dev-ranked T3 pick without veto')
            yield from ranked
            return
        pairs = self.cfg.get('holdout_seed_pairs', [[202, 0], [313, 1], [424, 2]])[:3]
        same = lambda a, b: (lambda d: d is not None and board not in d)(self.diff_boards(a, b))  # noqa: E731
        uniq = []
        for acc, v in ranked:  # one per distinct T3 code, best dev first
            if not any(same(acc['ws'], o['ws']) for o, _ in uniq):
                uniq.append((acc, v))
            if len(uniq) >= top:
                break

        def score(tag, ws):
            def one(j):
                p = fdir / f'unseen_{tag}_pair{j}.json'
                return self.evaluate_cached(ws, 'holdout_t3', p, pairs[j])
            with ThreadPoolExecutor(len(pairs)) as pool:
                return list(pool.map(one, range(len(pairs))))
        base = score('seed', seed_ws)
        if not all(e.get('correct') for e in base):
            raise RuntimeError('final: T3 veto could not establish a valid seed score')
        report = {}
        for acc, v in uniq:
            evs = score(acc['id'], acc['ws'])
            if not all(e.get('correct') for e in evs):
                report[acc['id']] = 'error (vetoed)'
                continue
            d = [c['boards'][board] - p['boards'][board] for c, p in zip(evs, base)]
            m = sum(d) / len(d)
            se = ((sum((x - m) ** 2 for x in d) / max(len(d) - 1, 1)) ** .5) / len(d) ** .5
            veto = m < -.5 and m < -2 * se
            report[acc['id']] = f"dev {v:.2f}, unseen gene {m:+.2f} ± {se:.2f}{' VETO' if veto else ''}"
            self.state.setdefault('unseen_gene', {})[acc['id']] = dict(dev=v, gain=m, se=se, veto=veto)
            if not veto:
                self.log(f'final: unseen-gene T3 check {report}')
                yield acc, v
                return
        self.log(f'final: unseen-gene T3 check {report}; no candidate passed, using the seed')

    def critic(self, w, kind):
        v = self.cfg.get(f'critic_{kind}', 'default')
        if v is False:
            return None
        return v if isinstance(v, dict) else self.role(w, 'critic')

    def role(self, w, name):
        """Stagger the ideator cycle across workers, with legacy model arms as a fallback."""
        schedule = self.cfg.get('ideator_cycle')
        if name == 'ideator' and schedule:
            cycle = self.state['workers'][w]['cycle']
            return schedule[(cycle + int(w[1:])) % len(schedule)]
        return (self.cfg.get('arms') or {}).get(w, {}).get(name) or self.cfg[name]

    @staticmethod
    def lessons():
        p = ROOT / 'agentic_scientist/library/lessons.md'
        return p.read_text() if p.exists() else '(none)'

    @staticmethod
    def library():
        lib = ROOT / 'agentic_scientist/library'
        g = (lib / 'global.md').read_text() if (lib / 'global.md').exists() else '(no synthesis yet)'
        es = [json.loads(l) for l in (lib / 'entries.jsonl').read_text().splitlines() if l.strip()] if (lib / 'entries.jsonl').exists() else []
        keep = [e for e in es if e.get('source') == 'agentic_scientist' or e.get('status') in ('promising', 'negative')]
        from agentic_scientist.knowledge import line
        les = (lib / 'lessons.md').read_text() if (lib / 'lessons.md').exists() else ''
        return les + '\n\n' + g[:6000] + '\n\n### Selected records\n' + '\n'.join(line(e) for e in keep[-40:])

    @staticmethod
    def holdout_files():
        man = ROOT / 'data/holdout.enc/manifest.tsv'
        rows = [l.split('\t') for l in man.read_text().splitlines()] if man.exists() else []
        return [r[0] for r in rows if r[0].startswith('data/raw/')]

    def holdout_missing(self):
        files = self.holdout_files()
        if self.cfg.get('require_calibrated_final'):
            files = [p for p in files if p.startswith('data/raw/T3/')]
        return [r for r in files if not (ROOT / r).exists()]

    def calibrated_t3(self, options, seed_ws, fdir):
        """Filter promotions against the test-scored T3 seed on registered calibrated splits."""
        checks = self.cfg.get('calibrated_t3_splits', [])
        if not checks:
            return []
        report_path = 'agentic_scientist/checks/next_calibration.json'
        if self.lock['files'].get(report_path) != file_sha(ROOT / report_path):
            raise RuntimeError('T3 calibration report is missing from the lock or has changed')
        report = json.loads((ROOT / report_path).read_text())
        if any(report.get(split, {}).get('ordering') != 'passes' or
               report[split]['board'] != 'perturbation' or report[split]['set'] != 'dev' for split in checks):
            raise RuntimeError('unqualified T3 selection check')
        reference_ws = ROOT / self.cfg.get('calibrated_t3_baseline_workspace', seed_ws)
        manifest = workspace_manifest(reference_ws)
        files = {name: sha for name, sha in manifest.items() if self.board_of(name) == 'perturbation'}
        if digest(files) != self.cfg.get('calibrated_t3_baseline_sha256'):
            raise RuntimeError('T3 reference differs from the test-scored program')
        baseline = dict(id='reference', ws=reference_ws)
        def replays(candidate):
            return [self.evaluate_cached(candidate['ws'], 'dev',
                                         fdir / f"calibrated_{candidate['id']}_{j}.json", pair, checks)
                    for j, pair in enumerate(self.cfg['holdout_seed_pairs'])]
        refs = replays(baseline)
        if any(not result.get('correct') for result in refs):
            raise RuntimeError('failed to replay the T3 baseline')
        eligible = []
        for candidate, _ in options:
            results = replays(candidate)
            if any(not result.get('correct') for result in results):
                continue
            stats = self.paired_stats(results, refs, self.cfg['acceptance']['alpha'])
            bound = stats['perturbation']['lb']
            if math.isfinite(bound) and bound > self.cfg['holdout_margin']:
                eligible.append((candidate, stats['perturbation']['mean']))
        return sorted(eligible, key=lambda entry: (-entry[1], entry[0]['id']))

    def final_calibrated(self, seed_ws, fdir, ranked, forked):
        if not forked:
            raise RuntimeError('calibrated final requires board-scoped workspaces')
        if (self.cfg.get('t1_composition_veto', True)
                and not self.evaluate(seed_ws, 'composition', fdir / 'seed_composition.json').get('plausible')):
            raise RuntimeError('T1 seed failed the test-configuration composition veto')
        options = self.calibrated_t3(ranked.get('perturbation', []), seed_ws, fdir)
        reference = ROOT / self.cfg.get('calibrated_t3_baseline_workspace', seed_ws)
        winner = next(self.unseen_veto('perturbation', options, reference, fdir), None)
        selected = fdir / 'selected'
        shutil.rmtree(selected, ignore_errors=True)
        shutil.copytree(seed_ws, selected, ignore=shutil.ignore_patterns('__pycache__'))
        if winner:
            self.copy_board(winner[0]['ws'], selected, 'perturbation')
        picked = winner[0]['id'] if winner else None
        # T1/T2 have no qualified selection check: the selected program keeps the scored seed for those boards and
        # their dev-best distinct programs are listed for human review (never exported automatically).
        review = {board: [dict(id=c['id'], ws=str(c['ws']), dev_board_mean=round(score, 4))
                          for c, score in ranked.get(board, [])[:3]]
                  for board in ('temporal', 'heart', 'embryo')}
        write_json(fdir / 'final.json', dict(
            lock_id=self.lock['lock_id'], chosen=picked or 'seed',
            rule='T3 paired win over the test-scored reference and unseen-gene veto',
            t3_promotion=picked, eligible_for_export=bool(winner), review_candidates=review,
            selected_sha256=digest(workspace_manifest(selected)),
            agent_calls=self.state['calls'], cost_usd=self.state['cost_usd']))
        if options:
            with (ROOT / 'agentic_scientist/library/holdout_ledger.jsonl').open('a') as ledger:
                ledger.write(json.dumps(dict(t=time.time(), run=self.dir.name, board='perturbation',
                                              calibrated=len(options), promoted=picked)) + '\n')

    def final(self, seed_ws, seed_eval):
        from agentic_scientist.evaluate import SETS, harness as H

        fdir = self.dir / 'final'
        fdir.mkdir(exist_ok=True)
        seed = dict(id='seed', ws=str(seed_ws), proxy=seed_eval['proxy'])
        pairs = self.cfg['holdout_seed_pairs']
        held = {H.SPLITS[s]['board'] for s in SETS['holdout']['splits']}
        if self.cfg.get('holdout_select_boards') is not None:  # boards whose local holdout agrees with the test
            held &= set(self.cfg['holdout_select_boards'])
        # Boards whose local folds failed the calibration ladder (known-TEST-score programs ranked the wrong way):
        # the seed's files are exported for them, whatever was accepted on Dev.
        frozen = set(self.cfg.get('freeze_boards') or [])
        held -= frozen
        held_splits = self.board_splits('holdout', held)
        forked = self.forked(seed_ws)
        ranked = self.rank_boards(seed_ws, seed_eval) if forked else {}
        if self.cfg.get('require_calibrated_final'):
            return self.final_calibrated(seed_ws, fdir, ranked, forked)
        if forked:
            shortlist = {a['id']: a for b in sorted(held) for a, _ in ranked.get(b, [])[:self.cfg['shortlist']]}
            # ablation: also hold out each shortlisted change's accepted parent, so a stacked edit that does not
            # beat its own parent on the holdout is dropped (per_board prefers the ancestor within ablation_tol)
            acc = {a['id']: a for a in self.state['accepted']}
            pending = list(shortlist.values())
            while pending:
                a = pending.pop()
                pid = (self.state.get('parent') or {}).get(a['id'])
                if pid in acc and pid not in shortlist and self.diff_boards(seed_ws, acc[pid]['ws']):
                    shortlist[pid] = acc[pid]
                    pending.append(acc[pid])
        else:
            shortlist = {a['id']: a for a in sorted(self.state['accepted'], key=lambda a: -a['proxy'])[:self.cfg['shortlist']]}
        dev_picks = {}
        if forked:
            for board in sorted(ranked.keys() - held - frozen):
                for candidate, score in self.unseen_veto(board, ranked[board], seed_ws, fdir):
                    dev_picks[board] = (candidate, score)
                    break

        def one(c, j):
            p = fdir / f"holdout_{c['id']}_pair{j}.json"
            changed = self.diff_boards(seed_ws, c['ws']) if c['id'] != 'seed' else None
            if changed is None:
                return self.evaluate_cached(c['ws'], 'holdout', p, pairs[j], held_splits)
            key = self.evaluation_key(c['ws'], 'holdout', pairs[j], held_splits)
            cached = read_cached(p, key)
            if cached is not None:
                return cached
            base = one(seed, j)
            splits = self.board_splits('holdout', changed & held)
            ev = base
            if splits:
                sub = self.evaluate_cached(c['ws'], 'holdout', p.with_name(p.stem + '_sub.json'), pairs[j], splits)
                ev = self.splice(base, sub)
            write_json(p, dict(ev, cache_key=key))
            return ev

        def hold(c):
            with ThreadPoolExecutor(len(pairs)) as pool:
                evs = list(pool.map(lambda j: one(c, j), range(len(pairs))))
            errors = [e.get('error') for e in evs if not e.get('correct')]
            if errors:
                return dict(c, holdout=None, holdout_boards=None, holdout_error=errors[0])
            boards = {b: sum(e['boards'][b] for e in evs) / len(evs) for b in evs[0]['boards']}
            hp = [e['proxy'] for e in evs]
            return dict(c, holdout=sum(hp) / len(hp), holdout_pairs=hp, holdout_boards=boards)

        self.log(f'final: holdout evaluation of {len(shortlist) + 1} candidates')
        seed_row = hold(seed)
        if seed_row['holdout'] is None:
            raise RuntimeError(f"seed holdout evaluation failed: {seed_row['holdout_error']}")
        with ThreadPoolExecutor(max(1, len(shortlist))) as pool:
            rows = [seed_row, *pool.map(hold, shortlist.values())]

        chosen = seed_row
        if forked:
            board_picks = self.per_board(rows, fdir, len(pairs))
            if board_picks or dev_picks:
                ws = fdir / 'final_ws'
                shutil.rmtree(ws, ignore_errors=True)
                shutil.copytree(seed_ws, ws, ignore=shutil.ignore_patterns('__pycache__'))
                for board, (candidate, _) in {**board_picks, **dev_picks}.items():
                    self.copy_board(candidate['ws'], ws, board)
                chosen = hold(dict(id='composed', ws=str(ws), proxy=None,
                                   parts={b: dict(id=r['id'], **stats) for b, (r, stats) in board_picks.items()},
                                   dev_only_parts={b: dict(id=r['id'], score=v) for b, (r, v) in dev_picks.items()}))
                dev = self.eval_scoped(ws, dict(ws=str(seed_ws), eval=seed_eval), fdir / 'final_ws_dev.json')
                if chosen['holdout'] is None or not dev.get('correct'):
                    raise RuntimeError('the composed program failed re-evaluation')
                chosen['dev_proxy'] = dev['proxy']
                rows.append(chosen)
            rule = 'boardwise paired holdout lower bound over seed; dev-only winners subject to the configured veto'
        else:
            chosen = max((r for r in rows if r['holdout'] is not None), key=lambda r: r['holdout'])
            rule = 'legacy whole-program holdout selection'
        sel = fdir / 'selected'
        shutil.rmtree(sel, ignore_errors=True)
        shutil.copytree(chosen['ws'], sel, ignore=shutil.ignore_patterns('__pycache__'))
        result = dict(lock_id=self.lock['lock_id'], rule=rule, candidates=rows, chosen=chosen['id'],
                      selected_sha256=digest(workspace_manifest(sel)), cost_usd=self.state['cost_usd'],
                      agent_calls=self.state['calls'])
        write_json(fdir / 'final.json', result)
        self.log(f"final choice {chosen['id']} holdout {chosen['holdout']} (seed {seed_row['holdout']})")
        with (ROOT / 'agentic_scientist/library/holdout_ledger.jsonl').open('a') as f:
            f.write(json.dumps(dict(t=time.time(), run=self.dir.name, candidates=len(rows), chosen=chosen['id'],
                                    seed_holdout=seed_row['holdout'], chosen_holdout=chosen['holdout'])) + '\n')


def hard_stop_watchdog(run):
    """cfg['hard_stop_at']: whatever is running stops. If the final export is not complete by then, the latest
    automated checkpoint's files (research_end first) become final/submission_fallback, the evidence is packaged and
    the whole process group (agents, evaluations) is terminated."""
    t = Run.at(run.cfg.get('hard_stop_at'))
    if t is None:
        return

    def loop():
        while time.time() < t:
            time.sleep(min(20, max(0.5, t - time.time())))
        fdir = run.dir / 'final'
        disk = json.loads(run.state_path.read_text())  # the finalization process may own the state by now
        done = (fdir / 'submission' / 'manifest.json').exists() and disk.get('phase') == 'done'
        run.log(f"HARD STOP reached ({run.cfg['hard_stop_at']}); final export {'complete' if done else 'INCOMPLETE'}")
        if not done:
            try:
                cps = [c for c in reversed(disk.get('checkpoints', [])) if c.get('ok')]
                cps.sort(key=lambda c: c['stamp'] != 'research_end')
                if cps:
                    src = run.dir / 'checkpoints' / cps[0]['stamp']
                    dst = fdir / 'submission_fallback'
                    fdir.mkdir(exist_ok=True)
                    shutil.rmtree(dst, ignore_errors=True)
                    shutil.copytree(src / 'submission', dst)
                    write_text(fdir / 'FALLBACK.md', f"Hard stop before the final selection finished. Files = automated "
                               f"checkpoint {cps[0]['stamp']} (parts {json.dumps(cps[0].get('parts'))}).\n")
                    run.log(f"hard stop: fallback submission = checkpoint {cps[0]['stamp']}")
                from agentic_scientist.export_final import package, package_upload_ready
                lock = next((ROOT / 'agentic_scientist/locks').glob(f"{run.lock['lock_id']}*.json"), None)
                package(run.dir, fdir / f'evidence_{run.dir.name}.zip', lock=lock)
                package_upload_ready(run.dir, fdir / 'upload_ready', lock=lock)
            except Exception as e:  # noqa: BLE001
                run.log(f'hard stop fallback error {e!r}')
        if not done:
            disk = json.loads(run.state_path.read_text())
            disk['phase'] = 'hard_stopped'
            write_json(run.state_path, disk)
        import signal
        os.killpg(0, signal.SIGTERM)
    threading.Thread(target=loop, daemon=True, name='hard-stop').start()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--lock', required=True)
    ap.add_argument('--run-name', required=True)
    ap.add_argument('--config')
    ap.add_argument('--final-only', action='store_true', help='phase 2: holdout selection only (no agents)')
    a = ap.parse_args()
    try:
        os.setpgrp()  # the hard stop terminates this process group (agents, evaluations), not the supervisor
    except OSError:
        pass
    if a.final_only:
        os.environ['MG_PRIVATE_FINAL'] = '1'
        f = Run(a.lock, a.run_name, a.config, True)
        hard_stop_watchdog(f)
        f.run()
        return
    with (ROOT.parent / '.agentic_scientist-holdout.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_SH | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SystemExit('holdout finalization is active')
        r = Run(a.lock, a.run_name, a.config)
        hard_stop_watchdog(r)
        r.run()
        r.stop = True
    if r.cfg.get('auto_final') and r.state.get('phase') == 'awaiting_holdout':
        if not any(c.get('stamp') == 'research_end' for c in r.state.get('checkpoints', [])):
            try:
                r.checkpoint('research_end')  # fallback files before selection starts
            except Exception as e:  # noqa: BLE001
                r.log(f'research_end checkpoint error {e!r}')
        os.environ['MG_PRIVATE_FINAL'] = '1'
        f = Run(a.lock, a.run_name, a.config, True)
        f.log('automatic finalization: holdout selection, export, evidence')
        f.run()


if __name__ == '__main__':
    main()
