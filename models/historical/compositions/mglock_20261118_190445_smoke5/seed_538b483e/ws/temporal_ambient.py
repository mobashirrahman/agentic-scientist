"""Input-calibrated ambient-globin observation layer for the temporal (T1) board.

Rationale
---------
Droplet scRNA-seq of solid tissue carries cell-free ambient mRNA from lysed
cells, and haemoglobin transcripts are the canonical ambient marker (SoupX uses
the Hb genes as the "not expressed" set; the contamination is 2-50 % and its
profile is the input suspension's, i.e. it is measurable in the passed inputs).
In the released T1 series the E10.5 target shows exactly this: every non-Blood
annotation carries Hbb-y 1.0-3.0 while the other erythroid genes stay at
baseline (Alas2 0.04, Gypa 0.03, Slc4a1 0.01, Cpox 0.19).  So the leaked signal
is the high-abundance globin transcripts of lysed primitive erythroblasts, not
a general erythroid programme, and it cannot be produced by composition: even
the true Blood share reproduces only part of the pseudobulk globin level.

The E9.5 input carries the same soup at low level (non-Blood Hbb-y 0.32), which
is a direct, input-only measurement of soup per unit of erythroid content.  The
layer therefore adds

    delta_g = clip(soup_g * (clip(q_plan / f, 1, 8) - 1), 0, 2.5)

to every predicted cell, where ``soup_g`` is the latest input's non-erythroid
mean of gene g and ``q_plan / f`` is the ratio of the already-shipped erythroid
mass plan's expected share (after enrichment) to the eligible share before it,
i.e. the model's own planned fold-increase of erythroid content.  A longer
horizon or a larger planned blood load raises the soup automatically; there is
no free tuned constant, no target data, no extra RNG.

Gene set: derived from the passed inputs' own blood-vs-non-blood contrast, not
a hardcoded panel -- keep genes whose marker-corroborated erythroid mean is at
least 3.5 log1p CP10k (the four embryonic/adult globins at E9.5: 5.63 / 4.83 /
4.53 / 4.23), whose non-erythroid mean is at least 0.05 (0.32 / 0.26 / 0.15 /
0.07), and which are at least 10x enriched in erythroid cells over the rest
(17-58x for the globins).  The blood-mean test alone also admits ubiquitous
high-abundance transcripts (Malat1, Fth1, the mitochondrial genes), which are
not the ambient leak, so the enrichment guard is what keeps the edit
globin-specific; it excludes Alas2 (1.99), Gypa (2.13), Slc4a1 (2.58), Cpox
(2.39) and the next non-globin candidate Tmem14c (4.4x).
Composition, geometry, the donor law, the
anchor calibration, the sparse realisation and every non-globin gene are
untouched; the operation is a post-hoc observation-layer edit on the final
normalised matrix and cannot change which cells were drawn.

The biology is stage-generic: primitive erythroblasts enter the circulation at
E8.25-E9.0 and accumulate haemoglobin as a semi-synchronous cohort that
enucleates from E12.5, so both blood content and globin release rise toward the
E12.5 test horizon.  Scaling by the model's own planned erythroid mass means a
longer horizon raises the soup instead of freezing it at the dev level.

Guards (all soft): no-op unless the erythroid prior is enabled with a finite
planned mass, the input has >= 2 marker genes and 30 eligible erythroid donors
with 0 < share < 0.5, the planned fold-increase is >= 1.5, at least two globin
genes pass the contrast, and horizon / interval >= 0.5.
"""
import numpy as np
from scipy import sparse

from temporal_temporal_sampling import ERY_MARKERS, erythroid_eligibility

MIN_BLOOD_MEAN = 3.5      # log1p CP10k: the gene must be strongly erythroid
MIN_SOUP = 0.05           # log1p CP10k: and measurably present outside it
MIN_ENRICH = 10.0         # blood/non-blood fold enrichment: specificity guard
MIN_SCALE = 1.5           # below this planned fold-increase the layer abstains
MAX_SCALE = 8.0           # same 8x ceiling as the donor odds cap
MAX_DELTA = 2.5           # log1p CP10k cap on any single gene's ambient add
MAX_VALUE = 9.0           # log1p(1e4) is 9.21: keep the scale physical
MIN_HORIZON_FRACTION = 0.5
MIN_ERY = 30
MAX_ERY_FRACTION = 0.5


def _info():
    """Flat, h5ad-safe no-op diagnostics (nested dicts cannot be stored)."""
    return dict(applied=0.0, n_genes=0.0, scale=1.0, q_plan=0.0, f=0.0,
                horizon=0.0, interval=0.0, ery_fraction=0.0, n_ery=0.0,
                n_candidates=0.0, genes=np.array([], dtype=str),
                deltas=np.array([], dtype=np.float64),
                soup=np.array([], dtype=np.float64),
                blood_mean=np.array([], dtype=np.float64),
                mean_before=0.0, mean_after=0.0)


def _column_means(a, mask):
    """Per-gene mean log-expression over ``mask`` (sparse- or dense-safe)."""
    n = float(mask.sum())
    if n <= 0:
        return np.zeros(a.n_vars, dtype=np.float64)
    x = a.X
    if sparse.issparse(x):
        s = np.asarray(x[mask].sum(axis=0), dtype=np.float64).ravel()
    else:
        s = np.asarray(x, dtype=np.float64)[mask].sum(axis=0)
    return s / n


