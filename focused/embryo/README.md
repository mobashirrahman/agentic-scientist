# focused_morphogen_t2_embryo

Autonomous T2 embryo interpolation (E7.75) run for the Virtual Embryo Challenge, Agent Team track.
The builder improves a one-native-scaffold endpoint-mixture model (round 0), two improver rounds follow, and a
pre-registered selection rule picks the final checkpoint and exports it automatically. Protocol: `PROTOCOL.md`.

## Setup (once)
The validation answer E7.5 is stored encrypted. Decrypt it into `data/protected/` before launching:

    ./setup_data.sh          # prompts for the holdout passphrase, verifies the sha256

## Launch / resume
    cmd status                # must show an authenticated Command Code account
    ./run.sh                  # preflight + background launch; prints the run id
    ./run.sh t2e_YYYYmmdd_HHMMSS  # resume the same run after a crash or reboot

Watch: `runs/<id>/run.log`, `runs/<id>/state.json`, `runs/<id>/ATTENTION.txt` (only if action is needed).

## Outputs
- `runs/<id>/final/submission/T2__embryo__test_interp.h5ad` + `manifest.json`
- `runs/<id>/final/evidence/{trajectory,prompts,harness,other}.zip`, `SHA256SUMS`, `README.md`
- `runs/<id>/focused_t2_embryo_<id>_agent_full.zip` (everything above in one file)

## Layout
- `fm/` harness: orchestrator, agents (headless CLI sessions in Landlock), evaluation (spool service, sandboxed
  runner, scorer), final (selection, export, packaging), lock, preflight.
- `kit/` starting program, the agent tools copied into each workspace, and a short generic prior-knowledge note.
- `prompts/` task brief, builder, improver, continuation prompts.
- `data/train` (agent-readable: E6.75, E8.0), `data/protected` (E7.25 guard target, E7.5 validation target),
  `data/panels`.
- `tests/` fake agent and config for the end-to-end harness test.
