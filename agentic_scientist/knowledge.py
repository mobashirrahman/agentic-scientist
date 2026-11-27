"""AgenticScientist knowledge bank: what worked, what did not, and why. Part of the run lock.

Two layers, both inside the run directory:
  knowledge/entries.jsonl  one structured record per finished cycle (every outcome, never truncated)
  knowledge/knowledge.md   curated, bounded synthesis rewritten by the curator after each cycle
Agents query the full bank with agentic_scientist/tools/kb.py; prompts get the synthesis plus relevant entries.
"""
import json
import math
import threading
from pathlib import Path

BOARDS = ('temporal', 'heart', 'embryo', 'perturbation')
WEIGHTS = {'temporal': 1.0, 'heart': .5, 'embryo': .5, 'perturbation': 1.0}
SECTIONS = ('Established (held up; effect sizes and cycles)', 'Dead ends (and the condition under which a retry is justified)',
            'Promising / inconclusive leads', 'Per-board state of the art and weakest metrics',
            'Method pitfalls (statistics, evaluation, reasoning traps)', 'Implementation pitfalls (crashes, helper quirks, contract)',
            'Open questions')
EMPTY = '# Knowledge bank\n\n' + '\n\n'.join(f'## {s}\n(none yet)' for s in SECTIONS) + '\n'
_LOCK = threading.RLock()


class Bank:
    def __init__(self, run_dir):
        self.dir = Path(run_dir) / 'knowledge'
        self.dir.mkdir(parents=True, exist_ok=True)
        self.entries_path = self.dir / 'entries.jsonl'
        self.md_path = self.dir / 'knowledge.md'
        if not self.md_path.exists():
            self.md_path.write_text(EMPTY)

    # ---------- write ----------
    def add(self, entry):
        with _LOCK, self.entries_path.open('a') as f:
            f.write(json.dumps(entry, default=float) + '\n')

    def entries(self):
        out = []
        if self.entries_path.exists():
            for line in self.entries_path.read_text().splitlines():
                try:
                    out.append(json.loads(line))
                except ValueError:
                    pass
        return out

    def synthesis(self):
        return self.md_path.read_text()

    def set_synthesis(self, text, limit):
        text = text.strip()
        if not text.startswith('#') or '## ' not in text:  # reject malformed curator output; keep the previous version
            return False
        with _LOCK:
            (self.dir / 'history').mkdir(exist_ok=True)
            n = len(list((self.dir / 'history').glob('*.md')))
            (self.dir / 'history' / f'{n:03d}.md').write_text(self.synthesis())
            self.md_path.write_text(text[:limit] + '\n')
        return True

    # ---------- read ----------
    def relevant(self, boards=None, k=25):
        """Compact one-line records: everything about the given boards plus the most recent others."""
        es = self.entries()
        boards = set(boards or [])
        hit = [e for e in es if boards & set(e.get('tags', {}).get('boards', []))]
        rest = [e for e in es if e not in hit][-max(5, k - len(hit)):]
        chosen = sorted(hit[-k:] + rest, key=lambda e: e.get('t', 0))
        return '\n'.join(line(e) for e in chosen) or '(no entries yet)'

    def pitfalls(self):
        md = self.synthesis()
        keep, on = [], False
        for l in md.splitlines():
            if l.startswith('## '):
                on = 'pitfall' in l.lower()
            if on:
                keep.append(l)
        return '\n'.join(keep) or '(none yet)'


def line(e):
    d = e.get('deltas') or {}
    ds = ' '.join(f"{b[:4]}{d[b]:+.2f}" for b in BOARDS if d.get(b) is not None)
    tags = e.get('tags', {})
    return (f"[{e['id']}] {e.get('status', '?').upper()} | {', '.join(tags.get('boards', []))} | "
            f"{', '.join(tags.get('family', []))} | {e.get('title', '')} | Δproxy {e.get('delta_proxy', 0):+.2f} "
            f"(z {e.get('z', 0):+.1f}) {ds} | {e.get('lesson', '')}"
            + (f" | PORTABLE: {e['portable']}" if e.get('portable') else '')
            + (f" | {e['signature']['summary']}" if e.get('signature') else '')
            + (f" | origin {e['origin']}" if e.get('origin') else '')
            + (f" | gain kinds: dist {e['transfer'].get('distribution', 0):+.2f} DE {e['transfer'].get('de_based', 0):+.2f}"
               f" size {e['transfer'].get('size', 0):+.2f}" if e.get('transfer') else ''))


