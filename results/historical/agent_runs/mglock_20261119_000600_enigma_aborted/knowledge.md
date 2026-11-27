# Knowledge bank

## Established (held up; effect sizes and cycles)
- Still no established experimental result: both attempted cycles [w0_c00] [w2_c00] were skipped before implementation, so no program, board delta, or measured proxy effect exists. The Δproxy +0.00 (z +0.0) in both records is a default placeholder, not evidence.
- Operational fact, now repeated: the empty-ideation failure reproduced across two workers, 2/2 attempted cycles, Δproxy placeholder +0.00 both times [w0_c00] [w2_c00]. This is a process finding, not an evidence-class result.
- Baseline bookkeeping: the seed dev proxy 185.2868 is reported identically for w0, w1, w2 and w3 [w0_c00] [w2_c00]. Treat it as a shared default starting value, not an accepted improvement.

## Dead ends (and the condition under which a retry is justified)
- Empty ideation → skipped cycle: two occurrences, zero hypotheses, zero boards, zero measured deltas [w0_c00] [w2_c00]. Retry only when the ideator output contains a mechanism, a named target board, an expected direction, and a numeric success threshold; otherwise abort before spending a cycle.
- Emitting numeric deltas for skipped cycles: Δproxy +0.00 and z +0.0 appeared twice with nothing measured [w0_c00] [w2_c00]. Retry this formatting only if deltas are explicitly nulled for unmeasured cycles.

## Promising / inconclusive leads
- None yet. [w0_c00] and [w2_c00] produced no proxy measurement and no board result, so there is no mean, bound, or effect size to classify as promising or inconclusive.

## Per-board state of the art and weakest metrics
- No board-level state of the art exists: `boards` is null in both records [w0_c00] [w2_c00]. The best accepted per-worker figure (185.29 for w0–w3) is the shared seed baseline, not a validated program score.
- Weakest metrics cannot be ranked until a cycle reports per-board scores; record every board baseline before the first real test [w0_c00] [w2_c00].
- Risk to watch: identical 185.29 values across all four workers may indicate a default rather than four independent measurements [w0_c00] [w2_c00].

## Method pitfalls (statistics, evaluation, reasoning traps)
- Never average placeholder Δproxy = 0.00 or z = 0.0 into comparisons; skipped records are missing data, not zero-effect results [w0_c00] [w2_c00].
- Do not read repeated identical baselines (185.29 for every worker) as convergence or consensus; demand per-board provenance before calling anything state of the art [w0_c00] [w2_c00].
- A skip says nothing about hypothesis quality or board difficulty — do not infer "no effect" or "hard board" from it [w0_c00] [w2_c00].
- Filter on status before any aggregation: 2/2 records so far are skipped, so an unfiltered leaderboard is empty and must not be reported as a tie [w0_c00] [w2_c00].
- Require n>=3 repeated prediction/fit seeds for any variance claim; n=1 screens understate variance and cannot support an evidence class [w0_c00].

## Implementation pitfalls (crashes, helper quirks, contract)
- Guard the ideator → implementer handoff: an empty hypothesis must set status=skipped and leave deltas null, never 0.0 [w0_c00] [w2_c00].
- Prefer null over default 0.0 for unmeasured `delta_proxy` and `z` so downstream synthesis cannot mistake defaults for experiments [w0_c00] [w2_c00].
- Log the raw ideator output on every empty handoff; "ideator wrote nothing" twice points at a prompt/wiring/parse contract, not model silence [w0_c00] [w2_c00].
- Schema-validate the hypothesis (mechanism, target board, direction, threshold) before spawning an implementer and fail fast with a blocked reason [w0_c00].
- Ensure each record carries an explicit measured/skipped flag; absent flags let a default-constructed result pass as real [w0_c00] [w2_c00].

## Open questions
- Why did the ideator emit nothing in both w0 and w2 — prompt contract, missing context, or rejected output parsing? [w0_c00] [w2_c00]
- What exact minimum hypothesis schema should gate implementation, and who enforces it? [w0_c00]
- Which board should the first real cycle target, and which per-board baseline metrics must be captured first? [w0_c00] [w2_c00]
- Is 185.2868 a computed proxy or a seeded default? This determines whether future Δproxy values are comparable [w0_c00] [w2_c00].
- Are w1 and w3 also at risk of empty ideation, given the same baseline and no records yet? [w0_c00] [w2_c00]
