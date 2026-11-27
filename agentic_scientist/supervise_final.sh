#!/usr/bin/env bash
# Keep the locked AgenticScientist FINAL run alive until it is done or the configured hard stop has passed.
#   setsid nohup agentic_scientist/supervise_final.sh <lock.json> <run-name> <config> > agentic_scientist/runs/<run-name>.supervisor.log 2>&1 &
# Restarts resume from the cycle markers (research) or the cached evaluations (finalization). Never restarts after
# the hard stop, after a clean finish, or on a lock/config violation.
set -u
cd "$(dirname "$0")/.."
LOCK=$1; NAME=$2; CONFIG=$3; MAX_RESTARTS=${MAX_RESTARTS:-40}
mkdir -p agentic_scientist/runs; LOG=agentic_scientist/runs/$NAME.log
finished() {
  .venv/bin/python -I - "$LOCK" "$NAME" "$CONFIG" <<'EOF'
import json, sys, time
from datetime import datetime
from pathlib import Path
lock, name, config = sys.argv[1:]
cfg = json.loads(Path(config).read_text())
lid = json.loads(Path(lock).read_text())['lock_id']
st = Path('agentic_scientist/runs') / f'{lid}_{name}' / 'state.json'
phase = json.loads(st.read_text()).get('phase') if st.exists() else None
hard = cfg.get('hard_stop_at')
past = hard is not None and time.time() >= datetime.fromisoformat(hard).timestamp()
print(f'phase={phase} past_hard_stop={past}')
sys.exit(0 if phase in ('done', 'hard_stopped') or past else 1)
EOF
}
for attempt in $(seq 0 "$MAX_RESTARTS"); do
  if finished; then echo "$(date '+%F %T') run finished or past the hard stop: not starting"; exit 0; fi
  echo "$(date '+%F %T') start attempt=$attempt"
  .venv/bin/python agentic_scientist/orchestrator.py --lock "$LOCK" --run-name "$NAME" --config "$CONFIG" >> "$LOG" 2>&1
  code=$?; echo "$(date '+%F %T') exit code=$code"
  if [ $code -eq 0 ] && finished; then echo "clean finish"; exit 0; fi
  if tail -n 5 "$LOG" | grep -q 'Lock violation\|Effective config\|Config absent from lock\|seed program fails\|sandbox probe failed'; then
    echo "fatal: not restarting"; exit 1
  fi
  sleep 90
done
echo "giving up"; exit 1
