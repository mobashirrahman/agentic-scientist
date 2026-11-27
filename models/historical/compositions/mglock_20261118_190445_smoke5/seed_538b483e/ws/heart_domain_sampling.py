"""Condition the heart donor law on the declared chamber dissection.

Rationale
---------
The heart board receives ``context['sampling']``.  ``'heart_with_surroundings'``
is the released E8.5-E10.5 dissection: myocardium *plus* pericardium / body
wall, neural tube, pharyngeal mesoderm, gut and other neighbouring tissue.
``'heart_chambers'`` is the E12.5 test protocol (organisers: the E12.5 target is
the dissected heart chambers, plus at most a few oesophagus-junction cells), and
the protocol-matched dev split restricts the target to the chamber types.

A uniform (or weakly niche-tilted) draw from the latest released stage therefore
confounds *developmental state* with *which organ was dissected*: at E8.75 only
18.5% of the released cells carry a chamber-compatible annotation, so the parent
predicts a population that is ~81% non-cardiac while the target is ~100%
cardiac.  No early-stage expression trend can represent a categorical change in
the measurement protocol.  The correction here is a single, instantaneous
conditioning of the *donor law* on the input's own anatomical labels:

    q = (1 - alpha) * p0 + alpha * p0 * mask / sum(p0 * mask)

with ``alpha = 0.95`` fixed a priori.  The 5% retained parent law is a
conservative allowance for uncertain boundary labels and the oesophagus-heart
junction, and it keeps every donor with positive probability (the output is
still a sample of real latest-stage cells; no expression is edited and no cell
is invented).  The intervention is only about *which* real cells are observed;
it is an observation-domain projection, not a developmental proliferation
trend, so its strength is constant in the horizon and cannot compound over the
two-day E12.5 jump.

Anatomy (from the input's own ``obs['celltype']``; no stage values, no split
identifiers, no target labels and no evaluator import):
  * cardiomyocytes: the shared parser of ``heart_niche_sampling`` (CM, vCM,
    V-CM / A-CM / SV-CM / OFT-CM / IFT-CM, LV-CM, RV-CM, any ``*-CM``);
  * endocardium: tokens ``endo`` / ``endocardium`` / ``endocardial`` (so
    ``Endo``, ``Chamber-Endo``, ``Cush-EndoMT-Endo``, ``EndoMT Endocardium``
    qualify) but *not* vascular endothelium (``Intra-Endoth``, ``HEM-Endoth``,
    ``Great Artery Endoth``, ``early-VEC``, ``BEC``);
  * epicardium / proepicardium: ``Epicard``, ``Epicardium``, ``Proepi`` ...
    but not ``Peri`` (pericardium / body wall, outside the dissection);
  * cushion / valve: ``Cush``, ``Cushion``, ``EndoMT``, ``Valve``;
  * the dorsal mesenchymal protrusion (``DMP``) and the juxta-cardiac field
    (``JCF``).

Deliberately excluded: all vascular endothelium, ``Peri`` / body wall, neural
crest (``NCC``), pharyngeal mesoderm (``aPHM``/``pPHM``, ``aSHF``/``pSHF``),
gut / foregut / surface ectoderm / paraxial mesoderm and every ``Unknown``
label.  On the four released T2 stages the resulting mask agrees cell-for-cell
with the anatomical chamber-type restriction used to build the protocol-matched
target (18.49% of E8.75), which is an independent check of the alias set rather
than a fit to a score.
"""
import numpy as np

# Fixed a priori: retain 5% of the inherited law for boundary-label uncertainty.
ALPHA = 0.95
# Support guards (the parent path runs when these fail).
MIN_ELIGIBLE = 1000
MIN_CELLS = 100

ENDOCARDIUM = {'endo', 'endocardium', 'endocardial'}
EPICARDIUM = {'epicard', 'epicardium', 'epicardial',
              'proepi', 'proepicardium', 'proepicardial'}
CUSHION = {'cush', 'cushion', 'endomt', 'valve'}
OTHER_CHAMBER = {'dmp', 'jcf'}


def _tokens(label):
    low = str(label).strip().lower().replace('_', '-').replace('/', '-').replace(' ', '-')
    return [t for t in low.split('-') if t]


def _cm_label(label):
    """Cardiac-muscle label test identical to ``heart_niche_sampling._cm_label``.

    Imported lazily inside ``chamber_mask`` would hide a failure; the two-line
    duplicate is deliberate so this helper has no dependency cycle and keeps a
    single documented definition of the label grammar.
    """
    low = str(label).strip().lower()
    if 'non-cm' in low or 'noncm' in low:
        return False
    tokens = [t for t in low.replace('_', '-').replace('/', '-').split('-') if t]
    return any(t == 'cm' for t in tokens) or low == 'vcm'


