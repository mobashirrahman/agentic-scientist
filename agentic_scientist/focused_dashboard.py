#!/usr/bin/env python3
"""AgenticScientist operator console for focused T1, T2 heart and T2 embryo runs.

Read-only: it reads state.json, evals.jsonl, run.log and the CLI transcripts under the configured run roots and serves a
small auto-refreshing page. It never writes to the runs.

    python run_dashboard.py [--port 8790] [--host 127.0.0.1]
"""
import argparse
import json
import os
import time
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
ROOTS = {
    't1': ROOT / 'focused/temporal/runs',
    'heart': ROOT / 'focused/heart/runs',
    'embryo': ROOT / 'focused/embryo/runs',
}
PREFIX = {'t1': 't1_', 'heart': 't2h_', 'embryo': 't2e_'}
LABELS = {'t1': 'T1 · E12.5 temporal extrapolation', 'heart': 'T2 heart · E12.5 extrapolation',
          'embryo': 'T2 embryo · E7.75 interpolation'}
SHORT = {'t1': 'T1', 'heart': 'Heart', 'embryo': 'Embryo'}
TAILS = {}
MAX_EVENTS = 2000
CHUNK = 8 << 20


def read_json(path, default=None):
    try:
        return json.loads(Path(path).read_text())
    except (FileNotFoundError, ValueError, OSError):
        return default


def latest_run(key):
    root = ROOTS[key]
    cands = [p for p in root.glob(PREFIX[key] + '*') if p.is_dir() and (p / 'state.json').exists()]
    if not cands:
        return None

    def stamp(p):
        out = 0.0
        for f in ('state.json', 'run.log'):
            try:
                out = max(out, (p / f).stat().st_mtime)
            except OSError:
                pass
        return out
    return max(cands, key=stamp)


def alive(pid):
    if not pid:
        return False
    try:
        os.kill(int(pid), 0)
        return True
    except (OSError, ValueError, TypeError):
        return False


def tail_lines(path, n=16):
    try:
        with open(path, 'rb') as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            f.seek(max(0, size - 64 * 1024))
            data = f.read().decode('utf-8', 'replace')
        return data.splitlines()[-n:]
    except OSError:
        return []


def count_evals(key, rnd):
    p = latest_run(key)
    if not p:
        return 0
    f = p / 'rounds' / f'r{int(rnd):02d}' / 'evals.jsonl'
    try:
        return sum(1 for line in f.read_text(errors='replace').splitlines()
                   if line.strip() and json.loads(line).get('kind') == 'validate')
    except (OSError, ValueError):
        return 0


def run_info(key):
    p = latest_run(key)
    if not p:
        return dict(key=key, label=LABELS[key], short=SHORT[key], exists=False)
    st = read_json(p / 'state.json') or {}
    cfg = read_json(p.parent.parent / 'config.json') or {}
    pid = (read_json(p / 'orchestrator.pid.json') or {}).get('pid')
    max_evals = cfg.get('max_evals') or []
    rounds = []
    for k, r in sorted((st.get('rounds') or {}).items(), key=lambda kv: int(kv[0])):
        i = int(k)
        c = r.get('checkpoint') or {}
        rd = p / 'rounds' / f'r{i:02d}'
        files = sorted(x.name for x in (rd / 'transcripts').glob('*.jsonl')) if (rd / 'transcripts').exists() else []
        rounds.append(dict(
            round=i, status=r.get('status'), cli=r.get('cli'), model=r.get('model'),
            active_s=round(r.get('active_s') or 0), budget_s=r.get('budget_s'),
            max_evals=(max_evals[0] if i == 0 else max_evals[1]) if len(max_evals) > 1 else None,
            evals_count=count_evals(key, i), evaluations=r.get('evaluations'),
            sessions=len(r.get('sessions') or []), started=r.get('started'),
            checkpoint=c.get('snapshot'), validation=c.get('validation'),
            occupancy=((c.get('splits') or {}).get('val') or {}).get('native_occupancy'),
            files=files))
    running = [r['round'] for r in rounds if r['status'] == 'running']
    current = max(running) if running else (rounds[-1]['round'] if rounds else 0)
    final = read_json(p / 'final/selection.json') or {}
    sub = read_json(p / 'final/submission/manifest.json') or {}
    rlog = p / 'run.log'
    return dict(
        key=key, label=LABELS[key], short=SHORT[key], exists=True, id=p.name, dir=str(p), phase=st.get('phase'),
        alive=alive(pid), pid=pid, current_round=current,
        builder=(cfg.get('builder') or {}), improver=(cfg.get('improver') or {}),
        deadline=cfg.get('deadline'), improve_rounds=cfg.get('improve_rounds'),
        rounds=rounds, log=tail_lines(rlog), log_mtime=(rlog.stat().st_mtime if rlog.exists() else None),
        selected=sub.get('selected_snapshot') or final.get('selected'), rule=final.get('rule'),
        submission=(dict(file=sub.get('file'), sha256=sub.get('sha256'), n_cells=sub.get('n_cells'),
                         validation=sub.get('validation'), heldout=sub.get('heldout', sub.get('late_guard')),
                         occupancy=sub.get('native_occupancy'), model=sub.get('model'),
                         framework=sub.get('framework'), harness=sub.get('harness'))
                    if sub else None))


