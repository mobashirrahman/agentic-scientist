"""Future-anchor expression drift from external, rule-compliant late-stage data.

External source: Qiu et al. 2024 (CELLxGENE Census), Theiler stage 23 (~E15) as
the late anchor and TS12-13 (~E8-E9) for platform calibration. Nothing from the
excluded window (after E9.5 up to and including E13.5) is ever loaded.

Mechanism, per released cell type t and gene g (log1p CP10k space):
  gain_g        = clip(sum_c C[c,g]*O[c,g] / sum_c C[c,g]^2, 0.25, 4.0)
                  (zero-intercept diagonal slope over matched calibration-type
                  centroids C = Qiu calibration, O = released reference stage)
  anchor_t,g    = gain_g * mean_qiu_anchor(t,g)
  drift_t,g     = anchor_t,g - mean_ours_latest(t,g)
  shift at time = weight * fraction * drift, fraction = (T - t_latest)/(t_anchor - t_latest)
Types with too few matched anchor cells receive no shift. Shifts are bounded.

Why a zero-intercept diagonal gain rather than the parent's pooled additive
offset: a positive additive offset learned from expressing populations creates
an apparent future program in lineages where the atlas is nearly silent (e.g.
Myl7 in blood/endocardial endothelium).  A through-origin per-gene slope keeps
an atlas-zero centroid at zero, so lineage specificity survives platform
transfer, while a well-supported signal may be calibrated up or down.  The
gain bounds are fixed a priori and are not fitted on any score.
"""
import anndata as ad
import numpy as np
from scipy import sparse

from temporal_transport import LatentFlow, lineages, as_dense

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


def centroids(x, labels, types):
    return np.vstack([np.asarray(x[labels == t].mean(0)).ravel() for t in types])


# --- discordance between the near-term released trend and the atlas trend ----
# A lineage-by-gene comparison is only called when the lineage has enough cells
# in ALL FOUR groups (two released stages, Qiu calibration, Qiu anchor) and the
# gene is positively measured in at least 10 cells of each group, so a centroid
# difference is not driven by a handful of detections.  A coordinate is
# "discordant" only when both contrasts are at least 0.10 stored log1p units in
# size AND point in opposite directions; that is the evidence conflict whose
# extra displacement is shrunk in temporal_transport.py.
MIN_GROUP_CELLS = 30
MIN_GENE_POSITIVES = 10
DISCORD_MIN_ABS = 0.10


def _label_stats(x, labels, keep):
    """Per-label (positive-cell counts, mean log1p) with ONE binary copy per group.

    Slicing the binary matrix once per label costs one pass over the group in
    total (the label masks partition its rows), so the whole comparison is
    O(nnz of the four groups) rather than O(n_labels * nnz).
    """
    b = x.copy()
    b.data = (b.data > 0).astype(np.int8)
    b.eliminate_zeros()
    pos, mean = {}, {}
    for t in keep:
        m = labels == t
        pos[t] = np.asarray(b[m].sum(0)).ravel().astype(np.int32)
        mean[t] = np.asarray(x[m].mean(0)).ravel().astype(np.float64)
    return pos, mean


