"""AgenticScientist live dashboard (read-only; not part of the run lock).

  .venv/bin/python agentic_scientist/dashboard.py [--port 8478]
  ssh -L 8478:localhost:8478 bio06.cluster.example   ->  http://localhost:8478
"""
import argparse
import hashlib
import difflib
import json
import os
import re
import shutil
import subprocess
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
MG = ROOT / 'agentic_scientist'
RUNS = MG / 'runs'
RUN_ROOTS = [RUNS]
HTML = Path(__file__).with_name('dashboard.html')
FLEET = ROOT / 'shinka_ve/fleet'
LIMIT_RE = re.compile(r'rate.?limit|usage limit|quota|\b429\b|overloaded', re.I)
STEPS = (('ideate', 'hypothesis.json'), ('critic', 'critique.json'), ('implement', 'implemented'),
         ('review', 'code_review.json'), ('eval', 'eval.json'), ('done', 'outcome.json'))
ROLE = {'curate': 'curator', 'ideate': 'researcher', 'critic_plan': 'critic (plan)', 'implement': 'worker', 'critic_code': 'critic (code)',
        'review_fix': 'worker (review fix)', 'distill': 'distiller', 'debug': 'debugger'}


def jload(p):
    try:
        return json.loads(Path(p).read_text())
    except (OSError, ValueError):
        return None


def text(p, limit=None):
    try:
        t = Path(p).read_text(errors='replace')
    except OSError:
        return ''
    return t[-limit:] if limit else t


def tail(p, n):
    return text(p, 400_000).splitlines()[-n:]


def safe(name):
    return name and '/' not in name and '..' not in name


def rundir(q):
    name = q.get('name', [''])[0]
    if not safe(name):
        return None
    return next((runs / name for runs in RUN_ROOTS if (runs / name).is_dir()), None)


def run_dirs():
    """Include a locked run while its first seed evaluation is still pending."""
    found = {}
    for runs in RUN_ROOTS:
        for d in runs.iterdir():
            if not d.is_dir() or d.name in found:
                continue
            started = (runs / f"{d.name.split('_', 3)[-1]}.supervisor.log").is_file()
            if (d / 'state.json').is_file() or (started and lock_for(d).is_file()):
                found[d.name] = d
    return found.values()


def lock_for(d):
    return d.parent.parent / 'locks' / ('_'.join(d.name.split('_')[:3]) + '.json')


def role_of(fname):
    base = fname.split('.')[0]
    for k, v in ROLE.items():
        if base.startswith(k):
            return v
    return base


# ---------- transcript parsing (claude stream-json, codex --json, opencode --format json) ----------
def short(x, n=1500):
    s = x if isinstance(x, str) else json.dumps(x, ensure_ascii=False)
    return s if len(s) <= n else s[:n] + f' … [{len(s) - n} more chars]'


def events(path, last=None):
    out = []
    for line in text(path).splitlines():
        try:
            ev = json.loads(line)
        except ValueError:
            if line.strip():
                out.append(dict(k='raw', t=short(line, 600)))
            continue
        if not isinstance(ev, dict):
            continue
        t = ev.get('type')
        if t == 'assistant':  # claude
            for c in ev.get('message', {}).get('content', []):
                if c.get('type') == 'text' and c.get('text', '').strip():
                    out.append(dict(k='say', t=short(c['text'], 4000)))
                elif c.get('type') == 'tool_use':
                    out.append(dict(k='tool', n=c.get('name'), t=short(c.get('input'))))
                elif c.get('type') == 'thinking' and c.get('thinking'):
                    out.append(dict(k='think', t=short(c['thinking'], 2000)))
        elif t == 'user':
            for c in ev.get('message', {}).get('content', []) if isinstance(ev.get('message', {}).get('content'), list) else []:
                if c.get('type') == 'tool_result':
                    cont = c.get('content')
                    if isinstance(cont, list):
                        cont = ' '.join(x.get('text', '') for x in cont if isinstance(x, dict))
                    out.append(dict(k='result', t=short(cont or '', 1200), err=bool(c.get('is_error'))))
        elif t == 'result':
            out.append(dict(k='done', t=f"{ev.get('subtype', '')} · ${ev.get('total_cost_usd', 0):.3f} · "
                                          f"{ev.get('num_turns', '?')} turns · {ev.get('duration_ms', 0) / 1000:.0f}s"))
        elif t == 'system' and ev.get('subtype') == 'init':
            out.append(dict(k='sys', t=f"session start · model {ev.get('model')}"))
        elif t and t.startswith('item.'):  # codex
            it = ev.get('item', {})
            ty = it.get('type')
            if t == 'item.completed' and ty == 'agent_message':
                out.append(dict(k='say', t=short(it.get('text', ''), 4000)))
            elif t == 'item.completed' and ty == 'reasoning':
                out.append(dict(k='think', t=short(it.get('text', ''), 2000)))
            elif ty == 'command_execution' and t == 'item.completed':
                out.append(dict(k='tool', n='shell', t=short(it.get('command', ''))))
                out.append(dict(k='result', t=short(it.get('aggregated_output', ''), 1200), err=it.get('exit_code') not in (0, None)))
            elif ty == 'file_change' and t == 'item.completed':
                out.append(dict(k='tool', n='edit', t=short([c.get('path') for c in it.get('changes', [])])))
        elif t == 'turn.completed':
            u = ev.get('usage', {})
            out.append(dict(k='done', t=f"turn done · in {u.get('input_tokens')} / out {u.get('output_tokens')} tokens"))
        elif 'part' in ev:  # opencode
            p = ev['part']
            pt = p.get('type')
            if pt == 'text' and p.get('text', '').strip():
                out.append(dict(k='say', t=short(p['text'], 4000)))
            elif pt == 'reasoning' and p.get('text'):
                out.append(dict(k='think', t=short(p['text'], 2000)))
            elif pt == 'tool':
                st = p.get('state', {})
                out.append(dict(k='tool', n=p.get('tool'), t=short(st.get('input', ''))))
                if st.get('output') is not None or st.get('error'):
                    out.append(dict(k='result', t=short(st.get('output') or st.get('error') or '', 1200),
                                    err=st.get('status') == 'error'))
            elif pt == 'step-finish':
                tok = p.get('tokens', {})
                out.append(dict(k='done', t=f"step · in {tok.get('input')} / out {tok.get('output')} tokens"))
    return out[-last:] if last else out


# ---------- run views ----------
def cycle_dirs(d):
    return sorted((d / 'cycles').glob('*')) if (d / 'cycles').exists() else []


