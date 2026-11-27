"""Future-anchor expression drift from external, rule-compliant late-stage data.

External source: Qiu et al. 2024 (CELLxGENE Census), Theiler stage 23 (~E15) as
the late anchor and TS12-13 (~E8-E9) for platform calibration. Nothing from the
excluded window (after E9.5 up to and including E13.5) is ever loaded.

Mechanism, per released cell type t and gene g (log1p CP10k space):
  offset_g      = mean_ours_early(g) - mean_qiu_calibration(g)   (pooled over matched types)
  anchor_t,g    = mean_qiu_anchor(t,g) + offset_g
  drift_t,g     = anchor_t,g - mean_ours_latest(t,g)
  shift at time = weight * fraction * drift, fraction = (T - t_latest)/(t_anchor - t_latest)
Types with too few matched anchor cells receive no shift. Shifts are bounded.
"""
import anndata as ad
import numpy as np
from scipy import sparse

from src.v2.transport import LatentFlow, lineages, as_dense

CM = {'OFT/RV-CM', 'OFT-CM', 'V-CM', 'SV-CM', 'IFT-CM', 'AVC-CM', 'A-CM'}
# Census cell_type -> released types it may be matched to. Unlisted Census types
# are dropped. Restricting by broad class prevents e.g. fibroblasts becoming CMs.
COMPATIBLE = {
    'cardiac muscle cell': CM,
    'splanchnic mesodermal cell': CM | {'pSHF', 'aSHF', 'pPHM', 'aPHM', 'Pericardium', 'Proepicardium', 'ST', 'Epicardial'},
    'endocardial cell': {'Endocardium'},
    'endothelial cell': {'Endocardium', 'BEC'},
    'vein endothelial cell': {'BEC', 'Endocardium'},
    'endothelial cell of artery': {'BEC'},
    'embryonic blood vessel endothelial progenitor cell': {'BEC', 'Endocardium'},
    'hepatocyte': {'Hepatocyte'},
    'lateral mesodermal cell': {'pSHF', 'aSHF', 'pPHM', 'aPHM', 'ST', 'Proepicardium', 'Pericardium', 'Epicardial', 'NCC-derived'},
    'mesodermal cell': {'pPHM', 'aPHM', 'NCC-derived', 'ST', 'pSHF', 'aSHF'},
    'fibroblast': {'NCC-derived', 'ST', 'Proepicardium', 'Epicardial', 'Pericardium'},
    'epithelial cell': {'Foregut', 'Epithelium', 'Surface Ectoderm'},
    'primitive erythrocyte': {'Blood'},
    'erythrocyte': {'Blood'},
}


def lognorm(counts, genes):
    x = sparse.csr_matrix(counts, dtype=np.float32)
    lib = np.asarray(x.sum(1)).ravel()
    x = sparse.diags(1e4 / np.maximum(lib, 1)) @ x
    x.data = np.log1p(x.data)
    return x.tocsr()


def load_external(paths, genes):
    """Concatenate Census pieces on the released gene order, log-normalized on shared genes."""
    parts = []
    for p in paths:
        a = ad.read_h5ad(p)
        allowed = {'Theiler stage 12', 'Theiler stage 13', 'Theiler stage 23', 'Theiler stage 24', 'Theiler stage 25'}
        assert set(a.obs.development_stage.astype(str)) <= allowed, f'forbidden stage in {p}'
        have = set(a.var_names)
        shared = [g for g in genes if g in have]
        b = a[:, shared].copy()
        b.X = lognorm(b.X, shared)
        parts.append(b)
    out = ad.concat(parts, join='outer', fill_value=0)
    have = set(out.var_names)
    return out[:, [g for g in genes if g in have]].copy()


def centroids(x, labels, types):
    return np.vstack([np.asarray(x[labels == t].mean(0)).ravel() for t in types])


