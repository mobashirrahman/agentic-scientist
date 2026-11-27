"""Next-run changes (option C): per-task code, one task per worker, dev combiner, holdout safety rule.

Run AFTER full2's holdout step, AFTER promote.py (if any), and AFTER checks/apply_pending.py:
  .venv/bin/python agentic_scientist/checks/next/apply_next.py [--root DIR]   (DIR = a copy for a dry run)
Idempotent: every edit checks whether it is already applied.
"""
import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

ap = argparse.ArgumentParser(); ap.add_argument('--root', default=str(Path(__file__).resolve().parents[3])); a = ap.parse_args()
R = Path(a.root)


def edit(rel, old, new):
    p = R / rel; s = p.read_text()
    if new in s:
        return print('already', rel)
    assert old in s, f'anchor not found in {rel}: {old[:70]!r}'
    p.write_text(s.replace(old, new, 1)); print('edited', rel)


# 1. seed -> per-task layout (each board owns <board>.py + private <board>_*.py copies of every helper)
seed = R / 'agentic_scientist/seed'
if 'Frozen dispatcher' not in (seed / 'program.py').read_text():
    tmp = R / 'agentic_scientist/seed_forked_tmp'
    subprocess.run([sys.executable, str(R / 'agentic_scientist/checks/next/fork_seed.py'), str(seed), str(tmp)], check=True)
    hist = R / 'agentic_scientist/seed_history' / (time.strftime('%Y%m%d_%H%M%S') + '_prefork')
    shutil.copytree(seed, hist, ignore=shutil.ignore_patterns('__pycache__'))
    shutil.rmtree(seed); tmp.rename(seed)
    pv = seed / 'PROVENANCE.json'
    prov = json.loads(pv.read_text()) if pv.exists() else {}
    prov.update(forked_from=str(hist.relative_to(R)), forked_at=time.time(), fork_note='per-task fork (option C); dev scores identical')
    pv.write_text(json.dumps(prov, indent=1))
    print('seed forked; old seed archived in', hist)
else:
    print('already forked seed')

