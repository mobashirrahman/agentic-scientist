# Focused AgenticScientist T1 protocol

A builder and two improvers run in Command Code with isolated workspaces. The starting code reproduces the team-authored empirical sampler by drawing real latest-stage donor rows with bounded type growth. Each round nominates one working workspace. The next round receives the latest nominated checkpoint and public diagnostic history.

| Use | Inputs | Target | Scoring |
|---|---|---|---|
| Local validation | E8.5, E9.5 | Official unlocked E10.5 | Three scorer draws, diagnostic |
| Format rehearsal | E8.5, E9.5 | E11.5 configuration | Output check |
| Final independent check | E14.5, E16.5 | E18.5 | Two prediction draws, three scorer draws each |
| T1 export | E8.5, E9.5, official unlocked E10.5 | E12.5 heart-chamber configuration | Unscored |

The independent check uses the locally curated wild-type whole-heart Feulner dataset from GSE150817. Its prep script verifies the source hash and exclusively reads the three post-E13.5 stages. Its panel is the intersection of the atlas and challenge genes after per-cell log1p CP10k normalization using all measured genes. This is a late, cross-assay transfer check with the same forecast horizon. The whole-heart dissection, developmental regime and capture differ from the challenge. Its numbers estimate performance on those data only.

The seed is always included. A nominated checkpoint must beat the seed by at least one point on average on the independent check, with a nonnegative difference for each prediction draw. Its mean DE-direction skill must stay within one point of the seed. Rank qualifying candidates by the mean independent-check score, with earlier rounds first on ties. For each ranked candidate verify the exact T1 test configuration at prediction seeds 42 and 101. Both outputs must pass the format contract and the adult-globin veto measured against the same E10.5 cardiac-plus-Blood reference. The first passing candidate exports at seed 42. Fall back to the empirical seed if needed. The one-day validation score does not rank candidates at finalization.

Agents can read E8.5 and E9.5. Only sandboxed prediction processes receive the arguments for their configuration, and scoring sees target expression in a separate process. The agents do not receive E10.5 or independent guard files, detailed feedback from protected runs, portal access, or submissions. The launcher locks code, config, prompts, and checksums of all data files. Artifacts and evidence stay local.
