"""Query the AgenticScientist knowledge bank of the current run (every past cycle, nothing truncated).

  python agentic_scientist/tools/kb.py summary                      curated synthesis (knowledge.md)
  python agentic_scientist/tools/kb.py list [--board heart] [--status negative] [--family sampling] [--grep text]
  python agentic_scientist/tools/kb.py show <cycle_id>               full record: hypothesis, deltas, lesson, critic, pitfalls
  python agentic_scientist/tools/kb.py stats                         counts by board x status, best confirmed per board
  python agentic_scientist/tools/kb.py code <id>                    program / diff of a past cycle (agentic_scientist runs only)
Add --scope all to search the cross-run library (all earlier runs + Shinka history; dev scores only).
  python agentic_scientist/tools/kb.py --scope all summary         curated cross-run synthesis (library/global.md)
The run is taken from $MG_RUN (set by the orchestrator).
"""
import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from agentic_scientist.knowledge import BOARDS, Bank, line  # noqa: E402


def run_dir():
    if os.environ.get('MG_RUN'):
        return Path(os.environ['MG_RUN'])
    runs = sorted((ROOT / 'agentic_scientist/runs').glob('*/knowledge'), key=lambda p: p.stat().st_mtime)
    if not runs:
        sys.exit('no knowledge bank found')
    return runs[-1].parent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('cmd', choices=['summary', 'list', 'show', 'stats', 'code'])
    ap.add_argument('id', nargs='?')
    ap.add_argument('--board')
    ap.add_argument('--status')
    ap.add_argument('--family')
    ap.add_argument('--grep')
    ap.add_argument('--scope', choices=['run', 'all'], default='run')
    a = ap.parse_args()
    lib = ROOT / 'agentic_scientist/library'
    if a.scope == 'all':
        es = [json.loads(l) for l in (lib / 'entries.jsonl').read_text().splitlines() if l.strip()]
    else:
        bank = Bank(run_dir())
        es = bank.entries()
    if a.cmd == 'code':
        e = next((e for e in es if e['id'] == a.id), None)
        arts = (e or {}).get('artifacts') or {}
        p = arts.get('diff') or arts.get('code')
        if not p and a.scope == 'run':
            p = str(run_dir() / 'cycles' / str(a.id) / 'ws/program.py')
        print((ROOT / p).read_text() if p and (ROOT / p).exists() else f'no code for {a.id} (Shinka code is not shared)')
    elif a.cmd == 'summary':
        print(((lib / 'lessons.md').read_text() + '\n\n' if (lib / 'lessons.md').exists() else '') + (lib / 'global.md').read_text() if a.scope == 'all' and (lib / 'global.md').exists() else
              ('(no global synthesis yet)' if a.scope == 'all' else bank.synthesis()))
    elif a.cmd == 'list':
        for e in es:
            t = e.get('tags', {})
            if a.board and a.board not in t.get('boards', []):
                continue
            if a.status and e.get('status') != a.status:
                continue
            if a.family and not any(a.family.lower() in f.lower() for f in t.get('family', [])):
                continue
            if a.grep and a.grep.lower() not in json.dumps(e).lower():
                continue
            print(line(e))
    elif a.cmd == 'show':
        e = next((e for e in es if e['id'] == a.id), None)
        print(json.dumps(e, indent=1) if e else f'no entry {a.id}')
    else:
        print(f'{len(es)} entries')
        for b in BOARDS:
            mine = [e for e in es if b in e.get('tags', {}).get('boards', [])]
            counts = {}
            for e in mine:
                counts[e.get('status')] = counts.get(e.get('status'), 0) + 1
            conf = [e for e in mine if e.get('status') == 'confirmed']
            best = max(conf, key=lambda e: (e.get('deltas') or {}).get(b, -1e9), default=None)
            print(f"{b}: {counts}" + (f" | best confirmed {best['id']} {best['deltas'].get(b):+.2f}: {best['title']}" if best else ''))


if __name__ == '__main__':
    main()