O = 'agentic_scientist/orchestrator.py'
# 2. helpers: focus, scope check, combiner, holdout safeguard
edit(O, "    def role(self, w, name):", '''    BOARDS = ('temporal', 'heart', 'embryo', 'perturbation')

    @staticmethod
    def forked(ws):
        p = Path(ws) / 'program.py'
        return p.exists() and 'Frozen dispatcher' in p.read_text()

    def focus(self, w):
        """The worker's own task; after 2/3 of the cycles a worker stuck for 3+ cycles may help on any one task."""
        f = (self.cfg.get('focus') or {}).get(w)
        st = self.state['workers'][w]
        if f and st['cycle'] >= 2 * self.cfg['cycles_per_worker'] // 3 and st['fails'] >= 3:
            return None
        return f

    def focus_text(self, w):
        f = self.focus(w)
        if f:
            return (f"YOUR TASK: you own the **{f}** board. Change only `{f}.py` and `{f}_*.py` in the workspace "
                    f"(other boards are owned by other workers; edits outside your files are rejected automatically).")
        return ("YOUR TASK: free choice. Your own board has stalled, so pick the board with the most recoverable headroom. "
                "Change the files of exactly ONE board (`<board>.py`, `<board>_*.py`).")

    def scope(self, w, parent_ws, ws):
        """Per-task layout rule: a candidate changes the files of exactly one board (its owner's), never program.py,
        and never imports another board's files. Keeps the dev combiner exact."""
        import filecmp
        import re
        if not self.forked(parent_ws):
            return None
        names = {p.name for d in (parent_ws, ws) for p in Path(d).glob('*.py')}
        changed = [n for n in names if not ((Path(parent_ws) / n).exists() and (Path(ws) / n).exists()
                                             and filecmp.cmp(Path(parent_ws) / n, Path(ws) / n, shallow=False))]
        if 'program.py' in changed:
            return 'program.py (the frozen dispatcher) was edited'
        owner = lambda n: next((b for b in self.BOARDS if n == f'{b}.py' or n.startswith(f'{b}_')), None)  # noqa: E731
        stray = [n for n in changed if owner(n) is None]
        if stray:
            return f'files must be named <board>.py or <board>_*.py: {stray}'
        touched = {owner(n) for n in changed}
        if len(touched) > 1:
            return f'changes span several boards {sorted(touched)}; one board per candidate'
        f = self.focus(w)
        if f and touched and touched != {f}:
            return f'out of scope: worker owns {f}, changed {sorted(touched)}'
        for n in changed:
            if (Path(ws) / n).exists():
                for b in self.BOARDS:
                    if b != owner(n) and re.search(rf'^\\s*(from|import)\\s+{b}(_\\w+)?\\b', (Path(ws) / n).read_text(), re.M):
                        return f'{n} imports another board\\'s code ({b})'
        return None

    def board_means(self, ws, first_eval):
        """Mean dev board scores over the cached (prediction, fit) seed pairs of an accepted program."""
        evs = [first_eval] + [json.loads(p.read_text()) for p in sorted(Path(str(ws) + '_evals').glob('pair[0-9].json'))]
        evs = [e for e in evs if e and e.get('correct')]
        return {b: sum(e['boards'][b] for e in evs) / len(evs) for b in evs[0]['boards']} if evs else {}

    def combine(self, seed_ws, seed_eval, fdir):
        """Deterministic dev combiner: per board, take that board's files from the accepted program with the best
        mean dev score on that board (must beat the seed's), on top of the seed. No holdout data is used."""
        if not self.forked(seed_ws):
            return None
        base = self.board_means(seed_ws, seed_eval)
        pick = {}
        for acc in self.state['accepted']:
            if acc['id'] == 'merge' or not self.forked(acc['ws']):
                continue
            ev = json.loads((Path(acc['ws']).parent / 'eval.json').read_text())
            for b, v in self.board_means(acc['ws'], ev).items():
                if v > base.get(b, 1e9) and v > pick.get(b, (None, -1e9))[1]:
                    pick[b] = (acc, v)
        if len(pick) < 2:  # nothing to combine: a single best program is already a candidate
            self.log(f'combiner: {len(pick)} board(s) improved; skipped')
            return None
        ws = fdir / 'combo_ws'
        shutil.rmtree(ws, ignore_errors=True)
        shutil.copytree(seed_ws, ws, ignore=shutil.ignore_patterns('__pycache__'))
        for b, (acc, v) in pick.items():
            for p in list(ws.glob(f'{b}.py')) + list(ws.glob(f'{b}_*.py')):
                p.unlink()
            for p in list(Path(acc['ws']).glob(f'{b}.py')) + list(Path(acc['ws']).glob(f'{b}_*.py')):
                shutil.copy(p, ws / p.name)
        ev = fleet.evaluate(ws, 'dev', fdir / 'combo_dev.json')
        parts = {b: acc['id'] for b, (acc, v) in pick.items()}
        self.log(f"combiner: {parts} -> dev {ev.get('proxy')} correct={ev.get('correct')}")
        (fdir / 'combo.json').write_text(json.dumps(dict(parts=parts, dev=ev.get('proxy'), correct=ev.get('correct'))))
        return dict(id='combo', ws=str(ws), proxy=ev['proxy'], parts=parts) if ev.get('correct') else None

    def safeguard(self, chosen, seed_row, hold, fdir, n_pairs):
        """Holdout safety rule (can only move toward the seed): every board of the chosen program that drops by more
        than 2 SE (and > 0.5) versus the seed on the holdout seed pairs reverts to the seed's files for that board."""
        if chosen['id'] == 'seed' or not (self.forked(chosen['ws']) and self.forked(seed_row['ws'])):
            return chosen, []
        rd = lambda i, j: json.loads((fdir / f'holdout_{i}_pair{j}.json').read_text())  # noqa: E731
        bad = []
        for b in chosen['holdout_boards']:
            d = [rd(chosen['id'], j)['boards'][b] - rd('seed', j)['boards'][b] for j in range(n_pairs)]
            m = sum(d) / len(d)
            se = ((sum((x - m) ** 2 for x in d) / max(len(d) - 1, 1)) ** .5) / len(d) ** .5
            if m < -.5 and m < -2 * se:
                bad.append(b)
        if not bad:
            return chosen, []
        ws = fdir / 'safe_ws'
        shutil.rmtree(ws, ignore_errors=True)
        shutil.copytree(chosen['ws'], ws, ignore=shutil.ignore_patterns('__pycache__'))
        for b in bad:
            for p in list(ws.glob(f'{b}.py')) + list(ws.glob(f'{b}_*.py')):
                p.unlink()
            for p in list(Path(seed_row['ws']).glob(f'{b}.py')) + list(Path(seed_row['ws']).glob(f'{b}_*.py')):
                shutil.copy(p, ws / p.name)
        row = hold(dict(id=f"{chosen['id']}_safe", ws=str(ws), proxy=chosen['proxy']))
        self.log(f"safeguard: {chosen['id']} reverted {bad} to the seed -> holdout {row.get('holdout')}")
        if row.get('holdout') is None:
            return chosen, bad
        return (row if row['holdout'] > seed_row['holdout'] else seed_row), bad

    def role(self, w, name):''')

# 3. focus in every prompt of the cycle; scope check before the paired test
edit(O, "        if not (cdir / 'hypothesis.json').exists():\n            (cdir / 'analysis').mkdir(exist_ok=True)",
     "        sub['focus'] = self.focus_text(w)\n        if not (cdir / 'hypothesis.json').exists():\n            (cdir / 'analysis').mkdir(exist_ok=True)")