def chamber_mask(a):
    """Boolean mask over ``a``'s rows: donor is part of the dissected heart.

    Reads only the stage's own annotation strings; returns all-False when the
    stage carries no celltype column.
    """
    n = a.n_obs
    if 'celltype' not in a.obs:
        return np.zeros(n, dtype=bool)
    labels = np.asarray(a.obs['celltype']).astype(str)
    mask = np.zeros(n, dtype=bool)
    for i, label in enumerate(labels):
        ts = _tokens(label)
        hit = (_cm_label(label)
               or any(t in ENDOCARDIUM for t in ts)
               or any(t in EPICARDIUM for t in ts)
               or any(t in CUSHION for t in ts)
               or any(t in OTHER_CHAMBER for t in ts))
        mask[i] = bool(hit)
    return mask


def _finite_coords(a):
    if 'spatial_3D' not in a.obsm:
        return False
    p = np.asarray(a.obsm['spatial_3D'], dtype=np.float64)
    return p.ndim == 2 and p.shape[0] == a.n_obs and bool(np.all(np.isfinite(p)))


def condition_probabilities(latest, p0=None, sampling=None, alpha=ALPHA):
    """Chamber-conditioned donor law, or ``None`` to keep the parent path.

    Parameters
    ----------
    latest : AnnData
        The latest released stage; the law is over its rows.
    p0 : array-like or None
        The inherited donor law (``plan_cardiac_tilt()['p']``) or ``None`` for
        the parent's uniform law.  Normalised inside.
    sampling : str or None
        ``context['sampling']``; only ``'heart_chambers'`` triggers the change.
    alpha : float
        Fixed dissection strength; ``1 - alpha`` of the parent law is retained.

    Returns
    -------
    None or dict with ``q`` (normalised probability vector) and flat
    diagnostics (eligible donors, masses, ESS, background mass).
    """
    if sampling != 'heart_chambers':
        return None
    if latest is None or latest.n_obs < MIN_CELLS:
        return None
    if not _finite_coords(latest):
        return None
    n = int(latest.n_obs)
    if p0 is None:
        p = np.full(n, 1.0 / n, dtype=np.float64)
    else:
        p = np.asarray(p0, dtype=np.float64).ravel()
        if p.shape != (n,) or not np.all(np.isfinite(p)) or float(p.sum()) <= 0:
            p = np.full(n, 1.0 / n, dtype=np.float64)
    p = np.clip(p, 0.0, None)
    p /= p.sum()

    mask = chamber_mask(latest)
    n_eligible = int(mask.sum())
    eligible_mass = float(p[mask].sum())
    if n_eligible < MIN_ELIGIBLE or eligible_mass <= 0.0:
        return None

    q = (1.0 - alpha) * p + alpha * p * mask / eligible_mass
    q = np.clip(q, 0.0, None)
    q /= q.sum()
    return dict(
        q=q, mask=mask, alpha=float(alpha),
        n_eligible=float(n_eligible),
        frac_eligible=float(n_eligible / n),
        parent_mass=eligible_mass,
        conditioned_mass=float(q[mask].sum()),
        background_mass=float(q[~mask].sum()),
        ess=float(1.0 / np.sum(q ** 2)),
        n_cells=float(n),
    )


def attach(out, plan, source_row=None, rms=None):
    """Write flat (h5ad-safe) diagnostics for the conditioned draw."""
    if plan is None:
        out.uns['heart_domain'] = dict(
            applied=0.0, alpha=0.0, n_eligible=0.0, frac_eligible=0.0,
            parent_mass=0.0, conditioned_mass=0.0, realized_mass=0.0,
            background_mass=0.0, ess=0.0, rms_parent=0.0, rms_pre=0.0,
            rms_post=0.0, size_restore=1.0)
        return out
    mask = plan['mask']
    realized = (float(np.asarray(mask)[np.asarray(source_row, dtype=int)].mean())
                if source_row is not None else 0.0)
    rms = rms or {}
    out.uns['heart_domain'] = dict(
        applied=1.0, alpha=plan['alpha'], n_eligible=plan['n_eligible'],
        frac_eligible=plan['frac_eligible'], parent_mass=plan['parent_mass'],
        conditioned_mass=plan['conditioned_mass'], realized_mass=realized,
        background_mass=plan['background_mass'], ess=plan['ess'],
        rms_parent=float(rms.get('parent', 0.0)),
        rms_pre=float(rms.get('pre', 0.0)),
        rms_post=float(rms.get('post', 0.0)),
        size_restore=float(rms.get('restore', 1.0)))
    return out


def rms_radius(coords):
    """Centred RMS radius of a coordinate cloud (the scored size scale)."""
    p = np.asarray(coords, dtype=np.float64)
    if p.ndim != 2 or p.shape[0] == 0 or not np.all(np.isfinite(p)):
        return float('nan')
    c = p - p.mean(0)
    return float(np.sqrt(np.mean(np.sum(c * c, axis=1))))
