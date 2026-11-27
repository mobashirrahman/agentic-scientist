#!/usr/bin/env bash
# Keep one locked AgenticScientist run alive (resumes from its cycle markers). Part of the AgenticScientist lock.
#   setsid nohup agentic_scientist/supervise.sh <lock.json> <run-name> > agentic_scientist/runs/<run-name>.supervisor.log 2>&1 &
set -u
cd "$(dirname "$0")/.."
LOCK=$1; NAME=$2; MAX_RESTARTS=${MAX_RESTARTS:-20}
CONFIG_ARGS=()
if [[ -n ${3:-} ]]; then CONFIG_ARGS=(--config "$3"); fi
mkdir -p agentic_scientist/runs; LOG=agentic_scientist/runs/$NAME.log
for attempt in $(seq 0 "$MAX_RESTARTS"); do
  echo "$(date '+%F %T') start attempt=$attempt"
  .venv/bin/python agentic_scientist/orchestrator.py --lock "$LOCK" --run-name "$NAME" "${CONFIG_ARGS[@]}" >> "$LOG" 2>&1
  code=$?; echo "$(date '+%F %T') exit code=$code"
  if [ $code -eq 0 ]; then echo "clean exit"; exit 0; fi
  if tail -n 5 "$LOG" | grep -q 'Lock violation\|Effective config\|Config absent from lock\|seed program fails'; then echo "fatal: not restarting"; exit 1; fi
  sleep 120
done
echo "giving up"; exit 1
