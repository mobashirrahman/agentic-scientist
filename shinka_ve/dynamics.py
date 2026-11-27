"""Learned developmental dynamics passed to programs as context['dynamics'] (harness side; programs never train it).

A small neural velocity field v(z, t) in a PCA space of the board's genes, trained by conditional flow matching with
minibatch optimal-transport pairing between consecutive time points. Training data = the split's OWN input stages
(never its target) + the board's vetted external data (already stage-filtered by harness.load_anchor / load_external).
So the field has more than two time points to learn from (T1: Qiu ~E8.25/E8.75 and E15-E17; embryo: atlas E6.5-E9.5;
heart: Feulner E14.5-E18.5), while nothing from a held-out stage or the split's target enters it.

Platform calibration per external source:
  'offset'   a released input stage lies within 0.75 day of a source stage: per-gene mean offset estimated there and
             applied to the whole source (same platform throughout).
  'zscore'   no nearby shared stage (heart: Feulner starts at E14.5): genes are standardised within the source and
             mapped onto our pooled input scale. Cross-source level changes are then only partly real; say so.
The object is cached per (board, inputs, external data, code version) under data/external/dynamics/.

Program-facing API (numpy in, numpy out):
  d.genes, d.times, d.sources (list of dicts: name, times, cells, calibration)
  d.encode(X)                 X: cells x len(d.genes) log-expression (columns in d.genes order) -> Z (cells x k)
  d.push(Z, t0, t1, steps=32) integrate the field from time t0 to t1 (days) -> Z at t1
  d.velocity(Z, t)            field at time t (latent units per day)
  d.decode_delta(dZ)          latent displacement -> per-gene log-expression change (cells x len(d.genes))
  d.report()                  one-paragraph description of what it was trained on
"""
import hashlib
import json
import tempfile
from pathlib import Path

import numpy as np
from scipy import sparse
from scipy.optimize import linear_sum_assignment

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / 'data/external/dynamics'
CODE_VERSION = 'dyn-v2'
K, HVG, CAP, STEPS, BATCH, HIDDEN = 30, 2000, 3000, 3000, 256, 256
THEILER_DAYS = {'Theiler stage 12': 8.25, 'Theiler stage 13': 8.75, 'Theiler stage 23': 15.0,
                'Theiler stage 24': 16.0, 'Theiler stage 25': 17.0}


def _dense(x):
    return np.asarray(x.toarray() if sparse.issparse(x) else x, dtype=np.float32)


def _ext_groups(board, ext):
    """[(source_name, days array, X dense on ext.var_names)] from the board's vetted external AnnData."""
    if ext is None or not hasattr(ext, 'obs'):
        return []
    if 'stage_days' in ext.obs:
        days = np.asarray(ext.obs['stage_days'], float)
    elif 'development_stage' in ext.obs:
        days = ext.obs['development_stage'].astype(str).map(THEILER_DAYS).to_numpy(float)
    else:
        return []
    src = (ext.obs['anchor_source'].astype(str).to_numpy() if 'anchor_source' in ext.obs
           else np.full(ext.n_obs, {'temporal': 'qiu2024'}.get(board, board + '_external')))
    ok = np.isfinite(days)
    return [(s, days[ok & (src == s)], ext[ok & (src == s)]) for s in np.unique(src[ok])]


class Dynamics:
    def __init__(self, state, meta):
        import torch
        self.meta = meta
        self.genes, self.times, self.sources = meta['genes'], meta['times'], meta['sources']
        self._mean = np.asarray(meta['mean'], np.float32)
        self._comp = np.asarray(meta['components'], np.float32)
        self._t0, self._tspan = meta['t0'], meta['tspan']
        self.net = _net(len(self._comp), meta['hidden'])
        self.net.load_state_dict(state)
        self.net.eval()
        self._torch = torch

    def encode(self, X):
        return (_dense(X) - self._mean) @ self._comp.T

    def velocity(self, Z, t):
        with self._torch.no_grad():
            z = self._torch.as_tensor(np.asarray(Z, np.float32))
            tt = self._torch.full((len(z), 1), (t - self._t0) / self._tspan)
            return self.net(self._torch.cat([z, tt], 1)).numpy()

    def push(self, Z, t0, t1, steps=32):
        Z = np.asarray(Z, np.float32).copy()
        h = (t1 - t0) / steps
        for i in range(steps):
            Z += h * self.velocity(Z, t0 + i * h)
        return Z

    def decode_delta(self, dZ):
        return np.asarray(dZ, np.float32) @ self._comp

    def report(self):
        s = '; '.join(f"{x['name']} {x['times']} ({x['cells']} cells, {x['calibration']})" for x in self.sources)
        return (f"Flow-matching velocity field, {len(self._comp)} PCs over {len(self.genes)} genes, trained on time points "
                f"{self.times} days, transitions within each source only ({'; '.join(self.meta.get('transitions', []))}). Sources: {s}. Final training loss {self.meta['loss']:.4f}.")


def _net(k, hidden):
    import torch.nn as nn
    return nn.Sequential(nn.Linear(k + 1, hidden), nn.SiLU(), nn.Linear(hidden, hidden), nn.SiLU(),
                         nn.Linear(hidden, k))


def _key(board, inputs, times, ext):
    h = hashlib.sha1(f'{CODE_VERSION}|{board}|{list(times)}'.encode())
    for a in inputs:
        h.update(f'{a.shape}|{a.obs_names[0]}|{a.obs_names[-1]}|{a.var_names[0]}'.encode())
    if ext is not None and hasattr(ext, 'shape'):
        h.update(f'{ext.shape}|{ext.obs_names[0]}|{ext.obs_names[-1]}'.encode())
    return h.hexdigest()[:20]