def evals_for(key, rnd):
    p = latest_run(key)
    if not p:
        return []
    f = p / 'rounds' / f'r{int(rnd):02d}' / 'evals.jsonl'
    out = []
    try:
        lines = f.read_text(errors='replace').splitlines()
    except OSError:
        return []
    for line in lines:
        try:
            x = json.loads(line)
        except ValueError:
            continue
        if x.get('kind') != 'validate':
            continue
        v = (x.get('splits') or {}).get('val') or {}
        out.append(dict(n=x.get('n'), validation=x.get('validation'), note=(x.get('note') or '')[:300],
                        snapshot=x.get('snapshot'), seconds=x.get('seconds'),
                        occupancy=v.get('native_occupancy'), metrics=v.get('metrics') or {}))
    return out[-250:]


def transcript_files(key, rnd):
    p = latest_run(key)
    if not p:
        return []
    d = p / 'rounds' / f'r{int(rnd):02d}' / 'transcripts'
    return sorted(x.name for x in d.glob('*.jsonl')) if d.exists() else []


def cliptext(value, n=1200):
    if isinstance(value, str):
        s = value
    elif isinstance(value, list):
        s = '\n'.join(cliptext(x, n) for x in value)
    elif isinstance(value, dict):
        if 'text' in value:
            s = str(value.get('text'))
        elif 'content' in value:
            s = cliptext(value.get('content'), n)
        else:
            s = json.dumps(value, ensure_ascii=False)
    elif value is None:
        s = ''
    else:
        s = str(value)
    s = s.strip()
    return s if len(s) <= n else s[:n] + f' … [{len(s) - n} more chars]'


def stamp_of(ev):
    t = ev.get('timestamp') or (ev.get('event') or {}).get('timestamp')
    try:
        return time.strftime('%H:%M:%S', time.localtime(float(t) / 1000.0)) if t else ''
    except (ValueError, TypeError, OSError):
        return ''


def normalize(e):
    out = []
    if not isinstance(e, dict):
        return out
    ts = stamp_of(e)
    typ = e.get('type')
    if typ == 'event':
        ev = e.get('event') or {}
        t = ev.get('type')
        if t == 'run_start':
            out.append(dict(kind='system', text=f"session {ev.get('sessionId', '')}", ts=ts))
        elif t == 'thinking_end':
            out.append(dict(kind='think', text=cliptext(ev.get('text')), ts=ts))
        elif t == 'message_end':
            blocks = ev.get('content') or []
            text = '\n'.join(b.get('text', '') for b in blocks if isinstance(b, dict) and b.get('type') == 'text')
            if text.strip():
                out.append(dict(kind='msg', text=cliptext(text), ts=ts))
        elif t == 'tool_queued':
            out.append(dict(kind='tool', name=ev.get('toolName'), text=cliptext(ev.get('input'), 600), ts=ts))
        elif t == 'tool_completed':
            out.append(dict(kind='result', name=ev.get('toolName'), text=cliptext(ev.get('result')), ts=ts))
        elif t == 'turn_start':
            out.append(dict(kind='sep', text=f"turn {ev.get('turnNumber', '')}", ts=ts))
        return out
    if typ in ('assistant', 'user'):
        msg = e.get('message') or {}
        for b in msg.get('content') or []:
            if not isinstance(b, dict):
                continue
            bt = b.get('type')
            if bt == 'text':
                out.append(dict(kind='msg' if typ == 'assistant' else 'result', text=cliptext(b.get('text')), ts=ts))
            elif bt == 'thinking':
                out.append(dict(kind='think', text=cliptext(b.get('thinking')), ts=ts))
            elif bt == 'tool_use':
                out.append(dict(kind='tool', name=b.get('name'), text=cliptext(b.get('input'), 600), ts=ts))
            elif bt == 'tool_result':
                out.append(dict(kind='result', text=cliptext(b.get('content')), ts=ts))
        return out
    if typ == 'system':
        out.append(dict(kind='system', text=f"system {e.get('subtype', '')} {e.get('model', '')}".strip(), ts=ts))
        return out
    if typ == 'rate_limit_event':
        info = e.get('rate_limit_info') or {}
        out.append(dict(kind='error', text=f"rate limit {info.get('status', '')} {info.get('rateLimitType', '')}", ts=ts))
        return out
    if typ == 'result':
        sub = e.get('subtype')
        if sub == 'success':
            out.append(dict(kind='final', text=cliptext(e.get('finalText') or e.get('result')), ts=ts))
        else:
            out.append(dict(kind='error', text=cliptext(e.get('error') or e.get('result') or sub), ts=ts))
        return out
    if typ == 'thread.started':
        out.append(dict(kind='system', text=f"thread {e.get('thread_id', '')}", ts=ts))
        return out
    if typ == 'turn.failed':
        out.append(dict(kind='error', text=cliptext((e.get('error') or {}).get('message') or e.get('error')), ts=ts))
        return out
    if typ == 'item.completed':
        it = e.get('item') or {}
        k = it.get('type')
        if k == 'agent_message':
            out.append(dict(kind='msg', text=cliptext(it.get('text')), ts=ts))
        elif k == 'reasoning':
            out.append(dict(kind='think', text=cliptext(it.get('text')), ts=ts))
        elif k == 'command_execution':
            out.append(dict(kind='tool', name='shell', text=cliptext(it.get('command'), 600), ts=ts))
            if it.get('aggregated_output'):
                out.append(dict(kind='result', text=cliptext(it.get('aggregated_output')), ts=ts))
        elif k == 'file_change':
            paths = [c.get('path') for c in it.get('changes') or [] if isinstance(c, dict)]
            out.append(dict(kind='tool', name='edit', text=cliptext(paths, 300), ts=ts))
        elif k == 'web_search':
            out.append(dict(kind='tool', name='web', text=cliptext(it.get('query'), 300), ts=ts))
        return out
    return out


