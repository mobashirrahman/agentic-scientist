"""Efficiency and quality report for a AgenticScientist run (time, tokens, cost per role; code errors; research quality).

  .venv/bin/python agentic_scientist/tools/run_report.py <run_dir> [--json out.json]
"""
import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from agentic_scientist.dashboard import events, role_of  # noqa: E402


def usage(path):
    """(input, output, cache_read, cost_usd, steps, tool_calls, tool_errors) from any CLI transcript."""
    u = dict(input=0, output=0, cache_read=0, cost=0.0, steps=0)
    for line in Path(path).read_text(errors='replace').splitlines():
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        if not isinstance(ev, dict):
            continue
        if ev.get('type') == 'result':  # claude
            us = ev.get('usage', {})
            u['input'] += us.get('input_tokens', 0) + us.get('cache_creation_input_tokens', 0)
            u['output'] += us.get('output_tokens', 0)
            u['cache_read'] += us.get('cache_read_input_tokens', 0)
            u['cost'] += ev.get('total_cost_usd', 0) or 0
            u['steps'] += ev.get('num_turns', 0) or 0
        elif ev.get('type') == 'turn.completed':  # codex
            us = ev.get('usage', {})
            u['input'] += us.get('input_tokens', 0) - us.get('cached_input_tokens', 0)
            u['cache_read'] += us.get('cached_input_tokens', 0)
            u['output'] += us.get('output_tokens', 0) + us.get('reasoning_output_tokens', 0)
            u['steps'] += 1
        elif (ev.get('part') or {}).get('type') == 'step-finish':  # opencode
            t = ev['part'].get('tokens', {})
            u['input'] += t.get('input', 0)
            u['output'] += t.get('output', 0) + t.get('reasoning', 0)
            u['cache_read'] += (t.get('cache') or {}).get('read', 0)
            u['cost'] += ev['part'].get('cost', 0) or 0
            u['steps'] += 1
    ev = events(path)
    u['tool_calls'] = sum(e['k'] == 'tool' for e in ev)
    u['tool_errors'] = sum(e['k'] == 'result' and bool(e.get('err')) for e in ev)
    return u


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('run')
    ap.add_argument('--json')
    a = ap.parse_args()
    d = Path(a.run)
    durations = defaultdict(list)
    for l in (d / 'run.log').read_text().splitlines():
        m = re.search(r'agent (\S+) (\S+?) exit=(\S+) (\d+)s', l)
        if m:
            durations[role_of(m.group(2))].append((int(m.group(4)), m.group(3)))
    roles = defaultdict(lambda: defaultdict(float))
    for t in d.glob('cycles/*/*.jsonl'):
        r = role_of(t.name)
        for k, v in usage(t).items():
            roles[r][k] += v
        roles[r]['calls'] += 1
    print(f'# Run report: {d.name}\n')
    print(f'{"role":22s} {"calls":>5s} {"time(s)":>8s} {"timeouts":>8s} {"in tok":>9s} {"out tok":>8s} {"cache rd":>10s} {"$":>7s} {"tools":>6s} {"tool err":>8s}')
    tot = defaultdict(float)
    for r, u in sorted(roles.items()):
        secs = sum(x for x, _ in durations.get(r, []))
        to = sum(c == 'timeout' for _, c in durations.get(r, []))
        print(f'{r:22s} {int(u["calls"]):5d} {secs:8d} {to:8d} {int(u["input"]):9d} {int(u["output"]):8d} {int(u["cache_read"]):10d} '
              f'{u["cost"]:7.3f} {int(u["tool_calls"]):6d} {int(u["tool_errors"]):8d}')
        for k in ('input', 'output', 'cache_read', 'cost'):
            tot[k] += u[k]
        tot['secs'] += secs
    print(f'{"TOTAL":22s} {"":5s} {int(tot["secs"]):8d} {"":8s} {int(tot["input"]):9d} {int(tot["output"]):8d} {int(tot["cache_read"]):10d} {tot["cost"]:7.3f}')
    print('\n## Cycles')
    cyc = []
    for c in sorted((d / 'cycles').glob('*')):
        o = json.loads((c / 'outcome.json').read_text()) if (c / 'outcome.json').exists() else {}
        h = json.loads((c / 'hypothesis.json').read_text()) if (c / 'hypothesis.json').exists() else {}
        cr = json.loads((c / 'critique.json').read_text()) if (c / 'critique.json').exists() else {}
        rv = json.loads((c / 'code_review.json').read_text()) if (c / 'code_review.json').exists() else {}
        ev = json.loads((c / 'eval.json').read_text()) if (c / 'eval.json').exists() else {}
        urls = sum('http' in str(e.get('source', '')) for e in h.get('evidence', []))
        data = sum('http' not in str(e.get('source', '')) for e in h.get('evidence', []))
        debug = len(list(c.glob('debug*.jsonl')))
        qe = int((c / 'ws/.quick_eval_runs').read_text()) if (c / 'ws/.quick_eval_runs').exists() else 0
        row = dict(id=c.name, title=h.get('title'), verdict=o.get('verdict'), reason=o.get('reason'),
                   critic=cr.get('verdict'), critic_issues=len(cr.get('issues', [])), review=rv.get('verdict'),
                   review_issues=len(rv.get('issues', [])), eval_ok=ev.get('correct'), eval_error=ev.get('error'),
                   debug_rounds=debug, quick_evals=qe, url_evidence=urls, data_evidence=data,
                   retry_ideation=(c / 'ideate_retry').exists(), proxy=ev.get('proxy'), parent=o.get('parent_proxy'))
        cyc.append(row)
        print(f"- {c.name}: {row['verdict']} ({row['reason']}) | critic {row['critic']} ({row['critic_issues']} issues) | "
              f"review {row['review']} ({row['review_issues']}) | eval ok {row['eval_ok']} | debug rounds {debug} | "
              f"quick_evals {qe} | evidence {urls} URLs + {data} data | {row['title']}")
    kb = d / 'knowledge/entries.jsonl'
    if kb.exists():
        print('\n## Knowledge bank')
        for l in kb.read_text().splitlines():
            e = json.loads(l)
            print(f"- [{e['id']}] {e['status']} Δ{e['delta_proxy']:+.2f} z{e['z']:+.1f}: {e.get('lesson')}")
    if a.json:
        Path(a.json).write_text(json.dumps(dict(roles=roles, cycles=cyc), indent=1, default=float))


if __name__ == '__main__':
    main()