def dynamics_for(board, inputs, times, ext, seed=0):
    """Train (or load cached) dynamics for a split. Returns None when torch or external data is unavailable."""
    if board not in ('temporal', 'heart', 'embryo') or ext is None:
        return None
    try:
        import torch
    except ImportError:
        return None
    key = _key(board, inputs, times, ext)
    path = CACHE / f'{board}_{key}.pt'
    if path.exists():
        blob = torch.load(path, weights_only=False)
        return Dynamics(blob['state'], blob['meta'])
    rng = np.random.default_rng(seed)
    torch.manual_seed(seed)
    genes = [g for g in inputs[-1].var_names if all(g in set(a.var_names) for a in inputs)]
    if len(genes) > HVG:  # T1 whole transcriptome: the most variable genes of the inputs (computed sparse)
        X = sparse.vstack([sparse.csr_matrix(a[:, genes].X) for a in inputs]).tocsc()
        m = np.asarray(X.mean(0)).ravel()
        v = np.asarray(X.multiply(X).mean(0)).ravel() - m ** 2
        genes = [genes[i] for i in np.argsort(-v)[:HVG]]
    ours = [(t, _dense(a[:, genes].X)) for a, t in zip(inputs, times)]
    pooled = np.vstack([x for _, x in ours])
    mu, sd = pooled.mean(0), pooled.std(0) + 1e-6
    sources, groups = [], [('released', t, x) for t, x in ours]
    for name, days, a in _ext_groups(board, ext):
        have = set(a.var_names)
        X = np.zeros((a.n_obs, len(genes)), np.float32)
        cols = [i for i, g in enumerate(genes) if g in have]
        X[:, cols] = _dense(a[:, [genes[i] for i in cols]].X)
        near = [(abs(d - t), d, t, x) for d in np.unique(days) for t, x in ours if abs(d - t) <= .75]
        if near:
            _, d, t, x = min(near, key=lambda r: r[0])
            X = np.maximum(X + (x.mean(0) - X[days == d].mean(0)), 0)
            cal = f'offset at E{d:g} vs released E{t:g}'
        else:
            X = (X - X.mean(0)) / (X.std(0) + 1e-6) * sd + mu
            cal = 'zscore (no shared stage; cross-source level changes only partly real)'
        for d in np.unique(days):
            groups.append((name, float(d), X[days == d]))
        sources.append(dict(name=name, times=sorted(float(d) for d in np.unique(days)), cells=int(a.n_obs), calibration=cal))
    sources.insert(0, dict(name='released inputs', times=[float(t) for t in times], cells=int(len(pooled)), calibration='reference'))
    # PCA on our released inputs only
    U, S, Vt = np.linalg.svd(pooled[rng.choice(len(pooled), min(len(pooled), 8000), replace=False)] - mu, full_matrices=False)
    comp = Vt[:K].astype(np.float32)
    # Transitions only WITHIN a source (consecutive stages of one platform), so a platform difference between
    # sources can never be learned as developmental velocity. Sources then contribute different time ranges.
    Zt, pairs = {}, []
    for name in dict.fromkeys(g[0] for g in groups):
        st = sorted((float(t), x) for n, t, x in groups if n == name)
        for t, x in st:
            idx = rng.choice(len(x), min(len(x), CAP), replace=False)
            Zt[(name, t)] = ((x[idx] - mu) @ comp.T).astype(np.float32)
        pairs += [((name, a), (name, b)) for (a, _), (b, _) in zip(st[:-1], st[1:])]
    ts = sorted({k[1] for k in Zt})
    t0, tspan = ts[0], max(ts[-1] - ts[0], 1e-6)
    net = _net(K, HIDDEN)
    opt = torch.optim.Adam(net.parameters(), lr=1e-3)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, STEPS)
    loss_ema = None
    for step in range(STEPS):
        ka, kb = pairs[step % len(pairs)]
        a, b = ka[1], kb[1]
        x0 = Zt[ka][rng.choice(len(Zt[ka]), BATCH)]
        x1 = Zt[kb][rng.choice(len(Zt[kb]), BATCH)]
        r, c = linear_sum_assignment(((x0[:, None] - x1[None]) ** 2).sum(-1))  # minibatch OT pairing
        x0, x1 = x0[r], x1[c]
        s = rng.random((BATCH, 1)).astype(np.float32)
        xt = (1 - s) * x0 + s * x1
        tt = (a + s * (b - a) - t0) / tspan
        target = (x1 - x0) / (b - a)
        pred = net(torch.as_tensor(np.hstack([xt, tt]).astype(np.float32)))
        loss = ((pred - torch.as_tensor(target)) ** 2).mean()
        opt.zero_grad()
        loss.backward()
        opt.step()
        sched.step()
        loss_ema = float(loss) if loss_ema is None else .98 * loss_ema + .02 * float(loss)
    meta = dict(transitions=[f'{a[0]}: E{a[1]:g}->E{b[1]:g}' for a, b in pairs], genes=genes, times=ts, sources=sources, mean=mu.tolist(), components=comp.tolist(), t0=t0, tspan=tspan,
                hidden=HIDDEN, loss=loss_ema, code=CODE_VERSION, key=key)
    CACHE.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=CACHE, delete=False, suffix='.tmp') as f:
        torch.save(dict(state=net.state_dict(), meta=meta), f.name)
    Path(f.name).replace(path)  # atomic: parallel evaluations never read a half-written file
    (CACHE / f'{board}_{key}.json').write_text(json.dumps({k: v for k, v in meta.items() if k not in ('mean', 'components')}, indent=1))
    return Dynamics(net.state_dict(), meta)
