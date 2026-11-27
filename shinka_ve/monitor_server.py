"""Monitoring server for ShinkaEvolve runs (read-only).

Usage:  .venv/bin/python shinka_ve/monitor_server.py --port 8477
Tunnel: ssh -L 8477:localhost:8477 bio06   ->  http://localhost:8477
"""
import argparse
import json
import re
import sqlite3
import subprocess
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent
RUNS_DIR = ROOT / 'runs'
MAX_FILE = 400_000  # cap per file sent to the browser


# ---------- helpers ----------
def read_text(p, limit=MAX_FILE, tail=False):
    try:
        data = Path(p).read_bytes()
    except OSError:
        return None
    if len(data) > limit:
        data = data[-limit:] if tail else data[:limit]
    return data.decode('utf-8', errors='replace')


def read_json(p):
    t = read_text(p)
    if t is None:
        return None
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        return None


def list_runs():
    runs = [d for d in RUNS_DIR.glob('lock_*') if d.is_dir()]
    return sorted(runs, key=lambda p: p.stat().st_mtime, reverse=True)


def resolve_run(name=None):
    runs = list_runs()
    if name:
        for r in runs:
            if r.name == name:
                return r
    return runs[0] if runs else None


def process_alive(run_dir):
    # run name is the suffix after the timestamp, e.g. bio06_run1
    m = re.match(r'lock_\d+_\d+_(.+)$', run_dir.name)
    pattern = f'run_evo.py.*{m.group(1)}' if m else 'run_evo.py'
    try:
        return subprocess.run(['pgrep', '-f', pattern], capture_output=True,
                              timeout=3).returncode == 0
    except Exception:
        return False


def gen_num(p):
    try:
        return int(p.name.split('_')[1])
    except (IndexError, ValueError):
        return -1


def safe_join(base, rel):
    """Resolve rel under base; return None if it escapes."""
    p = (base / rel).resolve()
    try:
        p.relative_to(base.resolve())
    except ValueError:
        return None
    return p


# ---------- data readers ----------
def attempts_for_gen(gdir):
    """All patch attempts (LLM transcripts) for a generation, oldest first."""
    out = []
    adir = gdir / 'attempts'
    if not adir.exists():
        return out
    for pdir in adir.rglob('patch_*'):
        if not pdir.is_dir():
            continue
        meta = read_json(pdir / 'metadata.json') or {}
        has_resp = (pdir / 'llm_response.txt').exists()
        mtime = max((f.stat().st_mtime for f in pdir.iterdir()), default=0)
        out.append({
            'path': str(pdir.relative_to(gdir.parent)),
            'generation': gen_num(gdir),
            'patch_name': meta.get('patch_name'),
            'model': meta.get('llm_model'),
            'cost': meta.get('llm_cost'),
            'success': meta.get('success'),
            'error': meta.get('error_msg'),
            'timestamp': meta.get('timestamp'),
            'mtime': mtime,
            'pending': not has_resp and not meta,
            'description': meta.get('patch_description'),
        })
    out.sort(key=lambda a: a['mtime'])
    return out


def read_generations(run_dir):
    gens = []
    for d in sorted(run_dir.glob('gen_*'), key=gen_num):
        if gen_num(d) < 0:
            continue
        res = d / 'results'
        m = read_json(res / 'metrics.json')
        c = read_json(res / 'correct.json') or {}
        attempts = attempts_for_gen(d)
        final = next((a for a in reversed(attempts) if a.get('success')), None) \
            or (attempts[-1] if attempts else {})
        g = {
            'generation': gen_num(d),
            'evaluated': m is not None,
            'correct': bool(c.get('correct', False)),
            'error': c.get('error'),
            'combined_score': (m or {}).get('combined_score'),
            'board_scores': ((m or {}).get('public') or {}).get('board_scores', {}),
            'split_scores': ((m or {}).get('private') or {}).get('split_scores', {}),
            'text_feedback': (m or {}).get('text_feedback'),
            'patch_name': final.get('patch_name'),
            'model': final.get('model'),
            'cost': sum((a.get('cost') or 0) for a in attempts),
            'n_attempts': len(attempts),
            'has_diff': (d / 'edit.diff').exists(),
            'mtime': d.stat().st_mtime,
        }
        gens.append(g)
    return gens


def archive(run_dir, limit=30):
    db = run_dir / 'programs.sqlite'
    if not db.exists():
        return []
    try:
        conn = sqlite3.connect(f'file:{db}?mode=ro', uri=True, timeout=2)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            'SELECT id, generation, combined_score AS score, island_idx AS island, '
            'correct, parent_id, children_count FROM programs '
            'ORDER BY combined_score DESC LIMIT ?', (limit,)).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        return [{'error': str(e)}]


def limit_events(run_dir):
    t = read_text(run_dir / 'limit_events.jsonl', tail=True) or ''
    ev = []
    for line in t.splitlines()[-200:]:
        try:
            ev.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    return ev


