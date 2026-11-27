# Pending integration (apply after full2 finishes; these files are locked during a run)

1. **Do-no-harm T3 test → pipeline**
   - orchestrator: after a T3-touching candidate passes the paired test, run `checks/noharm.py`.
     Store `gene_specific`, `median_ratio` and `verdict` in outcome.json and the knowledge bank.
   - Diagnostic for now, not a hard reject: real KO samples can carry gene-independent shifts (batch, staging).
   - Critic prompts get the numbers, plus the rule "a T3 gain from a gene-blind change is a Gata4 fit".
   - Tool for agents: `agentic_scientist/tools/noharm.py` (copy of the check), listed in the diagnostics skill.

2. **Adversarial controls → one-time scorer audit** (`checks/controls.json`). Fix any hole before the next lock.

3. **Ceiling → brief.** A per-board headroom table from `checks/ceiling.json`.

4. **Published baselines → brief "Known dead ends"**
   - shift_transfer (copy the training KO's pseudobulk shift onto any gene): 42.5 on the official board.
   - gene_ko (the same, plus zeroing the gene): 42.5.
   - Both are below the wt_identity floor of 50. Organisers: "every model gets the direction of the response wrong".
   - pseudobulk_shift (per-type constant velocity), T1: 48.6.
   - copy_last on interpolation boards copies a stage about 5.5× too small by volume.

5. **Critic visibility:** the critic prompts also get the cross-run lessons (library/lessons.md).

6. **Official website facts → brief** (in apply_pending.py step 2b): URL and pages, final test stages, Ctnnb1 and Wnt-gene panel facts, T3 and T2 weights, scale controls.
7. **Per-worker task ownership** in the next config (4 workers: T3, T1, heart, embryo). Shared-code changes allowed with critic approval; the harness lets idle workers help after 2/3 of the run. Acceptance stays on the full score.
8. **Longer-horizon dev tests** (2–3 days, heart and temporal), where the data allows.

## Option C (approved 2026-11-16): `agentic_scientist/checks/next/apply_next.py`, dry-run and unit-tested
Order after full2's holdout step: promote.py (if a candidate won) -> apply_pending.py -> apply_next.py -> make_lock -> start.
- fork_seed.py: the seed becomes program.py (frozen dispatcher) + <board>.py + private <board>_* copies of every helper.
- One board per worker (w0 T3, w1 T1, w2 heart, w3 embryo). After 2/3 of the cycles, a worker that has failed 3+ times in a row may pick any one board.
- Scope check before the paired test: exactly one board's files, never program.py, no cross-board imports.
- final(): a deterministic dev combiner (best accepted program per board, by mean dev over the cached seed pairs) joins the holdout candidates. The LLM merge is off.
- Holdout safety rule: a board of the pick that drops >2SE and >0.5 reverts to the seed's files (re-scored on the holdout).
- 4 holdout seed pairs. A "portable" hypothesis key is carried into the knowledge bank.
