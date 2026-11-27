#!/bin/bash
# Paired dev test: Codex T2 workspaces vs enigma's selected program, same prediction seeds.
cd /scratch/user/ve-next
PY=/scratch/user/virtual-embryo/.venv/bin/python
EN=/scratch/user/virtual-embryo/agentic_scientist/runs/mglock_20261119_012037_enigma/final/final_ws
H=heart_early,heart_late,heart_long,heart_e875,heart_organ_proxy
O=humantrack/paired
ev(){ OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 timeout 1800 $PY agentic_scientist/evaluate.py --workspace $1 --set dev --splits $2 --pred-seed $3 --out $O/$4_$3.json --workers 3 > $O/$4_$3.log 2>&1 || echo "FAIL $4 $3"; }
for s in 101 211 307 401 503 601 701 809; do
  ev $EN $H,embryo_early $s enigma &
  ev humantrack/t2_heart $H $s heart &
  ev humantrack/t2_embryo embryo_early $s embryo &
  wait; echo "seed $s done $(date +%T)"
done
