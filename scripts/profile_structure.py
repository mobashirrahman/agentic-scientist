"""Structural profile of each raw .h5ad file, opened backed (read-only, X not loaded).

Run with: .venv/bin/python -I scripts/profile_structure.py [paths...]
"""
import glob
import os
import sys

import anndata as ad
import h5py
import numpy as np
import pandas as pd

ROOT = "/scratch/user/virtual-embryo/data/raw"


def describe_series(s):
    if isinstance(s.dtype, pd.CategoricalDtype):
        return f"categorical[{len(s.cat.categories)} cats]"
    return str(s.dtype)


def describe_x(a):
    X = a.X
    if X is None:
        return "X=None"
    if isinstance(X, h5py.Dataset):
        return f"dense h5py.Dataset dtype={X.dtype} shape={X.shape}"
    # backed sparse group
    return f"{type(X).__name__} (backed)"


def show_h5_tree(path):
    """Print the raw HDF5 layout top levels to catch anything anndata hides."""
    with h5py.File(path, "r") as f:
        print("  HDF5 top-level keys:", list(f.keys()))
        if "X" in f:
            x = f["X"]
            if isinstance(x, h5py.Group):
                print("  X group attrs:", {k: str(v) for k, v in x.attrs.items()})
                for k in x.keys():
                    print(f"    X/{k}: shape={x[k].shape} dtype={x[k].dtype}")
            else:
                print(f"  X dataset: shape={x.shape} dtype={x.dtype}")


def profile(path):
    print("=" * 100)
    print(path)
    print(f"  size: {os.path.getsize(path)/1e6:.1f} MB")
    a = ad.read_h5ad(path, backed="r")
    print(f"  shape (obs x var): {a.shape}")
    print(f"  X: {describe_x(a)}")
    print(f"  is_view: {a.is_view}  filename: {a.filename}")
    show_h5_tree(path)

    print("  layers:", list(a.layers.keys()))
    for k in a.layers.keys():
        L = a.layers[k]
        print(f"    layers[{k}]: {type(L).__name__} shape={getattr(L,'shape',None)} dtype={getattr(L,'dtype',None)}")

    print("  obs columns:")
    for c in a.obs.columns:
        print(f"    {c}: {describe_series(a.obs[c])}")
    print("  obs index head:", list(a.obs_names[:3]), "unique:", a.obs_names.is_unique)

    print("  obsm keys:")
    for k in a.obsm.keys():
        M = a.obsm[k]
        shp = getattr(M, "shape", None)
        dt = getattr(M, "dtype", None)
        print(f"    obsm[{k}]: {type(M).__name__} shape={shp} dtype={dt}")
    print("  obsp keys:", list(a.obsp.keys()))

    print("  var columns:")
    for c in a.var.columns:
        print(f"    {c}: {describe_series(a.var[c])}")
    print("  var index head:", list(a.var_names[:3]), "unique:", a.var_names.is_unique)
    print("  varm keys:", list(a.varm.keys()), " varp keys:", list(a.varp.keys()))

    print("  uns keys:", list(a.uns.keys()))
    for k in a.uns.keys():
        v = a.uns[k]
        desc = type(v).__name__
        if isinstance(v, dict):
            desc += f" keys={list(v.keys())[:15]}"
        elif hasattr(v, "shape"):
            desc += f" shape={v.shape}"
        print(f"    uns[{k}]: {desc}")

    a.file.close()


if __name__ == "__main__":
    paths = sys.argv[1:] or sorted(glob.glob(os.path.join(ROOT, "*", "*.h5ad")))
    for p in paths:
        profile(p)
