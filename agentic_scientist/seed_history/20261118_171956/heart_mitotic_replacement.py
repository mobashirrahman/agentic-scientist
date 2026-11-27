"""Empirical mitotic-state transport at frozen heart anatomy.

Biology
-------
Differentiating cardiomyocytes progressively restrict cycling and acquire
mature expression programs (clonal-expansion study; de Boer et al. 2012:
proliferation is regional, falls on recruitment into myocardium and declines
in the ventricular walls).  The late fetal hearts in ``context['external']``
(Feulner et al. 2024, dissected wild-type hearts at E14.5/E16.5/E18.5) show a
decline of the canonical mitotic module (Top2a, Cenpf, Ccna2, Cdk1) across
those stages.  Only the *direction* of that decline is transferred: the
external platform is Drop-seq and the released input is MERFISH, so per-gene
additive offsets are calibrated against the latest released input and cancel
in the temporal difference.  No external expression level is used as a
target, no external stage value is branched on, and no late maternal level is
copied.

Why replacement instead of a weight tilt
----------------------------------------
The previous confirmed operator tilted the *donor law* inside each annotation.
That can change the realised anatomy because donors with different spatial
neighbourhoods change share.  Here the parent's accepted geometry is frozen:
the output coordinates, row order and count are never touched, and the same
local transport is realised as a *minimal replacement of whole real
expression profiles* between neighbouring donors of the same annotation and
the same spatial patch.  Formally, a maximal (gamma) coupling between the
incoming law ``p0`` and the tilted law ``p1`` keeps donor ``i`` with
probability ``min(1, p1_i / p0_i)`` and otherwise re-draws inside ``i``'s own
block from the residual ``max(p1 - p0, 0)``.  The output law equals ``p1`` in
expectation, while the expected fraction of replacements is the total
variation ``0.5 * sum|p1 - p0|`` and every replacement stays inside one
annotation x patch, so annotation and patch masses are exactly conserved and
no lineage identity is crossed.

Steps
-----
1. ``external_orientation``: earliest/latest available external ``stage_days``
   (no exact-time branch), broad external classes by label token
   (cardiomyocyte / endocardial / epicardial).  Offset per gene = median, over
   the latest input's supported CM and endocardial classes, of
   ``latest input mean - earliest external mean``.  A gene is retained when its
   end-minus-start change is negative in >= 2 supported external classes and
   the class-median change is negative (>= 2 genes required).  Offsets cancel
   in the within-platform temporal difference; they cannot identify age versus
   platform effects, which is exactly why only the sign is used.  ``Peri`` is
   not treated as epicardium and only CM/endocardial classes calibrate.
2. ``plan_local_state``: module score ``s`` = mean log expression over the
   retained genes on the latest stage.  Per annotation (original latest-stage
   ``obs['celltype']``, ``Unknown`` excluded case-insensitively, >= 50 cells in
   both of the last two inputs) standardise ``z = (s - mean) / max(sd, 0.1)``
   and damp with ``beta = h / (h + dt)``.  Spatial axes are divided by their
   stage SD (z is a section index) and MiniBatchKMeans with
   ``K = max(1, ceil(N / 64))`` defines local patches.  Inside each
   annotation x patch block multiply ``p0`` by
   ``exp(clip(-beta * z, -log(2)/2, +log(2)/2))`` and renormalise to the exact
   incoming block mass.  Hence ``p1 / p0`` lies in ``[0.5, 2]`` and every
   annotation and patch mass is conserved; the 64-cell nominal patch is chosen
   a priori to keep donor moves local (the coarser 256-cell comparator moved
   profiles across several scored 15-NN niches).
3. ``replace_profiles``: whole real expression rows are copied from the
   replacement donor (never averaged, never renormalised); coordinates are
   kept byte-for-byte; an independent ``SeedSequence([seed, 31973])`` stream
   leaves every parent random draw untouched.

The intervention is a state prior, not a model of division rate and not a
claim that transcript abundance measures proliferation.  Its direction is
externally corroborated; transfer to an earlier proliferative regime is a
falsifiable assumption, so it stays ON and is scored on every heart split.
"""
import numpy as np
from sklearn.cluster import MiniBatchKMeans

