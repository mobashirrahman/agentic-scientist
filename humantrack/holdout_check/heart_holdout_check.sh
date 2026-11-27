#!/usr/bin/env bash
# One-off pre-registered holdout check: Codex T2 heart (ve-next/humantrack/t2_heart) vs enigma's selected program.
# Rule (identical to the final selection's per-board rule, config frozen in the enigma lock):
#   paired difference Codex - enigma on holdout splits heart_e105 + heart_e105_long (heart board score),
#   4 holdout seed pairs [[202,0],[313,1],[424,2],[535,3]]; accept iff one-sided 95% lower bound > +0.25.
# Decrypts ONLY data/raw/T2/E10.5.h5ad, local evaluation only (no fleet), wipes plaintext on exit.
# Usage (from anywhere): printf '%s\n' '<passphrase>' | bash heart_holdout_check.sh
set -euo pipefail
ROOT=/scratch/user/virtual-embryo
OUT=/scratch/user/ve-next/humantrack/holdout_check
EN=$ROOT/agentic_scientist/runs/mglock_20261119_012037_enigma/final/final_ws
CX=/scratch/user/ve-next/humantrack/t2_heart
cd "$ROOT"
TARGET=data/raw/T2/E10.5.h5ad
row=$(awk -F '\t' -v p="$TARGET" '$1 == p' data/holdout.enc/manifest.tsv)
[[ -n "$row" ]] || { echo "manifest row missing"; exit 1; }
IFS=$'\t' read -r path encrypted checksum <<< "$row"

exec 9>"$(dirname "$PWD")/.agentic_scientist-holdout.lock"
flock -n 9 || { echo 'another finalization is active'; exit 1; }
if pgrep -f 'orchestrator[.]py --lock|claude -p|codex exec|opencode run' > /dev/null; then
  echo 'refusing: an orchestrator or agent is running'; exit 1
fi
[[ -e "$path" || -L "$path" ]] && { echo "refusing to overwrite existing plaintext: $path"; exit 1; }

cleanup() { rc=$?; echo "$(date '+%F %T') wiping plaintext held-out data"; rm -f -- "$path"; unset MGPASS; exit $rc; }
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

read -r -s -p "Holdout passphrase: " MGPASS; echo
export MGPASS
openssl enc -d -aes-256-cbc -pbkdf2 -iter 300000 -pass env:MGPASS -in "data/holdout.enc/$encrypted" -out "$path"
unset MGPASS
printf '%s  %s\n' "$checksum" "$path" | sha256sum -c --status
echo "decrypted and verified $path"

ev() {  # ws tag pred fit
  OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 timeout 2400 .venv/bin/python agentic_scientist/evaluate.py \
    --workspace "$1" --set holdout --splits heart_e105,heart_e105_long --pred-seed "$3" --fit-seed "$4" \
    --out "$OUT/holdout_$2_$3.json" --workers 2 > "$OUT/holdout_$2_$3.log" 2>&1
}
pids=()
for p in "202 0" "313 1" "424 2" "535 3"; do
  set -- $p
  ev "$EN" enigma "$1" "$2" & pids+=($!)
  ev "$CX" codex "$1" "$2" & pids+=($!)
done
fail=0; for p in "${pids[@]}"; do wait "$p" || fail=1; done
(( fail == 0 )) || { echo "an evaluation failed; see $OUT/holdout_*.log"; exit 1; }

.venv/bin/python - "$OUT" <<'PY'
import json, statistics as st, sys
from scipy import stats
o = sys.argv[1]
def heart(tag, s):
    d = json.load(open(f'{o}/holdout_{tag}_{s}.json'))
    assert d['correct'], d.get('error')
    return d['boards']['heart']
seeds = (202, 313, 424, 535)
c = [heart('codex', s) for s in seeds]; e = [heart('enigma', s) for s in seeds]
d = [a - b for a, b in zip(c, e)]
m = st.mean(d); lb = m - stats.t.ppf(0.95, len(d) - 1) * st.stdev(d) / len(d) ** .5
res = dict(rule='heart board, paired Codex-enigma, 4 holdout pairs, one-sided 95% LB > 0.25',
           codex=c, enigma=e, diffs=d, mean=m, lb95=lb, verdict='ACCEPT' if lb > 0.25 else 'REJECT')
json.dump(res, open(f'{o}/verdict.json', 'w'), indent=1)
print(f"heart holdout: codex {st.mean(c):.2f} vs enigma {st.mean(e):.2f}; diffs {[round(x, 2) for x in d]}")
print(f"mean {m:+.2f}, 95% LB {lb:+.2f} -> {res['verdict']}")
PY