def assign(external, reference, ref_labels, min_margin=0.02):
    """Correlation to reference type centroids on shared variable genes, within compatible classes."""
    types = np.unique(ref_labels)
    ref = reference.X
    mean = np.asarray(ref.mean(0)).ravel()
    var = np.asarray(ref.power(2).mean(0)).ravel() - mean**2
    feat = np.argsort(var)[-2000:]
    c = centroids(ref[:, feat], ref_labels, types)
    e = as_dense(external.X[:, feat])

    def z(m):
        m = m - m.mean(1, keepdims=True)
        return m / np.maximum(np.linalg.norm(m, axis=1, keepdims=True), 1e-8)
    corr = z(e) @ z(c).T
    out = np.full(external.n_obs, '', dtype=object)
    census = external.obs.cell_type.astype(str).to_numpy()
    for i in range(external.n_obs):
        ok = COMPATIBLE.get(census[i])
        if not ok:
            continue
        mask = np.isin(types, list(ok))
        if not mask.any():
            continue
        scores = np.where(mask, corr[i], -np.inf)
        order = np.argsort(scores)[::-1]
        if mask.sum() == 1 or scores[order[0]] - scores[order[1]] >= min_margin:
            out[i] = types[order[0]]
    return out


class AnchorFlow:
    """LatentFlow composition/state plus a calibrated drift toward an external late anchor."""

    def __init__(self, earlier, latest, external, t_earlier, t_latest, t_anchor, seed=0, min_cells=30):
        self.flow = LatentFlow(earlier, latest, t_latest - t_earlier, seed)
        self.latest = self.flow.latest
        self.t_latest, self.t_anchor = t_latest, t_anchor
        genes = list(self.latest.var_names)
        have = set(external.var_names)
        ext = external[:, [g for g in genes if g in have]].copy()
        position = {g: i for i, g in enumerate(genes)}
        self.gene_index = np.array([position[g] for g in ext.var_names])
        early = self.flow.earlier
        la, lb = self.flow.labels_a, self.flow.labels_b
        cal = ext[ext.obs.group.astype(str).to_numpy() == 'calibration'].copy()
        anc = ext[ext.obs.group.astype(str).to_numpy() == 'anchor'].copy()
        early_sub = early[:, list(ext.var_names)].copy()
        latest_sub = self.latest[:, list(ext.var_names)].copy()
        cal_lab = assign(cal, early_sub, la)
        anc_lab = assign(anc, latest_sub, lb)
        # Platform offset per gene: pooled over types matched at the calibration stage,
        # each type weighted equally so abundant lineages do not dominate.
        cal_types = [t for t in np.unique(la) if (cal_lab == t).sum() >= min_cells and (la == t).sum() >= min_cells]
        self.calibration_types = cal_types
        if cal_types:
            ours = centroids(early_sub.X, la, cal_types)
            theirs = centroids(cal.X, cal_lab, cal_types)
            self.offset = np.median(ours - theirs, axis=0)
        else:
            self.offset = np.zeros(ext.n_vars)
        self.drift = {}
        self.anchor_counts = {t: int((anc_lab == t).sum()) for t in np.unique(lb)}
        for t in np.unique(lb):
            if self.anchor_counts[t] < min_cells:
                continue
            anchor = np.asarray(anc.X[anc_lab == t].mean(0)).ravel() + self.offset
            now = np.asarray(latest_sub.X[lb == t].mean(0)).ravel()
            self.drift[t] = (np.maximum(anchor, 0) - now).astype(np.float32)
        self.calibration_counts = {t: int((cal_lab == t).sum()) for t in np.unique(la)}

    def predict(self, horizon, n=3000, seed=42, state=.35, growth=.25, weight=.5, bound=.5):
        out = self.flow.predict(horizon, n=n, seed=seed, state=state, growth=growth)
        if weight:
            fraction = horizon / (self.t_anchor - self.t_latest)
            labels = lineages(self.latest)[out.obs['source_row'].to_numpy()]
            x = as_dense(out.X).astype(np.float32)
            counts = np.expm1(x)
            for t, d in self.drift.items():
                rows = labels == t
                if rows.any():
                    shift = np.clip(weight * fraction * d, -bound, bound)
                    # Apply in log space to log1p values, then renormalize library.
                    sub = np.log1p(counts[np.ix_(rows, self.gene_index)])
                    sub = np.maximum(sub + shift, 0)
                    counts[np.ix_(rows, self.gene_index)] = np.expm1(sub)
            counts *= 1e4 / np.maximum(counts.sum(1, keepdims=True), 1e-8)
            out.X = sparse.csr_matrix(np.log1p(counts))
        out.uns['method'] = 'latent flow plus calibrated external late-anchor drift (Qiu 2024 TS23)'
        out.uns['anchor'] = dict(weight=weight, bound=bound, t_anchor=self.t_anchor,
                                 types_with_drift=sorted(self.drift))
        return out
