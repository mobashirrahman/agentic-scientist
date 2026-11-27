"""Build the cross-run AgenticScientist library (run by a human between runs, never by agents).

  .venv/bin/python agentic_scientist/library_build.py [--curate]

Merges every AgenticScientist run's knowledge/entries.jsonl and Shinka's programs (dev splits only) into
agentic_scientist/library/entries.jsonl; --curate rewrites agentic_scientist/library/global.md with the curator model.
Holdout scores, final selections and Shinka code are never imported (Shinka's fitness included holdout splits).
"""
import argparse
import json
import sqlite3
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / 'agentic_scientist/library'
DEV = {'temporal_val': 'temporal', 'temporal_heartonly': 'temporal', 'heart_early': 'heart', 'heart_late': 'heart',
       'heart_long': 'heart', 'heart_e875': 'heart', 'heart_organ_proxy': 'heart', 'heart_e875_organ': 'heart',
       'heart_long_organ': 'heart', 'embryo_early': 'embryo', 'guard_embryo_e80': 'embryo',
       'gata4_1': 'perturbation', 'gata4_2': 'perturbation', 'mab21l2_e95': 'perturbation', 'hand2_e825': 'perturbation',
       'hand2_e925': 'perturbation', 'mef2c_e90': 'perturbation', 'mef2c_e85': 'perturbation'}
W = {'temporal': 1.0, 'heart': .5, 'embryo': .5, 'perturbation': 1.0}
DROP = ('holdout', 'final_choice', 'holdout_boards')


def dev_boards(split_scores):
    b = {}
    for s, v in split_scores.items():
        if s in DEV and v is not None:
            b.setdefault(DEV[s], []).append(v)
    return {k: sum(v) / len(v) for k, v in b.items()}


def morphogen_entries():
    out = []
    for kb in sorted((ROOT / 'agentic_scientist/runs').glob('*/knowledge/entries.jsonl')):
        run = kb.parent.parent
        rule = 'paired-racing' if '"stats"' in kb.read_text() else 'single-seed, fixed bar 1.0'
        for l in kb.read_text().splitlines():
            try:
                e = json.loads(l)
            except ValueError:
                continue
            for k in DROP:
                e.pop(k, None)
            cdir = run / 'cycles' / e['id']
            e.update(id=f"{run.name}/{e['id']}", source='agentic_scientist', run=run.name, rule=e.get('rule', rule),
                     artifacts={k: str(p.relative_to(ROOT)) for k, p in
                                dict(code=cdir / 'ws/program.py', diff=cdir / 'diff.patch', hypothesis=cdir / 'hypothesis.json',
                                     critique=cdir / 'critique.json', eval=cdir / 'eval.json').items() if p.exists()})
            if e.get('status') == 'disqualified':
                e['lesson'] = '[DISQUALIFIED by an over-strict audit, never evaluated: idea untested, NOT a dead end] ' + str(e.get('lesson', ''))
            out.append(e)
    for run in sorted((ROOT / 'agentic_scientist/runs').glob('*')):
        if (run / 'knowledge/entries.jsonl').exists():
            continue
        for cdir in sorted(run.glob('cycles/*')):
            o = json.loads((cdir / 'outcome.json').read_text()) if (cdir / 'outcome.json').exists() else None
            if not o:
                continue
            h = json.loads((cdir / 'hypothesis.json').read_text()) if (cdir / 'hypothesis.json').exists() else {}
            dp = (o.get('proxy') or 0) - (o.get('parent_proxy') or o.get('proxy') or 0)
            out.append(dict(id=f'{run.name}/{cdir.name}', source='agentic_scientist', run=run.name, rule='single-seed, fixed bar 1.0 (pre-bank)',
                            title=h.get('title') or o.get('title'), hypothesis=str(h.get('hypothesis', ''))[:600],
                            status='inconclusive' if o.get('verdict') == 'rejected' and abs(dp) < 1.5 else o.get('verdict'),
                            delta_proxy=dp, z=0.0, deltas={}, tags=dict(boards=h.get('boards', []), family=[]),
                            lesson=f"{o.get('verdict')}: {o.get('reason')} (one seed; small effects unresolved)",
                            artifacts={k: str(p.relative_to(ROOT)) for k, p in dict(code=cdir / 'ws/program.py',
                                       hypothesis=cdir / 'hypothesis.json').items() if p.exists()}))
    return out


