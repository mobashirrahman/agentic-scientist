"""Run frozen-choice confirmations on the existing isolated fleet deployment."""
import json
from pathlib import Path
import shlex
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.data import ROOT
from scripts.fleet_run import REMOTE_ROOT
from scripts.evaluate_candidates import EXPERIMENTS

host=sys.argv[1]
names=sys.argv[2:]
files={'scripts/confirm_selection.py','submissions/selection.json'}
for name in names:
    spec=EXPERIMENTS[name]
    files.update('data/raw/'+p for p in spec['inputs']+[spec['target']])
subprocess.run(['rsync','-aR',*sorted(files),host+':'+REMOTE_ROOT+'/'],cwd=ROOT,check=True)
for name in names:
    command='cd '+shlex.quote(REMOTE_ROOT)+' && OPENBLAS_NUM_THREADS=2 OMP_NUM_THREADS=2 .venv/bin/python scripts/confirm_selection.py '+shlex.quote(name)
    subprocess.run(['ssh','-o','BatchMode=yes',host,command],check=True)
    destination=ROOT/'submissions/development'/name/'prediction_43'
    destination.mkdir(parents=True,exist_ok=True)
    subprocess.run(['rsync','-a','--include=*/','--include=*.json','--exclude=*',
        f'{host}:{REMOTE_ROOT}/submissions/development/{name}/prediction_43/',str(destination)+'/'],check=True)
