# AgenticScientist heart study protocol

The lock covers code, prompts, controls, panel files, scoring sources and checksums of all observed stages. The CLI sessions run in isolated homes. The candidate process receives read-only access to each replay's inputs and cannot open TCP connections. The trusted scorer reads the target separately. Agents see development metrics only. The operator can watch process status without using intermediate results to steer a locked entry.

| Replay | Inputs | Observed target | Role |
|---|---|---|---|
| One-day chamber | E8.25, E8.75, E9.5 | E10.5, annotated chamber subset | Development and final regression check |
| One-day full | E8.25, E8.75, E9.5 | Full E10.5 | Development diagnostic |
| Two-day chamber | E8.25, E8.5 | E10.5, annotated chamber subset | Primary selection replay |
| Earlier chamber | E8.25, E8.5, E8.75 | E9.5, annotated chamber subset | Secondary regression check |
| Export | All five stages through E10.5 | Hidden E12.5 | Format and evidence |

The two E10.5 replays reuse one biological target. The chamber filter approximates dissection. All three scored targets are retrospective for this project.

The fixed controls are copy last, chamber crop, and crop with damped size growth. Each uses 3,000 cells. The archived focused model is a comparison-only control for retrospective evaluation. Candidates must beat the strongest control, including the archived model, by at least 0.75 mean points on the two-day replay across two paired prediction seeds and three scoring draws, with a nonnegative difference for each prediction seed. Each shorter chamber replay allows at most a 0.50-point loss. The finalizer ranks qualifying challengers by the primary replay, followed by the eligible fixed controls. A fallback control is marked as research output, and the archived comparator is excluded from export. These tolerances are pre-registered engineering margins. The scores do not imply biological replication.

The locked agent writes the final H5AD and evidence. Use the portal's format-only check on the exact exported file when working toward an official entry. The planned research cutoff reserves the final hour of the internal deadline. Runs that exhaust the research budget go directly to selection.

During final selection the harness can dispatch independent scoring jobs to the four registered BIOServers. Workers use pre-existing authorized stage copies and verify stage checksums, panel, harness code and scorer versions. The agent runs locally. The trusted scheduler owns SSH dispatch, and a failed worker evaluation can fall back to local scoring.