class Tail:
    def __init__(self, path):
        self.path = Path(path)
        self.offset = 0
        self.buf = b''
        self.events = deque(maxlen=MAX_EVENTS)

    def reset(self):
        self.offset = 0
        self.buf = b''
        self.events.clear()

    def update(self, limit=400):
        try:
            size = self.path.stat().st_size
        except OSError:
            return []
        if size < self.offset:
            self.reset()
        if size - self.offset > CHUNK:
            self.offset = size - CHUNK
            self.buf = b''
        if size == self.offset:
            return list(self.events)[-limit:]
        try:
            with self.path.open('rb') as f:
                f.seek(self.offset)
                data = f.read(size - self.offset)
        except OSError:
            return list(self.events)[-limit:]
        self.offset = size
        self.buf += data
        parts = self.buf.split(b'\n')
        self.buf = parts.pop()
        for raw in parts:
            line = raw.decode('utf-8', 'replace').strip()
            if not line:
                continue
            try:
                e = json.loads(line)
            except ValueError:
                continue
            for ev in normalize(e):
                self.events.append(ev)
        return list(self.events)[-limit:]


def transcript(key, rnd, name, limit=400):
    files = transcript_files(key, rnd)
    if name not in files:
        name = files[-1] if files else None
    if not name:
        return dict(events=[], files=[], file=None, mtime=None, size=0)
    p = latest_run(key) / 'rounds' / f'r{int(rnd):02d}' / 'transcripts' / name
    k = str(p)
    t = TAILS.get(k)
    if t is None:
        t = TAILS[k] = Tail(p)
    return dict(events=t.update(limit), files=files, file=name,
                mtime=(p.stat().st_mtime if p.exists() else None),
                size=(p.stat().st_size if p.exists() else 0))