# Fixed canonical mitotic / proliferation module (shared panel members only).
CANONICAL_MARKERS = ('Top2a', 'Cenpf', 'Ccna2', 'Cdk1')
MIN_MARKERS = 2            # a priori: need two measured module members
MIN_CLASS_CELLS = 50       # external/internal class support per endpoint
MIN_ANNOT_CELLS = 50       # annotation support in BOTH passed inputs
MIN_SIGN_CLASSES = 2       # negative calibrated change in >=2 external classes
PATCH_NOMINAL = 64         # one spatial patch per ~64 donors
MIN_SD = 0.1               # floor on the within-annotation score SD
HALF_LOG2 = 0.5 * float(np.log(2.0))   # per-donor weight clip
CALIB_CLASSES = ('cm', 'endo')         # classes used for the additive offset
REPLACEMENT_STREAM = 31973             # independent child seed for the coupling


def external_class(label):
    """Broad cardiac class of an external (Feulner) label, by token only.

    ``Peri...`` labels are not epicardium here: only a literal ``epicard``
    token qualifies, so pericardium/body-wall cells remain ``other`` and
    never enter the calibration.
    """
    low = str(label).strip().lower()
    if 'endocard' in low:
        return 'endo'
    if 'epicard' in low:
        return 'epi'
    if 'cardiomyocyte' in low or 'cardiac muscle' in low or 'cardiacmuscle' in low:
        return 'cm'
    return 'other'


def input_class(label):
    """Broad cardiac class of a released heart-region label, by token only.

    Handles the released vocabulary (``V-CM``, ``IFT-CM``, ``OFT-CM``,
    ``A-CM``, ``Endo``, ``Chamber-Endo``, ``Peri`` ...) without assuming any
    cross-stage ontology: only the label string carried by that stage is read.
    """
    low = str(label).strip().lower()
    tokens = [t for t in low.replace('_', '-').replace('/', '-').split('-') if t]
    # Endocardial labels: 'Endo', 'Chamber-Endo', 'Cush-EndoMT-Endo'.  Every
    # endothelial label ('HEM-Endoth', 'Great Artery Endoth', 'BEC') must NOT
    # match, so the test is on a whole token, not a substring.
    if 'endocard' in low or any(t == 'endo' for t in tokens):
        return 'endo'
    if 'epicard' in low or low == 'peri':
        return 'epi'
    if 'non-cm' in low or 'noncm' in low:
        return 'other'
    if any(t == 'cm' for t in tokens) or low == 'vcm':
        return 'cm'
    if 'cardiomyocyte' in low:
        return 'cm'
    return 'other'


def _dense_columns(a, genes):
    """Dense (n_obs, n_present) log-expression block plus the present genes."""
    pos = {g: i for i, g in enumerate(a.var_names)}
    present = [g for g in genes if g in pos]
    if not present:
        return np.zeros((a.n_obs, 0), dtype=np.float32), []
    block = a.X[:, [pos[g] for g in present]]
    block = block.toarray() if hasattr(block, 'toarray') else np.asarray(block)
    return np.asarray(block, dtype=np.float32), present


def _nanmean(x, axis=0):
    with np.errstate(invalid='ignore'):
        m = np.nanmean(np.asarray(x, dtype=np.float64), axis=axis)
    return np.where(np.isfinite(m), m, 0.0)


