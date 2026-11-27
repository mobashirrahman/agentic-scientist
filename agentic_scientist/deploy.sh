#!/usr/bin/env bash
# Provision the remote mirror at the same absolute root used by fleet.py and final.sh.
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT=$PWD
SHARED="$(dirname "$ROOT")/virtual-embryo"
SSH=(ssh -o BatchMode=yes -o ConnectTimeout=10 -o ServerAliveInterval=30)
hosts=$(awk '{sub(/#.*/, ""); if (NF) print $1}' shinka_ve/fleet_hosts.txt)
inputs=$(.venv/bin/python agentic_scientist/preflight.py --inputs)
expected=$(.venv/bin/python agentic_scientist/preflight.py)
pids=()

for host in $hosts; do
  (
    if [[ "$ROOT" != "$SHARED" ]]; then
      # Link only the released/opted-in inputs identified by the evaluator.
      # Never link the whole raw directory, since finalization writes holdouts there.
      {
        printf 'set -eu\ncd %q\n' "$ROOT"
        printf 'mkdir -p vendor data/external/ko_validation\n'
        for path in .venv vendor/veckit vendor/vec-community-kit \
          data/external/{qiu2024,heart_anchor,heart_spatial,embryo_anchor,go_prior,expression_prior,ko_validation/hand2}; do
          printf 'test -e %q\nif ! test -e %q; then ln -s %q %q; fi\n' "$SHARED/$path" "$path" "$SHARED/$path" "$path"
        done
        while IFS= read -r path; do
          [[ "$path" == data/raw/* ]] || continue
          printf 'mkdir -p %q\ntest -f %q\nif ! test -e %q; then ln -s %q %q; fi\n' \
            "$(dirname "$path")" "$SHARED/$path" "$path" "$SHARED/$path" "$path"
        done <<< "$inputs"
      } | "${SSH[@]}" "$host" "mkdir -p '$ROOT' && bash -s"
    fi
    rsync -aR --exclude runs --exclude locks --exclude __pycache__ -e "${SSH[*]}" \
      agentic_scientist src shinka_ve/{harness,dynamics,fleet_evaluate}.py "$host:$ROOT/"
    actual=$("${SSH[@]}" "$host" "cd '$ROOT' && test ! -e .env && .venv/bin/python agentic_scientist/preflight.py")
    if [[ "$actual" != "$expected" ]]; then
      echo "$host FAIL: evaluator code, dependencies, or inputs differ" >&2
      exit 1
    fi
    echo "$host ok"
  ) &
  pids+=("$!")
done

failed=0
for pid in "${pids[@]}"; do
  wait "$pid" || failed=1
done
exit "$failed"