SIGNATURE_TOL = 0.3  # skill points; a predicted '=' allows this much movement, '+'/'-' need at least this much


def signature(hyp, parent_eval, cand_eval, tol=SIGNATURE_TOL):
    """Mechanism check: did the dev metrics move the way hypothesis['metric_signature'] predicted?
    The signature maps metric -> '+', '-' or '=' on the hypothesis' first target board (or signature['board']);
    deltas are the mean over that board's dev splits of candidate minus parent (first seed pair).
    Returns None when nothing can be checked."""
    sig = (hyp or {}).get('metric_signature')
    if not isinstance(sig, dict) or not cand_eval or not cand_eval.get('correct') or not parent_eval:
        return None
    board = sig.get('board') or next(iter((hyp or {}).get('target_boards') or []), None)

    def per_metric(ev):
        acc = {}
        for r in (ev.get('splits') or {}).values():
            if r.get('board') == board:
                for k, v in (r.get('metrics') or {}).items():
                    acc.setdefault(k, []).append(v)
        return {k: sum(v) / len(v) for k, v in acc.items()}
    p, c = per_metric(parent_eval), per_metric(cand_eval)
    checks = {}
    for m, want in sig.items():
        want = str(want).strip()
        if m == 'board' or m not in p or m not in c or want not in ('+', '-', '='):
            continue
        d = c[m] - p[m]
        ok = d >= tol if want == '+' else d <= -tol if want == '-' else abs(d) < tol
        checks[m] = dict(pred=want, delta=round(d, 2), ok=ok)
    if not checks:
        return None
    hit = sum(x['ok'] for x in checks.values())
    return dict(board=board, checks=checks, hit=hit, n=len(checks),
                summary=f'signature {hit}/{len(checks)}: ' + ', '.join(
                    f"{m} {x['pred']}{'ok' if x['ok'] else 'MISS'}{x['delta']:+.1f}" for m, x in checks.items()))


def classify(outcome, parent_eval, cand_eval, tau=None):
    """Evidence class from the paired dev comparison and scoring-seed noise."""
    v = outcome.get('verdict')
    if v in ('vetoed', 'disqualified', 'skipped', 'research_only'):
        return v, {}, 0.0, 0.0
    if not cand_eval or not cand_eval.get('correct'):
        return 'crashed', {}, 0.0, 0.0
    st = outcome.get('stats')
    if st and st.get('proxy'):  # paired repeated test from the race (preferred)
        P = st['proxy']
        deltas = {b: v['mean'] for b, v in st.items() if b != 'proxy'}
        if v == 'accepted':
            status = 'confirmed'
        elif P['lb'] > 0 or any(x['lb'] > 0 for b, x in st.items() if b != 'proxy'):
            status = 'promising'  # significant somewhere but rejected (e.g. another board dropped)
        elif P['ub'] < 0:
            status = 'negative'
        else:
            status = 'inconclusive'
        return status, deltas, P['mean'], P['z']
    deltas = {b: cand_eval['boards'].get(b, 0) - parent_eval['boards'].get(b, 0) for b in parent_eval['boards']}
    dp = cand_eval['proxy'] - parent_eval['proxy']
    se = []
    for ev in (parent_eval, cand_eval):
        bse = ev.get('board_se') or {}
        se.append(sum((WEIGHTS[b] * s) ** 2 for b, s in bse.items()))
    sd = math.sqrt(sum(se)) if any(se) else 0.35  # fallback: typical seed noise of the proxy
    z = dp / max(sd, 1e-6)
    if v == 'accepted':
        status = 'confirmed'
    elif dp > 0 and z >= 2:  # (screen-only fallback)
        status = 'promising'  # real but below the acceptance bar (or a board fell)
    elif z <= -2:
        status = 'negative'
    else:
        status = 'inconclusive'
    return status, deltas, dp, z