def external_orientation(ext, latest):
    """Direction-only external consensus on the canonical mitotic module.

    Returns ``None`` when the external table, its stages, its class support or
    the internal calibration classes cannot support the estimate.
    """
    if ext is None or getattr(ext, 'n_obs', 0) == 0:
        return None
    if 'stage_days' not in ext.obs:
        return None
    genes = [g for g in CANONICAL_MARKERS
             if g in ext.var_names and g in latest.var_names]
    if len(genes) < MIN_MARKERS:
        return None
    t_ext = np.asarray(ext.obs['stage_days'], dtype=np.float64).ravel()
    ok_t = np.isfinite(t_ext)
    if not ok_t.any():
        return None
    stages = np.unique(t_ext[ok_t])
    if len(stages) < 2:
        return None
    t0, t1 = float(stages[0]), float(stages[-1])
    if not t1 > t0:
        return None
    xe, genes = _dense_columns(ext, genes)
    if len(genes) < MIN_MARKERS:
        return None
    ext_labels = (np.asarray(ext.obs['cell_type']).astype(str)
                  if 'cell_type' in ext.obs
                  else np.asarray([''] * ext.n_obs))
    ecls = np.array([external_class(s) for s in ext_labels], dtype=object)

    means0, means1, supported = {}, {}, []
    for c in ('cm', 'endo', 'epi'):
        m0 = (ecls == c) & (t_ext == t0)
        m1 = (ecls == c) & (t_ext == t1)
        if int(m0.sum()) < MIN_CLASS_CELLS or int(m1.sum()) < MIN_CLASS_CELLS:
            continue
        supported.append(c)
        means0[c] = _nanmean(xe[m0])
        means1[c] = _nanmean(xe[m1])
    if len(supported) < MIN_SIGN_CLASSES:
        return None

    # Per-gene additive platform calibration against the *latest input*: the
    # offset is removed again by the temporal difference, so only direction is
    # transferred (never a literal external level).  Only bona fide CM and
    # endocardial classes calibrate; epicardium is used for sign support only.
    icls = (np.array([input_class(s) for s in
                      np.asarray(latest.obs['celltype']).astype(str)], dtype=object)
            if 'celltype' in latest.obs else np.zeros(latest.n_obs, dtype=object))
    xi, _ = _dense_columns(latest, genes)
    offsets = []
    for c in CALIB_CLASSES:
        m = (icls == c)
        if int(m.sum()) >= MIN_CLASS_CELLS and c in supported:
            offsets.append(_nanmean(xi[m]) - means0[c])
    if not offsets:
        return None
    offset = np.median(np.vstack(offsets), axis=0)

    deltas = np.vstack([(means1[c] + offset) - (means0[c] + offset)
                        for c in supported])
    sign_support = (deltas < 0.0).sum(axis=0)
    class_median = np.median(deltas, axis=0)
    keep = (sign_support >= MIN_SIGN_CLASSES) & (class_median < 0.0)
    kept_genes = [g for g, k in zip(genes, keep) if k]
    if len(kept_genes) < MIN_MARKERS:
        return None
    order = [i for i, k in enumerate(keep) if k]
    return dict(
        genes=kept_genes,
        stage_times=np.asarray([t0, t1], dtype=np.float64),
        classes=np.asarray(supported, dtype=str),
        calibration_offset=offset[order].astype(np.float64),
        external_gene_deltas=deltas[:, order].astype(np.float64),
        sign_support=sign_support[order].astype(np.float64),
        class_median_delta=class_median[order].astype(np.float64),
        n_genes_considered=float(len(genes)))


def _module_score(latest, genes):
    """Mean log expression over the retained module, one value per donor."""
    x, present = _dense_columns(latest, genes)
    if x.shape[1] == 0:
        return None, []
    return np.asarray(x.mean(axis=1), dtype=np.float64).ravel(), present


