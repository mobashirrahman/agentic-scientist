# T2 human-track dev report

The standalone [heart](t2_heart/program.py) and [embryo](t2_embryo/program.py) workspaces take only the stage inputs supplied to `predict`. The heart model projects expression, composition and size from earlier stages. The embryo model interpolates populations on one native scaffold.

## Paired dev results

I replayed the read-only Enigma seed at prediction seeds **101, 211 and 307**. Seed 101 reproduced the archived `seed_dev.json` split scores and scoring-seed totals. The largest metric difference from the archive was 0.0033 skill points for organ-proxy neighbourhood MMD. Every replay and candidate run used fit seed 0 and evaluator scoring seeds 101–103. Each paired difference is human minus Enigma after averaging over those scoring seeds. The E9.5 result averages the organ proxy and the mean of the three splits with surrounding tissue. The heart board gives E8.75 and E9.5 equal weight.

| Board or heart target | Enigma mean | Human mean | Δ101 | Δ211 | Δ307 | Mean Δ | One-sided 95% lower bound |
|---|---:|---:|---:|---:|---:|---:|---:|
| **Heart board** | 53.48 | 58.44 | +5.45 | +4.46 | +5.00 | +4.97 | +4.13 |
| E8.75 | 52.58 | 55.74 | +4.16 | +2.50 | +2.82 | +3.16 | +1.68 |
| E9.5 | 54.38 | 61.15 | +6.74 | +6.42 | +7.17 | +6.77 | +6.14 |
| E9.5 with surroundings (three-split mean) | 54.49 | 56.68 | +2.42 | +1.99 | +2.16 | +2.19 | +1.82 |
| E9.5 organ proxy | 54.26 | 65.62 | +11.05 | +10.85 | +12.18 | +11.36 | +10.15 |
| **Embryo board** | 56.17 | 58.56 | +2.03 | +2.43 | +2.70 | +2.39 | +1.82 |

The t bounds use three prediction-seed pairs on the same targets. Seed 101 informed model selection. The remaining pairs check prediction variability on dev.

### Split scores and metrics

Each cell shows **Enigma → human (paired mean Δ)** in skill points. Higher is better for every displayed metric. The evaluator applies the neighbourhood gate to the shape contribution before aggregating each split score.

| Dev split | Score | DE score | DE direction | MMD | Variogram | D2 shape | Occupancy Dice | Scale | Neighbourhood MMD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| heart_early | 53.76 → 58.08 (+4.32) | 55.63 → 58.34 (+2.71) | 57.49 → 59.85 (+2.35) | 53.75 → 57.74 (+3.99) | 53.59 → 55.58 (+1.98) | 48.56 → 48.11 (-0.45) | 52.48 → 53.60 (+1.12) | 54.17 → 75.37 (+21.20) | 53.07 → 57.34 (+4.27) |
| heart_late | 54.22 → 57.02 (+2.80) | 56.22 → 54.98 (-1.24) | 58.36 → 57.94 (-0.42) | 53.78 → 56.82 (+3.04) | 53.70 → 53.84 (+0.13) | 47.65 → 48.71 (+1.05) | 52.22 → 54.37 (+2.15) | 59.34 → 75.72 (+16.37) | 52.77 → 56.42 (+3.65) |
| heart_long | 55.50 → 54.94 (-0.56) | 51.79 → 48.71 (-3.07) | 59.82 → 59.03 (-0.79) | 53.62 → 57.24 (+3.61) | 53.54 → 53.80 (+0.26) | 61.79 → 34.51 (-27.28) | 48.16 → 47.29 (-0.87) | 67.06 → 68.30 (+1.24) | 53.59 → 59.96 (+6.37) |
| heart_e875 | 52.58 → 55.74 (+3.16) | 51.57 → 49.88 (-1.69) | 54.72 → 53.61 (-1.11) | 52.75 → 53.18 (+0.44) | 53.48 → 50.69 (-2.80) | 50.28 → 50.71 (+0.43) | 50.82 → 51.52 (+0.70) | 51.38 → 81.57 (+30.18) | 53.28 → 57.75 (+4.47) |
| heart_organ_proxy | 54.26 → 65.62 (+11.36) | 57.94 → 68.42 (+10.48) | 59.88 → 68.94 (+9.06) | 53.00 → 66.90 (+13.90) | 53.32 → 62.54 (+9.21) | 47.07 → 50.89 (+3.81) | 47.70 → 45.92 (-1.78) | 62.14 → 87.23 (+25.09) | 52.72 → 67.32 (+14.61) |
| embryo_early | 56.17 → 58.56 (+2.39) | 55.97 → 55.30 (-0.67) | 66.84 → 67.38 (+0.54) | 52.60 → 55.72 (+3.12) | 19.12 → 44.88 (+25.76) | 93.01 → 49.55 (-43.46) | 50.40 → 49.59 (-0.81) | 50.95 → 94.64 (+43.69) | 59.25 → 56.91 (-2.34) |

