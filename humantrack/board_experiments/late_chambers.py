"""Test whether independent E14.5 non-blood chamber composition can rank T1."""
from collections import Counter
import csv
import io
from pathlib import Path
from types import SimpleNamespace
from urllib.request import Request, urlopen
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import numpy as np
from agentic_scientist import evaluate
from agentic_scientist.artifacts import write_json
from agentic_scientist.composition import shares
from humantrack.board_experiments.run import temporal

GROUPS = ('cardiomyocyte', 'endothelial', 'epicardial')
ARCHIVE = Path('/scratch/user/virtual-embryo/agentic_scientist/runs/mglock_20261119_012037_enigma/final/selected')
OUT = Path(__file__).with_name('late_chambers.json')


def chamber_reference(strain):
    url = f'https://cells.ucsc.edu/mouse-dev-heart/{strain}/meta.tsv'
    request = Request(url, headers={'User-Agent': 'Codex Virtual Embryo E14.5 cohort evaluation'})
    with urlopen(request, timeout=30) as response:
        rows = csv.DictReader(io.TextIOWrapper(response), delimiter='\t')
        counts = Counter((row['zone'], row['cell_type_broad']) for row in rows
                         if row['stage'].strip().lower().removeprefix('e') == '14.5')
    chamber_counts = np.array([[counts[zone, group] for group in GROUPS]
                               for zone in ('LA', 'RA', 'LV', 'RV')], dtype=float)
    if np.any(chamber_counts.sum(axis=1) == 0):
        raise ValueError(f'{strain}: an E14.5 chamber is missing')
    return (chamber_counts / chamber_counts.sum(axis=1, keepdims=True)).mean(axis=0)


def main():
    reference = {strain: chamber_reference(strain) for strain in ('c57bl6', 'cd1')}
    report = {'models': {}}
    write_json(OUT, report)
    harness = evaluate.harness
    spec = dict(harness.SPLITS['temporal_test_composition'], time=14.5)
    harness.SPLITS['late_chamber_probe'] = spec
    models = {variant: SimpleNamespace(predict=lambda board, inputs, times, target, context, v=variant:
                                        temporal(inputs, times, target, v, context['seed']))
              for variant in ('baseline', 'composition', 'expression')}
    models['enigma'] = evaluate.load(ARCHIVE)
    for label, program in models.items():
        pred, _ = harness.run_split(program, 'late_chamber_probe', 42, params=evaluate.load_params(ARCHIVE)
                                     if label == 'enigma' else {})
        fractions = shares(pred)
        values = np.array([fractions[group] for group in GROUPS])
        values /= values.sum()
        report['models'][label] = {
            'normalized_marker_shares': dict(zip(GROUPS, values)),
            'distance': {strain: float(np.abs(values - target).sum()) for strain, target in reference.items()},
        }
        write_json(OUT, report)
        print(label, report['models'][label]['distance'], flush=True)
    report['recovers_order_in_both_strains'] = all(
        report['models']['baseline']['distance'][strain] < report['models']['enigma']['distance'][strain]
        for strain in reference)
    write_json(OUT, report)


if __name__ == '__main__':
    main()
