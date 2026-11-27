"""Deploy a frozen confirmation plan; copies no team credentials."""
import argparse,fcntl,json,shlex,subprocess,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from src.data import ROOT
from scripts.fleet_run import ssh,REMOTE_ROOT
parser=argparse.ArgumentParser();parser.add_argument('--host',required=True);parser.add_argument('--fit-seed',type=int,required=True)
parser.add_argument('--prediction-seed',type=int,required=True);parser.add_argument('experiment',choices=['heart_early','heart_late','embryo_early','embryo_late']);args=parser.parse_args();host=args.host
from scripts.evaluate_candidates import EXPERIMENTS
spec=EXPERIMENTS[args.experiment]
if not host.endswith('.cluster.example'):raise ValueError(host)
files=['requirements.txt','src/data.py','src/models.py','src/v2/__init__.py','src/v2/transport.py',
 'scripts/evaluate_candidates.py','scripts/v2/__init__.py','scripts/v2/evaluate.py','scripts/v2/confirm_spatial.py','scripts/v2/job.py',
 'experiments/v2/spatial_confirmation.json',*['data/raw/'+p for p in spec['inputs']+[spec['target']]]]
ssh(host,f"from pathlib import Path; Path({REMOTE_ROOT!r}).mkdir(parents=True,exist_ok=True)")
subprocess.run(['rsync','-aR',*files,host+':'+REMOTE_ROOT+'/'],cwd=ROOT,check=True)
command=f"set -e\ncd {REMOTE_ROOT}\nif [ ! -x .venv/bin/python ]; then python3 -m venv .venv; .venv/bin/pip install -q -r requirements.txt; fi\n"
subprocess.run(['ssh','-o','BatchMode=yes',host,'bash -c '+shlex.quote(command)],check=True)
job=f'confirmation_{args.experiment}_fit_{args.fit_seed}_pred_{args.prediction_seed}'
code=f'''import json,os,subprocess
from pathlib import Path
root=Path({REMOTE_ROOT!r});os.chdir(root);job=root/'submissions/v2/jobs'/{job!r};job.mkdir(parents=True,exist_ok=True)
with (job/'launch.json').open('x') as f:f.write(json.dumps(dict(phase='confirmation')))
with (job/'worker.log').open('wb') as log:
 p=subprocess.Popen([str(root/'.venv/bin/python'),'scripts/v2/job.py',{job!r},'scripts/v2/confirm_spatial.py',{args.experiment!r},'--fit-seed',str({args.fit_seed}),'--prediction-seed',str({args.prediction_seed})],stdout=log,stderr=subprocess.STDOUT,start_new_session=True,env=dict(os.environ,OPENBLAS_NUM_THREADS='2',OMP_NUM_THREADS='2'))
print(json.dumps(dict(pid=p.pid)))
'''
handle=json.loads(ssh(host,code));handle.update(host=host,root=REMOTE_ROOT,job=job,experiment='confirmation_'+args.experiment,fit_seed=args.fit_seed,
 prediction_seed=args.prediction_seed,output=f'confirmation_{args.experiment}/fit_{args.fit_seed}_pred_{args.prediction_seed}')
path=ROOT/'submissions/v2/fleet_jobs.json'
with path.with_suffix('.lock').open('w') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX);rows=json.loads(path.read_text());rows.append(handle);path.write_text(json.dumps(rows,indent=2)+'\n')
print('Launched',json.dumps(handle),flush=True)
