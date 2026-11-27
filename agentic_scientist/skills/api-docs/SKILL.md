---
name: api-docs
description: Exact signatures and docstrings of the installed library versions and of our own helpers (src.v2.*). Use before calling an unfamiliar function, to avoid version-mismatch crashes.
---
# API docs

`$MG_ROOT/.venv/bin/python $MG_ROOT/agentic_scientist/tools/apidoc.py ...`
- `src.v2.transport.LatentFlow`: our helper class, its signature and methods
- `sklearn.neighbors.NearestNeighbors`: signature + docstring of the installed version
- `scipy.sparse --list`: public names in a module
- `--versions`: numpy, scipy, sklearn, anndata, scanpy, torch, pandas versions (numpy 2.x, anndata 0.13: mind API changes)
