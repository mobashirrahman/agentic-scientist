# Focused AgenticScientist T1

Standalone T1 adaptation of the focused AgenticScientist workflows. See PROTOCOL.md for the split definitions and promotion rule.

Run ./run.sh to preflight and start a restartable background run. Pass an existing run ID to resume unchanged locked files. Follow runs/<id>/run.log and state.json. Final reports, any T1 output, and evidence appear under runs/<id>/final. The run performs local research and format checks.

The stage files are copied from the main repository's released T1 training stages and official unlocked E10.5. setup_guard.py derives the later whole-heart check from the curated local GSE150817 data. The protected directory stays outside the agent's filesystem permissions.