def parent_ws(d, cid):
    """Parent = the worker's latest accepted cycle before this one, else the seed."""
    w, n = cid.split('_c')
    par = d / 'seed_ws'
    for c in cycle_dirs(d):
        cw, cn = c.name.split('_c')
        o = jload(c / 'outcome.json')
        if cw == w and int(cn) < int(n) and o and o.get('verdict') == 'accepted':
            par = c / 'ws'
    return par


def cycle_summary(c):
    hyp = jload(c / 'hypothesis.json') or {}
    out = jload(c / 'outcome.json')
    ev = jload(c / 'eval.json') or {}
    crit = jload(c / 'critique.json') or {}
    rev = jload(c / 'code_review.json') or {}
    steps = [s for s, f in STEPS if (c / f).exists()]
    tr = sorted(c.glob('*.jsonl'), key=lambda p: p.stat().st_mtime)
    active = tr and time.time() - tr[-1].stat().st_mtime < 90 and not out
    return dict(id=c.name, step=steps[-1] if steps else 'ideate', title=hyp.get('title'),
                critic=crit.get('verdict'), review=rev.get('verdict'), outcome=out, boards=ev.get('boards'),
                proxy=ev.get('proxy'), error=ev.get('error'), active=bool(active),
                current=role_of(tr[-1].name) if tr else None, started=c.stat().st_ctime,
                updated=max([p.stat().st_mtime for p in c.iterdir()] or [c.stat().st_mtime]))


def proc_alive(d):
    try:
        out = subprocess.run(['ps', '-eo', 'pid,args'], capture_output=True, text=True, timeout=5).stdout
    except Exception:  # noqa: BLE001
        return False
    run_name = d.name.split('_', 3)[-1]
    return any('orchestrator.py' in line and lock_for(d).name in line
               and re.search(rf'--run-name\s+{re.escape(run_name)}(?:\s|$)', line)
               for line in out.splitlines())


def run_detail(d):
    state = jload(d / 'state.json') or {}
    cycles = [cycle_summary(c) for c in cycle_dirs(d)]
    workers = {w: dict(cycle=s['cycle'], fails=s['fails'], best_id=s['best']['id'],
                       best_proxy=s['best']['eval'].get('proxy'), best_boards=s['best']['eval'].get('boards'))
               for w, s in state.get('workers', {}).items()}
    lock = jload(lock_for(d)) or {}
    best = max(state.get('accepted', []), key=lambda a: a['proxy'], default=None)
    return dict(name=d.name, alive=proc_alive(d), calls=state.get('calls'), cost_usd=state.get('cost_usd'),
                global_best=state.get('global_best'), stale=state.get('stale'), impl_stats=state.get('impl_stats'),
                accepted=state.get('accepted', []), workers=workers, seed=jload(d / 'seed_dev.json'), cycles=cycles,
                final=jload(d / 'final/final.json'), best=best, config=lock.get('config'), lock_id=lock.get('lock_id'),
                lock_note=lock.get('note'), started=d.stat().st_ctime)


def cycle_detail(d, cid):
    c = d / 'cycles' / cid
    if not safe(cid) or not c.is_dir():
        return None
    ws, par = c / 'ws', parent_ws(d, cid)
    diff = []
    if ws.exists():
        names = sorted({p.relative_to(ws) for p in ws.rglob('*.py')} | {p.relative_to(par) for p in par.rglob('*.py')})
        for n in names:
            if '__pycache__' in n.parts:
                continue
            a = text(par / n).splitlines() if (par / n).exists() else []
            b = text(ws / n).splitlines() if (ws / n).exists() else []
            diff += difflib.unified_diff(a, b, f'parent/{n}', f'candidate/{n}', lineterm='')
    files = {str(p.relative_to(ws)): text(p, 200_000) for p in sorted(ws.rglob('*'))
             if ws.exists() and p.is_file() and p.suffix in ('.py', '.md') and '__pycache__' not in p.parts}
    analysis = {p.name: text(p, 60_000) for p in sorted((c / 'analysis').glob('*')) if p.is_file()} \
        if (c / 'analysis').exists() else {}
    return dict(id=cid, parent=str(par.relative_to(d)), hypothesis=jload(c / 'hypothesis.json'),
                critique=jload(c / 'critique.json'), review=jload(c / 'code_review.json'), eval=jload(c / 'eval.json'),
                eval_log=text(c / 'eval.log', 30_000), outcome=jload(c / 'outcome.json'), diff='\n'.join(diff),
                files=files, analysis=analysis,
                transcripts=[dict(file=p.name, role=role_of(p.name), size=p.stat().st_size, mtime=p.stat().st_mtime)
                             for p in sorted(c.glob('*.jsonl'), key=lambda p: p.stat().st_mtime)])


def live(d, n=60):
    """Agent transcripts touched in the last 10 minutes, newest first, with their latest events."""
    out = []
    for p in sorted(d.glob('cycles/*/*.jsonl'), key=lambda p: -p.stat().st_mtime)[:6]:
        age = time.time() - p.stat().st_mtime
        if age > 600 and out:
            break
        out.append(dict(cycle=p.parent.name, file=p.name, role=role_of(p.name), age=age, events=events(p, n)))
    return out


def pid_alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def fleet():
    hosts = [l.split('#')[0].strip() for l in text(ROOT / 'shinka_ve/fleet_hosts.txt').splitlines()]
    hosts = [h for h in hosts if h]
    lines = tail(FLEET / 'dispatch.log', 3000)
    st = {h: dict(host=h.split('.')[0], busy=None, last=None, done=0, fail=0, secs=[]) for h in hosts}
    pat = re.compile(r'^(\S+ \S+) pid=(\d+) (?:mg |bra )?(start|done|fail)\s+(\S+)(.*)$')
    open_jobs = {}
    for l in lines:
        m = pat.match(l)
        if not m or m.group(4) not in st:
            continue
        ts, pid, what, h, rest = m.groups()
        s = st[h]
        s['last'] = ts
        kind = 'agentic_scientist' if (' mg ' in l or ' bra ' in l) else 'shinka'
        if what == 'start':
            open_jobs.setdefault((h, pid), []).append((ts, kind, rest.strip()[-60:]))
        else:
            if open_jobs.get((h, pid)):
                open_jobs[(h, pid)].pop(0)
            if what == 'done':
                s['done'] += 1
                mm = re.search(r'(\d+)s$', rest.strip())
                if mm:
                    s['secs'].append(int(mm.group(1)))
            else:
                s['fail'] += 1
    for (h, pid), jobs in open_jobs.items():
        # A dispatcher that was killed never logs 'done': its jobs are not running (dispatchers run on this node).
        if not jobs or not pid_alive(int(pid)):
            continue
        ts, kind, what = jobs[-1]
        if st[h]['busy'] is None or ts > st[h]['busy']['since']:
            st[h]['busy'] = dict(since=ts, kind=kind, what=what, n=len(jobs))
        else:
            st[h]['busy']['n'] = st[h]['busy'].get('n', 1) + len(jobs)
    for h, s in st.items():
        cd = FLEET / 'cooldown' / h
        s['cooldown'] = cd.exists() and time.time() - cd.stat().st_mtime < 1800
        s['mean_s'] = round(sum(s['secs']) / len(s['secs'])) if s['secs'] else None
        del s['secs']
    return dict(hosts=list(st.values()), log=lines[-80:])