def total_cost(run_dir):
    t = read_text(run_dir / 'evolution_run.log', limit=300_000, tail=True) or ''
    m = re.findall(r'Total Cost: \$([0-9.]+)', t)
    return float(m[-1]) if m else 0.0


# ---------- HTTP ----------
class Handler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def log_message(self, *a):
        pass

    def send_body(self, body, ctype, code=200):
        self.send_response(code)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)

    def send_json(self, data, code=200):
        self.send_body(json.dumps(data).encode(), 'application/json', code)

    def do_GET(self):
        u = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        try:
            if u.path in ('/', '/index.html'):
                html = (ROOT / 'monitor_dashboard.html').read_bytes()
                return self.send_body(html, 'text/html; charset=utf-8')
            if u.path == '/api/runs':
                return self.send_json([r.name for r in list_runs()])
            run = resolve_run(q.get('run'))
            if u.path.startswith('/api/') and run is None:
                return self.send_json({'error': 'no runs found'}, 404)
            fn = getattr(self, 'api_' + u.path[5:], None) if u.path.startswith('/api/') else None
            if fn is None:
                return self.send_json({'error': 'not found'}, 404)
            return self.send_json(fn(run, q))
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as e:  # never kill the server on a bad request
            try:
                self.send_json({'error': f'{type(e).__name__}: {e}'}, 500)
            except Exception:
                pass

    # -- endpoints --
    def api_overview(self, run, q):
        gens = read_generations(run)
        scored = [g for g in gens if g['evaluated'] and g['combined_score'] is not None]
        ok = [g for g in scored if g['correct']]
        best = max(ok, key=lambda g: g['combined_score'], default=None)
        base = next((g for g in scored if g['generation'] == 0), None)
        log = run / 'evolution_run.log'
        return {
            'run_name': run.name,
            'alive': process_alive(run),
            'server_time': time.time(),
            'log_mtime': log.stat().st_mtime if log.exists() else None,
            'cost': total_cost(run),
            'n_gens': len(gens),
            'n_evaluated': len(scored),
            'n_correct': len(ok),
            'best_score': best['combined_score'] if best else None,
            'best_gen': best['generation'] if best else None,
            'baseline': base['combined_score'] if base else None,
            'latest_gen': gens[-1]['generation'] if gens else None,
            'generations': gens,
            'limit_events': len(limit_events(run)),
        }

    def api_log(self, run, q):
        """Incremental log tail. offset=N returns bytes after N; no offset = last 60KB."""
        f = run / 'evolution_run.log'
        if q.get('which') == 'main':
            f = RUNS_DIR / (run.name.split('_', 3)[-1] + '.log')
        if not f.exists():
            return {'size': 0, 'text': '', 'reset': True}
        size = f.stat().st_size
        off = int(q['offset']) if q.get('offset', '').isdigit() else None
        reset = off is None or off > size
        start = max(0, size - 60_000) if reset else off
        with open(f, 'rb') as fh:
            fh.seek(start)
            data = fh.read(400_000)
        return {'size': start + len(data), 'text': data.decode('utf-8', errors='replace'),
                'reset': reset}

    def api_attempts(self, run, q):
        out = []
        for d in sorted(run.glob('gen_*'), key=gen_num):
            out.extend(attempts_for_gen(d))
        # in-flight prompts that have no attempt dir yet
        out.sort(key=lambda a: a['mtime'], reverse=True)
        return out[:int(q.get('limit', 200))]

    def api_attempt(self, run, q):
        p = safe_join(run, q.get('path', ''))
        if p is None or not p.is_dir():
            return {'error': 'bad path'}
        files = {}
        for name in ('headless_prompt.md', 'llm_response.txt', 'patch.txt', 'metadata.json'):
            files[name] = read_text(p / name)
        return {'path': q['path'], 'files': files}

    def api_gen(self, run, q):
        d = run / f'gen_{int(q.get("gen", 0))}'
        if not d.is_dir():
            return {'error': 'no such generation'}
        res = d / 'results'
        return {
            'generation': gen_num(d),
            'code': read_text(d / 'main.py'),
            'diff': read_text(d / 'edit.diff'),
            'metrics': read_json(res / 'metrics.json'),
            'correct': read_json(res / 'correct.json'),
            'job_out': read_text(res / 'job_log.out', 60_000, tail=True),
            'job_err': read_text(res / 'job_log.err', 60_000, tail=True),
        }

    def api_best(self, run, q):
        return {'code': read_text(run / 'best' / 'main.py'),
                'metrics': read_json(run / 'best' / 'results' / 'metrics.json')}

    def api_limits(self, run, q):
        return limit_events(run)

    def api_archive(self, run, q):
        return archive(run)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--port', type=int, default=8477)
    ap.add_argument('--host', default='127.0.0.1',
                    help='default is localhost-only (use an SSH tunnel); 0.0.0.0 exposes code and prompts')
    a = ap.parse_args()
    srv = ThreadingHTTPServer((a.host, a.port), Handler)
    srv.daemon_threads = True
    print(f'Shinka monitor: http://{a.host}:{a.port}', flush=True)
    srv.serve_forever()


if __name__ == '__main__':
    main()
