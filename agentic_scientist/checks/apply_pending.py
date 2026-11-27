"""Apply the post-full2 integration to locked AgenticScientist files (run only when no locked run is active).
  .venv/bin/python agentic_scientist/checks/apply_pending.py [--root DIR]   (DIR = a copy for a dry run)
"""
import argparse
import shutil
from pathlib import Path

ap = argparse.ArgumentParser(); ap.add_argument('--root', default=str(Path(__file__).resolve().parents[2])); a = ap.parse_args()
R = Path(a.root)


def edit(rel, old, new):
    p = R / rel; s = p.read_text()
    if new in s:
        return print('already', rel)
    assert old in s, f'anchor not found in {rel}: {old[:60]!r}'
    p.write_text(s.replace(old, new, 1)); print('edited', rel)


# 1. agent tool: gene-specificity test
shutil.copy(R / 'agentic_scientist/checks/noharm.py', R / 'agentic_scientist/tools/noharm.py')
shutil.copy(R / 'agentic_scientist/checks/mgcheck.py', R / 'agentic_scientist/tools/mgcheck.py')
edit('agentic_scientist/skills/diagnostics/SKILL.md', '(dev splits:',
     '`agentic_scientist/tools/noharm.py <workspace>`: gene-specificity of your T3 model. It knocks out genes that are barely expressed and '
     'compares the response with Gata4 (ratio ~1 = gene-blind template; report gene_specific and global_scale).\n(dev splits:')

# 2. brief: known dead ends + the knockout global-scale fact
edit('agentic_scientist/prompts/brief.md', '## Generalisation rules', '''## Known dead ends and traps (official baselines and our own checks)
- shift_transfer (copy the training knockout's pseudobulk shift onto any gene) and gene_ko (the same, plus zeroing the gene)
  score 42.5 on the official T3 board: below the do-nothing floor. The organisers: every published model gets the
  direction of the response wrong. Copying the Gata4 response onto other genes is a documented failure.
- The real Gata4 knockout samples have ~17.5% lower overall expression than wild type (global scale 0.825). The
  human baseline and every program so far reproduce a ~0.86-0.88 global shrink for EVERY gene (gene-blind template).
  A uniform 0.75 rescale of wild type beats do-nothing by ~4 points on our local T3 scorer but is held below the floor
  on the official board. Do not chase global scale: it is a property of the Gata4 samples, not a transferable mechanism.
- Run `agentic_scientist/tools/noharm.py <your ws>`: a T3 change is only worth keeping if `gene_specific` grows
  (the response to Gata4 differs from the response to genes that are barely expressed).
- pseudobulk_shift (per-type constant velocity) scores 48.6 on T1: below copy_last.

## Generalisation rules''')

# 2b. brief: official competition facts (public website, read 2026-11-16)
edit('agentic_scientist/prompts/brief.md', '## Generalisation rules', '''## Official competition facts (public website https://virtualembryo.ai/challenge/ ; you may WebFetch it)
Useful pages: /challenge/tasks/temporal, /challenge/tasks/spatial, /challenge/tasks/perturbation, /challenge/baselines,
/challenge/evaluation, /challenge/faq, /challenge/rules. Read them for research; never submit or log in anywhere.
- Final hidden tests: T1 E12.5 (2-3 days past the data); heart E12.5 (long extrapolation); embryo E7.75 (interpolation
  between E7.5 and E8.0); T3 beta-catenin (Ctnnb1) knockout at E8.75. Methods must hold up at long horizons, not just 1 day ahead.
- T3: the training knockout is Mab21l2 at E9.5, but the test is at E8.75, so the stage difference matters. Ctnnb1 is broadly
  expressed, so its effect is spread across many cell types (the organisers call it the hardest). Ctnnb1 is NOT on the
  500-gene panel. Wnt-related genes that are on the panel: Wnt3a, Dkk1, Fgf8, Isl1. (T, Axin2, Lef1, Sp5 and Cdx are not.)
  Weights: response-gene recovery 30%, direction 25%, magnitude (absolute) 25%, cell-state distribution 20%. All
  changes are measured against the matched wild type. Copying the matched wild type already gets 0.956 pseudobulk Pearson,
  so absolute accuracy is worthless; only the knockout-minus-wild-type change scores.
- T2: four groups at 25% each: expression change, cell-state distribution, shape and growth scale (rotation-invariant),
  and local neighbours. Do not pad or truncate cell counts. Spatiotemporal_ode's score comes mostly from extrapolating the
  growth rate analytically.
- Scale controls: the organisers intend a 1% global shrink to score at the floor. Do not chase global rescaling.
- A copied stage that is too small hurts shape terms a lot (copy_last is ~5.5x too small by volume on interpolation boards).

## Generalisation rules''')

# 3. critics: lessons + gene-specificity rule
for crit in ('agentic_scientist/prompts/critic_plan.md', 'agentic_scientist/prompts/critic_code.md'):
    edit(crit, '\n## ', '\nT3 gene-specificity: a T3 gain from a change that is gene-blind (same response for any knockout gene, or a global '
         'expression rescale) is a Gata4 fit: verdict revise/fix. Held-out lessons from earlier runs:\n$lessons\n\n## ')
edit('agentic_scientist/orchestrator.py', "pitfalls=self.bank.pitfalls(), siblings=sibs, complexity=complexity)",
     "pitfalls=self.bank.pitfalls(), siblings=sibs, complexity=complexity,\n                   lessons=self.lessons())")
edit('agentic_scientist/orchestrator.py', "    @staticmethod\n    def library():", """    @staticmethod
    def lessons():
        p = ROOT / 'agentic_scientist/library/lessons.md'
        return p.read_text() if p.exists() else '(none)'

    @staticmethod
    def library():""")

# 4. orchestrator: gene-specificity measured on every T3-changing candidate, recorded in the outcome and knowledge bank
edit('agentic_scientist/orchestrator.py', "        mean_proxy = parent['eval']['proxy'] + stats['proxy']['mean'] if stats else ev.get('proxy')", """        nh = None
        if ev.get('correct') and any(s.startswith('gata4') for s in self.changed_splits(ev, parent['eval'])):
            try:
                subprocess.run([str(ROOT / '.venv/bin/python'), str(ROOT / 'agentic_scientist/tools/noharm.py'), str(ws),
                                '--json', str(cdir / 'noharm.json')], cwd=ROOT / 'agentic_scientist/tools', capture_output=True, timeout=1800)
                nh = json.loads((cdir / 'noharm.json').read_text())
                nh = {k: nh[k] for k in ('gene_specific', 'median_ratio', 'gata4_global_scale', 'verdict')}
                reason_suffix = f" | gene-specificity {nh['gene_specific']:+.2f} ({nh['verdict'].split(':')[0]})"
            except Exception as e:  # noqa: BLE001
                nh, reason_suffix = dict(error=repr(e)), ''
        else:
            reason_suffix = ''
        mean_proxy = parent['eval']['proxy'] + stats['proxy']['mean'] if stats else ev.get('proxy')""")
edit('agentic_scientist/orchestrator.py', "        outcome = dict(title=hyp.get('title'), verdict='accepted' if ok else 'rejected', reason=reason, stats=stats,",
     "        outcome = dict(title=hyp.get('title'), verdict='accepted' if ok else 'rejected', reason=reason + reason_suffix, stats=stats, noharm=nh,")
print('done')