def shinka_entries():
    out = []
    for db in sorted((ROOT / 'shinka_ve/runs').glob('lock_*/programs.sqlite')):
        c = sqlite3.connect(db)
        rows = c.execute('select id, parent_id, generation, correct, private_metrics, metadata, text_feedback from programs').fetchall()
        dev = {}
        for pid, _, _, ok, pm, _, _ in rows:
            try:
                dev[pid] = dev_boards(json.loads(pm or '{}').get('split_scores', {})) if ok else None
            except ValueError:
                dev[pid] = None
        for pid, par, gen, ok, pm, md, fb in rows:
            m = json.loads(md or '{}')
            if gen == 0:
                continue
            b, pb = dev.get(pid), dev.get(par)
            deltas = {k: b[k] - pb[k] for k in b if pb and k in pb} if b and pb else {}
            dp = sum(W[k] * v for k, v in deltas.items())
            st = 'crashed' if not ok else ('inconclusive' if abs(dp) < 1.5 else ('promising' if dp > 0 else 'negative'))
            out.append(dict(id=f'shinka:{db.parent.name}/gen{gen}', source='shinka', run=db.parent.name,
                            rule='shinka single-seed (dev splits only shown; noise sd ~1.4 per program)',
                            title=m.get('patch_name', ''), hypothesis=m.get('patch_description', '')[:600],
                            status=st, delta_proxy=dp, z=dp / 2.0, deltas=deltas,
                            tags=dict(boards=sorted(k for k, v in deltas.items() if abs(v) > .5) or sorted(deltas)[:1],
                                      family=['shinka-mutation']),
                            lesson=f"Shinka gen {gen}: dev Δ{dp:+.2f} vs parent (one seed; |Δ|<1.5 is within noise)."))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--curate', action='store_true')
    a = ap.parse_args()
    LIB.mkdir(exist_ok=True)
    es = morphogen_entries() + shinka_entries()
    blob = json.dumps(es).lower()
    assert '"holdout' not in blob, 'holdout field leaked into the library'
    (LIB / 'entries.jsonl').write_text(''.join(json.dumps(e, default=float) + '\n' for e in es))
    print(f'{len(es)} entries ({sum(e["source"] == "shinka" for e in es)} shinka)')
    if a.curate:
        from agentic_scientist.knowledge import line
        prompt = ((ROOT / 'agentic_scientist/prompts/curator.md').read_text().split('---')[0] +
                  '\n\nYou are curating the CROSS-RUN library (all past runs). Note each record\'s rule: single-seed/old-bar '
                  'rejections are weak evidence; disqualified = untested. Shinka records are one-seed and noisy.\n\nHELD-OUT LESSONS (authoritative; mark affected records as overfitting, not established):\n' + ((LIB / 'lessons.md').read_text() if (LIB / 'lessons.md').exists() else '') + '\n\nRECORDS:\n' +
                  '\n'.join(line(e) for e in es) + '\n\nOutput only the markdown document.')
        r = subprocess.run(['claude', '-p', '--model', 'sonnet', '--strict-mcp-config'], input=prompt,
                           capture_output=True, text=True, timeout=900, cwd=ROOT)
        txt = r.stdout.strip()
        if txt.startswith('```'):
            txt = txt.split('\n', 1)[1].rsplit('```', 1)[0].strip()
        txt = txt[txt.find('#'):] if '#' in txt else txt
        if txt.startswith('#'):
            (LIB / 'global.md').write_text(txt[:12000] + '\n')
            print('global.md written', len(txt))
        else:
            print('curator failed:', r.returncode, r.stdout[:300], r.stderr[-300:])


if __name__ == '__main__':
    import sys
    sys.path.insert(0, str(ROOT))
    main()
