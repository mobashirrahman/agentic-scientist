"""Run the CURRENT workspace program in the final TEST configuration (inputs E7.5, E8.0 -> E7.75, up to 5,000 cells).
Returns pass/fail and an error class only (no messages, no numbers), because this configuration reads a protected
stage.   python tools/testcheck.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _client import request  # noqa: E402

r = request('testcheck')
print('TEST CONFIGURATION:', 'PASS' if r.get('ok') else f"FAIL ({r.get('error_type') or r.get('error')})",
      f"| ~{r.get('seconds')}s | checks left: {r.get('checks_left')} | time left: {r.get('remaining_seconds', 0) // 60} min")
