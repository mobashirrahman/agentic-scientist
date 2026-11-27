"""ShinkaEvolve evaluator for the Virtual Embryo task. NOT evolvable.

combined_score = T1 + T3 + 0.5*heart + 0.5*embryo (local backtest proxy of the official
total; T1/heart-E10.5/embryo-E7.5/Gata4 targets are officially unlocked P2 validation stages).
"""
import argparse
import json
import os
import re
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault('OMP_NUM_THREADS', '2')
os.environ.setdefault('OPENBLAS_NUM_THREADS', '2')

from shinka.core import run_shinka_eval  # noqa: E402
from shinka_ve.harness import SPLITS, WEIGHTS, screen  # noqa: E402

SCORING_SEEDS = [int(s) for s in os.environ.get('VE_SCORING_SEEDS', '101,102').split(',')]
SPLIT_NAMES = os.environ.get('VE_SPLITS', ','.join(SPLITS)).split(',')
WORKERS = int(os.environ.get('VE_EVAL_WORKERS', '4'))
EXTRA_FORBIDDEN = [r'load_stage', r'harness', r'SPLITS', r'src\.data', r'\bROOT\b', r'sys\.modules',
                   r'globals\s*\(', r'vec_local_score', r'score_many', r'\binspect\b']
BLOCK = re.compile(r'# EVOLVE-BLOCK-START(.*?)# EVOLVE-BLOCK-END', re.S)


def outside_block(text):
    # rstrip: Shinka's patch applier drops the file's trailing newline, which is not a code change
    return BLOCK.sub('', text).rstrip()


def static_check(program_path):
    text = Path(program_path).read_text()
    m = BLOCK.search(text)
    if not m:
        return 'EVOLVE-BLOCK markers missing'
    original = (ROOT / 'shinka_ve/initial.py').read_text()
    if outside_block(text) != outside_block(original):
        return 'Code outside the EVOLVE-BLOCK must not change'
    block = m.group(1)
    err = screen(block)
    if err:
        return err
    for pattern in EXTRA_FORBIDDEN:
        if re.search(pattern, block):
            return f'Forbidden pattern in program: {pattern}'
    return None


def get_kwargs(i):
    return dict(split=SPLIT_NAMES[i], seed=101, fit_seed=0, scoring_seeds=SCORING_SEEDS)


def aggregate(results):
    per_split = {r['split']: r for r in results}
    boards = {}
    for r in results:
        boards.setdefault(r['board'], []).append(r['score'])
    board_scores = {b: float(np.mean(v)) for b, v in boards.items()}
    combined = float(sum(WEIGHTS[b] * s for b, s in board_scores.items()))
    lines = [f'{b}: {s:.2f}' for b, s in sorted(board_scores.items())]
    for name, r in per_split.items():
        worst = sorted(r['metrics'].items(), key=lambda kv: kv[1])[:3]
        lines.append(f"{name}: {r['score']:.2f}; weakest skills " +
                     ', '.join(f'{k}={v:.1f}' for k, v in worst))
    return dict(combined_score=combined,
                public=dict(board_scores=board_scores, total_proxy=combined),
                private=dict(split_scores={k: v['score'] for k, v in per_split.items()},
                             split_metrics={k: v['metrics'] for k, v in per_split.items()}),
                extra_data={}, text_feedback='\n'.join(lines))


def main(program_path, results_dir):
    os.makedirs(results_dir, exist_ok=True)
    err = static_check(program_path)
    if err:
        Path(results_dir, 'metrics.json').write_text(json.dumps(dict(
            combined_score=0.0, public={}, private={}, extra_data={}, text_feedback=err)))
        Path(results_dir, 'correct.json').write_text(json.dumps(dict(correct=False, error=err)))
        print(err)
        return
    metrics, correct, error = run_shinka_eval(
        program_path=program_path, results_dir=results_dir, experiment_fn_name='run_experiment',
        num_runs=len(SPLIT_NAMES), get_experiment_kwargs=get_kwargs, aggregate_metrics_fn=aggregate,
        run_workers=WORKERS)
    print(json.dumps(metrics.get('public', {}), indent=1), correct, error)


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--program_path', required=True)
    p.add_argument('--results_dir', required=True)
    a = p.parse_args()
    main(a.program_path, a.results_dir)