# ---------- final-run monitoring: health/progress, per-task lineage, T3 gate, tuning ----------
BOARDS = ('temporal', 'heart', 'embryo', 'perturbation')


def run_config(d):
    """The config the run actually uses (state.effective_config path), else the lock's default config."""
    eff = ((jload(d / 'state.json') or {}).get('effective_config') or {}).get('path')
    if eff and (ROOT / eff).exists():
        return jload(ROOT / eff) or {}
    return (jload(lock_for(d)) or {}).get('config') or {}


def board_of_cycle(cid, outcome, cfg):
    f = (cfg.get('focus') or {}).get(cid.split('_c')[0])
    if isinstance(f, str):
        return f
    st = (outcome or {}).get('stats') or {}
    bs = {k: abs(v.get('mean') or 0) for k, v in st.items() if k in BOARDS and isinstance(v, dict)}
    return max(bs, key=bs.get) if bs and max(bs.values()) > 1e-9 else None

# ---- Normandy panel: what is new in this run (seed fixes, fold trust from the calibration ladder, frozen boards) ----
NORMANDY_TEST = [  # board, previous seed on TEST, public top range, what the seed changed
    ('T1', 71.1, '80-84', 'keeps the latest-stage lineage masses (cardiomyocytes ~20% instead of 6%); cardiomyocyte floor gate'),
    ('Heart', 65.2, '74-77', "epicardium label 'Epi' counted as organ; radius capped at 510.5; attached-only donors as a switch"),
    ('Embryo', 68.4, '79-81', 'midpoint geometry per native axis (occupancy was 3.7); gate re-referenced to midpoint geometry'),
    ('T3', 69.0, '75-78', 'deep delay: real WT cells 2.3 sampling intervals earlier (E8.0 + E8.25) on the systemic gate'),
]
NORMANDY_TRUST = {  # split -> (ladder verdict, note)
    'temporal_matched': ('agrees', 'new split: target matched to the last input lineage shares; ranks the new seed above the old one'),
    'temporal_heartonly': ('diagnostic', 'unmatched target rewards continuing the lineage trend (wrong on the test)'),
    'temporal_val': ('weak', 'whole E10.5 target, not a chamber dissection'),
    't1_guard_2d': ('coarse', 'puts the previous seed first; cannot rank small gains'),
    'heart_e105_long_organ': ('agrees', 'ranks whole-section copy < crop ~ previous seed, as on the test'),
    'heart_e105_long_region': ('agrees', 'label-free spatial target; same ranking as the test'),
    'heart_e105_organ': ('fails', 'ranks the whole-section copy first: weight cut to 0.02'),
    'heart_long_organ': ('agrees', ''), 'heart_organ_proxy': ('agrees', ''), 'heart_e875_organ': ('agrees', ''),
    'embryo_late': ('untestable', 'known programs are within 0.7 on the test'),
    'embryo_early': ('untestable', 'known programs are within 0.7 on the test'),
    'guard_embryo_e80': ('untestable', ''),
}


def normandy(d):
    cfg, state = run_config(d), jload(d / 'state.json') or {}
    if 'normandy' not in str(cfg.get('seed_dir', '')):
        return None
    import sys
    sys.path.insert(0, str(ROOT))
    try:
        from agentic_scientist import evaluate as E
        weights = {s: E.harness.SPLITS[s].get('weight') for s in E.harness.SPLITS}
        sets = {s: k for k in ('dev', 'holdout') for s in E.SETS[k]['splits']}
        board = {s: E.harness.SPLITS[s].get('board') for s in E.harness.SPLITS}
    except Exception:  # noqa: BLE001
        weights, sets, board = {}, {}, {}
    seed = (jload(d / 'seed_dev.json') or {}).get('splits') or {}
    frozen = cfg.get('freeze_boards') or []
    folds = []
    for s in sorted(sets, key=lambda s: (str(board.get(s)), sets[s], s)):
        if board.get(s) == 'perturbation':
            v, note = ('fails', 'ranks delay mixtures below the matched wild type (test: 68 vs 50)') if sets[s] == 'dev' else ('untestable', '')
        else:
            v, note = NORMANDY_TRUST.get(s, ('untested', ''))
        folds.append(dict(split=s, board=board.get(s), set=sets[s], weight=weights.get(s), verdict=v, note=note,
                          seed=(seed.get(s) or {}).get('score')))
    workers = []
    for w, f in (cfg.get('focus') or {}).items():
        n = len([c for c in cycle_dirs(d) if c.name.startswith(w + '_c') and (c / 'outcome.json').exists()])
        ds = (cfg.get('directives') or {}).get(w)
        k = min(n, len(ds) - 1) if isinstance(ds, list) and ds else None
        phase = (ds[k].split('(')[0].split(':')[0].strip()[:28] if k is not None else '')
        workers.append(dict(worker=w, board=f, done=n, phase=phase, best=(state.get('workers', {}).get(w, {}).get('best') or {}).get('id')))
    return dict(test=[dict(board=b, score=sc, top=t, change=c) for b, sc, t, c in NORMANDY_TEST], total=206.9,
                folds=folds, frozen=frozen, workers=workers, ideators=[x.get('model') for x in cfg.get('ideator_cycle') or []],
                stops={k: cfg.get(k) for k in ('no_new_cycles_at', 'research_kill_at', 'hard_stop_at')})


