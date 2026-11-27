---
name: leaderboard
description: The public P3 TEST leaderboard with every entry's per-metric test scores and model name, a curated decoding of the strongest public recipes, and our own earlier test entries with what each program did. Use at the start of every cycle to choose WHAT to build and which public recipe to replicate.
---
# Leaderboard evidence

`$MG_ROOT/.venv/bin/python $MG_ROOT/agentic_scientist/tools/leaderboard.py [--live] <command>`; boards: `T1`, `T3`, `heart`, `embryo`.

| command | answers |
|---|---|
| `recipes <board>` | What the strongest public names say they did, decoded, and the shared core of every top entry. **Start here.** |
| `ours [<board>]` | Our own earlier test entries: per-metric test scores, what each program did, next to the public top-10 mean. |
| `gaps <board> --ws <parent ws>` | Per metric: weight, best / top-10 / median test value, where the leaders separate from the field, and our parent's DEV value of the same metric. |
| `top <board> [--metric m] [-n 50]` | Entries by headline or by one metric, all metrics plus model name. |
| `entry <board> <rank or team regex>` | One entry in full. |
| `families <board>` / `sweeps <board>` | Naming schemes (shared code) and knob tokens (d230, k150, N25179, rms510p5, tilt075 ...) with Spearman trends. |
| `search <regex>` / `diff` | Keyword search over all boards; what changed between the two newest snapshots. |

`--live` fetches the current public board (same JSON the website renders, no key). The harness also saves a fresh
snapshot every hour; without `--live` the newest snapshot is used.

Rules:
- All public data is fair game: names, the numbers in them, scores, per-metric results. Explicitly try to REPLICATE
  the strongest decodable recipe on your board (first one or two cycles), then build on it.
- The one restriction (live rules, section 10, last bullet): "Returned scores may be used to choose among predictions,
  not to compute them." Do not solve for a hidden target property by inverting the skill map or by differencing
  scores. Trying a recipe or a parameter value that a public entry describes is ordinary leaderboard work.
- Public scores are each team's best of many test submissions (optimistic) and validation predicts test poorly. A
  replicated recipe still has to win the paired dev race; when the dev splits cannot see the test property (e.g.
  dissection protocol, E12.5 size), say so in hypothesis.json and argue from the public evidence.
- Record what you used: `origin: "leaderboard"`, `leaderboard_evidence` (entries, metrics, recipe), and a
  `metric_signature` matching the test gap you target.
