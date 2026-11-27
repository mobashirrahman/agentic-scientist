"""Persistent generic v2 worker with PID identity and explicit terminal status."""
import json,os,subprocess,sys,time
from pathlib import Path
root=Path(__file__).resolve().parents[2]
job=root/'submissions/v2/jobs'/sys.argv[1]
job.mkdir(parents=True,exist_ok=True)
status=dict(state='running',pid=os.getpid(),start_ticks=int(Path('/proc/self/stat').read_text().split()[21]),started=time.time(),command=sys.argv[2:])
def save():
 p=job/'status.tmp';p.write_text(json.dumps(status,indent=2)+'\n');p.replace(job/'status.json')
save()
try:
 p=subprocess.run([sys.executable,*sys.argv[2:]],cwd=root)
 status.update(state='complete' if p.returncode==0 else 'failed',exit_code=p.returncode,finished=time.time())
except Exception as e:status.update(state='failed',error=str(e),finished=time.time())
save()