def health(d):
    """Alerts and progress for an unattended run: stalls, a dead orchestrator, fleet trouble, disk, memory, ETA."""
    cfg, alerts = run_config(d), []
    alive, final = proc_alive(d), (d / 'final' / 'final.json').exists()
    rl = d / 'run.log'
    age = time.time() - rl.stat().st_mtime if rl.exists() else None
    if not alive and not final and (jload(d / 'state.json') or {}).get('phase') not in ('awaiting_holdout', 'final', 'done'):
        alerts.append(dict(level='error', text='orchestrator is not running and the run has no final selection yet'))
    try:
        lim = json.loads((d / 'state.json').read_text()).get('limited_until') or {}
    except (OSError, ValueError):
        lim = {}
    for cli, until in sorted(lim.items()):
        if until > time.time():
            alerts.append(dict(level='warn', text=f'{cli} out of quota until {time.strftime("%a %H:%M", time.localtime(until))}; '
                                                  'ideation falls back to the other ideator, then to the DeepSeek overflow (the wall-clock deadline still runs)'))
    if alive and age is not None and age > 2700 and not any(u > time.time() for u in lim.values()):
        alerts.append(dict(level='warn', text=f'run.log silent for {age / 60:.0f} min'))
    errs = [l for l in tail(rl, 400) if 'Traceback' in l or ' error ' in l.lower() or 'fatal' in l.lower()]
    if errs:
        alerts.append(dict(level='warn', text=f'{len(errs)} error line(s) in the recent run.log; last: {errs[-1][:160]}'))
    sup = list(d.parent.glob(f"{'_'.join(d.name.split('_')[3:]) or d.name}*.supervisor.log"))
    restarts = sum(l.count('restart') for f in sup for l in tail(f, 200))
    if restarts:
        alerts.append(dict(level='warn', text=f'supervisor restarted the orchestrator {restarts} time(s)'))
    try:
        fl = fleet()['hosts']
        cool = [h['host'] for h in fl if h.get('cooldown')]
        if cool:
            alerts.append(dict(level='warn', text=f'fleet hosts in failure cooldown: {", ".join(cool)}'))
    except Exception:  # noqa: BLE001
        fl = []
    free = shutil.disk_usage(d).free / 1e9
    if free < 50:
        alerts.append(dict(level='warn' if free > 10 else 'error', text=f'only {free:.0f} GB free on the run disk'))
    mem = None
    try:
        mi = dict(l.split(':', 1) for l in Path('/proc/meminfo').read_text().splitlines())
        mem = int(mi['MemAvailable'].split()[0]) / 1e6
        if mem < 4:
            alerts.append(dict(level='warn', text=f'head node has only {mem:.1f} GB memory available'))
    except Exception:  # noqa: BLE001
        pass
    state = jload(d / 'state.json') or {}
    if cfg.get('max_agent_calls') and (state.get('calls') or 0) > 0.9 * cfg['max_agent_calls']:
        alerts.append(dict(level='warn', text=f"agent calls {state.get('calls')} of {cfg['max_agent_calls']}"))
    if state.get('claude_off'):
        alerts.append(dict(level='info', text='Claude ideator switched to GPT (weekly budget guard)'))
    done = sorted((c / 'outcome.json').stat().st_mtime for c in cycle_dirs(d) if (c / 'outcome.json').exists())
    total = (cfg.get('workers') or 0) * (cfg.get('cycles_per_worker') or 0)
    rate = eta = None
    win = done[-12:]
    if len(win) >= 3 and win[-1] > win[0]:
        rate = (len(win) - 1) / ((win[-1] - win[0]) / 3600)  # cycles per hour, recent window
    if rate and total and alive:
        eta = time.time() + max(0, total - len(done)) / rate
    # Wall-clock schedule (max_research_seconds from research start; no new cycles in the last cycle_drain_seconds).
    t0, lim, drain = state.get('research_started'), cfg.get('max_research_seconds'), cfg.get('cycle_drain_seconds') or 0
    sched = None
    if t0 and lim:
        sched = dict(start=t0, admit_until=t0 + lim - drain, research_until=t0 + lim, final_by=t0 + lim + 8 * 3600)
    phase = state.get('phase') or ('research' if alive else None)
    if phase == 'awaiting_holdout':
        alerts.append(dict(level='info', text='research finished: waiting for the passphrase (final.sh)'))
    rl_tail = tail(rl, 20000)
    overflow = sum(1 for l in rl_tail if 'overflow:' in l)
    paused = [l for l in rl_tail if ' paused: no quota' in l]
    if paused:
        alerts.append(dict(level='warn', text=f'worker paused for quota {len(paused)} time(s); last: {paused[-1][-140:]}'))
    ideators = {}
    for c in cycle_dirs(d):
        for t in c.glob('*ideate*.jsonl'):
            m = None
            try:
                with open(t, errors='replace') as fh:
                    head = fh.read(4000)
                m = re.search(r'"model"\s*:\s*"([^"]+)"', head)
            except OSError:
                pass
            k = m.group(1) if m else 'gpt-6.2-sol / deepseek'
            ideators[k] = ideators.get(k, 0) + 1
    plan = d / 'plan.md'
    plans = sorted((d / 'planner').glob('p*')) if (d / 'planner').exists() else []
    planner = dict(n=len(plans), updated=plan.stat().st_mtime if plan.exists() else None,
                   text=text(plan, 4000) if plan.exists() else None)
    return dict(alerts=alerts, alive=alive, final=final, log_age=age, sched=sched, phase=phase, overflow=overflow,
                ideators=ideators, planner=planner, done=len(done), total=total, rate=rate, eta=eta,
                accepted=len(state.get('accepted', [])), disk_free_gb=round(free), mem_avail_gb=mem,
                fleet_busy=sum(1 for h in fl if h.get('busy')), fleet_hosts=len(fl))


def pair_split_scores(ws, first):
    """{pair: {split: score}} for the T3 splits: pair 0 from `first`, others from the per-board pair cache."""
    out = {0: {s: r['score'] for s, r in (first or {}).get('splits', {}).items()
               if r.get('board') == 'perturbation' and 'score' in r}}
    cache = Path(str(ws) + '_evals')
    for j in range(1, 8):
        e = jload(cache / f'pair{j}_perturbation.json')
        if e and e.get('correct'):
            out[j] = {s: r['score'] for s, r in e['splits'].items() if r.get('board') == 'perturbation'}
    return out


def mse(v):
    n = len(v)
    if not n:
        return None, None, 0
    m = sum(v) / n
    se = (sum((x - m) ** 2 for x in v) / (n - 1)) ** .5 / n ** .5 if n > 1 else None
    return m, se, n


