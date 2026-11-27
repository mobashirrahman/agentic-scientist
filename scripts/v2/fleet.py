"""Launch and observe v2 backtests on the user-authorized Bio fleet."""
import argparse,fcntl,json,subprocess,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from src.data import ROOT
from scripts.fleet_run import ssh,REMOTE_ROOT
from scripts.evaluate_candidates import EXPERIMENTS


def launch(host,experiment,pred,fit):
 if not host.endswith('.cluster.example'):raise ValueError(host)
 files={'requirements.txt','src/data.py','src/models.py','scripts/evaluate_candidates.py',
        'src/v2/__init__.py','src/v2/transport.py','scripts/v2/__init__.py','scripts/v2/evaluate.py','scripts/v2/worker.py'}
 spec=EXPERIMENTS[experiment]
 files.update('data/raw/'+p for p in spec['inputs']+[spec['target']])
 if spec['task']=='T3':files.add('data/raw/T2/E8.5.h5ad')
 ssh(host,f"from pathlib import Path; Path({REMOTE_ROOT!r}).mkdir(parents=True,exist_ok=True)")
 subprocess.run(['rsync','-aR',*sorted(files),host+':'+REMOTE_ROOT+'/'],cwd=ROOT,check=True)
 # Existing first-run environments can be reused unchanged. New hosts get an
 # isolated venv with the same pinned scientific dependencies.
 command=f"set -e\ncd {REMOTE_ROOT}\nif [ ! -x .venv/bin/python ]; then python3 -m venv .venv; .venv/bin/pip install -q -r requirements.txt; fi\n"
 import shlex
 subprocess.run(['ssh','-o','BatchMode=yes',host,'bash -c '+shlex.quote(command)],check=True)
 jobname=f'{experiment}_fit_{fit}_pred_{pred}'
 code=f'''import json,os,subprocess
from pathlib import Path
root=Path({REMOTE_ROOT!r});os.chdir(root)
job=root/'submissions/v2/jobs'/{jobname!r};job.mkdir(parents=True,exist_ok=True)
with (job/'launch.json').open('x') as f:f.write(json.dumps(dict(experiment={experiment!r},prediction_seed={pred},fit_seed={fit})))
with (job/'worker.log').open('wb') as log:
 p=subprocess.Popen([str(root/'.venv/bin/python'),'scripts/v2/worker.py',{experiment!r},str({pred}),str({fit})],stdout=log,stderr=subprocess.STDOUT,start_new_session=True,env=dict(os.environ,OPENBLAS_NUM_THREADS='2',OMP_NUM_THREADS='2'))
print(json.dumps(dict(pid=p.pid,experiment={experiment!r},prediction_seed={pred},fit_seed={fit},job={jobname!r})))
'''
 handle=json.loads(ssh(host,code));handle['host']=host;handle['root']=REMOTE_ROOT
 path=ROOT/'submissions/v2/fleet_jobs.json'
 with path.with_suffix('.lock').open('w') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX)
  rows=json.loads(path.read_text()) if path.exists() else []
  rows.append(handle);path.write_text(json.dumps(rows,indent=2)+'\n')
 print('Launched',json.dumps(handle),flush=True)


def collect():
 path=ROOT/'submissions/v2/fleet_jobs.json'
 rows=json.loads(path.read_text())
 observed=[]
 for handle in rows:
  host=handle['host'];job=handle['job']
  code=f'''import json
from pathlib import Path
p=Path({REMOTE_ROOT!r})/'submissions/v2/jobs'/{job!r}/'status.json'
status=json.loads(p.read_text()) if p.exists() else {{'state':'starting'}}
try:
 stat=Path('/proc/'+str({handle['pid']})+'/stat').read_text().split()
 status['process_live']=stat[2]!='Z'
 if 'start_ticks' in status:status['same_process']=int(stat[21])==status['start_ticks']
except FileNotFoundError:status['process_live']=False
print(json.dumps(status))
'''
  try:status=json.loads(ssh(host,code))
  except Exception as error:
   observed.append(dict(handle=handle,observation_error=str(error)));print(host,job,'observation failed; not assumed stopped',flush=True);continue
  observed.append(dict(handle=handle,status=status))
  print(host,job,status,flush=True)
  relative=handle.get('output',f"{handle['experiment']}/fit_{handle['fit_seed']}_pred_{handle['prediction_seed']}")
  destination=ROOT/'submissions/v2'/relative
  destination.mkdir(parents=True,exist_ok=True)
  subprocess.run(['rsync','-a','--include=*/','--include=*.json','--exclude=*',
    f'{host}:{REMOTE_ROOT}/submissions/v2/{relative}/',str(destination)+'/'],check=False)
  subprocess.run(['rsync','-a',f'{host}:{REMOTE_ROOT}/submissions/v2/jobs/{job}/worker.log',str(destination/'worker.log')],check=True)
 (ROOT/'submissions/v2/fleet_status.json').write_text(json.dumps(observed,indent=2)+'\n')

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('action',choices=['launch','collect'])
 parser.add_argument('--host');parser.add_argument('--experiment',choices=EXPERIMENTS)
 parser.add_argument('--prediction-seed',type=int,default=101);parser.add_argument('--fit-seed',type=int,default=0)
 args=parser.parse_args()
 if args.action=='collect':collect()
 else:launch(args.host,args.experiment,args.prediction_seed,args.fit_seed)
