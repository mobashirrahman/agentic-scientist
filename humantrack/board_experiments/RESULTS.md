# T1, heart and embryo experiments

All planned spatial comparisons completed at three prediction seeds in the current evaluator. These are local scores. The two heart views use the same biological stage. Both embryo splits fail the historical three-way selection calibration.

## T1

| Program | Blood-like share across E12.5 seeds | Composition passes |
|---|---:|---:|
| First-bundle sampler | 13.50–14.33% | 3/3 |
| Consistent-trend composition | 10.80–11.67% | 3/3 |
| Consistent-trend expression | 14.07–14.90% | 3/3 |

The blood-like cap is 17.51%. The lower share of the composition variant does not establish better E12.5 accuracy.

### E14.5 chamber probe

| Program | C57BL/6 distance | CD1 distance |
|---|---:|---:|
| First-bundle sampler | 0.598 | 1.176 |
| Consistent-trend composition | 0.487 | 1.065 |
| Consistent-trend expression | 0.598 | 1.176 |
| Enigma | 0.579 | 1.157 |

Lower is closer. The probe preferred Enigma over the first bundle in both strains, the reverse of the known official order. The composition variant was closer on this probe, but that gain cannot qualify it for promotion. The probe compares predicted marker shares with sequencing-based atlas annotations at one prediction seed.

## T2 heart

| Program | Ordinary E8.5 | Dissected E8.5 |
|---|---:|---:|
| First-bundle anchor | 49.52 | 50.60 |
| Geometry only | 49.85 | 51.39 |
| Local expression only | 49.06 | 50.67 |
| Geometry + local expression | 49.40 | 51.46 |
| Codex at native cell count | 52.19 | 61.78 |

Geometry alone improved slightly across both views relative to the first-bundle anchor. Codex remained ahead on every paired seed. The geometry and expression ablations use 3,000 cells, while Codex uses its native larger output.

## T2 embryo

| Program | E8.0 guard | E7.25 dev |
|---|---:|---:|
| First-bundle endpoint mixture | 82.78 | 56.99 |
| Region-shifted scaffold, random donor assignment | 78.37 | 44.52 |
| Region-shifted scaffold, spatial donor assignment | 82.55 | 52.88 |
| Mild region warp with donor positions preserved | 82.76 | 56.89 |

Spatial donor assignment preserved substantially more score than random assignment. It still lost to the baseline on both targets. The mild region warp was tested after observing the initial scaffold results and did not improve either mean.

No private holdout was opened. No prediction was promoted, locked or uploaded, and no format check was run.