def tasks(d):
    cfg, state = run_config(d), jload(d / 'state.json') or {}
    seed = jload(d / 'seed_dev.json') or {}
    best_ids = {w: s['best']['id'] for w, s in state.get('workers', {}).items()}
    rows = []
    for a in state.get('accepted', []):  # initial elites (not cycles)
        if a['id'].startswith('init_'):
            b = a.get('boards') or {}
            diffs = {k: (b.get(k) or 0) - (seed.get('boards') or {}).get(k, 0) for k in BOARDS}
            rows.append(dict(id=a['id'], board=max(diffs, key=lambda k: abs(diffs[k])), title='initial elite', parent='seed',
                             gain=None, lb=None, board_gain=None, proxy=a.get('proxy'), time=None,
                             board_score=b.get(max(diffs, key=lambda k: abs(diffs[k])))))
    for c in cycle_dirs(d):
        o = jload(c / 'outcome.json')
        if not o or o.get('verdict') != 'accepted':
            continue
        b = board_of_cycle(c.name, o, cfg)
        st = o.get('stats') or {}
        rows.append(dict(id=c.name, board=b, title=o.get('title'), parent=o.get('parent_id'),
                         gain=(st.get('proxy') or {}).get('mean'), se=(st.get('proxy') or {}).get('se'),
                         lb=(st.get('proxy') or {}).get('lb'), board_gain=(st.get(b) or {}).get('mean'),
                         board_score=(o.get('boards') or {}).get(b), proxy=o.get('proxy'),
                         time=(c / 'outcome.json').stat().st_mtime, tune=o.get('tune')))
    per = {b: [r for r in rows if r['board'] == b] for b in BOARDS}
    # T3: severity gate per split (seed vs current T3 best) and per-gene paired gains of each accepted T3 program vs seed
    t3_best = next((best_ids[w] for w, f in (cfg.get('focus') or {}).items() if f == 'perturbation' and w in best_ids), None)
    bev = jload(d / 'cycles' / t3_best / 'eval.json') if t3_best and t3_best != 'seed' else None
    gate = []
    for s, r in (seed.get('splits') or {}).items():
        if r.get('board') != 'perturbation':
            continue
        br = (bev or {}).get('splits', {}).get(s, r)
        gate.append(dict(split=s, seed=r.get('score'), best=br.get('score'), seed_sev=r.get('severity'), best_sev=br.get('severity')))
    seed_s = pair_split_scores(d / 'seed_ws', seed)
    genes = sorted({g['split'].split('_')[0] for g in gate})
    pg = []
    for r in per['perturbation']:
        if r['id'].startswith('init_'):
            continue
        cs = pair_split_scores(d / 'cycles' / r['id'] / 'ws', jload(d / 'cycles' / r['id'] / 'eval.json'))
        common = sorted(set(cs) & set(seed_s))
        row = dict(id=r['id'], title=r['title'], genes={})
        for g in genes:
            sp = [x['split'] for x in gate if x['split'].split('_')[0] == g]
            diffs = [sum(cs[j][s] - seed_s[j][s] for s in sp) / len(sp) for j in common
                     if all(s in cs[j] and s in seed_s[j] for s in sp)]
            m, se, n = mse(diffs)
            row['genes'][g] = dict(mean=m, se=se, n=n)
        pg.append(row)
    return dict(per_board=per, best_ids=best_ids, focus=cfg.get('focus'), seed_boards=seed.get('boards'),
                t3_best=t3_best, gate=gate, genes=genes, per_gene=pg)


def tuning(d):
    out = []
    for c in cycle_dirs(d):
        t = c / 'tune'
        if not t.is_dir():
            continue
        res = jload(t / 'tune.json')
        if res:
            trials = [dict(trial=x['trial'], round=x.get('round'), score=x.get('score'), params=x.get('params'))
                      for x in res.get('trials', [])]
        else:  # running: what has been scored so far
            trials = []
            for td in sorted(t.glob('trial*')):
                pr, ev = jload(td / 'params.json'), next(iter(sorted(td.glob('eval_911_9.json'))), None)
                e = jload(ev) if ev else None
                trials.append(dict(trial=int(td.name[5:]), round=None, params=pr,
                                   score=(e or {}).get('boards', {}).get(res.get('board') if res else None)
                                   if e and e.get('correct') else None))
            ws_knobs = next(iter((c / 'ws').glob('*_knobs.json')), None)
            b = ws_knobs.name[:-len('_knobs.json')] if ws_knobs else None
            for x, td in zip(trials, sorted(t.glob('trial*'))):
                e = jload(td / 'eval_911_9.json')
                x['score'] = (e or {}).get('boards', {}).get(b) if e and e.get('correct') else None
        out.append(dict(cycle=c.name, done=bool(res), board=(res or {}).get('board'), knobs=(res or {}).get('knobs'),
                        current=(res or {}).get('current'), chosen=(res or {}).get('chosen'),
                        improved=(res or {}).get('improved'), gain=(res or {}).get('gain'),
                        gain_se=(res or {}).get('gain_se'), reason=(res or {}).get('reason'),
                        finalists=(res or {}).get('finalists'), trials=trials,
                        updated=max([p.stat().st_mtime for p in t.rglob('*.json')] or [t.stat().st_mtime])))
    return sorted(out, key=lambda r: -r['updated'])


def activity(d, n=80):
    """Recent file changes in the run and the agentic_scientist code tree, plus git status."""
    mg, root = d.parent.parent, d.parents[2]
    items = []
    for base in (d, mg):
        for p in base.rglob('*'):
            if not p.is_file() or '__pycache__' in p.parts:
                continue
            if base == mg and p.relative_to(mg).parts[0] in ('runs', 'smoke'):
                continue
            if True:
                try:
                    items.append((p.stat().st_mtime, p.stat().st_size, str(p.relative_to(root))))
                except OSError:
                    pass
    items.sort(reverse=True)
    try:
        git = subprocess.run(['git', '-C', str(root), 'status', '--short', '--', 'agentic_scientist', 'docs', 'scripts', 'src'],
                             capture_output=True, text=True, timeout=10).stdout.splitlines()[:60]
    except Exception:  # noqa: BLE001
        git = []
    return dict(files=[dict(mtime=m, size=s, path=p) for m, s, p in items[:n]], git=git)


def limits(d):
    out = []
    for p in d.glob('cycles/*/*.jsonl'):
        for l in text(p, 200_000).splitlines():
            if LIMIT_RE.search(l) and ('error' in l.lower() or 'limit' in l.lower()):
                out.append(dict(file=f'{p.parent.name}/{p.name}', mtime=p.stat().st_mtime, line=short(l, 300)))
                break
    for l in tail(d / 'run.log', 5000):
        if LIMIT_RE.search(l):
            out.append(dict(file='run.log', mtime=None, line=l))
    return sorted(out, key=lambda x: -(x['mtime'] or 0))[:100]


def logs(d, which):
    runs, mg, root = d.parent, d.parent.parent, d.parents[2]
    path = {'run': d / 'run.log', 'notebook': d / 'notebook.md',
            'supervisor': runs / f"{d.name.split('_', 3)[-1]}.supervisor.log",
            'stdout': runs / f"{d.name.split('_', 3)[-1]}.log",
            'fleet': root / 'shinka_ve/fleet/dispatch.log'}.get(which)
    if path is None:
        return None
    if not path.exists() and which == 'stdout':  # pilot / smoke runs log next to the package
        cand = sorted(mg.glob(f"{d.name.split('_', 3)[-1]}*.log")) + sorted((mg / 'smoke').glob('*.log'))
        path = cand[0] if cand else path
    return dict(path=str(path.relative_to(root)) if path.exists() else str(path), lines=tail(path, 1500))


