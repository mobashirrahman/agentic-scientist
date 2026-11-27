#!/bin/bash
# focused_morphogen_t1 launcher. Usage: ./run.sh [RUN_ID]
# Preflight, then the orchestrator in the background under a restart loop (survives logout and crashes; a restart
# resumes from state.json and refuses to continue if any locked file changed). Give an existing RUN_ID to resume.
set -euo pipefail
cd "$(dirname "$0")"
PY="$(realpath ../..)/.venv/bin/python"
RUN_ID=${1:-t1_$(date +%Y%m%d_%H%M%S)}
export FM_CONFIG=${FM_CONFIG:-config.json}
mkdir -p runs/$RUN_ID
$PY -I fm/preflight.py --run "$RUN_ID" ${FM_SKIP_PROBES:+--skip-agents}
setsid nohup bash -c "
  for i in \$(seq 1 30); do
    $PY -I fm/orchestrator.py --run '$RUN_ID' && exit 0
    echo \"\$(date '+%F %T') orchestrator exited \$?; restart \$i in 60 s\"; sleep 60
  done" >> runs/$RUN_ID/supervisor.log 2>&1 < /dev/null &
echo "launched run $RUN_ID (supervisor pid $!). Log: runs/$RUN_ID/run.log"