def plan_local_state(earlier, latest, p0, external, h, dt, fit_seed):
    """Build the tilted law ``p1`` and its annotation x patch blocks.

    ``p0`` is the exact donor law the parent output was drawn from (niche tilt,
    chamber-conditioned law, or uniform).  Returns ``None`` (parent unchanged)
    whenever external support, internal annotation support or the horizon is
    invalid.  Support rules only: never a score.
    """
    ori = external_orientation(external, latest)
    if ori is None:
        return None
    if not (np.isfinite(h) and np.isfinite(dt) and dt > 0.0 and h > 0.0):
        return None
    if 'celltype' not in latest.obs or 'celltype' not in earlier.obs:
        return None
    if 'spatial_3D' not in latest.obsm:
        return None
    coords = np.asarray(latest.obsm['spatial_3D'], dtype=np.float64)
    if coords.ndim != 2 or coords.shape[0] != latest.n_obs or not np.all(np.isfinite(coords)):
        return None

    score, genes = _module_score(latest, ori['genes'])
    if score is None or len(genes) < MIN_MARKERS:
        return None

    n = int(latest.n_obs)
    p = np.asarray(p0, dtype=np.float64).ravel() if p0 is not None else None
    if p is None or p.shape != (n,) or not np.all(np.isfinite(p)) or float(p.sum()) <= 0.0:
        p = np.full(n, 1.0 / n, dtype=np.float64)
    p = np.clip(p, 0.0, None)
    p = p / p.sum()

    labels = np.asarray(latest.obs['celltype']).astype(str)
    prev = np.asarray(earlier.obs['celltype']).astype(str)
    # z is a section index, not a distance: normalise each spatial axis by the
    # stage's own SD so the clustering metric is scale-free.
    sd = np.maximum(coords.std(axis=0), 1e-10)
    cnorm = coords / sd
    beta = float(h / (h + dt))

    p1 = p.copy()
    blocks = []
    block_of = np.full(n, -1, dtype=np.int64)
    eligible_labels = []
    n_eligible_cells = 0
    rng_seed = int(fit_seed)
    for label in np.unique(labels):
        if str(label).strip().lower() == 'unknown':
            continue
        idx = np.flatnonzero(labels == label)
        if len(idx) < MIN_ANNOT_CELLS or int(np.sum(prev == label)) < MIN_ANNOT_CELLS:
            continue
        s = score[idx]
        spread = float(s.std())
        z = (s - float(s.mean())) / max(spread, MIN_SD)
        k = max(1, int(np.ceil(len(idx) / float(PATCH_NOMINAL))))
        if k > 1:
            patch = MiniBatchKMeans(n_clusters=k, n_init=1, batch_size=1024,
                                    random_state=rng_seed).fit_predict(cnorm[idx])
        else:
            patch = np.zeros(len(idx), dtype=np.int64)
        w = np.exp(np.clip(-beta * z, -HALF_LOG2, HALF_LOG2))
        eligible_labels.append(str(label))
        n_eligible_cells += len(idx)
        for u in np.unique(patch):
            loc = np.flatnonzero(patch == u)
            rows = idx[loc]
            mass = float(p[rows].sum())
            if mass <= 0.0:
                continue
            num = p[rows] * w[loc]
            tot = float(num.sum())
            if not np.isfinite(tot) or tot <= 0.0:
                continue
            p1[rows] = mass * num / tot
            block_of[rows] = len(blocks)
            blocks.append(rows)
    if not blocks:
        return None

    tv = float(0.5 * np.abs(p1 - p).sum())
    return dict(
        genes=genes, ori=ori, beta=beta, p0=p, p1=p1,
        blocks=blocks, block_of=block_of, score=score, coords_norm=cnorm,
        labels=labels,
        tv=tv, ess_p0=float(1.0 / np.sum(p ** 2)),
        ess_p1=float(1.0 / np.sum(p1 ** 2)),
        module_p0=float(p @ score), module_p1=float(p1 @ score),
        mean_score=float(score.mean()),
        n_blocks=float(len(blocks)), n_eligible_cells=float(n_eligible_cells),
        eligible_labels=eligible_labels,
        block_mass_error=float(max(
            abs(float(p1[rows].sum()) - float(p[rows].sum())) for rows in blocks)))


def replace_profiles(out, latest, plan, seed):
    """Maximal coupling of the output donor law ``p0`` onto ``p1``.

    Keeps each source donor with probability ``min(1, p1/p0)`` and otherwise
    redraws inside the same annotation x patch from ``max(p1 - p0, 0)``.  Whole
    real expression rows are copied and the coordinates are left untouched.
    Returns ``(geometry_source_row, realized_source_row)``.
    """
    src = np.asarray(out.obs['source_row'], dtype=np.int64).ravel()
    n = int(src.size)
    p0, p1 = plan['p0'], plan['p1']
    block_of = plan['block_of']

    rng = np.random.default_rng(np.random.SeedSequence([int(seed), REPLACEMENT_STREAM]))
    dst = src.copy()
    ratio = np.ones(n, dtype=np.float64)
    positive = p0[src] > 0.0
    ratio[positive] = np.minimum(1.0, p1[src[positive]] / p0[src[positive]])
    # One uniform draw for every output position, consumed before any block
    # choice so the coupling is reproducible and independent of block order.
    u = rng.random(n)
    switched = positive & (u > ratio)

    for b in np.unique(block_of[src[switched]]):
        if b < 0:
            continue
        rows = plan['blocks'][int(b)]
        hit = np.flatnonzero(switched & (block_of[src] == b))
        if hit.size == 0:
            continue
        resid = np.maximum(p1[rows] - p0[rows], 0.0)
        total = float(resid.sum())
        if total <= 0.0:
            continue
        dst[hit] = rng.choice(rows, size=hit.size, replace=True, p=resid / total)

    # --- Copy whole real profiles for replaced positions only ---
    changed = np.flatnonzero(dst != src)
    if changed.size:
        block = latest[dst, out.var_names].X
        out.X = block.copy() if hasattr(block, 'copy') else np.asarray(block)
        # All observation columns of the parent output come from the donor, so
        # re-index them consistently.  Annotation is identical by construction.
        for col in list(latest.obs.columns):
            if col in out.obs.columns:
                try:
                    out.obs[col] = np.asarray(latest.obs[col])[dst]
                except Exception:
                    out.obs[col] = np.asarray(
                        np.asarray(latest.obs[col])[dst], dtype=object)
        out.obs['source_row'] = dst
    out.obs['geometry_source_row'] = src
    return src, dst, changed


