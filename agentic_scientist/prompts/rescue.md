# Role: RESEARCHER-IMPLEMENTER, WRAP-UP (worker $worker, cycle $cycle)

The research session for this cycle ended before it wrote $cycle_dir/hypothesis.json (usually it was stopped at its
wall-clock limit while a long analysis was still running). Without that file the harness discards the cycle and all of
its work. Your job is to turn the work already done into ONE tested candidate. You have $minutes minutes in total; the
session is stopped at that point.

$focus

## What the previous session did
- Full digest (its messages, the commands it ran and their outputs, in order): $digest_path
- Its analysis scripts and files: $cycle_dir/analysis/
- Candidate workspace (your working directory; it may already contain part of the change): $ws
- Research brief (rules, TEST configuration, file contract): $brief_path
- Workspace changes so far versus the parent program:
```
$ws_diff
```
- The last part of the digest:
```
$digest_tail
```

## Steps (no new research and no new sweeps: use what the session already measured)
1. Read the digest (`sed -n` ranges, `tail -c`, `grep`), then pick the ONE hypothesis its evidence best supports. If its
   last screen was cut off, use the strongest result it did obtain; prefer the simplest variant it measured.
2. Within your first 10 minutes WRITE $cycle_dir/hypothesis.json, keys:
   {"title", "claim" (falsifiable; which metrics move and roughly how much), "mechanism", "evidence": [{"source", "finding"}],
    "change_plan", "target_boards": ["<your board>"], "expected_gain", "risk", "complexity" (1-5),
    "generalisation_argument" (why it holds for the TEST configuration in the brief), "metric_signature":
    {"board": "...", "<metric>": "+"|"-"|"="} (2-5 dev metrics), "origin": "leaderboard"|"knowledge_bank"|"literature"|"diagnostic",
    "leaderboard_evidence" (optional), "portable" (optional)}
   Cite only evidence the previous session actually obtained (sources it read, numbers it measured).
3. IMPLEMENT or finish the change in $ws under the usual rules: only your board's files (`<board>.py`, flat
   `<board>_*.py`, `<board>_knobs.json`); never program.py or another board's files; no subdirectories; keep the
   predict() contract; no file/network/process access inside the program; no branching on exact times or split names;
   comments explain the biology.
4. CHECK once: `timeout 600 $root/.venv/bin/python $root/agentic_scientist/tools/quick_eval.py <dev split>` from $ws
   (a crash and sanity check, not tuning). Every command must finish within 10 minutes; run nothing in the background.
5. Write $ws/CHANGES.md: what changed, the quick-eval result, and that this cycle was wrapped up from an unfinished
   research session.

The harness then runs the full dev evaluation, the paired race against the parent, the test-file export gates and the
review by a second model. Finish by printing the title.
