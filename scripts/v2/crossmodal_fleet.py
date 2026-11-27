import fcntl,json,subprocess,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from src.data import ROOT
from scripts.fleet_run import ssh,REMOTE_ROOT
host='bio01.cluster.example'
files=['src/v2/crossmodal.py','scripts/v2/evaluate_crossmodal.py','scripts/v2/job.py','data/raw/T2/E10.5.h5ad']
subprocess.run(['rsync','-aR',*files,host+':'+REMOTE_ROOT+'/'],cwd=ROOT,check=True)
job='heart_late_crossmodal_fit_0_pred_101'
code=f'''import json,os,subprocess
from pathlib import Path
root=Path({REMOTE_ROOT!r});os.chdir(root);job=root/'submissions/v2/jobs'/{job!r};job.mkdir(parents=True,exist_ok=True)
with (job/'launch.json').open('x') as f:f.write(json.dumps(dict(family='rna_guided_spatial_state')))
with (job/'worker.log').open('wb') as log:
 p=subprocess.Popen([str(root/'.venv/bin/python'),'scripts/v2/job.py',{job!r},'scripts/v2/evaluate_crossmodal.py'],stdout=log,stderr=subprocess.STDOUT,start_new_session=True,env=dict(os.environ,OPENBLAS_NUM_THREADS='2',OMP_NUM_THREADS='2'))
print(json.dumps(dict(pid=p.pid)))
'''
handle=json.loads(ssh(host,code));handle.update(job=job,host=host,root=REMOTE_ROOT,experiment='heart_late_crossmodal',fit_seed=0,prediction_seed=101,output='heart_late_crossmodal/fit_0_pred_101')
path=ROOT/'submissions/v2/fleet_jobs.json'
with path.with_suffix('.lock').open('w') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX);rows=json.loads(path.read_text());rows.append(handle);path.write_text(json.dumps(rows,indent=2)+'\n')
print('Launched',json.dumps(handle),flush=True)
