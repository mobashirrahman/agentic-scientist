"""Run the CURRENT workspace program in the final TEST configuration (inputs E8.25, E8.5, E8.75, E9.5, E10.5 ->
E12.5, heart_chambers_only, up to 34,641 cells). Returns pass/fail and an error class only (no messages, no numbers),
because this configuration reads protected stages.   python tools/testcheck.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _client import request  # noqa: E402

r = request('testcheck')
print('TEST CONFIGURATION:', 'PASS' if r.get('ok') else f"FAIL ({r.get('error_type') or r.get('error')})",
      f"| ~{r.get('seconds')}s | checks left: {r.get('checks_left')} | time left: {r.get('remaining_seconds', 0) // 60} min")