PAGE = r"""<!doctype html>
<html><head><meta charset="utf-8"><title>focused runs</title>
<style>
:root{--bg:#0b0f14;--card:#111821;--line:#26303c;--fg:#d7dee8;--dim:#8b98a8;--accent:#58a6ff;
--msg:#e2b8ff;--think:#7d8896;--tool:#7ee787;--result:#79c0ff;--err:#ff7b72;--ok:#3fb950;--warn:#d29922}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:13px/1.5 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}
header{position:sticky;top:0;z-index:5;background:#0d131a;border-bottom:1px solid var(--line);
 padding:8px 14px;display:flex;gap:14px;align-items:center;flex-wrap:wrap}
header h1{font-size:15px;margin:0;font-weight:600;letter-spacing:.2px}
.tabs{display:flex;gap:4px}.tabs button{background:#161e28;border:1px solid var(--line);color:var(--dim);
 padding:3px 10px;border-radius:999px;cursor:pointer;font:inherit;font-size:12px}
.tabs button.on{color:var(--fg);border-color:var(--accent);background:#1b2635}
.clock{margin-left:auto;color:var(--dim);font-size:12px}
#runs{padding:12px;display:flex;flex-direction:column;gap:14px;max-width:1900px;margin:0 auto}
.run{background:var(--card);border:1px solid var(--line);border-radius:10px;overflow:hidden}
.run.hidden{display:none}
.runhead{display:flex;gap:10px;align-items:center;flex-wrap:wrap;padding:10px 14px;border-bottom:1px solid var(--line)}
.runhead h2{font-size:14px;margin:0;font-weight:600}
.pill{border:1px solid var(--line);border-radius:999px;padding:1px 8px;font-size:11px;color:var(--dim)}
.pill.live{color:var(--ok);border-color:#1f6f3f;background:#0e1b14}
.pill.dead{color:var(--err);border-color:#5a2a2a;background:#1b1010}
.pill.phase{color:var(--accent);border-color:#25415f;background:#0e1723}
.meta{color:var(--dim);font-size:12px}
.status{display:grid;grid-template-columns:1.1fr 1fr 1.4fr;gap:12px;padding:10px 14px;border-bottom:1px solid var(--line)}
@media(max-width:1000px){.status{grid-template-columns:1fr}}
.stat .k{color:var(--dim);font-size:11px;text-transform:uppercase;letter-spacing:.4px}
.stat .v{font-size:13px;margin-top:2px}
.bar{height:6px;background:#0b1119;border:1px solid var(--line);border-radius:999px;overflow:hidden;margin-top:5px}
.bar i{display:block;height:100%;background:var(--accent);width:0}
.bar.green i{background:var(--ok)}.bar.warn i{background:var(--warn)}
.now{margin-top:4px;color:var(--fg);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.now b{color:var(--tool)}
.rounds{display:flex;gap:6px;flex-wrap:wrap;padding:8px 14px;border-bottom:1px solid var(--line)}
.chip{background:#161e28;border:1px solid var(--line);border-radius:6px;padding:4px 8px;font:inherit;font-size:11.5px;
 color:var(--dim);cursor:pointer}.chip:hover{border-color:var(--accent)}
.chip.sel{border-color:var(--accent);color:var(--fg);background:#1b2635}
.chip.running{color:var(--ok);border-color:#1f6f3f}
.chip .s{font-weight:600;margin-left:5px}
.grid{display:grid;grid-template-columns:minmax(0,2.1fr) minmax(0,1fr);gap:0}
@media(max-width:1200px){.grid{grid-template-columns:1fr}}
.col{padding:10px 14px;min-width:0}.col+ .col{border-left:1px solid var(--line)}
@media(max-width:1200px){.col+ .col{border-left:0;border-top:1px solid var(--line)}}
.colhead{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:6px}
.colhead .t{font-weight:600}.colhead .sub{color:var(--dim);font-size:11.5px}
.toolbar{margin-left:auto;display:flex;gap:6px;align-items:center;flex-wrap:wrap}
select,button.act{background:#161e28;color:var(--fg);border:1px solid var(--line);border-radius:5px;
 padding:2px 7px;font:inherit;font-size:11.5px}button.act{cursor:pointer}button.act:hover{border-color:var(--accent)}
label.sw{color:var(--dim);font-size:11.5px;display:flex;gap:4px;align-items:center;cursor:pointer}
.activity{height:440px;overflow:auto;background:#080c11;border:1px solid var(--line);border-radius:6px;padding:8px}
.ev{margin:0 0 6px;white-space:pre-wrap;word-break:break-word}
.ev .ts{color:#4b5666;font-size:10px;margin-right:6px}
.ev .nm{color:#ffa657;margin-right:6px}
.ev.msg{color:var(--msg)}
.ev.think{color:var(--think);font-style:italic}
.ev.tool{color:var(--tool)}
.ev.result{color:var(--result)}
.ev.error{color:var(--err)}
.ev.final{color:var(--ok)}
.ev.system{color:var(--dim)}
.ev.sep{color:#4b5666;border-top:1px dashed #1b242e;padding-top:5px;margin-top:7px}
.ev.evalresult{color:var(--ok);background:#0d1a12;border-left:2px solid var(--ok);padding:2px 6px}
.ev details summary{cursor:pointer;color:var(--dim)}
.ev details pre{margin:4px 0 0;white-space:pre-wrap;color:var(--result);max-height:220px;overflow:auto}
.spark{width:100%;height:46px;display:block;margin:2px 0 6px}
.latest{display:flex;gap:12px;align-items:baseline;padding:6px 8px;background:#0d1a12;border:1px solid #1f6f3f;
 border-radius:6px;margin-bottom:8px;flex-wrap:wrap}
.latest .big{font-size:22px;color:var(--ok);font-weight:600}
.latest .d{color:var(--dim)}.latest .note{color:var(--dim);font-size:11.5px;flex:1;min-width:160px}
.evals{height:330px;overflow:auto}
table{width:100%;border-collapse:collapse;font-size:11.5px}
th,td{text-align:left;padding:3px 5px;border-bottom:1px solid #1a222c;white-space:nowrap}
th{color:var(--dim);font-weight:500;position:sticky;top:0;background:var(--card)}
tr.best td{background:#0e1b14}
td.note{color:var(--dim);white-space:normal;max-width:360px}
.good{color:var(--ok)}.bad{color:var(--err)}.acc{color:var(--accent)}
pre.log{margin:0;max-height:120px;overflow:auto;font-size:11px;color:var(--dim);background:#080c11;
 padding:6px;border-radius:5px;border:1px solid var(--line)}
.sub{padding:10px 14px;border-top:1px solid var(--line);color:var(--dim);font-size:12px}
</style></head><body>
<header><h1>focused agent runs</h1>
<div class="tabs" id="tabs"><button data-tab="all" class="on">All</button><button data-tab="t1">T1</button><button data-tab="embryo">Embryo</button><button data-tab="heart">Heart</button></div>
<span class="clock" id="clock"></span></header>
<div id="runs"></div>
<script>
const RUN_KEYS=['t1','heart','embryo'];
const S={tab:'all',...Object.fromEntries(RUN_KEYS.map(k=>[k,
  {round:null,currentRound:null,file:null,think:false,out:false,follow:true,built:false,run:null,key:''}]))};
const $=id=>document.getElementById(id);
const esc=s=>String(s==null?'':s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const hhmm=s=>{s=Math.max(0,Math.round(s||0));const h=Math.floor(s/3600),m=Math.floor(s%3600/60);return h?`${h}h ${m}m`:`${m}m`};
const num=(v,d=2)=>v==null?'—':(+v).toFixed(d);
const ago=t=>{if(!t)return '—';const s=Math.max(0,Date.now()/1000-t);return s<60?`${Math.round(s)}s ago`:`${Math.round(s/60)}m ago`};
const base=k=>k==='heart'?'#ffa657':'#58a6ff';
function spark(vals){if(vals.length<2)return '';const w=320,h=42,p=3,mn=Math.min(...vals),mx=Math.max(...vals),d=mx-mn||1;
 const pts=vals.map((v,i)=>`${p+i*(w-2*p)/(vals.length-1)},${h-p-(v-mn)/d*(h-2*p)}`).join(' ');
 return `<svg class="spark" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none"><polyline points="${pts}" fill="none" stroke="#3fb950" stroke-width="1.6"/></svg>`}
function shell(k,info){
 const r0=info.rounds[0]||{}; const model=(r0.model||'');
 return `<section class="run" id="run-${k}">
  <div class="runhead"><h2>${esc(info.label)}</h2>
    <span class="pill ${info.alive?'live':'dead'}" id="live-${k}">${info.alive?'running':'not running'}</span>
    <span class="pill">${esc(info.id)}</span><span class="pill phase" id="phase-${k}">phase ${esc(info.phase)}</span>
    <span class="meta" id="meta-${k}"></span></div>
  <div class="status">
    <div class="stat"><div class="k">current round</div><div class="v" id="cr-${k}"></div>
      <div class="bar" id="tbar-${k}"><i></i></div><div class="meta" id="tmeta-${k}"></div></div>
    <div class="stat"><div class="k">evaluations</div><div class="v" id="evc-${k}"></div>
      <div class="bar green" id="ebar-${k}"><i></i></div><div class="meta" id="evmeta-${k}"></div></div>
    <div class="stat"><div class="k">what is happening</div><div class="now" id="now-${k}">—</div>
      <div class="meta" id="nowmeta-${k}"></div></div>
  </div>
  <div class="rounds" id="rounds-${k}"></div>
  <div class="grid">
    <div class="col"><div class="colhead"><span class="t">Activity</span><span class="sub" id="actmeta-${k}"></span>
      <div class="toolbar" id="tools-${k}"></div></div>
      <div class="activity" id="act-${k}"></div></div>
    <div class="col"><div class="colhead"><span class="t">Evaluations</span>
      <span class="sub" id="evalsub-${k}"></span></div>
      <div id="spark-${k}"></div><div id="latest-${k}"></div><div class="evals" id="evals-${k}"></div></div>
  </div>
  <div class="sub" id="sub-${k}"></div>
  <div class="col"><pre class="log" id="log-${k}"></pre></div>
 </section>`;
}
function tools(k,info){
 const st=S[k]; const rnd=st.round??info.current_round; const round=info.rounds.find(r=>r.round===rnd)||{};
 const files=round.files||[];
 return `<select onchange="setFile('${k}',this.value)" title="transcript session">${files.map(f=>`<option ${f===st.file?'selected':''}>${esc(f)}</option>`).join('')}</select>
  <button class="act" onclick="setFile('${k}',null)">latest</button>
  <label class="sw"><input type="checkbox" ${st.think?'checked':''} onchange="setFlag('${k}','think',this.checked)">thinking</label>
  <label class="sw"><input type="checkbox" ${st.out?'checked':''} onchange="setFlag('${k}','out',this.checked)">tool output</label>
  <label class="sw"><input type="checkbox" ${st.follow?'checked':''} onchange="setFlag('${k}','follow',this.checked)">follow</label>
  <button class="act" onclick="toBottom('${k}')">latest ↓</button>
  <a class="act" style="text-decoration:none" href="/api/raw?run=${k}&round=${rnd}&file=${encodeURIComponent(st.file||'')}">raw ↓</a>`;
}
function updateShell(k,info){
 const rnd=S[k].round??info.current_round; const r=info.rounds.find(x=>x.round===rnd)||{};
 $('live-'+k).className='pill '+(info.alive?'live':'dead'); $('live-'+k).textContent=info.alive?'running':'not running';
 $('phase-'+k).textContent='phase '+(info.phase||'');
 $('phase-'+k).className='pill phase';
 $('meta-'+k).textContent=[info.builder&&info.builder.model,info.deadline&&('deadline '+info.deadline),info.selected&&('selected '+info.selected)].filter(Boolean).join(' · ');
 $('cr-'+k).textContent=`r${String(rnd).padStart(2,'0')} · ${r.status||'—'} · ${r.cli||''}:${r.model||''}`;
 $('tbar-'+k).querySelector('i').style.width=Math.min(100,100*(r.active_s||0)/Math.max(1,r.budget_s||1))+'%';
 const wall=r.started?Math.max(0,Date.now()/1000-new Date(r.started.replace(' ','T')).getTime()/1000):0;
 $('tmeta-'+k).textContent=`${hhmm(wall)} wall · ${hhmm(r.active_s)} active of ${hhmm(r.budget_s)}`;
 const ev=r.evals_count||0, mx=r.max_evals||0;
 $('evc-'+k).textContent=`${ev}${mx?` / ${mx}`:''}`;
 $('ebar-'+k).querySelector('i').style.width=(mx?Math.min(100,100*ev/mx):0)+'%';
 $('evmeta-'+k).textContent=r.sessions?`${r.sessions} agent sessions`:'';
 $('rounds-'+k).innerHTML=info.rounds.map(x=>`<button class="chip ${x.round===rnd?'sel':''} ${x.status||''}" onclick="pickRound('${k}',${x.round})">
   r${String(x.round).padStart(2,'0')} <span class="s">${x.status==='done'?'✓':x.status==='running'?'●':'○'}</span>
   <span class="s">${x.validation==null?'':num(x.validation)}</span></button>`).join('');
 $('tools-'+k).innerHTML=tools(k,info);
 $('sub-'+k).textContent=info.submission?`submission ${info.submission.file} · ${info.submission.n_cells} cells · val ${num(info.submission.validation)} · guard ${num(info.submission.heldout)}${info.submission.occupancy==null?'':` · occ ${num(info.submission.occupancy,3)}`} · ${info.submission.model||''}`:(info.rule?('selection rule: '+info.rule):'');
 $('log-'+k).textContent=(info.log||[]).join('\n');
}
function summarize(e){
 const t=(e.text||'').replace(/\s+/g,' ').trim();
 if(e.kind==='tool'){
   let a=t; if(e.name==='read_file'){const m=t.match(/"file_path":\s*"([^"]+)"/); if(m)a=m[1].split('/').pop();}
   else if(e.name==='shell'){a=t.replace(/^\/usr\/bin\/bash -lc ['"]?/,'').slice(0,180);}
   else if(e.name==='web'){a=t.slice(0,160);}
   return `<b>${esc(e.name||'tool')}</b> ${esc(a.slice(0,220))}`;
 }
 return esc(t.slice(0,240));
}
function renderEvents(k){
 const st=S[k]; const evs=st.events||[];
 const html=evs.map(e=>{
   const ts=`<span class="ts">${esc(e.ts||'')}</span>`;
   if(e.kind==='think'){
     if(!st.think)return '';
     return `<div class="ev think">${ts}<details><summary>thinking · ${ (e.text||'').length } chars</summary>${esc(e.text||'')}</details></div>`;
   }
   if(e.kind==='result'){
     const t=e.text||'';
     if(/validation\s*=/.test(t)) return `<div class="ev evalresult">${ts}${esc(t.split('\n')[0])}</div>`;
     if(!st.out) return '';
     return `<div class="ev result">${ts}<details><summary>${esc(e.name||'result')} · ${t.length} chars</summary>${esc(t)}</details></div>`;
   }
   if(e.kind==='tool') return `<div class="ev tool">${ts}<span class="nm">▸</span>${summarize(e)}</div>`;
   if(e.kind==='msg') return `<div class="ev msg">${ts}${esc((e.text||'').slice(0,1600))}</div>`;
   if(e.kind==='sep') return `<div class="ev sep">${ts}${esc(e.text||'')}</div>`;
   if(e.kind==='error') return `<div class="ev error">${ts}${esc(e.text||'')}</div>`;
   if(e.kind==='final') return `<div class="ev final">${ts}${esc(e.text||'')}</div>`;
   return `<div class="ev system">${ts}${esc(e.text||'')}</div>`;
 }).join('');
 const box=$('act-'+k); if(!box)return;
 const near=box.scrollHeight-box.scrollTop-box.clientHeight<60;
 box.innerHTML=html||'<span class="ev system">no events yet</span>';
 if(st.follow&&near)box.scrollTop=box.scrollHeight;
 // now line
 const last=[...(st.events||[])].reverse().find(e=>e.kind!=='sep'&&e.kind!=='system');
 if(last){
   $('now-'+k).innerHTML=last.kind==='tool'?summarize(last):
     last.kind==='think'?`<b>thinking…</b> ${esc((last.text||'').slice(0,180))}`:
     last.kind==='msg'?('agent: '+esc((last.text||'').slice(0,180))):esc((last.text||'').slice(0,180));
   $('now-'+k).title=(last.text||'').slice(0,600);
 }
 $('nowmeta-'+k).textContent=`last write ${ago(st.mtime)} · ${st.file||''} · ${st.events?st.events.length:0} events shown`;
 $('actmeta-'+k).textContent=`${st.file||''} · ${(st.size/1024).toFixed(0)} KiB`;
}
function renderEvals(k,info){
 const st=S[k]; const evs=st.evals||[];
 const best=evs.reduce((a,b)=>((b.validation||-1)>(a.validation||-1)?b:a),{});
 const last=evs[evs.length-1];
 $('spark-'+k).innerHTML=spark(evs.map(e=>e.validation).filter(v=>v!=null));
 if(last){
   const prev=evs[evs.length-2];
   const d=prev&&prev.validation!=null&&last.validation!=null?last.validation-prev.validation:null;
   $('latest-'+k).innerHTML=`<div class="latest"><span class="big">${num(last.validation)}</span>
     <span class="d">${d==null?'':(d>=0?'+':'')+d.toFixed(3)} vs prev · eval #${last.n} · ${esc(last.snapshot||'')}</span>
     <span class="note">${esc(last.note||'')}</span></div>`;
 } else $('latest-'+k).innerHTML='';
 $('evalsub-'+k).textContent=`${evs.length} evals · best ${best.validation==null?'—':num(best.validation)}`;
 $('evals-'+k).innerHTML=`<table><thead><tr><th>#</th><th>val</th><th>Δ</th>${k==='t1'?'':'<th>occ</th>'}<th>note</th></tr></thead><tbody>
  ${evs.slice(-40).reverse().map(e=>{const i=evs.indexOf(e);const p=evs[i-1];
    const d=p&&p.validation!=null&&e.validation!=null?e.validation-p.validation:null;
    return `<tr class="${e.n===best.n?'best':''}"><td>${e.n??''}</td><td class="good">${num(e.validation,3)}</td>
      <td class="${d==null?'':d>=0?'good':'bad'}">${d==null?'':(d>=0?'+':'')+d.toFixed(3)}</td>
      ${k==='t1'?'':`<td class="acc">${num(e.occupancy,3)}</td>`}<td class="note">${esc(e.note||'')}</td></tr>`}).join('')}
  </tbody></table>`;
}
async function loadEvals(k){
 const st=S[k]; const rnd=st.round;
 const evs=await (await fetch(`/api/evals?run=${k}&round=${rnd}`)).json();
 st.evals=evs; renderEvals(k);
}
async function loadActivity(k){
 const st=S[k]; const rnd=st.round;
 const d=await (await fetch(`/api/transcript?run=${k}&round=${rnd}&file=${encodeURIComponent(st.file||'')}`)).json();
 st.files=d.files; st.file=d.file; st.size=d.size; st.mtime=d.mtime;
 const key=`${d.file}|${d.size}|${d.events.length}`;
 if(key!==st.key){st.key=key;st.events=d.events;renderEvents(k);}
 else { if($('nowmeta-'+k))$('nowmeta-'+k).textContent=`last write ${ago(st.mtime)} · ${st.file||''} · ${st.events.length} events shown`; }
}
async function refresh(){
 const d=await (await fetch('/api/overview')).json();
 for(const k of RUN_KEYS){
   const info=d[k]; const st=S[k];
   if(!info?.exists)continue;
   if(!st.built||st.run!==info.id){
     const old=$('run-'+k); if(old)old.remove();
     $('runs').insertAdjacentHTML('beforeend',shell(k,info));
     st.built=true;st.run=info.id;st.round=info.current_round;st.file=null;st.key='';
   }else if(st.round===st.currentRound && st.currentRound!==info.current_round){
     st.round=info.current_round;st.file=null;st.key='';
   }
   st.currentRound=info.current_round;
   $('run-'+k).classList.toggle('hidden',S.tab!=='all'&&S.tab!==k);
   updateShell(k,info);
   await loadEvals(k); await loadActivity(k);
 }
 $('clock').textContent=new Date().toLocaleTimeString();
}
function setTab(t){S.tab=t;document.querySelectorAll('#tabs button').forEach(b=>b.classList.toggle('on',b.dataset.tab===t));
 for(const k of RUN_KEYS){const el=$('run-'+k);if(el)el.classList.toggle('hidden',t!=='all'&&t!==k);}}
function pickRound(k,r){S[k].round=r;S[k].file=null;S[k].key='';refresh();}
function setFile(k,f){S[k].file=f;S[k].key='';refresh();}
function setFlag(k,f,v){S[k][f]=v;if(f==='follow'&&v){toBottom(k)}refresh();}
function toBottom(k){const b=$('act-'+k);if(b)b.scrollTop=b.scrollHeight;}
document.querySelectorAll('#tabs button').forEach(b=>b.onclick=()=>setTab(b.dataset.tab));
refresh();setInterval(refresh,5000);
</script></body></html>"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype='application/json', extra=None):
        data = body if isinstance(body, bytes) else body.encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        u = urlparse(self.path)
        q = {k: v[-1] for k, v in parse_qs(u.query).items()}
        try:
            if u.path == '/':
                return self._send(200, PAGE, 'text/html; charset=utf-8')
            if u.path == '/api/overview':
                return self._send(200, json.dumps({k: run_info(k) for k in ROOTS}))
            if u.path == '/api/evals':
                k = q.get('run', '')
                if k not in ROOTS:
                    return self._send(400, json.dumps(dict(error='bad run')))
                return self._send(200, json.dumps(evals_for(k, int(q.get('round', 0)))))
            if u.path == '/api/transcript':
                k = q.get('run', '')
                if k not in ROOTS:
                    return self._send(400, json.dumps(dict(error='bad run')))
                return self._send(200, json.dumps(transcript(k, int(q.get('round', 0)), q.get('file') or '')))
            if u.path == '/api/raw':
                k = q.get('run', '')
                files = transcript_files(k, int(q.get('round', 0)))
                name = q.get('file') or ''
                if k not in ROOTS or name not in files:
                    return self._send(404, json.dumps(dict(error='not found')))
                p = latest_run(k) / 'rounds' / f"r{int(q.get('round', 0)):02d}" / 'transcripts' / name
                return self._send(200, p.read_bytes(), 'application/x-ndjson',
                                  {'Content-Disposition': f'attachment; filename="{name}"'})
            return self._send(404, json.dumps(dict(error='not found')))
        except Exception as e:  # noqa: BLE001 - dashboard must stay up
            return self._send(500, json.dumps(dict(error=f'{type(e).__name__}: {e}')))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--port', type=int, default=8790)
    ap.add_argument('--host', default='127.0.0.1')
    a = ap.parse_args()
    srv = ThreadingHTTPServer((a.host, a.port), Handler)
    print(f'dashboard: http://{a.host}:{a.port}  (Ctrl-C to stop)', flush=True)
    srv.serve_forever()


if __name__ == '__main__':
    main()
