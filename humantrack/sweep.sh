#!/bin/bash
# usage: sweep.sh name 'k=v,k=v'  -> copies t1_lt with KNOBS overrides and scores dev T1 splits
set -e
n=$1; ov=$2; W=sweeps/$n; mkdir -p $W
cp t1_lt/program.py t1_lt/temporal.py $W/
echo "KNOBS.update(dict($ov))" >> $W/temporal.py
cd /scratch/user/ve-next
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 timeout 900 /scratch/user/virtual-embryo/.venv/bin/python agentic_scientist/evaluate.py --workspace humantrack/$W --set dev --splits temporal_val,temporal_heartonly --out humantrack/$W/r.json --workers 2 > humantrack/$W/log 2>&1
python3 -c "
import json;d=json.load(open('humantrack/$W/r.json'));s=d['splits']
print('$n', round(d['proxy'],2), *[(k,round(s[k]['score'],1),{m:round(v,1) for m,v in s[k]['metrics'].items()}) for k in s])"
