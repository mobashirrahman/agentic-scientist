"""Validate a fleet mirror using stages already staged in the user's remote account."""
import json
import sys
from importlib.metadata import version
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fm.common import FM, STAGES, panel_genes, sha256
from fm.landlock import abi

SCORER_PACKAGES = ('anndata', 'numpy', 'pandas', 'scipy', 'scikit-learn', 'veckit', 'vec-community-kit')


def runtime():
    return {'python': '.'.join(map(str, sys.version_info[:3])),
            **{package: version(package) for package in SCORER_PACKAGES}}


def link_existing(source, destination):
    if not source.is_file():
        raise FileNotFoundError(source)
    destination.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    if not destination.is_symlink() and not destination.exists():
        destination.symlink_to(source)


def main():
    if abi() < 4:
        raise SystemExit('Worker requires Landlock ABI 4 or later')
    root = FM.parents[1]
    released_mirror = root.with_name('focused_morphogen_t2_heart') / 'data'
    for stage in STAGES.values():
        path = stage['file']
        link_existing(released_mirror / path.parent.name / path.name, path)
        if sha256(path) != stage['sha256']:
            raise ValueError(f'Worker stage checksum mismatch for {path.name}')
    panels = root / 'data' / 'panels'
    lane_panels = FM / 'data' / 'panels'
    if not lane_panels.exists() and not lane_panels.is_symlink():
        lane_panels.symlink_to(panels, target_is_directory=True)
    if len(panel_genes()) != 500:
        raise ValueError('Expected the 500-gene heart panel')
    fingerprint = {
        'runtime': runtime(),
        'panel': sha256(lane_panels / 'T2__heart__test_extrap.genes.txt'),
        'code': {p.name: sha256(p) for p in sorted((FM / 'fm').glob('*.py'))},
    }
    print(json.dumps(fingerprint, sort_keys=True))


if __name__ == '__main__':
    main()
