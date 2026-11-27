"""Replay trusted workspaces on local checks and test each observed ordering."""
import argparse
import math
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from agentic_scientist.artifacts import file_sha, write_json

ORDERS = {
    'temporal': [('first', 'enigma', True)],
    'heart': [('codex', 'enigma', True), ('enigma', 'first', True)],
    'embryo': [('first', 'enigma', False), ('enigma', 'codex', True)],
    'perturbation': [('enigma', 'first', True)],
}


def calibrate_order(board, scores):
    for high, low, strict in ORDERS[board]:
        a, b = scores.get(high), scores.get(low)
        if a is None or b is None or not math.isfinite(a) or not math.isfinite(b):
            return 'missing'
        if a < b or (strict and a == b):
            return 'reversed_or_tied'
    return 'passes'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--enigma', type=Path, required=True)
    parser.add_argument('--sets', nargs='+', choices=['dev', 'guard', 'sanity', 'composition'],
                        default=['dev', 'guard', 'sanity', 'composition'])
    parser.add_argument('--splits', nargs='+')
    parser.add_argument('--first-test-t1', type=Path)
    parser.add_argument('--enigma-test-t1', type=Path)
    parser.add_argument('--use-user-unlocked-holdouts', action='store_true',
                        help='Operator only, after rekeying and opening the holdouts locally')
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    if args.use_user_unlocked_holdouts:
        os.environ['MG_PRIVATE_FINAL'] = '1'
    from agentic_scientist import evaluate
    workspaces = {'first': ROOT / 'agentic_scientist/checks/first_bundle', 'enigma': args.enigma.resolve()}
    artifacts = {'first': args.first_test_t1, 'enigma': args.enigma_test_t1}
    if any(artifacts.values()) and not all(artifacts.values()):
        parser.error('provide both scored T1 files to replay the composition veto on artifacts')
    report = {}
    sets = [*args.sets, 'holdout', 'holdout_t3'] if args.use_user_unlocked_holdouts else args.sets
    for name in sets:
        for split in evaluate.SETS[name]['splits']:
            if args.splits and split not in args.splits:
                continue
            spec = evaluate.harness.SPLITS.get(split)
            if spec is None or any(not (ROOT / 'data/raw' / path).is_file()
                                   for path in spec['inputs'] + ([spec['target']] if 'target' in spec else [])):
                report[split] = dict(set=name, ordering='missing')
                write_json(args.out, report)
                continue
            board = spec['board']
            programs = dict(workspaces)
            if board in ('heart', 'embryo'):
                programs['codex'] = ROOT / 'humantrack' / f't2_{board}'
            rows = {}
            if name == 'composition' and all(artifacts.values()):
                import anndata
                from agentic_scientist.composition import compare

                ref = evaluate.harness.load_stage(spec['inputs'][-1])
                chambers = ref.obs['celltype'].isin(set(evaluate._T1MAP['cardiac']) | {'Blood'})
                for label, artifact in artifacts.items():
                    result = compare(anndata.read_h5ad(artifact), ref, ref[chambers])
                    rows[label] = dict(composition=result, artifact_sha256=file_sha(artifact))
                report[split] = dict(board=board, set=name, rows=rows, ordering='veto_only',
                                     calibration='passes' if not rows['first']['composition']['failures']
                                     and rows['enigma']['composition']['failures'] else 'fails')
                write_json(args.out, report)
                continue
            for label, workspace in programs.items():
                result = evaluate.evaluate(workspace, name, [split], workers=1, historical=True)
                row = result.get('splits', {}).get(split, {})
                rows[label] = {key: row[key] for key in ('score', 'seed_scores', 'sanity', 'composition') if key in row}
                if not result['correct']:
                    rows[label]['error'] = result['error']
            scores = {label: row.get('score') for label, row in rows.items()}
            report[split] = dict(board=board, set=name, rows=rows,
                                 ordering=calibrate_order(board, scores) if name in ('dev', 'guard', 'holdout') else 'veto_only')
            write_json(args.out, report)


if __name__ == '__main__':
    main()