| Dev split | Δ101 | Δ211 | Δ307 |
|---|---:|---:|---:|
| `heart_early` | +3.92 | +4.08 | +4.97 |
| `heart_late` | +2.72 | +2.11 | +3.57 |
| `heart_long` | +0.61 | -0.22 | -2.07 |
| `heart_e875` | +4.16 | +2.50 | +2.82 |
| `heart_organ_proxy` | +11.05 | +10.85 | +12.18 |
| `embryo_early` | +2.03 | +2.43 | +2.70 |

Raw evaluator outputs are saved in each workspace as `r.json`, `r_211.json` and `r_307.json`. The paired seed rows are in `enigma_dev.json`.

## Heart extrapolation

The PeacyBlose25 and devalexnguyenxsvf model names motivated a latest-stage bulk offset and a large empirical donor pool. The model emits **25,179 cells**, the evaluator's heart cap. It estimates each type's mean log expression and gene detection frequency at every input stage, then projects recent changes from the latest mean. Stages are weighted by recency and shared support. Broader chamber families contribute when exact annotation support is limited. The model edits detection and positive values in real donor rows, then restores each donor's original molecule budget.

The donor law projects the relative abundance of broad lineages. It gives additional weight to annotated organ residents and their spatial neighbours, including vascular and pericardial cells. Explicit dissection metadata uses a 45% blend. With surrounding tissue, the blend rises with forecast horizon as the growing heart takes up more of the field. Systematic resampling preserves the fitted mixture with low draw variance.

Coordinates travel with each donor. Repeated copies receive local jitter and the sampled cloud is scaled to the latest field RMS radius times the growth multiplier. The multiplier blends short-horizon whole-field size change with the growth of the ventricular compartment, whose RMS uses 95th-percentile winsorization. With explicit dissection the whole-field weight is halved.

| Tunable knob | Used | Range | Effect |
|---|---:|---:|---|
| `k` | 24 | 8–64 | Neighbourhood size for organ weighting and jitter distance |
| `bulk_weight` | 0.20 | 0–0.65 | Multiplies the expression step, with horizon factor `h / (interval + 0.5h)` |
| `clip` | 0.60 | 0.25–0.90 | Caps gain/drop probabilities and the absolute shift in positive log expression |
| `jitter` | 0.15 | 0–0.30 | Max per-axis jitter as a fraction of the kth-neighbour distance for repeated rows |

Fixed settings include at least 40 cells per pseudobulk, a 120-cell support prior, 0.75-day stage-weight decay and at least 100 cells for ventricular growth and organ weighting. The composition strength is 0.85 with a 0.001 share pseudocount and a ±1.2 log-fold cap. The surrounding-tissue blend is `0.40h / (0.75 + h)` with horizon in days. The whole-field timescale is 0.35 days, the field rate is bounded to −1.00 to +0.40 log-radius per day, the ventricular rate is bounded to 0 to +0.40, and the size multiplier is bounded to 0.80–1.80.

### What helped

The organ prior gave the largest E9.5 gains, especially in neighbourhood MMD, population MMD and expression direction. Letting the short whole-field trend contract the cloud helped the E8.75 scale estimate. A bulk offset with the first donor and growth law lost at E8.75. Under the final donor law, 0.20 bulk improved the seed-101 `heart_early` score by 1.04 points versus bulk off and cost 1.11 at E8.75. The final model keeps an active, bounded expression projection. Its gains over Enigma at both ages came chiefly from the spatial and composition model. The alternate k, clip and jitter settings moved the board by 0.11 points on that seed. That joint check has limited power to distinguish the three knobs.

| Exploratory setting at seed 101 | Heart board | E8.75 | E9.5 with surroundings | E9.5 organ proxy |
|---|---:|---:|---:|---:|
| First bulk-shift and growth variant, bulk 0.30 | 51.25 | 49.15 | 52.72 | 53.99 |
| Projected composition and revised growth, bulk 0.30 | 56.88 | 54.47 | 53.21 | 65.36 |
| Projected composition and revised growth, stronger composition and bulk 0.12 | 56.78 | 54.78 | 52.03 | 65.55 |
| Final anatomy prior with bulk off | 59.00 | 57.03 | 56.45 | 65.48 |
| Final anatomy prior with k 48, clip 0.40 and jitter 0.05 | 58.41 | 55.86 | 56.64 | 65.29 |
| **Final settings** | 58.53 | 55.93 | 56.76 | 65.50 |

The `heart_long` headline lost 0.56 points on average. Its D2 shape loss shows how reweighting anatomical regions can distort the distance distribution even when neighbourhood expression improves.

