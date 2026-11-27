#!/usr/bin/env bash
# Decrypt ONLY the two T2 test inputs (E10.5 heart, E7.5 embryo), export Codex T2 test files, wipe plaintext.
# Usage: printf '%s\n' '<passphrase>' | bash codex_t2_export.sh
set -euo pipefail
ROOT=/scratch/user/virtual-embryo; cd "$ROOT"
FILES=(data/raw/T2/E10.5.h5ad data/raw/T2/E7.5.h5ad)
exec 9>"$(dirname "$PWD")/.agentic_scientist-holdout.lock"
flock -n 9 || { echo 'another finalization is active'; exit 1; }
pgrep -f 'orchestrator[.]py --lock|claude -p|codex exec|opencode run' > /dev/null && { echo 'refusing: agent running'; exit 1; }
for f in "${FILES[@]}"; do [[ -e $f ]] && { echo "refusing to overwrite plaintext $f"; exit 1; }; done
written=()
cleanup() { rc=$?; echo "$(date '+%F %T') wiping plaintext held-out data"; rm -f -- "${written[@]}"; unset MGPASS; exit $rc; }
trap cleanup EXIT; trap 'exit 130' INT; trap 'exit 143' TERM
read -r -s -p "Holdout passphrase: " MGPASS; echo; export MGPASS
for f in "${FILES[@]}"; do
  IFS=$'\t' read -r path enc sum <<< "$(awk -F '\t' -v p="$f" '$1 == p' data/holdout.enc/manifest.tsv)"
  written+=("$path")
  openssl enc -d -aes-256-cbc -pbkdf2 -iter 300000 -pass env:MGPASS -in "data/holdout.enc/$enc" -out "$path"
  printf '%s  %s\n' "$sum" "$path" | sha256sum -c --status
done
unset MGPASS; echo "decrypted and verified ${#written[@]} files"
OMP_NUM_THREADS=2 .venv/bin/python /scratch/user/ve-next/humantrack/holdout_check/export_codex_t2.py 2>&1 | grep -v Warning