edit(O, "        ok, reason, stats = self.race(ws, ev, parent)\n        with LOCK:",
     "        bad_scope = self.scope(w, parent['ws'], ws)\n"
     "        if bad_scope:\n"
     "            return self.finish(w, cdir, dict(title=hyp.get('title'), verdict='rejected', reason='scope: ' + bad_scope), hyp)\n"
     "        ok, reason, stats = self.race(ws, ev, parent)\n        with LOCK:")

# 4. final(): add the combined program to the candidates; apply the safety rule to the pick
edit(O, "        cands = [dict(id='seed', ws=str(seed_ws), proxy=seed_eval['proxy'])] + short\n",
     "        cands = [dict(id='seed', ws=str(seed_ws), proxy=seed_eval['proxy'])] + short\n"
     "        combo = self.combine(seed_ws, seed_eval, fdir)\n"
     "        if combo:\n"
     "            cands.append(combo)\n")
edit(O, "        chosen = max(valid, key=lambda r: r['holdout']) if valid else rows[0]\n",
     "        chosen = max(valid, key=lambda r: r['holdout']) if valid else rows[0]\n"
     "        chosen, reverted = self.safeguard(chosen, rows[0], hold, fdir, len(pairs))\n"
     "        if reverted:\n"
     "            rows.append(chosen)\n")
edit(O, "rule='max holdout proxy among top-K dev, must beat seed on holdout',",
     "rule='max holdout proxy among top-K dev + dev combiner, must beat seed on holdout; boards dropping >2SE revert to seed',")

# 5. prompts
edit('agentic_scientist/prompts/brief.md', '## Contract', '''## Code layout (per-task; enforced automatically)
- `program.py` is a frozen dispatcher: never edit it.
- Each board's code lives in `<board>.py` (temporal, heart, embryo, perturbation) and private helpers named
  `<board>_*.py` (e.g. `heart_transport.py`). Every board has its OWN copy of the shared building blocks (LatentFlow,
  AnchorFlow, ...), so changing `heart_transport.py` cannot affect T1. Do not import `src.v2` or another board's files.
- A candidate changes the files of exactly ONE board: your worker's board (see YOUR TASK in your prompt).
- At the end, a deterministic combiner takes each board's files from the best program for that board, so improvements
  on different boards add up.
- PORTABLE lessons: if your change improves a building block in a way that should help another board too (e.g. a better
  latent fit in `<board>_transport.py`), say so in hypothesis key "portable" (one sentence: what, where, why). The
  owner of the other board sees it in the knowledge bank and may port it through their own paired test.

## Contract''')
edit('agentic_scientist/prompts/ideator.md', 'Inputs:\n', '$focus\n\nInputs:\n')
edit('agentic_scientist/prompts/ideator.md', '(read program.py and any helpers; read $root/src/v2/*.py for the available building blocks)',
     '(read your board\'s `<board>.py` and its `<board>_*.py` helpers; the other boards\' files show other building blocks)')
edit('agentic_scientist/prompts/ideator.md', ' "generalisation_argument": "why this transfers to E12.5 / Ctnnb1 / unseen splits"}',
     ' "generalisation_argument": "why this transfers to E12.5 / Ctnnb1 / unseen splits",\n'
     ' "portable": "optional: one sentence if this building-block change would help another board too"}')
edit('agentic_scientist/prompts/implementer.md', '\n', '\n$focus\nEdit only the files of that one board; never program.py; never import src.v2 or another board\'s files.\n')
for crit in ('agentic_scientist/prompts/critic_plan.md', 'agentic_scientist/prompts/critic_code.md'):
    edit(crit, '\n## ', '\n$focus (Changes outside that board are rejected automatically; flag them early.)\n\n## ')

# 6. knowledge bank: carry the portable note
edit(O, "claim=(hyp or {}).get('claim'), implementer=outcome.get('implementer'))",
     "claim=(hyp or {}).get('claim'), implementer=outcome.get('implementer'),\n"
     "                     portable=(hyp or {}).get('portable') if outcome.get('verdict') == 'accepted' else None)")
edit('agentic_scientist/knowledge.py', "f\"(z {e.get('z', 0):+.1f}) {ds} | {e.get('lesson', '')}\")",
     "f\"(z {e.get('z', 0):+.1f}) {ds} | {e.get('lesson', '')}\"\n"
     "            + (f\" | PORTABLE: {e['portable']}\" if e.get('portable') else ''))")

# 7. config: 4 workers, one board each, 4 holdout seed pairs; the LLM merge is replaced by the deterministic combiner
cp = R / 'agentic_scientist/config.json'
cfg = json.loads(cp.read_text())
cfg.update(workers=4, focus=dict(w0='perturbation', w1='temporal', w2='heart', w3='embryo'), merge=False,
           holdout_seed_pairs=[[202, 0], [313, 1], [424, 2], [535, 3]])
cp.write_text(json.dumps(cfg, indent=2) + '\n'); print('edited config.json')
subprocess.run([sys.executable, '-m', 'py_compile', str(R / O), str(R / 'agentic_scientist/knowledge.py')], check=True)
print('done')
