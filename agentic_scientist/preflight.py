"""Read-only manifest of the evaluator, its environment, and required dev inputs."""
import argparse
import json
import os
import sys
from importlib.metadata import version
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from agentic_scientist.artifacts import file_sha  # noqa: E402

EVALUATOR_PACKAGES = ('anndata', 'numpy', 'pandas', 'scipy', 'scikit-learn', 'veckit', 'vec-community-kit')


def versions(packages=EVALUATOR_PACKAGES):
    return {'python': '.'.join(map(str, sys.version_info[:3])), **{p: version(p) for p in packages}}


def dev_inputs():
    from agentic_scientist.evaluate import SETS, harness

    splits = SETS['dev']['splits'] + SETS['sanity']['splits']
    return sorted({os.path.normpath('data/raw/' + p)
                   for name in splits for p in harness.SPLITS[name]['inputs'] + [harness.SPLITS[name]['target']]})


def fingerprint():
    files = [*sorted((ROOT / 'src').rglob('*.py'))]
    files += [ROOT / x for x in ('agentic_scientist/artifacts.py', 'agentic_scientist/evaluate.py',
                              'agentic_scientist/data/t1_celltype_map.json', 'shinka_ve/harness.py', 'shinka_ve/dynamics.py')]
    # The pin alone does not catch working-tree patches to the scorer.
    for vendor in ('veckit', 'vec-community-kit'):
        files.extend(sorted((ROOT / 'vendor' / vendor).rglob('*.py')))
    inputs = dev_inputs()
    for name in inputs:
        if not (ROOT / name).is_file():
            raise FileNotFoundError(name)
    return {'versions': versions(), 'code': {p.relative_to(ROOT).as_posix(): file_sha(p) for p in files},
            'inputs': {p: file_sha(ROOT / p) for p in inputs}}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--inputs', action='store_true')
    args = parser.parse_args()
    print('\n'.join(dev_inputs()) if args.inputs else json.dumps(fingerprint(), sort_keys=True))


if __name__ == '__main__':
    main()
