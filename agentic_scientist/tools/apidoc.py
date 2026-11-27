"""Exact API of the installed library versions (offline; matches what the evaluator runs).

  python apidoc.py sklearn.neighbors.NearestNeighbors        signature + docstring
  python apidoc.py src.v2.transport.LatentFlow --members     our helper class: methods and their signatures
  python apidoc.py scipy.sparse --list                        public names in a module
  python apidoc.py --versions                                 key package versions
"""
import argparse
import importlib
import inspect
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def resolve(path):
    parts = path.split('.')
    for i in range(len(parts), 0, -1):
        try:
            obj = importlib.import_module('.'.join(parts[:i]))
        except ImportError:
            continue
        for p in parts[i:]:
            obj = getattr(obj, p)
        return obj
    raise SystemExit(f'cannot import {path}')


def sig(o):
    try:
        return str(inspect.signature(o))
    except (TypeError, ValueError):
        return ''


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('path', nargs='?')
    ap.add_argument('--members', action='store_true')
    ap.add_argument('--list', action='store_true')
    ap.add_argument('--versions', action='store_true')
    a = ap.parse_args()
    if a.versions:
        for m in ('numpy', 'scipy', 'sklearn', 'anndata', 'scanpy', 'torch', 'pandas', 'umap', 'matplotlib', 'ot'):
            try:
                print(m, importlib.import_module(m).__version__)
            except Exception:  # noqa: BLE001
                print(m, 'not installed')
        return
    o = resolve(a.path)
    if a.list:
        print(', '.join(n for n in dir(o) if not n.startswith('_')))
        return
    print(f'{a.path}{sig(o)}\n')
    print((inspect.getdoc(o) or '(no docstring)')[:6000])
    if a.members or inspect.isclass(o):
        print('\n## members')
        for n, m in inspect.getmembers(o):
            if not n.startswith('_') or n == '__init__':
                if callable(m):
                    print(f'- {n}{sig(m)}: {(inspect.getdoc(m) or "").splitlines()[0][:120] if inspect.getdoc(m) else ""}')


if __name__ == '__main__':
    main()
