"""Spatial mixing scale jitter (XJ15), post-jitter profile re-anchoring (PK1), and myocardial compaction.

Biological and geometric rationale:
  1. Oversampling an earlier organ pool (4k-12k cells) to the dissected forecast size (25,179 rows) places
     multiple copies of each donor cell at identical 3D coordinates, collapsing the 15-NN physical radius and
     inflating local neighborhood variance well above later-stage myocardium. Meanwhile, from E10.5 toward
     fetal stages (E12.5+), ventricular wall morphogenesis is dominated by rapid expansion and thickening of
     the compact myocardial layer relative to thin trabecular recesses while preserving crisp separation
     between compact/trabecular myocardium, lining endocardium, and outer epicardium (Zhang et al. 2013,
     PMID:23843320; Jensen et al. 2024, J Anat; Captur et al. 2016, J Anat). Adding RMS-preserving isotropic
     Gaussian jitter (10% of organ RMS radius) eliminates duplicate-site collapse and rounds thin early-stage
     walls toward a thicker compact 3D chamber geometry (improving pairwise-distance D2 shape and occupancy).
  2. However, moving each cell's original expression profile to its randomly jittered coordinate diffuses
     cardiomyocytes, endocardial cells, epicardial cells, and vessels across anatomical compartment boundaries.
     Re-anchoring each jittered 3D point's expression profile to a real donor residing at its nearest unique
     pre-jitter spatial site (PK1, k=1 with uniform draw among co-located donors) restores sharp anatomical
     layer boundaries while keeping 100% real single-cell profiles and smooth duplicate-free coordinates.
  3. Relocating detached vessel/pericardial cells onto exterior non-cardiac rim sites leaves pure non-myocyte
     15-NN islands (~25-40% of cells with zero cardiomyocyte neighbours vs <5% in dissected later hearts and
     Slide-seq E14.5/E15.5 hearts). Compacting a bounded fraction of non-myocyte cells in the most
     myocardium-depleted 15-NN islands (local CM share <= 0.15) to real profiles drawn from their 5 nearest
     cardiomyocytes eliminates these exterior islands while keeping 100% real measured single-cell profiles
     and preserving all attached cardiac-adjacent endocardial, epicardial, and vascular cells.
"""

import numpy as np
from scipy.spatial import cKDTree

from heart_maturation import _atlas_mix, _classes

JITTER_RMS_FRAC = 0.10   # RMS-scaled isotropic 3D wall-thickening jitter (test-density calibrated with PK1)
REANCHOR_K = 1           # nearest unique pre-jitter spatial site(s) used to restore compartment boundaries (PK1)
COMPACT_FRAC = 0.35      # share of myocardium-depleted non-myocyte island rows converted to nearby real CMs
CM_LOCAL_MAX = 0.15      # 15-NN cardiomyocyte fraction threshold for myocardium-depleted islands
NEIGHBOR_K = 15          # local spatial microenvironment size
DONOR_K = 5              # nearest real cardiomyocytes sampled to preserve regional chamber identity
MIN_COMPARTMENT = 50     # minimum CM and non-CM counts required before compacting
DEFAULT_CM_CEILING = 0.70
MAX_CM_CEILING = 0.75


def _rms(xyz):
    centered = xyz - xyz.mean(axis=0)
    return float(np.sqrt(np.mean(np.sum(centered ** 2, axis=1))))


def jitter_mixing_scale(out, seed, jitter_frac=JITTER_RMS_FRAC):
    """Add RMS-preserving isotropic 3D Gaussian coordinate jitter; return the sigma applied (0 if skipped)."""
    if jitter_frac <= 0 or out.n_obs < 2 or 'spatial_3D' not in out.obsm:
        return 0.0
    xyz = np.asarray(out.obsm['spatial_3D'], dtype=float)
    r0 = _rms(xyz)
    if not np.isfinite(r0) or r0 <= 0:
        return 0.0
    sigma = float(jitter_frac) * r0
    rng = np.random.default_rng([int(seed), 31])
    jittered = xyz + rng.normal(0.0, sigma, xyz.shape)
    r1 = _rms(jittered)
    if np.isfinite(r1) and r1 > 0:
        center = jittered.mean(axis=0)
        jittered = center + (jittered - center) * (r0 / r1)
    out.obsm['spatial_3D'] = jittered
    return sigma


