"""Run the fixed heart controls and archived challenger on released stages."""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fm.common import FM, SPLITS, write_json
from fm.evaluation import score_snapshot, snapshot

ROOT = FM.parents[1]
PREDICTION_SEEDS = (0, 1)
SCORING_SEEDS = (201, 202, 203)
SPLIT_NAMES = ('val_heart', 'ho_long', 'ho_heart')
METHODS = ('copy_last', 'crop', 'crop_scale', 'historical_focused')


def stage_control(mode, target):
    snapshot(FM / 'kit', target)
    write_json(target / 'tuned_params.json', {'control': mode})


def stage_method(name, target):
    if name == 'historical_focused':
        snapshot(ROOT / 'models/historical/heart', target)
    else:
        stage_control(name, target)


def comparison(splits, reference):
    result = {}
    for name in SPLIT_NAMES:
        trial, control = splits[name], reference[name]
        if 'score' in trial and 'score' in control:
            result[name] = {
                'headline': trial['score'] - control['score'],
                'prediction_seed_deltas': [
                    a - b for a, b in zip(trial['pred_seed_scores'], control['pred_seed_scores'], strict=True)
                ],
                'metric_deltas': {key: value - control['metrics'][key] for key, value in trial['metrics'].items()},
            }
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=ROOT / 'results/runs' /
                        f"heart-controls-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}")
    args = parser.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    print(f'Results directory {out}', flush=True)
    rows = {}
    for name in METHODS:
        program = out / 'programs' / name
        stage_method(name, program)
        result = score_snapshot(program, SPLIT_NAMES, PREDICTION_SEEDS, SCORING_SEEDS, out / 'work' / name)
        write_json(out / f'{name}.json', result)
        rows[name] = result
        print(json.dumps({name: {key: val.get('score', val.get('error')) for key, val in result.items()}}), flush=True)

    write_json(out / 'summary.json', {
        'research_only': True,
        'biological_holdout': False,
        'prediction_seeds': PREDICTION_SEEDS,
        'scoring_seeds': SCORING_SEEDS,
        'splits': {name: SPLITS[name] for name in SPLIT_NAMES},
        'methods': rows,
        'paired_delta_vs_copy_last': {name: comparison(row, rows['copy_last']) for name, row in rows.items()},
    })
    return int(any('score' not in values for row in rows.values() for values in row.values()))


if __name__ == '__main__':
    sys.exit(main())