def discord_masks(latest_sub, early_sub, lb, la, cal, anc, cal_lab, anc_lab,
                  gain, gene_index, n_genes):
    """Lineage x shared-gene masks where the two temporal evidences disagree.

    ``D_release`` is the latest minus the previous released lineage centroid
    (log1p CP10k, same labels).  ``D_Qiu`` is the Qiu anchor minus Qiu
    calibration centroid inside the same matched lineage, multiplied by the
    existing positive per-gene platform gain (so an atlas-zero centroid cannot
    invent a change).  All four matrices share the external gene columns whose
    indices in ``latest.var_names`` are ``gene_index``.  Returns masks keyed by
    the released (latest-stage) cell-type label, plus flat diagnostics.
    """
    masks, pair_counts = {}, {}
    keep = [t for t in sorted(set(lb) & set(la) & set(cal_lab) & set(anc_lab))
            if min(int((lb == t).sum()), int((la == t).sum()),
                   int((cal_lab == t).sum()), int((anc_lab == t).sum()))
            >= MIN_GROUP_CELLS]
    info = dict(n_supported_lineages=float(len(keep)),
                n_discord_lineages=0.0, n_discord_pairs=0.0,
                n_discord_genes=0.0, discord_names=np.array([], dtype=str),
                discord_pairs=np.array([], dtype=np.float64))
    if not keep:
        return masks, info
    p_l, m_l = _label_stats(latest_sub.X, lb, keep)
    p_e, m_e = _label_stats(early_sub.X, la, keep)
    p_c, m_c = _label_stats(cal.X, cal_lab, keep)
    p_a, m_a = _label_stats(anc.X, anc_lab, keep)
    for t in keep:
        ok = ((p_l[t] >= MIN_GENE_POSITIVES) & (p_e[t] >= MIN_GENE_POSITIVES)
              & (p_c[t] >= MIN_GENE_POSITIVES) & (p_a[t] >= MIN_GENE_POSITIVES))
        if not ok.any():
            continue
        d_release = m_l[t] - m_e[t]
        d_qiu = np.asarray(gain, dtype=np.float64) * (m_a[t] - m_c[t])
        disc = (ok & (d_release * d_qiu < 0)
                & (np.abs(d_release) >= DISCORD_MIN_ABS)
                & (np.abs(d_qiu) >= DISCORD_MIN_ABS))
        if not disc.any():
            continue
        mask = np.zeros(int(n_genes), dtype=bool)
        mask[gene_index] = disc
        masks[t] = mask
        pair_counts[t] = int(disc.sum())
    info.update(n_discord_lineages=float(len(masks)),
                n_discord_pairs=float(sum(pair_counts.values())),
                n_discord_genes=float(np.any(np.vstack(list(masks.values())), axis=0).sum()
                                      if masks else 0),
                discord_names=np.array(sorted(masks), dtype=str),
                discord_pairs=np.array([pair_counts[t] for t in sorted(masks)],
                                       dtype=np.float64))
    return masks, info


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

    # Fixed, a priori bounds on the diagonal platform-transfer gain.  They only
    # express "the atlas may be calibrated by a factor of 4 either way, never
    # inverted or zeroed", and are not the product of a dev sweep.
    GAIN_MIN, GAIN_MAX = 0.25, 4.0
    # Named genes whose drift change is reported in diagnostics only.
    PROBE_GENES = ('Myl7', 'Ttn', 'Col1a1', 'Col3a1')

    def __init__(self, earlier, latest, external, t_earlier, t_latest, t_anchor, seed=0,
                 min_cells=30, calibration_reference=None):
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
        # The released stage used to calibrate the external platform is the one
        # nearest the early calibration window (Qiu TS12-13, ~E8-9).  The caller
        # passes the earliest supplied input; with two inputs that is exactly
        # ``early`` above.  LatentFlow itself still fits the latest observed pair.
        cal_ref = early if calibration_reference is None else calibration_reference
        ref_genes = [g for g in ext.var_names if g in set(cal_ref.var_names)]
        ref_sub = cal_ref[:, ref_genes].copy()
        cal_sub = cal[:, ref_genes].copy()
        ref_lab = lineages(ref_sub)
        cal_lab = assign(cal_sub, ref_sub, ref_lab)
        anc_lab = assign(anc, latest_sub, lb)
        # Genes the reference stage does not carry keep unit gain (raw atlas).
        gain = np.ones(len(ref_genes), dtype=np.float64)
        # Platform gain per gene: nonnegative least-squares slope through the
        # origin across equally weighted matched calibration-type centroids.
        cal_types = [t for t in np.unique(ref_lab)
                     if (cal_lab == t).sum() >= min_cells and (ref_lab == t).sum() >= min_cells]
        self.calibration_types = cal_types
        if cal_types:
            ours = centroids(ref_sub.X, ref_lab, cal_types)      # O[c, g]
            theirs = centroids(cal_sub.X, cal_lab, cal_types)    # C[c, g]
            numerator = (theirs * ours).sum(0)
            denominator = (theirs ** 2).sum(0)
            fitted = np.where(denominator < 1e-8, 1.0,
                              np.clip(numerator / np.maximum(denominator, 1e-8),
                                      self.GAIN_MIN, self.GAIN_MAX))
            gain = fitted
            # Parent's pooled additive offset, kept for the drift-change report
            # only: it is never applied to the prediction.
            offset = np.median(ours - theirs, axis=0)
        else:
            offset = np.zeros(len(ref_genes))
        ref_pos = {g: i for i, g in enumerate(ref_genes)}
        self.gain = np.ones(ext.n_vars, dtype=np.float64)
        self.gain[[ref_pos[g] for g in ref_genes]] = gain
        # Parent's additive offset mapped to the external gene space, kept for
        # the drift-change report only: never applied to the prediction.
        offset_full = np.zeros(ext.n_vars, dtype=np.float64)
        offset_full[[ref_pos[g] for g in ref_genes]] = offset
        ext_genes = np.asarray(ext.var_names).astype(str)
        probe_index = {g: int(np.flatnonzero(ext_genes == g)[0])
                       for g in self.PROBE_GENES if g in ext_genes}
        # ``ext`` is a superset of every group used below (181k atlas cells in
        # the released run); all slices are independent copies by now, so drop
        # the large parent to keep the peak memory of the mask/drift steps down.
        del ext
        self.drift = {}
        self.anchor_counts = {t: int((anc_lab == t).sum()) for t in np.unique(lb)}
        drift_change = {}
        additive_gap = {}
        probe_change = {}
        gain_at_probe = {}
        for t in np.unique(lb):
            if self.anchor_counts[t] < min_cells:
                continue
            anchor_mean = np.asarray(anc.X[anc_lab == t].mean(0)).ravel()
            now = np.asarray(latest_sub.X[lb == t].mean(0)).ravel()
            # Zero-intercept transfer: an atlas-zero centroid stays zero.
            self.drift[t] = (self.gain * anchor_mean - now).astype(np.float32)
            # Diagnostics only: additive-parent drift and their difference.
            old = np.maximum(anchor_mean + offset_full, 0) - now
            diff = np.asarray(self.drift[t], dtype=np.float64) - old
            drift_change[t] = float(np.linalg.norm(diff) / np.sqrt(max(diff.size, 1)))
            additive_gap[t] = float(np.linalg.norm(old) / np.sqrt(max(old.size, 1)))
            for g, j in probe_index.items():
                probe_change[f'{g}|{t}'] = float(diff[j])
                gain_at_probe[f'{g}|{t}'] = float(self.gain[j])
        self.drift_change = drift_change
        self.additive_gap = additive_gap
        self.probe_change = probe_change
        self.gain_at_probe = gain_at_probe
        # Evidence-conflict mask for the amplified state shift (diagnostics and
        # transport.py use only; never a fitted score parameter).
        self.state_discord, self.discord_info = discord_masks(
            latest_sub, early_sub, lb, la, cal, anc, cal_lab, anc_lab,
            self.gain, self.gene_index, self.latest.n_vars)
        # Donor support of the anchor-drift types (share of the latest stage).
        supported = np.isin(lb, list(self.drift))
        self.supported_mass = float(supported.mean()) if supported.size else 0.0
        w = np.exp(0.25 * np.asarray(self.flow.log_growth, dtype=np.float64))
        self.supported_donor_mass = float(w[supported].sum() / max(w.sum(), 1e-12))
        self.calibration_counts = {t: int((cal_lab == t).sum()) for t in np.unique(ref_lab)}
        # RMS size of the parent's pooled additive offset (diagnostics only).
        self.offset_rms = float(np.linalg.norm(offset_full) / np.sqrt(max(offset_full.size, 1)))

    def predict(self, horizon, n=3000, seed=42, state=.35, growth=.25, weight=.5, bound=.5,
                state_gain=None, shift_clip=.35, state_discord=None):
        out = self.flow.predict(horizon, n=n, seed=seed, state=state, growth=growth,
                                state_gain=state_gain, shift_clip=shift_clip,
                                state_discord=(self.state_discord
                                               if state_discord is None else state_discord))
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
        out.uns['method'] = 'latent flow plus zero-intercept diagonal external anchor transfer (Qiu 2024 TS23)'
        out.uns['anchor'] = dict(weight=weight, bound=bound, t_anchor=self.t_anchor,
                                 types_with_drift=sorted(self.drift))
        # Atlas-vs-released evidence-conflict support (diagnostics only).
        out.uns['atlas_discord'] = dict(self.discord_info)
        # Flat transfer diagnostics (never used for control): gain support and
        # how much the transfer change moved each lineage's anchor field.
        g = np.asarray(self.gain, dtype=np.float64)
        out.uns['anchor_transfer'] = dict(
            model='zero_intercept_diagonal',
            n_calibration_types=int(len(self.calibration_types)),
            n_genes_with_gain=int(g.size),
            gain_min=float(self.GAIN_MIN), gain_max=float(self.GAIN_MAX),
            gain_q10=float(np.quantile(g, .10)), gain_q50=float(np.quantile(g, .50)),
            gain_q90=float(np.quantile(g, .90)),
            gain_frac_at_min=float(np.mean(g <= self.GAIN_MIN + 1e-12)),
            gain_frac_at_max=float(np.mean(g >= self.GAIN_MAX - 1e-12)),
            gain_frac_unit=float(np.mean(np.abs(g - 1.0) <= 1e-12)),
            supported_mass=self.supported_mass,
            supported_donor_mass=self.supported_donor_mass,
            drift_change_norm=np.array([self.drift_change[k] for k in sorted(self.drift_change)]),
            drift_change_types=np.array(sorted(self.drift_change), dtype=str),
            additive_drift_norm=np.array([self.additive_gap[k] for k in sorted(self.additive_gap)]),
            probe_drift_change=np.array([self.probe_change[k] for k in sorted(self.probe_change)]),
            probe_drift_names=np.array(sorted(self.probe_change), dtype=str),
            probe_gain=np.array([self.gain_at_probe[k] for k in sorted(self.gain_at_probe)]),
            probe_gain_names=np.array(sorted(self.gain_at_probe), dtype=str),
            offset_median_norm=float(self.offset_rms))
        return out
