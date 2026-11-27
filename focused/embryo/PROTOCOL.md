# focused_morphogen_t2_embryo: pre-registered protocol

Fixed before launch and covered by the run lock (`runs/<id>/lock.json`, sha256 of every harness, prompt, kit, test
and config file plus the four data files). A restart refuses to continue if any locked file changed.

## Goal and entry
Agent Team entry for T2:embryo:test_interp (E7.75). This harness was designed and launched once. After launch no human
edits code, steers agents or chooses among outputs.

## Agents
- Round 0, builder: Command Code `deepseek/deepseek-v4.1-flash`, effort max, headless `cmd -p`. It starts from the
  program in `kit/program.py`: an empirical endpoint mixture placed on one native embryo scaffold. This is a
  team-authored prior-research starting program, disclosed here.
- Rounds 1-2, improvers: the same model and effort. Round k starts from the best-validation checkpoint of rounds
  0..k-1 and receives earlier rounds' NOTES.md and validation logs (never guard results).
- Fallback: if the model fails (usage limit, authentication, error, or 30 min without output) the harness waits 600 s
  and retries. Waits are unbounded and never count against the budget, so an operator re-login (credential files are
  synced into the session homes) resumes the run. Every session's model is recorded and reported. Rounds are never
  skipped.
- Budgets: 3 h active time and 80 validation evaluations for round 0; 3 h and 60 for each improver round; 12
  test-configuration checks per round. A session that ends with more than 30 min left is resumed with a continuation
  prompt (up to 4 times).
- Each session runs with its own home directory (no operator transcripts, memories, sessions, MCP servers or
  plugins), inside Linux Landlock: read-only system, Python environment, CLI and training stages; read-write only its
  workspace, home, tmp and evaluation spool. E7.25 and E7.5 are unreadable.

## Data and splits (official files only, checksums verified at every start)
- Training (agent-readable): E6.75, E8.0.
- Validation (agent sees scores): inputs E7.25 + E8.0 -> 7.5, the official T2:embryo:val_interp board; 3 scoring
  seeds (101-103), prediction seed 0.
- Guard (never visible to agents): inputs E6.75 + E8.0 -> 7.25; reference E8.0; used once in the final phase as a
  veto. There is only one official embryo validation answer, so this is an internal released-stage holdout; the
  protocol discloses that it is not a hidden-test proxy.
- Test: inputs E7.5 + E8.0 -> 7.75, <= 5,000 cells.
- Scorer: vec_local_score.score_many (veckit metrics, copy-last floor, split-half ceiling) with the official T2
  structure gate. The harness also reports native occupancy: the official occupancy Dice of the prediction against
  the best input stage (1 = one native cloud).
- Programs run in a Landlock child that can read only their snapshot and the input stages of the configuration (never
  a target), with no TCP; the service scores in a separate process.

## Round checkpoint
After the round: the final workspace is evaluated if not already evaluated (uncounted). Candidates = this round's
evaluated snapshots in descending validation order; the first that has native occupancy >= 0.90 and also runs (format
only, unscored) in the guard and test configurations is the round checkpoint (at most 6 tried). Round 0 without one
falls back to the starting program.

## Harness tuning (Optuna)
After each session, the round's best validated program, if it declares 1-4 knobs in knobs.json, is tuned with Optuna
TPE (seed 0, 32 trials, first trial = current values) on validation. The best setting is adopted only if it beats the
current values by >= 0.25 on prediction seed 0 and again on seed 1; the tuned snapshot is then one more checkpoint
candidate. Tuning is local; no fleet is used.

## Final selection (automatic, no refit)
1. Every distinct checkpoint is scored on the guard (prediction seeds 0 and 1; scoring seeds 201-203) and re-scored on
   validation with the same two prediction seeds (reported), including native occupancy on validation.
2. Eligible = completed the guard, native occupancy >= 0.90, and guard score within 1.0 point of the round-0 starting
   model. Selected = highest validation among eligible; ties -> later round.
3. Export: the selected checkpoint **unchanged** in the test configuration (E7.5 + E8.0 -> 7.75), seed 0, gene order
   of T2__embryo__test_interp.genes.txt, checked for cell count, finiteness and spatial_3D. If export fails, the next
   checkpoint in the ranking is used (recorded as fallback).
4. No retraining or refitting on the validation target: the selected program is a deterministic resampler/geometry
   placement, and the test configuration already uses all permitted input stages.
5. Evidence is packaged automatically: trajectory.zip, prompts.zip, harness.zip, other.zip, SHA256SUMS and one full
   zip with the submission file.

## Compute
Agent validation evaluations and final scoring run locally on this host. Same code and seeds everywhere.

## Planned finish
2026-11-25 08:00 CET. If it passes, an ATTENTION note is written; rounds still run to completion.
