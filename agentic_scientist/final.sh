#!/usr/bin/env bash
# Decrypt the selection inputs, run finalization without agents, then remove plaintext.
# Usage: agentic_scientist/final.sh <lock.json> <run-name> [config] [--no-export]
# This entry point keeps decrypted selection inputs on the head node.
set -euo pipefail
umask 077
cd "$(dirname "$0")/.."
LOCK=$1
NAME=$2
shift 2
CONFIG=
if (( $# )) && [[ $1 != --* ]]; then CONFIG=$1; shift; fi
[[ $# -eq 0 || ( $# -eq 1 && $1 == --no-export ) ]] || exit 2
RUNDIR=agentic_scientist/runs/$(basename "$LOCK" .json)_$NAME
MANIFEST=data/holdout.enc/manifest.tsv

exec 9>"$(dirname "$PWD")/.agentic_scientist-holdout.lock"
flock -n 9 || { echo 'another finalization is active'; exit 1; }
if pgrep -f 'orchestrator[.]py --lock|claude -p|codex exec|opencode run' > /dev/null; then
  echo 'refusing: an evaluator or agent is still running on the head node'
  exit 1
fi
[[ -f "$RUNDIR/state.json" ]]
CONFIG=$(.venv/bin/python - "$RUNDIR/state.json" "$LOCK" "$CONFIG" <<'PY'
import json
import sys

from pathlib import Path
from agentic_scientist.artifacts import run_config

state = json.loads(Path(sys.argv[1]).read_text())
if state.get('phase') not in ('awaiting_holdout', 'final', 'done'):
    sys.exit('research must finish before finalization')
binding, config = run_config(Path.cwd(), json.loads(Path(sys.argv[2]).read_text()), sys.argv[3] or None, state)
if not config.get('local_evaluation_only'):
    sys.exit('finalization requires local evaluation')
print(binding['path'], 'T3' if config.get('require_calibrated_final') else 'all')
PY
)
read -r CONFIG HOLDOUT_SCOPE <<< "$CONFIG"
rows=$(awk -F '\t' -v scope="$HOLDOUT_SCOPE" '$1 ~ /^data\/raw\// && (scope == "all" || $1 ~ /^data\/raw\/T3\//)' "$MANIFEST")
[[ -n "$rows" ]]
mapfile -t files < <(cut -f1 <<< "$rows")
for path in "${files[@]}"; do
  if [[ -e "$path" || -L "$path" ]]; then
    echo "refusing to overwrite existing plaintext: $path" >&2
    exit 1
  fi
done

written=()
cleanup() {
  local rc=$?
  trap - EXIT INT TERM
  if (( ${#written[@]} )); then
    rm -f -- "${written[@]}" || rc=1
  fi
  unset MGPASS
  exit "$rc"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

read -r -s -p "Holdout passphrase: " MGPASS
echo
while IFS=$'\t' read -r path encrypted checksum; do
  mkdir -p "$(dirname "$path")"
  written+=("$path")
  openssl enc -d -aes-256-cbc -pbkdf2 -iter 300000 -pass fd:3 -in "data/holdout.enc/$encrypted" -out "$path" 3<<<"$MGPASS"
  printf '%s  %s\n' "$checksum" "$path" | sha256sum -c --status
done <<< "$rows"
unset MGPASS
MG_PRIVATE_FINAL=1 .venv/bin/python -I agentic_scientist/orchestrator.py --lock "$LOCK" --run-name "$NAME" --config "$CONFIG" --final-only \
  2>&1 | tee -a "$RUNDIR/final.log"
