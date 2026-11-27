"""Record authoritative PID identity and terminal exit code for one v2 experiment."""
import json,os,subprocess,sys,time
from pathlib import Path
root=Path(__file__).resolve().parents[2]
name,pred,fit=sys.argv[1:4]
job=root/'submissions/v2/jobs'/f'{name}_fit_{fit}_pred_{pred}'
job.mkdir(parents=True,exist_ok=True)
status=dict(state='running',pid=os.getpid(),start_ticks=int(Path('/proc/self/stat').read_text().split()[21]),started=time.time())
def save():
 temp=job/'status.tmp';temp.write_text(json.dumps(status,indent=2)+'\n');temp.replace(job/'status.json')
save()
try:
 process=subprocess.run([sys.executable,'scripts/v2/evaluate.py',name,'--prediction-seed',pred,'--fit-seed',fit],cwd=root)
 status.update(state='complete' if process.returncode==0 else 'failed',exit_code=process.returncode,finished=time.time())
except Exception as e:status.update(state='failed',error=str(e),finished=time.time())
save()