def _disabled_diag():
    return dict(
        applied=0.0, genes=np.array([], dtype=str), gene_count=0.0,
        external_t0=0.0, external_t1=0.0, beta=0.0,
        external_sign_support=np.array([], dtype=float),
        external_class_median=np.array([], dtype=float),
        module_p0=0.0, module_p1=0.0, module_mean_latest=0.0,
        tv=0.0, ess_p0=0.0, ess_p1=0.0,
        expected_replacement=0.0, realized_replacement=0.0,
        realized_module_delta=0.0, realized_module_before=0.0,
        realized_module_after=0.0, donor_separation=0.0,
        n_blocks=0.0, n_eligible_cells=0.0, n_labels=0.0,
        annotation_count_delta=0.0, patch_count_delta=0.0,
        block_mass_error=0.0, coord_max_abs_diff=0.0,
        n_replaced=0.0, n_output=0.0)


def _diag(plan, src, dst, changed, coords_before, coords_after):
    score = plan['score']
    before = float(score[src].mean()) if src.size else 0.0
    after = float(score[dst].mean()) if dst.size else 0.0
    sep = 0.0
    if changed.size:
        c = plan['coords_norm']
        sep = float(np.linalg.norm(c[dst[changed]] - c[src[changed]], axis=1).mean())
    # Annotation and patch counts are identical by block construction; the
    # diagnostics report the realised differences so any regression is visible.
    ann_delta = 0.0
    patch_delta = 0.0
    if changed.size:
        lab = plan['block_of']
        ann_delta = 0.0 if np.array_equal(plan['labels'][src], plan['labels'][dst]) else 1.0
        patch_delta = 0.0 if np.array_equal(lab[src], lab[dst]) else 1.0
    coord_diff = float(np.max(np.abs(np.asarray(coords_after, dtype=np.float64)
                                     - np.asarray(coords_before, dtype=np.float64)))) \
        if coords_before is not None else 0.0
    ori = plan['ori']
    return dict(
        applied=1.0, genes=np.asarray(plan['genes'], dtype=str),
        gene_count=float(len(plan['genes'])),
        external_t0=float(ori['stage_times'][0]),
        external_t1=float(ori['stage_times'][1]),
        beta=float(plan['beta']),
        external_sign_support=np.asarray(ori['sign_support'], dtype=float),
        external_class_median=np.asarray(ori['class_median_delta'], dtype=float),
        module_p0=float(plan['module_p0']), module_p1=float(plan['module_p1']),
        module_mean_latest=float(plan['mean_score']),
        tv=float(plan['tv']), ess_p0=float(plan['ess_p0']),
        ess_p1=float(plan['ess_p1']),
        expected_replacement=float(plan['tv']),
        realized_replacement=float(changed.size / max(src.size, 1)),
        realized_module_delta=float(after - before),
        realized_module_before=float(before), realized_module_after=float(after),
        donor_separation=float(sep),
        n_blocks=float(plan['n_blocks']),
        n_eligible_cells=float(plan['n_eligible_cells']),
        n_labels=float(len(plan['eligible_labels'])),
        annotation_count_delta=float(ann_delta),
        patch_count_delta=float(patch_delta),
        block_mass_error=float(plan['block_mass_error']),
        coord_max_abs_diff=float(coord_diff),
        n_replaced=float(changed.size), n_output=float(src.size))


def apply_state_replacement(out, earlier, latest, p0, external, h, dt, seed, fit_seed):
    """Postprocessor over the final parent output: plan, then couple, then log.

    A single entry point so both metadata protocols (with and without chamber
    conditioning) run the same state update on the parent's frozen anatomy.
    Any support failure leaves the parent output exactly as it was.
    """
    try:
        plan = plan_local_state(earlier, latest, p0, external, h, dt, fit_seed)
    except Exception:
        plan = None
    if plan is None:
        out.uns['mitotic_state'] = _disabled_diag()
        return out
    coords_before = np.array(out.obsm['spatial_3D'], dtype=np.float64, copy=True) \
        if 'spatial_3D' in out.obsm else None
    try:
        src, dst, changed = replace_profiles(out, latest, plan, seed)
    except Exception:
        out.uns['mitotic_state'] = _disabled_diag()
        return out
    coords_after = np.asarray(out.obsm['spatial_3D'], dtype=np.float64) \
        if 'spatial_3D' in out.obsm else None
    out.uns['mitotic_state'] = _diag(plan, src, dst, changed,
                                     coords_before, coords_after)
    return out