# ---------- final run: countdown, GPT vs Opus, quota, private held-out, metric gaps, exports ----------
DEADLINE_AOE = '2026-11-26T12:59:00+01:00'  # 25 Nov 23:59 AoE
PRIVATE_ROOT = Path('/scratch/user/as_private')
DEV_OF = {'T1': 'temporal', 'heart': 'heart', 'embryo': 'embryo', 'T3': 'perturbation'}


def _iso(v):
    from datetime import datetime
    try:
        return datetime.fromisoformat(v).timestamp() if v else None
    except ValueError:
        return None


def _jsonl(path, limit=None):
    out = []
    for l in text(path, limit).splitlines() if path.exists() else []:
        try:
            out.append(json.loads(l))
        except ValueError:
            pass
    return out


def wilson(k, n, z=1.96):
    if not n:
        return None, None
    ph = k / n
    den = 1 + z * z / n
    mid = (ph + z * z / (2 * n)) / den
    half = z * ((ph * (1 - ph) / n + z * z / (4 * n * n)) ** .5) / den
    return max(0.0, mid - half), min(1.0, mid + half)


def _lb_module():
    import importlib.util
    spec = importlib.util.spec_from_file_location('mg_leaderboard', MG / 'tools/leaderboard.py')
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def metric_gaps(d):
    """Weighted per-metric gap: public top-10 mean minus our best test entry (humans only)."""
    lb = _lb_module()
    snaps = sorted([p for p in (d / 'leaderboard').glob('*') if p.is_dir()]) or \
        sorted(p for p in (ROOT / 'docs/leaderboard').glob('*') if p.is_dir())
    if not snaps:
        return {}
    snap = snaps[-1]
    hist = (jload(MG / 'data/our_test_history.json') or {}).get('entries', [])
    out = {}
    for board, fname in lb.FILES.items():
        data = jload(snap / f'{fname}.json') or {}
        rows = sorted(data.get('rows') or [], key=lambda r: -(r.get('headline') or 0))
        top = rows[:10]
        ours = max((e for e in hist if e['board'] == board), key=lambda e: e['headline'], default=None)
        w = lb.WEIGHTS.get(board, {})
        mets = []
        for m, wt in w.items():
            vals = [r['metrics'][m] for r in top if isinstance(r.get('metrics'), dict) and r['metrics'].get(m) is not None]
            t10 = sum(vals) / len(vals) if vals else None
            o = (ours or {}).get('metrics', {}).get(m)
            mets.append(dict(metric=m, weight=wt, top10=t10, ours=o,
                             gap=None if t10 is None or o is None else wt * (t10 - o)))
        out[board] = dict(snapshot=snap.name, leader=rows[0]['headline'] if rows else None,
                          top10=sum(r['headline'] for r in top) / len(top) if top else None,
                          ours=ours['headline'] if ours else None, ours_entry=ours['entry'] if ours else None,
                          metrics=sorted(mets, key=lambda x: -(x['gap'] or -1e9)))
    return out


HELD_TARGET = {'temporal': '2-day dissected heart E14.5+E16.5 -> E18.5 (t1_guard_2d) + test-mode E12.5 vs E14.5',
               'heart': 'dissected E10.5 heart (organ + 2d long organ/region)', 'embryo': 'E7.5 embryo (embryo_late)',
               'perturbation': 'unseen non-cardiac knockout veto (Tet-TKO E7.5/E8.5 -> E8.5)'}


def held_of(o, hold_by):
    """Per-cycle held-out fields for the table: score, parent's score, status."""
    b = o.get('board')
    if o.get('dev_board') is None:
        return dict(held=None, held_parent=None, held_status='not evaluated')
    h = hold_by.get((o['id'], b))
    if h is None:
        return dict(held=None, held_parent=None, held_status='scoring' if b != 'perturbation' else 'none')
    par = hold_by.get((o.get('parent_id') or 'seed', b)) or {}
    if h.get('score') is None:
        if h.get('note') and 'no local held-out' in h['note']:
            return dict(held=None, held_parent=None, held_status='none')
        return dict(held=None, held_parent=par.get('score'), held_status='error', held_error=(h.get('error') or h.get('note') or '')[:300])
    return dict(held=h['score'], held_parent=par.get('score'), held_status='ok')


