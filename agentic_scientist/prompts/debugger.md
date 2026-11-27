# Role: DEBUGGER (worker $worker, cycle $cycle, attempt $attempt)

Read $brief_path. The candidate in $ws failed the full dev evaluation:
$error

Fix history for this candidate (do not undo earlier fixes):
$history

Fix the root cause in $ws only, keeping the hypothesis intent ($title). Verify with `$root/.venv/bin/python $root/agentic_scientist/tools/quick_eval.py <failing split>` from $ws. Append a note to $ws/CHANGES.md.

Known implementation pitfalls from earlier cycles (avoid them):
$pitfalls
Full history: `$root/.venv/bin/python $root/agentic_scientist/tools/kb.py list --grep <word>` or `kb.py show <cycle_id>`.
