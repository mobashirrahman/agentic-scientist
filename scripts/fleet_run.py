"""Deploy isolated CPU backtests to authorized Bio servers without credentials/data publication.

Only the selected experiment's released input/target files and source code are
copied. The API .env and any hidden-test material are never copied. Each launch
returns a PID-backed worker handle; collect verifies process state and retrieves
completed reports, not large prediction matrices.
"""
import argparse
import fcntl
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts.evaluate_candidates import EXPERIMENTS
from src.data import ROOT

REMOTE_ROOT='/scratch/user/virtual-embryo-first-20261116'


def ssh(host, code):
    p=subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=8',host,
        'python3 -c '+shlex.quote(code)],capture_output=True,text=True,check=True)
    return p.stdout.strip()


def deploy(host,names):
    if not host.endswith('.cluster.example'):
        raise ValueError('Only the authorized Bio fleet is supported')
    files={'requirements.txt','scripts/evaluate_candidates.py','scripts/worker_run.py','src/data.py','src/models.py'}
    for name in names:
        spec=EXPERIMENTS[name]
        files.update('data/raw/'+p for p in spec['inputs']+[spec['target']])
    ssh(host,f"from pathlib import Path; Path({REMOTE_ROOT!r}).mkdir(parents=True,exist_ok=True)")
    subprocess.run(['rsync','-aR',*sorted(files),host+':'+REMOTE_ROOT+'/'],cwd=ROOT,check=True)
    print('Copied',host,names,flush=True)
    # A worker-only venv avoids modifying any environment used by another project.
    command='set -e\ncd '+shlex.quote(REMOTE_ROOT)+'\npython3 -m venv .venv\n.venv/bin/pip install -q -r requirements.txt\n'
    subprocess.run(['ssh','-o','BatchMode=yes',host,'bash -c '+shlex.quote(command)],check=True)
    jobs=[]
    for name in names:
        code=f'''import json,os,subprocess
from pathlib import Path
root=Path({REMOTE_ROOT!r});os.chdir(root)
job=root/'jobs'/{name!r};job.mkdir(parents=True,exist_ok=True)
if (job/'status.json').exists():raise RuntimeError('Existing worker record; collect rather than restart')
with (job/'worker.log').open('wb') as log:
 p=subprocess.Popen([str(root/'.venv/bin/python'),'scripts/worker_run.py',{name!r}],stdout=log,stderr=subprocess.STDOUT,start_new_session=True,env=dict(os.environ,OPENBLAS_NUM_THREADS='2',OMP_NUM_THREADS='2'))
print(json.dumps(dict(pid=p.pid,experiment={name!r},root=str(root))))
'''
        handle=json.loads(ssh(host,code))
        handle['host']=host
        jobs.append(handle)
        print('Started',handle,flush=True)
    record=ROOT/'submissions/fleet_jobs.json'
    with record.with_suffix('.lock').open('w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        previous=json.loads(record.read_text()) if record.exists() else []
        record.write_text(json.dumps(previous+jobs,indent=2)+'\n')


def collect():
    records=json.loads((ROOT/'submissions/fleet_jobs.json').read_text())
    for handle in records:
        host,name=handle['host'],handle['experiment']
        code=f'''import json,os
from pathlib import Path
root=Path({REMOTE_ROOT!r});p=root/'jobs'/{name!r}/'status.json'
status=json.loads(p.read_text()) if p.exists() else {{'state':'starting'}}
try:
 current=Path('/proc/'+str({handle['pid']})+'/stat').read_text().split()
 status['process_exists']=current[2]!='Z'
 if 'start_ticks' in status:status['same_process']=int(current[21])==status['start_ticks']
except FileNotFoundError:status['process_exists']=False
print(json.dumps(status))
'''
        status=json.loads(ssh(host,code))
        print(host,name,status,flush=True)
        # Retrieve checkpointed JSON evidence and logs, including live progress.
        destination=ROOT/'submissions/development'/name/'prediction_42'
        destination.mkdir(parents=True,exist_ok=True)
        subprocess.run(['rsync','-a','--include=*/','--include=*.json','--exclude=*',
            f'{host}:{REMOTE_ROOT}/submissions/development/{name}/prediction_42/',str(destination)+'/'],check=True)
        subprocess.run(['rsync','-a',f'{host}:{REMOTE_ROOT}/jobs/{name}/worker.log',str(destination/'worker.log')],check=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=['deploy','collect'])
    parser.add_argument('--host')
    parser.add_argument('--experiments',nargs='+',choices=EXPERIMENTS)
    args=parser.parse_args()
    if args.action=='deploy':deploy(args.host,args.experiments)
    else:collect()
