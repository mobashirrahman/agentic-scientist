"""'Do no harm' cross-gene test for a workspace's T3 knockout model (no held-out data used).

Asks the program to knock out genes that are barely expressed in the wild type. Removing a gene that is not doing
anything should change almost nothing, so the honest prediction is close to wt_identity. A program that applies a
Gata4-style template to any gene fails. Reports, for each null gene, the predicted response size relative to the
program's response to Gata4 (ratio near 0 = gene-aware; near 1 = one template for every knockout).

  .venv/bin/python agentic_scientist/checks/noharm.py <workspace> [--genes 4] [--json out.json]
"""
import argparse
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np

from mgcheck import dense, harness, stages
from agentic_scientist.evaluate import load_params
from heavy_slot import acquire


def load(ws):
    sys.path.insert(0, str(ws))
    spec = importlib.util.spec_from_file_location('mg_prog', Path(ws) / 'program.py')
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m


def response(mod, inputs, spec, gene, seed, params):
    if harness.MASK_KNOCKOUT:
        inputs = [a[:, a.var_names != gene].copy() for a in inputs]
    external = harness.external_context('perturbation', list(inputs[-1].var_names), inputs, spec['times'])
    ctx = dict(seed=seed, fit_seed=0, n=3000, knockout=gene, params=params, **external)
    pred = mod.predict('perturbation', [a.copy() for a in inputs], list(spec['times']), spec['time'], ctx)
    ref = inputs[-1]
    p = dense(pred[:, list(ref.var_names)].X).mean(0)
    r = dense(ref.X).mean(0)
    comp = None
    if 'celltype' in pred.obs and 'celltype' in ref.obs:
        a = pred.obs['celltype'].astype(str).value_counts(normalize=True)
        b = ref.obs['celltype'].astype(str).value_counts(normalize=True)
        comp = float(0.5 * (a.reindex(a.index.union(b.index), fill_value=0) - b.reindex(a.index.union(b.index), fill_value=0)).abs().sum())
    return float(np.linalg.norm(p - r)), comp, float(p @ r / (r @ r))


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('workspace'); ap.add_argument('--genes', type=int, default=4); ap.add_argument('--json')
    a = ap.parse_args()
    acquire('T3 no-harm check')
    spec, inputs, ref, _tgt = stages('gata4_1')
    X = dense(ref.X); det = (X > 0).mean(0)
    names = np.asarray(ref.var_names)
    cand = [i for i in np.argsort(det) if 0 < det[i] < 0.005 and names[i] != 'Gata4']
    nulls = [names[i] for i in cand[:: max(1, len(cand) // a.genes)][: a.genes]]
    mod = load(Path(a.workspace).resolve())
    params = load_params(a.workspace).get('perturbation', {})
    g = [response(mod, inputs, spec, 'Gata4', s, params) for s in (101, 202)]
    base = np.mean([x[0] for x in g])
    rows = {}
    for gene in nulls:
        d, c, sc = response(mod, inputs, spec, gene, 101, params)
        rows[gene] = dict(detection=float(det[list(names).index(gene)]), response=round(d, 4), comp_shift=c, global_scale=round(sc, 3),
                          ratio_to_gata4=round(d / max(base, 1e-9), 3))
    ratio = float(np.median([r['ratio_to_gata4'] for r in rows.values()]))
    null = float(np.median([r['response'] for r in rows.values()]))
    # Real knockout samples can differ from wild type in gene-independent ways (batch, staging), so a shared component is not
    # automatically wrong. What this test isolates is how much of the predicted response depends on WHICH gene was removed.
    out = dict(workspace=a.workspace, gata4_global_scale=round(g[0][2], 3), true_gata4_ko_global_scale=0.825,
               gata4_response=round(base, 4), null_gene_response=round(null, 4),
               gene_specific=round(base - null, 4), wt_resample_noise=0.5, gata4_comp_shift=g[0][1], null_genes=rows,
               median_ratio=round(ratio, 3),
               verdict=('gene-aware' if ratio < 0.5 else 'partly gene-aware' if ratio < 0.85 else
                        'gene-blind: the same response for every knocked-out gene (a template, cannot transfer gene-specific effects)'))
    print(json.dumps(out, indent=1))
    if a.json:
        Path(a.json).write_text(json.dumps(out, indent=1))


if __name__ == '__main__':
    main()
