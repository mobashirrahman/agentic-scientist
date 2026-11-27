import argparse,fcntl,json,subprocess,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from src.data import ROOT
from scripts.fleet_run import ssh,REMOTE_ROOT
parser=argparse.ArgumentParser();parser.add_argument('experiment',choices=['gata4_1','gata4_2'])
parser.add_argument('--fit-seed',type=int,required=True);parser.add_argument('--prediction-seed',type=int,required=True)
args=parser.parse_args();host='bio19.cluster.example'
subprocess.run(['rsync','-aR','scripts/v2/confirm_complexity.py','scripts/v2/job.py','experiments/v2/complexity_confirmation.json',host+':'+REMOTE_ROOT+'/'],cwd=ROOT,check=True)
job=f'confirmation_{args.experiment}_complexity_fit_{args.fit_seed}_pred_{args.prediction_seed}'
code=f'''import json,os,subprocess
from pathlib import Path
root=Path({REMOTE_ROOT!r});os.chdir(root);job=root/'submissions/v2/jobs'/{job!r};job.mkdir(parents=True,exist_ok=True)
with (job/'launch.json').open('x') as f:f.write(json.dumps(dict(family='complexity replication')))
with (job/'worker.log').open('wb') as log:
 p=subprocess.Popen([str(root/'.venv/bin/python'),'scripts/v2/job.py',{job!r},'scripts/v2/confirm_complexity.py',{args.experiment!r},'--fit-seed',str({args.fit_seed}),'--prediction-seed',str({args.prediction_seed})],stdout=log,stderr=subprocess.STDOUT,start_new_session=True,env=dict(os.environ,OPENBLAS_NUM_THREADS='2',OMP_NUM_THREADS='2'))
print(json.dumps(dict(pid=p.pid)))
'''
handle=json.loads(ssh(host,code));name='confirmation_'+args.experiment+'_complexity'
handle.update(host=host,root=REMOTE_ROOT,job=job,experiment=name,fit_seed=args.fit_seed,prediction_seed=args.prediction_seed,
              output=f'{name}/fit_{args.fit_seed}_pred_{args.prediction_seed}')
path=ROOT/'submissions/v2/fleet_jobs.json'
with path.with_suffix('.lock').open('w') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX);rows=json.loads(path.read_text());rows.append(handle);path.write_text(json.dumps(rows,indent=2)+'\n')
print('Launched',json.dumps(handle),flush=True)
