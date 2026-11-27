"""Launch a bounded multi-stage heart experiment on an existing fleet worker."""
import argparse,fcntl,json,subprocess,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from src.data import ROOT
from scripts.fleet_run import ssh,REMOTE_ROOT

parser=argparse.ArgumentParser();parser.add_argument('--host',required=True);parser.add_argument('--experiment',choices=['heart_early','heart_late'],required=True)
args=parser.parse_args();host=args.host
if not host.endswith('.cluster.example'):raise ValueError(host)
files=['src/v2/multistage.py','scripts/v2/job.py','scripts/v2/evaluate_multistage.py','data/raw/T2/E8.5.h5ad']
subprocess.run(['rsync','-aR',*files,host+':'+REMOTE_ROOT+'/'],cwd=ROOT,check=True)
jobname=args.experiment+'_multistage_fit_0_pred_101'
code=f'''import json,os,subprocess
from pathlib import Path
root=Path({REMOTE_ROOT!r});os.chdir(root)
job=root/'submissions/v2/jobs'/{jobname!r};job.mkdir(parents=True,exist_ok=True)
with (job/'launch.json').open('x') as f:f.write(json.dumps(dict(experiment={args.experiment!r},family='multistage')))
with (job/'worker.log').open('wb') as log:
 p=subprocess.Popen([str(root/'.venv/bin/python'),'scripts/v2/job.py',{jobname!r},'scripts/v2/evaluate_multistage.py',{args.experiment!r}],stdout=log,stderr=subprocess.STDOUT,start_new_session=True,env=dict(os.environ,OPENBLAS_NUM_THREADS='2',OMP_NUM_THREADS='2'))
print(json.dumps(dict(pid=p.pid,job={jobname!r})))
'''
handle=json.loads(ssh(host,code));name=args.experiment+'_multistage'
handle.update(host=host,root=REMOTE_ROOT,experiment=name,fit_seed=0,prediction_seed=101,output=name+'/fit_0_pred_101')
path=ROOT/'submissions/v2/fleet_jobs.json'
with path.with_suffix('.lock').open('w') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX);rows=json.loads(path.read_text());rows.append(handle);path.write_text(json.dumps(rows,indent=2)+'\n')
print('Launched',json.dumps(handle),flush=True)