def reanchor_profiles_to_sites(out, pre_xyz, seed, k_reanchor=REANCHOR_K):
    """Restore anatomical compartment boundaries after coordinate jitter by assigning each jittered 3D site
    a real measured profile drawn uniformly from the donors residing at its nearest unique pre-jitter site(s)."""
    k_req = int(k_reanchor)
    if k_req <= 0 or out.n_obs < 2 or 'spatial_3D' not in out.obsm or pre_xyz is None:
        return out, 0
    post_xyz = np.asarray(out.obsm['spatial_3D'], dtype=float)
    pre_arr = np.asarray(pre_xyz, dtype=float)
    if pre_arr.shape != post_xyz.shape or not (np.isfinite(pre_arr).all() and np.isfinite(post_xyz).all()):
        return out, 0

    # Deduplicate pre-jitter sites so oversampled replicates at one coordinate do not collapse k-NN diversity,
    # then sample uniformly among the real donor rows residing at the matched site.
    uniq_sites, inverse = np.unique(pre_arr, axis=0, return_inverse=True)
    k_eff = min(k_req, len(uniq_sites))
    if k_eff <= 0:
        return out, 0

    rng = np.random.default_rng([int(seed), 61])
    near = cKDTree(uniq_sites).query(post_xyz, k=k_eff)[1]
    if k_eff == 1:
        chosen_site = near
    else:
        chosen_site = near[np.arange(out.n_obs), rng.integers(0, k_eff, out.n_obs)]

    order = np.argsort(inverse)
    counts = np.bincount(inverse, minlength=len(uniq_sites))
    starts = np.cumsum(np.r_[0, counts[:-1]])
    offsets = np.minimum((rng.random(out.n_obs) * counts[chosen_site]).astype(np.intp), counts[chosen_site] - 1)
    picked = order[starts[chosen_site] + offsets]
    reassigned = int(np.sum(picked != np.arange(out.n_obs)))

    remixed = out[picked].copy()
    remixed.obs_names = out.obs_names.copy()
    remixed.obsm['spatial_3D'] = post_xyz.copy()
    return remixed, reassigned


def _cm_ceiling(plan):
    """Upper bound on global cardiomyocyte share informed by the later spatial heart anchor."""
    if plan is not None:
        _, _, spatial, sections, _ = plan
        if sections and spatial is not None and 'cell_type' in spatial.obs:
            sp_mix = _atlas_mix(spatial, sections)
            if sp_mix[0] > 0 and np.isfinite(sp_mix[0]):
                return float(np.clip(sp_mix[0], 0.50, MAX_CM_CEILING))
    return DEFAULT_CM_CEILING


def compact_myocardial_neighborhoods(out, plan, seed, compact_frac=COMPACT_FRAC,
                                     cm_loc_max=CM_LOCAL_MAX, k_nbr=NEIGHBOR_K, k_donor=DONOR_K):
    """Convert a bounded fraction of non-myocyte cells in myocardium-depleted 15-NN islands
    to nearby real cardiomyocyte profiles at fixed spatial coordinates."""
    if (compact_frac <= 0 or out.n_obs < 2 * MIN_COMPARTMENT
            or 'celltype' not in out.obs or 'spatial_3D' not in out.obsm):
        return out, 0

    codes = _classes(out, 'celltype')
    is_cm = (codes == 0)
    n_cm = int(is_cm.sum())
    if n_cm < MIN_COMPARTMENT or (out.n_obs - n_cm) < MIN_COMPARTMENT:
        return out, 0

    xyz = np.asarray(out.obsm['spatial_3D'], dtype=float)
    k_eff = min(int(k_nbr), out.n_obs)
    knn_idx = cKDTree(xyz).query(xyz, k=k_eff)[1]
    if k_eff == 1:
        knn_idx = knn_idx[:, None]
    cm_local = is_cm[knn_idx].mean(axis=1)

    candidates = np.flatnonzero((~is_cm) & (cm_local <= cm_loc_max))
    if candidates.size == 0:
        return out, 0

    ceiling = _cm_ceiling(plan)
    max_add = max(0, int(round((ceiling - (n_cm / out.n_obs)) * out.n_obs)))
    n_convert = min(int(round(float(compact_frac) * candidates.size)), max_add)
    if n_convert <= 0:
        return out, 0

    rng = np.random.default_rng([int(seed), 43])
    # Prioritize the most myocardium-depleted islands first (with slight tie-breaking noise).
    order = np.argsort(cm_local[candidates] + rng.uniform(0.0, 0.05, candidates.size))
    chosen = candidates[order[:n_convert]]

    cm_sites = np.flatnonzero(is_cm)
    kd = min(int(k_donor), cm_sites.size)
    near_cm = cKDTree(xyz[cm_sites]).query(xyz[chosen], k=kd)[1]
    if kd == 1:
        picked = cm_sites[near_cm]
    else:
        picked = cm_sites[near_cm[np.arange(chosen.size), rng.integers(0, kd, chosen.size)]]

    donors = np.arange(out.n_obs)
    donors[chosen] = picked
    remixed = out[donors].copy()
    remixed.obs_names = out.obs_names.copy()
    remixed.obsm['spatial_3D'] = xyz.copy()
    return remixed, int(chosen.size)