def plan_ambient(latest, prior, horizon, interval):
    """Closed-form ambient-globin deltas from the input and the erythroid plan.

    ``prior`` is the flat erythroid-prior dict of ``temporal.py``: ``f`` is the
    eligible donor mass under the parent law and ``q`` the planned mass after
    the enrichment, so ``q/f`` is the planned fold-increase of erythroid
    content.  Everything else comes from the latest input alone.
    """
    info = _info()
    try:
        horizon = float(horizon)
        interval = float(interval)
    except (TypeError, ValueError):
        return info
    info['horizon'] = horizon if np.isfinite(horizon) else 0.0
    info['interval'] = interval if np.isfinite(interval) else 0.0
    if not prior or not float(prior.get('enabled', 0.0)):
        return info
    q = float(prior.get('q', 0.0))
    f = float(prior.get('f', 0.0))
    info['q_plan'] = q if np.isfinite(q) else 0.0
    info['f'] = f if np.isfinite(f) else 0.0
    if not (np.isfinite(q) and np.isfinite(f)) or q <= 0.0 or f <= 0.0:
        return info
    if not (np.isfinite(horizon) and np.isfinite(interval)) or interval <= 0.0:
        return info
    if horizon / interval < MIN_HORIZON_FRACTION:
        return info
    scale = float(np.clip(q / f, 1.0, MAX_SCALE))
    info['scale'] = scale
    if scale < MIN_SCALE:
        return info

    shared = [g for g in ERY_MARKERS
              if g in latest.var_names]
    if len(shared) < 2:
        return info
    ery = erythroid_eligibility(latest, shared)
    n_ery = int(ery.sum())
    ery_frac = float(ery.mean())
    info['n_ery'] = float(n_ery)
    info['ery_fraction'] = ery_frac
    if n_ery < MIN_ERY or not (0.0 < ery_frac < MAX_ERY_FRACTION):
        return info

    blood_mean = _column_means(latest, ery)
    soup = _column_means(latest, ~ery)
    # Specificity guard: a blood-mean-only test also catches ubiquitous
    # high-abundance transcripts (Malat1, Fth1, the mitochondrial genes, and
    # Tmem14c all passed it at E9.5), which the biology says are NOT the
    # ambient leak.  The globins are 17-58x enriched in erythroid cells there
    # while the next candidate (Tmem14c) is only 4.4x, so a >= 10x
    # blood/non-blood enrichment selects exactly the four globins and keeps the
    # edit globin-specific as the mechanism requires.
    sel = ((blood_mean >= MIN_BLOOD_MEAN) & (soup >= MIN_SOUP) &
           (blood_mean >= MIN_ENRICH * soup))
    info['n_candidates'] = float(sel.sum())
    if int(sel.sum()) < 2:
        return info

    names = np.asarray(latest.var_names).astype(str)
    deltas = np.clip(soup[sel] * (scale - 1.0), 0.0, MAX_DELTA)
    keep = deltas > 0.0
    if int(keep.sum()) < 2:
        return info
    info['applied'] = 1.0
    info['n_genes'] = float(keep.sum())
    info['genes'] = names[sel][keep]
    info['deltas'] = deltas[keep].astype(np.float64)
    info['soup'] = soup[sel][keep].astype(np.float64)
    info['blood_mean'] = blood_mean[sel][keep].astype(np.float64)
    return info


def apply_ambient(out, amb):
    """Add the ambient-globin deltas to every predicted cell (in place).

    Constant per-gene offsets leave every cell-to-cell difference inside a
    globin column unchanged, so only the gene's level and its co-variation
    with the other genes move.  The edit is applied to the final normalised
    matrix, after the sparse realisation, so no donor draw or anchor step sees
    it.  Values are clipped per column and the dtype of ``out.X`` is kept.
    """
    if not amb or not float(amb.get('applied', 0.0)):
        amb = dict(amb or {})
        amb['mean_before'] = 0.0
        amb['mean_after'] = 0.0
        out.uns['erythroid_ambient'] = amb
        return out
    pos = {g: i for i, g in enumerate(np.asarray(out.var_names).astype(str))}
    pairs = [(pos[str(g)], float(d)) for g, d in zip(amb['genes'], amb['deltas'])
             if str(g) in pos]
    if not pairs:
        amb = dict(amb)
        amb['applied'] = 0.0
        amb['mean_before'] = 0.0
        amb['mean_after'] = 0.0
        out.uns['erythroid_ambient'] = amb
        return out

    x = out.X
    n = out.n_obs
    if sparse.issparse(x):
        dtype = x.dtype if x.dtype is not None else np.float32
        csr = sparse.csr_matrix(x, dtype=np.float64)
    else:
        dtype = np.asarray(x).dtype
        csr = None
        dense = np.asarray(x, dtype=np.float64)
    rows, cols, data = [], [], []
    before, after = [], []
    for j, d in pairs:
        if csr is not None:
            col = np.asarray(csr[:, j].todense(), dtype=np.float64).ravel()
        else:
            col = dense[:, j]
        new = np.clip(col + d, 0.0, MAX_VALUE)
        diff = new - col
        before.append(float(col.mean()))
        after.append(float(new.mean()))
        rows.append(np.arange(n, dtype=np.int64))
        cols.append(np.full(n, j, dtype=np.int64))
        data.append(diff)
    before_mean = float(np.mean(before))
    after_mean = float(np.mean(after))
    if csr is not None:
        delta = sparse.csr_matrix(
            (np.concatenate(data), (np.concatenate(rows), np.concatenate(cols))),
            shape=csr.shape)
        out.X = sparse.csr_matrix(csr + delta).astype(dtype)
    else:
        out_x = dense
        for j, d in pairs:
            out_x[:, j] = np.clip(out_x[:, j] + d, 0.0, MAX_VALUE)
        out.X = out_x.astype(dtype)
    amb = dict(amb)
    amb['mean_before'] = before_mean
    amb['mean_after'] = after_mean
    out.uns['erythroid_ambient'] = amb
    return out