## Embryo interpolation

Each of the **5,000** coordinates is a scaled point from the earlier bracket. Cell-type quotas select the scaffold, earlier survivors and later donors. The later donor fraction is the target's elapsed time divided by the bracket duration, **0.40** on dev. The resulting proportions interpolate the two annotated populations up to integer rounding. Within each earlier type quota, later-donor slots are clustered using a smooth random field. A one-to-one assignment minimizes distances in expression and registered space with a penalty for mismatched shared labels. Earlier survivors retain their own profiles.

The radius grows with the cube root of interpolated cell count for the part of expansion supported by cell mass. Extra radius growth enters as the fourth power of the bracket fraction. This anchors both endpoint radii and keeps the early forecast less sensitive to rapid widening of the later field. When the later median inferred molecule depth is at least twice the earlier one, later donor molecules are thinned by hypergeometric sampling. The depth model caps log growth at 0.75 per day and preserves each later donor's relative depth.

| Setting | Value |
|---|---:|
| Expression match | 24 SVD components, with 0.25 minimum component scaling denominator |
| Registered coordinate cost weight | 0.65 |
| Shared-label mismatch cost | 0.50 |
| Registration support | At least 3 shared labels with ≥20 cells in each stage |
| Patch field | Up to 32 anchors, radius 0.25 in RMS-normalized units |
| Radius law | Cell-count exponent 1/3, extra expansion power 4 |
| Depth harmonization | 2× median-depth jump threshold, 0.75/day maximum log depth growth |

### What helped

The cell-count radius and molecule-depth harmonization drove the gain. Patch placement recovered part of the neighbourhood skill the native scaffold initially lost. A stronger registration-coordinate cost did little for the headline. Relative to Enigma, the final model improves MMD and variogram while losing DE recovery, D2 shape and neighbourhood skill on this split. It keeps the single-scaffold design motivated by the leaderboard. The dev bracket spans 1.25 days and crosses a large depth change, so both the geometry and the late-donor thinning may behave differently on a closer bracket.

| Exploratory setting at seed 101 | Score | MMD | Variogram | Scale | Neighbourhood |
|---|---:|---:|---:|---:|---:|
| Native scaffold with log-linear radius | 49.85 | 52.65 | 18.81 | 44.62 | 50.24 |
| Native scaffold with cell-count radius | 54.32 | 52.65 | 18.81 | 98.69 | 50.24 |
| Depth harmonization and smooth radius, dispersed placement | 57.65 | 57.50 | 44.00 | 94.64 | 51.95 |
| Stronger coordinate cost, dispersed placement | 57.63 | 57.45 | 44.27 | 94.64 | 51.15 |
| **Final patch placement** | 58.47 | 54.97 | 44.95 | 94.64 | 56.49 |

Raw occupancy Dice was similar at 16³ and changed sign across resolutions. Voxel edges spanned only about two to five median cell spacings on the scored dev target halves, so this diagnostic is sensitive to subsampling. Coordinates were checked against the exact early scaffold rows and the recorded scale for all three prediction seeds.

| Occupancy grid | Enigma raw Dice | Human raw Dice | Voxel edge / median truth spacing |
|---|---:|---:|---:|
| 12³ | 0.853 | 0.809 | 4.74 |
| 16³ | 0.773 | 0.771 | 3.56 |
| 24³ | 0.570 | 0.593 | 2.37 |

## E12.5 heart horizon

The evaluator's truth-free `heart_3d` check forecasts three days from E8.75 and E9.5 with dissected-heart metadata. Both the human model and Enigma passed at prediction seed 101.

| Plausibility measure | Enigma | Human |
|---|---:|---:|
| Fraction of genes with mean blow-up | 0.0000 | 0.0000 |
| Median per-gene variance ratio to latest input | 0.9828 | 0.8672 |
| Pseudobulk drift relative to linear input drift | 0.0177 | 0.1020 |
| Largest inferred type share | V-CM, 12.60% (input max 11.55%) | A-CM, 20.62% (input max 9.40%) |
| RMS radius ratio to latest input | 1.3132 | 1.8000 |

The heart prediction reaches its 1.80× radius cap in this check. That limits runaway growth, and it can understate expansion if a later starting heart grows faster. The latest-stage anatomy and donor families constrain the model's ability to represent looping, chamber remodeling, emerging lineages and changed tissue neighbourhoods. Section-index units on the third coordinate add uncertainty to using a single isotropic multiplier. The projected atrial compartment is more prominent than in either input on the sanity diagnostic. The organ proxy tests a dissection-related composition shift at E9.5, while the intended two-day forecast starts from a later heart. The sanity bounds check spike, collapse, dominance, drift and size. Transfer of the 2-day trend and the E12.5 geometry remains unverified.
