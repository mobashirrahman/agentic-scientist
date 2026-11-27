#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
python="$(realpath ../..)/.venv/bin/python"
id=${1:-t2h_$(date -u +%Y%m%d_%H%M%S)}
[[ $id =~ ^t2h_[A-Za-z0-9_-]+$ ]] || exit 2
mkdir -p "runs/$id"
if [[ ${2:-} == --supervise ]]; then
    for attempt in 1 2 3; do
        "$python" -I fm/orchestrator.py --run "$id" && exit 0
        printf 'Restarting attempt %s for %s\n' "$attempt" "$id"
        sleep 30
    done
    exit 1
fi
"$python" -I fm/preflight.py --run "$id"
setsid nohup ./run.sh "$id" --supervise >> "runs/$id/supervisor.log" 2>&1 < /dev/null &
printf 'Launched %s with supervisor PID %s.\n' "$id" "$!"
