#!/usr/bin/env bash
# Keep one locked Shinka run alive. NOT evolvable; part of the Agent-track lock.
#   setsid nohup shinka_ve/supervise.sh <lock.json> <run-name> > shinka_ve/runs/<run-name>.supervisor.log 2>&1 &
# Restarts run_evo.py with the SAME lock and run name after a crash; Shinka resumes from
# its database. No configuration can change between restarts (run_evo re-checks the lock).
# Stops on a clean exit, a lock violation, or after MAX_RESTARTS crashes.
set -u
cd "$(dirname "$0")/.."
LOCK=$1; NAME=$2; MAX_RESTARTS=${MAX_RESTARTS:-20}
LOG=shinka_ve/runs/$NAME.log
for attempt in $(seq 0 "$MAX_RESTARTS"); do
  echo "$(date '+%F %T') start attempt=$attempt"
  .venv/bin/python shinka_ve/run_evo.py --lock "$LOCK" --run-name "$NAME" >> "$LOG" 2>&1
  code=$?
  echo "$(date '+%F %T') exit code=$code"
  if [ $code -eq 0 ]; then echo "clean exit"; exit 0; fi
  if tail -n 5 "$LOG" | grep -q 'Lock violation'; then echo "lock violation: not restarting"; exit 1; fi
  sleep 60
done
echo "giving up after $MAX_RESTARTS restarts"; exit 1
