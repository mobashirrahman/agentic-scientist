"""Create the focused lanes' relative links from authorized stages staged under data/raw."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LANES = {
    'heart': ('T2', ('E8.25_late', 'E8.75', 'E9.5'), ('E8.5', 'E10.5'), 'T2__heart'),
    'embryo': ('T2', ('E6.75', 'E8.0'), ('E7.25', 'E7.5'), 'T2__embryo'),
    'temporal': ('T1', ('E8.5_RNA', 'E9.5_RNA'),
                 ('E10.5_RNA', 'guard_E14.5', 'guard_E16.5', 'guard_E18.5'), 'T1__'),
}


def link(source, destination):
    if destination.exists() and not destination.is_symlink():
        return
    if not source.is_file():
        raise FileNotFoundError(source)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.is_symlink():
        if destination.resolve() != source.resolve():
            raise ValueError(f'Unexpected link: {destination}')
        return
    destination.symlink_to(os.path.relpath(source, destination.parent))


def main():
    for name, (task, train, protected, pattern) in LANES.items():
        destination = ROOT / 'focused' / name / 'data'
        for role, stages in (('train', train), ('protected', protected)):
            for stage in stages:
                filename = f'{stage}.h5ad'
                link(ROOT / 'data/raw' / task / filename, destination / role / filename)
        for panel in (ROOT / 'data/panels').glob(f'{pattern}*.genes.txt'):
            link(panel, destination / 'panels' / panel.name)
    print('Focused dataset and gene panel links are ready.')


if __name__ == '__main__':
    main()