def final_view(d):
    cfg, state = run_config(d), jload(d / 'state.json') or {}
    now = time.time()
    times = [('no new cycles', _iso(cfg.get('no_new_cycles_at'))), ('research stops', _iso(cfg.get('research_kill_at'))),
             ('hard stop', _iso(cfg.get('hard_stop_at'))), ('deadline (AoE)', _iso(DEADLINE_AOE))]
    outs = []
    for c in cycle_dirs(d):
        o = jload(c / 'outcome.json')
        if o:
            o = dict(o, id=c.name)
            o.pop('stats', None)
            outs.append(o)
    priv = Path(cfg.get('private_root') or PRIVATE_ROOT) / d.name
    hold = [h for h in _jsonl(priv / 'holdout.jsonl') if not (h.get('board') == 'temporal' and h.get('score') is None)]
    has_t1 = any(h.get('board') == 'temporal' and h.get('score') is not None for h in hold)
    if not has_t1:
        hold += _jsonl(priv / 't1_holdout.jsonl')  # Run #1 fallback: T1 test-mode prediction vs dissected E14.5
    by_id = {(h.get('id'), h.get('board')): h.get('score') for h in hold if h.get('score') is not None}
    hold = [dict(h, parent_score=by_id.get((h.get('parent'), h.get('board')))) for h in hold]
    late = _jsonl(priv / 'monitor_late.jsonl')
    calls = _jsonl(d / 'agent_calls.jsonl')
    seed = jload(d / 'seed_dev.json') or {}
    # boards
    boards = {}
    for b in ('temporal', 'heart', 'embryo', 'perturbation'):
        bo = [o for o in outs if o.get('board') == b]
        acc = [o for o in bo if o.get('verdict') == 'accepted']
        bh = [h for h in hold if h.get('board') == b and h.get('score') is not None]
        sh = next((h['score'] for h in bh if h.get('id') == 'seed'), None)
        ah = [h for h in bh if h.get('verdict') == 'accepted']
        boards[b] = dict(cycles=len(bo), accepted=len(acc), seed_dev=(seed.get('boards') or {}).get(b),
                         best_dev=max((o['dev_board'] for o in acc if o.get('dev_board') is not None), default=None),
                         seed_hold=sh, last_acc_hold=ah[-1]['score'] if ah else None,
                         best_acc_hold=max((h['score'] for h in ah), default=None))
    # researchers (actual model that ran the cycle)
    res = {}
    for o in outs:
        k = o.get('researcher') or '?'
        r = res.setdefault(k, dict(model=k, n=0, accepted=0, skipped=0, gains=[], acc_gains=[], minutes=[], substitute=0,
                                   vetoed=0, hold=[]))
        r['n'] += 1
        v = o.get('verdict')
        r['accepted'] += v == 'accepted'
        r['skipped'] += v in ('skipped', 'error', 'invalid')
        r['vetoed'] += v == 'vetoed' or ((o.get('review') or {}).get('verdict') == 'veto')
        r['substitute'] += bool(o.get('substitute'))
        if o.get('dev_board') is not None and o.get('parent_dev_board') is not None:
            g = o['dev_board'] - o['parent_dev_board']
            r['gains'].append(g)
            if v == 'accepted':
                r['acc_gains'].append(g)
        if o.get('cycle_seconds'):
            r['minutes'].append(o['cycle_seconds'] / 60)
    for h in hold:
        if h.get('researcher') in res and h.get('score') is not None and h.get('parent_score') is not None:
            res[h['researcher']]['hold'].append(h['score'] - h['parent_score'])
    for r in res.values():
        lo, hi = wilson(r['accepted'], r['n'])
        mm = sorted(r.pop('minutes'))
        r.update(rate=r['accepted'] / r['n'] if r['n'] else None, lo=lo, hi=hi,
                 mean_gain=sum(r['gains']) / len(r['gains']) if r['gains'] else None,
                 mean_acc_gain=sum(r['acc_gains']) / len(r['acc_gains']) if r['acc_gains'] else None,
                 med_min=mm[len(mm) // 2] if mm else None,
                 mean_hold=sum(r['hold']) / len(r['hold']) if r['hold'] else None)
        r.pop('gains'); r.pop('acc_gains'); r.pop('hold')
    # providers
    lim = state.get('limited_until') or {}
    conc = cfg.get('provider_concurrency') or {}
    prov = {}
    for c in calls:
        pr = prov.setdefault(c['cli'], dict(cli=c['cli'], calls=0, last24=0, fails=0, limited=0, served_as_sub=0,
                                             seconds=[], last=None, models=set()))
        pr['calls'] += 1
        pr['last24'] += c['t'] > now - 86400
        pr['fails'] += c.get('exit') not in (0, None)
        pr['limited'] += bool(c.get('limited'))
        pr['served_as_sub'] += bool(c.get('substitute'))
        pr['seconds'].append(c.get('seconds') or 0)
        pr['last'] = max(pr['last'] or 0, c['t'])
        pr['models'].add(c.get('model'))
    for cli in set(conc) | set(lim):
        prov.setdefault(cli, dict(cli=cli, calls=0, last24=0, fails=0, limited=0, served_as_sub=0, seconds=[], last=None,
                                  models=set()))
    running = {}
    for t in d.glob('cycles/*/*.jsonl'):
        try:
            if now - t.stat().st_mtime < 90:
                pj = jload(t.with_suffix('.prompt.json')) or {}
                cli = (pj.get('role') or {}).get('cli')
                if cli:
                    running[cli] = running.get(cli, 0) + 1
        except OSError:
            pass
    for pr in prov.values():
        sec = pr.pop('seconds')
        pr.update(mean_s=sum(sec) / len(sec) if sec else None, models=sorted(m for m in pr['models'] if m),
                  limited_until=lim.get(pr['cli']) if (lim.get(pr['cli']) or 0) > now else None,
                  cap=conc.get(pr['cli']), active=running.get(pr['cli'], 0))
    # exports
    cps = []
    for c in state.get('checkpoints') or []:
        man = jload(d / 'checkpoints' / c['stamp'] / 'submission' / 'manifest.json') or {}
        cps.append(dict(c, files={b: dict(file=v.get('file'), n=v.get('n_cells'), ok=v.get('ok'))
                                  for b, v in (man.get('boards') or {}).items()} if isinstance(man.get('boards'), dict) else None))
    fin = d / 'final'
    final = dict(submission=jload(fin / 'submission' / 'manifest.json'), summary=text(fin / 'submission' / 'SUBMISSION.md', 6000),
                 fallback=text(fin / 'submission_fallback' / 'FALLBACK.md', 4000) if (fin / 'submission_fallback').exists() else None,
                 evidence=sorted(p.name for p in fin.glob('evidence_*.zip')))
    alerts = []
    for cli, pr in prov.items():
        if pr['limited_until']:
            alerts.append(dict(level='warn', msg=f"{cli} out of quota until {time.strftime('%a %H:%M', time.localtime(pr['limited_until']))}"))
    if state.get('claude_off'):
        alerts.append(dict(level='warn', msg=f"Claude weekly cap reached ({state.get('claude_week_util')}); Opus cycles use the fallback chain"))
    if state.get('paused_until'):
        alerts.append(dict(level='error', msg=f"workers paused (no quota anywhere) until {time.strftime('%a %H:%M', time.localtime(state['paused_until']))}"))
    if any(not c.get('ok') for c in cps[-2:]):
        alerts.append(dict(level='error', msg='latest checkpoint export FAILED'))
    hold_by = {(h.get('id'), h.get('board')): h for h in hold}
    probe = jload(d / 'sandbox_probe.json')
    if probe and not probe.get('ok'):
        alerts.append(dict(level='error', msg='sandbox probe failed'))
    return dict(now=now, phase=state.get('phase'), times=times, boards=boards, researchers=sorted(res.values(), key=lambda r: -r['n']),
                providers=sorted(prov.values(), key=lambda r: -r['calls']), claude_week_util=state.get('claude_week_util'),
                checkpoints=cps, final=final, alerts=alerts, gaps=metric_gaps(d), late=late[-50:],
                cycles=[dict(id=o['id'], board=o.get('board'), verdict=o.get('verdict'), researcher=o.get('researcher'),
                             intended=o.get('researcher_intended'), substitute=o.get('substitute'), t=o.get('finished'),
                             dev=o.get('dev_board'), parent_dev=o.get('parent_dev_board'), title=o.get('title'),
                             minutes=(o.get('cycle_seconds') or 0) / 60, review=(o.get('review') or {}).get('verdict'),
                             parent=o.get('parent_id'), **held_of(o, hold_by))
                        for o in sorted(outs, key=lambda o: o.get('finished') or 0)],
                held_targets=HELD_TARGET,
                holdout=[dict(id=h.get('id'), board=h.get('board'), verdict=h.get('verdict'), researcher=h.get('researcher'),
                              t=h.get('t'), score=h.get('score'), parent_score=h.get('parent_score'))
                         for h in hold if h.get('score') is not None])


# ---------- holdout phase 2 from the browser ----------
FINAL_JOBS, FAILS = {}, []


def pending_holdout():
    out = []
    for d in run_dirs():
        st = d / 'state.json'
        if d.is_dir() and st.exists():
            try:
                phase = json.loads(st.read_text()).get('phase')
            except ValueError:
                continue
            job = FINAL_JOBS.get(d.name)
            status = None
            if job:
                rc = job['proc'].poll()
                status = 'running' if rc is None else ('done' if rc == 0 else f'failed (exit {rc})')
            if run_config(d).get('auto_final') and not status:
                continue  # final run: selection starts automatically, no passphrase step
            if phase == 'awaiting_holdout' or status:
                out.append(dict(run=d.name, phase=phase, status=status, log=str(job['log'].relative_to(d.parents[2])) if job else None))
    return dict(pending=out, configs=sorted(p.name for p in MG.glob('config*.json')),
                locked_out=len([t for t in FAILS if time.time() - t < 600]) >= 3)


def start_final(body):
    run, pw = body.get('run', ''), body.get('passphrase', '')
    d = rundir({'name': [run]})
    if d is None or (jload(d / 'state.json') or {}).get('phase') != 'awaiting_holdout':
        return 400, 'run is not awaiting the holdout step'
    mg, root = d.parent.parent, d.parents[2]
    if run in FINAL_JOBS and FINAL_JOBS[run]['proc'].poll() is None:
        return 409, 'already running'
    if len([t for t in FAILS if time.time() - t < 600]) >= 3:
        return 429, 'too many wrong passphrases; wait 10 minutes'
    cfg = body.get('config') or 'config.json'
    if cfg not in {p.name for p in mg.glob('config*.json')}:
        return 400, 'unknown config'
    store = root / 'data/holdout.enc'
    rows = [line.split('\t') for line in (store / 'manifest.tsv').read_text().splitlines()]
    _, encrypted, expected = min(rows, key=lambda row: (store / row[1]).stat().st_size)
    chk = subprocess.run(['openssl', 'enc', '-d', '-aes-256-cbc', '-pbkdf2', '-iter', '300000', '-pass', 'env:MGPASS',
                          '-in', str(store / encrypted)],
                         env=dict(os.environ, MGPASS=pw), capture_output=True)
    if chk.returncode != 0 or hashlib.sha256(chk.stdout).hexdigest() != expected:
        FAILS.append(time.time())
        return 403, 'wrong passphrase'
    name = run.split('_', 3)[-1]
    lock = lock_for(d)
    log = d / 'final_web.log'
    with log.open('a') as f:
        proc = subprocess.Popen([str(mg / 'final.sh'), str(lock), name, f'agentic_scientist/{cfg}'] + (['--export'] if body.get('export') else []),
                                cwd=root, stdin=subprocess.PIPE, stdout=f, stderr=subprocess.STDOUT, start_new_session=True, text=True)
    proc.stdin.write(pw + '\n')
    proc.stdin.close()
    FINAL_JOBS[run] = dict(proc=proc, log=log)
    return 200, 'started'


class H(BaseHTTPRequestHandler):
    def send(self, code, body, ctype='application/json'):
        b = body.encode() if isinstance(body, str) else body
        self.send_response(code)
        self.send_header('Content-Type', ctype)
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(b)

    def do_POST(self):
        if urlparse(self.path).path != '/api/final' or self.headers.get('X-MG') != '1':  # custom header blocks cross-site posts
            return self.send(404, '{}')
        try:
            body = json.loads(self.rfile.read(int(self.headers.get('Content-Length', 0)) or 0) or b'{}')
            code, msg = start_final(body)
        except Exception as e:  # noqa: BLE001
            code, msg = 500, repr(e)
        return self.send(code, json.dumps(dict(message=msg)))

    def log_message(self, *a):  # never log request bodies or paths with secrets
        pass

    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        try:
            if u.path == '/':
                return self.send(200, HTML.read_text(), 'text/html; charset=utf-8')
            if u.path == '/api/runs':
                rs = [dict(name=d.name, mtime=d.stat().st_mtime) for d in run_dirs()]
                return self.send(200, json.dumps(sorted(rs, key=lambda r: -r['mtime'])))
            if u.path == '/api/pending':
                return self.send(200, json.dumps(pending_holdout()))
            if u.path == '/api/fleet':
                return self.send(200, json.dumps(fleet()))
            d = rundir(q)
            if d is None:
                return self.send(404, '{"error":"unknown run"}')
            p = u.path
            if p == '/api/run':
                r = run_detail(d)
            elif p == '/api/cycle':
                r = cycle_detail(d, q.get('id', [''])[0])
            elif p == '/api/transcript':
                f = d / 'cycles' / q.get('id', [''])[0] / q.get('file', [''])[0]
                r = dict(events=events(f)) if safe(q.get('file', [''])[0]) and f.exists() else None
            elif p == '/api/knowledge':
                kd = d / 'knowledge'
                ents = [json.loads(l) for l in text(kd / 'entries.jsonl').splitlines() if l.strip()]
                hist = sorted((kd / 'history').glob('*.md')) if (kd / 'history').exists() else []
                r = dict(synthesis=text(kd / 'knowledge.md'), entries=ents, versions=len(hist),
                         previous=text(hist[-1]) if hist else '', raw=text(d / 'notebook.md'))
            elif p == '/api/live':
                r = live(d)
            elif p == '/api/health':
                r = health(d)
            elif p == '/api/tasks':
                r = tasks(d)
            elif p == '/api/normandy':
                r = normandy(d) or {}
            elif p == '/api/tuning':
                r = tuning(d)
            elif p == '/api/activity':
                r = activity(d)
            elif p == '/api/final':
                r = final_view(d)
            elif p == '/api/limits':
                r = limits(d)
            elif p == '/api/log':
                r = logs(d, q.get('which', ['run'])[0])
            elif p == '/api/best':
                b = max((jload(d / 'state.json') or {}).get('accepted', []), key=lambda a: a['proxy'], default=None)
                ws = Path(b['ws']) if b else d / 'seed_ws'
                r = dict(id=b['id'] if b else 'seed', files={str(x.relative_to(ws)): text(x) for x in sorted(ws.rglob('*'))
                                                             if x.is_file() and x.suffix in ('.py', '.md') and '__pycache__' not in x.parts})
            else:
                r = None
            return self.send(200 if r is not None else 404, json.dumps(r, default=float))
        except Exception as e:  # noqa: BLE001
            return self.send(500, json.dumps(dict(error=repr(e))))

    def log_message(self, *a):
        pass


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--port', type=int, default=int(os.environ.get('MG_PORT', 8478)))
    ap.add_argument('--history-root', action='append', type=Path, default=[])
    a = ap.parse_args()
    RUN_ROOTS.extend(r.expanduser().resolve() / 'agentic_scientist/runs' for r in a.history_root)
    for path in RUN_ROOTS:
        if not path.is_dir():
            ap.error(f'run directory does not exist: {path}')
    ThreadingHTTPServer(('127.0.0.1', a.port), H).serve_forever()
