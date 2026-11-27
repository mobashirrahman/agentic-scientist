"""Persistent fleet worker: records process identity and terminal exit code."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
name=sys.argv[1]
job=ROOT/'jobs'/name
job.mkdir(parents=True,exist_ok=True)
status=dict(state='running',pid=os.getpid(),start_ticks=int(Path('/proc/self/stat').read_text().split()[21]),started=time.time())
(job/'status.json').write_text(json.dumps(status,indent=2))
try:
    process=subprocess.run([sys.executable,str(ROOT/'scripts/evaluate_candidates.py'),name],cwd=ROOT)
    status.update(state='complete' if process.returncode==0 else 'failed',exit_code=process.returncode,finished=time.time())
except Exception as e:
    status.update(state='failed',error=str(e),finished=time.time())
(job/'status.json').write_text(json.dumps(status,indent=2))
