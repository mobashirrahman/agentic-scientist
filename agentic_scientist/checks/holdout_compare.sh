#!/usr/bin/env bash
# One holdout look (logged in the ledger) comparing workspaces on the full holdout set over 3 seed pairs.
#   agentic_scientist/checks/holdout_compare.sh <ws1> <ws2> ...
set -u
cd "$(dirname "$0")/../.."
if pgrep -f "claude -p|codex exec|opencode run" > /dev/null; then echo "refusing: agents are running"; exit 1; fi
FILES=$(awk -F'\t' '$1 ~ /^data\/raw\// {print $1"\t"$2}' data/holdout.enc/manifest.tsv)
OUT=agentic_scientist/checks/holdout_compare_$(date +%Y%m%d_%H%M%S); mkdir -p "$OUT"
cleanup() { while IFS=$'\t' read -r path _; do rm -f "$path"; done <<< "$FILES"; echo "plaintext wiped"; }
trap cleanup EXIT INT TERM
read -r -s -p "Holdout passphrase: " MGPASS; echo; export MGPASS
while IFS=$'\t' read -r path enc; do
  openssl enc -d -aes-256-cbc -pbkdf2 -iter 300000 -pass env:MGPASS -in "data/holdout.enc/$enc" -out "$path" || { echo "wrong passphrase"; exit 1; }
done <<< "$FILES"
unset MGPASS
for ws in "$@"; do
  for pair in "202 0" "313 1" "424 2"; do
    set -- $pair
    .venv/bin/python agentic_scientist/evaluate.py --workspace "$ws" --set holdout --pred-seed $1 --fit-seed $2 --workers 4 \
      --out "$OUT/$(basename "$ws")_$1.json" > /dev/null 2>&1 &
  done
done; wait
.venv/bin/python - "$OUT" <<'PY'
import json, sys, glob, collections, time
rows = collections.defaultdict(list)
for f in glob.glob(sys.argv[1] + '/*.json'):
    e = json.load(open(f)); rows[f.split('/')[-1].rsplit('_', 1)[0]].append(e)
for ws, es in rows.items():
    ok = [e for e in es if e.get('correct')]
    b = {k: round(sum(e['boards'][k] for e in ok) / len(ok), 2) for k in ok[0]['boards']} if ok else {}
    print(ws, 'holdout', round(sum(e['proxy'] for e in ok) / max(len(ok), 1), 2), b, f'{len(ok)}/{len(es)} ok')
with open('agentic_scientist/library/holdout_ledger.jsonl', 'a') as f:
    f.write(json.dumps(dict(t=time.time(), run='manual holdout_compare', candidates=list(rows))) + '\n')
PY
