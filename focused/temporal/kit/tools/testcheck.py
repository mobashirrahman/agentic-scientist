"""Check the T1 output contract on a public-input forecast."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _client import request  # noqa: E402

r = request('testcheck')
print('TEST CONFIGURATION:', 'PASS' if r.get('ok') else f"FAIL ({r.get('error_type') or r.get('error')})",
      f"| ~{r.get('seconds')}s | checks left: {r.get('checks_left')} | time left: {r.get('remaining_seconds', 0) // 60} min")
