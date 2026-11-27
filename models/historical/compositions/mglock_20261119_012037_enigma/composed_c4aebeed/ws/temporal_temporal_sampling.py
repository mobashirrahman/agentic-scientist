"""Horizon-scaled erythroid source-sampling prior for the temporal (T1) board.

Rationale
---------
Primitive erythroblasts are a small but transcriptionally distinctive population
in the early heart-region dissections, and they are the largest under-predicted
signal on the dev target: the diagnosis measured ~1-2% Blood versus ~14.7% in
the E10.5 truth, with the embryonic globins (Hbb-y, Hba-x, Hbb-bh1, Hba-a1) the
largest DE genes predicted with the wrong magnitude/sign.

The biology says the Blood jump across E9.5->E10.5 is a developmental programme,
not a trend we can extrapolate: primitive erythroid cells (EryP) arise in the
yolk sac and enter the circulation once the heart contracts (~E9.0), maturing
there as a nearly synchronous cohort (Palis et al.; McGrath et al.).  The
released early stages bracket only the start of that influx, so E8.5->E9.5 does
not reveal it, and donor reweighting of the *latest* stage is the only unbiased
way to add these cells (no E9.5 donor of a later Blood state exists).

The intervention is *source-mass bounded*: it changes only the donor-sampling
probabilities of the latest input stage, so marker-corroborated erythroid
donors are drawn at increased odds, bounded by (i) an absolute probability-mass
budget and (ii) an odds cap that also respects how many draws the eligible
donors can supply.  No expression value is edited, no pool is resampled, no
seed changes.  Sampling real latest-stage cells keeps stage-appropriate
empirical programmes; the parent's anchor drift and sparse realisation are
applied afterwards exactly as before, and total donor mass is restored exactly
from the non-erythroid lineages by renormalisation.

The strength is a knob (``<board>_knobs.json``), not a guessed constant: the
w3_c00/w3_c01 measurements showed the 0.08 budget still binding (predicted
Blood 0.077 versus the 0.147 target, i.e. about half of the observed deficit)
with mass_binding = 1 and supply_binding = 0, so the default is now 0.12
(``q`` about 0.13 at the E9.5 eligible fraction of ~1.25%) and the declared
knob range lets on-demand tuning bracket the optimum instead of us fitting a
constant to a single dev split.  The horizon enters only through the
saturation ``s = min(horizon/interval, 1)``: after one observed interval the
prior is fully on, so a 2-day test horizon cannot compound it into a Blood
takeover.
"""
import numpy as np

# Shared erythroid marker panel: embryonic globins (Hbb-y, Hba-x, Hbb-bh1) plus
# the two adult alpha globins present throughout the erythroid programme.
ERY_MARKERS = ('Hbb-y', 'Hba-x', 'Hbb-bh1', 'Hba-a1', 'Hba-a2')
MIN_ELIGIBLE = 30          # support guard: below this we abstain entirely
# Knobs (defaults mirror temporal_knobs.json; on-demand tuning may override
# them through context['params']).  ERY_MASS_BUDGET is the absolute probability mass
# the eligible group may gain per saturated interval; ERY_MAX_ODDS bounds the
# per-donor odds multiplier at full saturation.
ERY_MASS_BUDGET = 0.12
ERY_MAX_ODDS = 14.0
# Supply cap: the expected number of draws per *distinct* eligible donor is
# q / f (eligible mass over eligible pool share).  A tilt that asks for more
# than this many uses of the same few donors is no longer "sampling real
# donors", it is duplicating them, so the odds are capped by the eligible
# fraction through this constant.  At the measured E9.5 eligible fraction
# (f ~ 0.0125) the budget 0.12 asks for q ~ 0.1325, i.e. ~10.6 draws per donor,
# so the cap of 16 is non-binding but still guards a tiny eligible pool.
ERY_SUPPLY_CAP = 16.0


def _marker_matrix(a, markers):
    """Dense (cells x markers) log-expression block on the markers present."""
    pos = {g: i for i, g in enumerate(a.var_names)}
    cols = [pos[g] for g in markers if g in pos]
    if not cols:
        return np.zeros((a.n_obs, 0), dtype=np.float32), []
    sub = a.X[:, cols]
    sub = sub.toarray() if hasattr(sub, 'toarray') else np.asarray(sub)
    return np.asarray(sub, dtype=np.float32), cols


def erythroid_eligibility(a, markers):
    """Boolean mask of marker-corroborated erythroid donors.

    Requires (i) a Blood / erythroid label (case-insensitive), (ii) mean shared
    marker log expression above 1.0 and (iii) at least two markers detected.
    This is a donor-identity rule from the input alone; no target information
    enters.
    """
    labels = np.asarray(a.obs['celltype']).astype(str)
    low = np.char.lower(labels)
    label_ok = np.array([('blood' in s) or ('erythro' in s) for s in low])
    x, cols = _marker_matrix(a, markers)
    if len(cols) < 2:
        return np.zeros(a.n_obs, dtype=bool)
    mean_marker = x.mean(axis=1)
    detected = (x > 0).sum(axis=1)
    return label_ok & (mean_marker > 1.0) & (detected >= 2)


def _odds_cap_from_fraction(f, supply_cap=ERY_SUPPLY_CAP):
    """Largest odds multiplier whose enriched mass uses each donor <= supply_cap times.

    With enriched eligible mass ``q = m f / (1 - f + m f)`` the average number
    of draws per distinct eligible donor is ``q / f`` (the pool holds ``f`` of
    its donors in the eligible group).  Requiring ``q <= supply_cap * f`` and
    solving for ``m`` gives ``m <= supply_cap (1-f) / (1 - supply_cap f)``.
    When the eligible group is already a large share of the pool that bound is
    above one and non-binding, so ``inf`` is returned.
    """
    denom = 1.0 - supply_cap * f
    if denom <= 0.0:
        return np.inf
    return max(1.0, supply_cap * (1.0 - f) / denom)


def plan_enrichment(flow, eligible, horizon, interval,
                    mass_budget=ERY_MASS_BUDGET, max_odds=ERY_MAX_ODDS):
    """Recover the parent source probabilities and the bounded tilt.

    The parent's sampler uses ``p = normalize(exp(0.25 * F * log_growth))`` with
    ``F = min(horizon/interval, 2)``.  We choose the desired eligible mass ``q``
    under an odds cap ``m0 = max_odds**s`` (``s = min(horizon/interval, 1)``
    saturates after one interval), an absolute budget ``q - f <= mass_budget*s``
    and a supply cap on the eligible fraction, then invert the tilt so the
    multiplier ``m`` is applied through the existing sampler.  Everything is
    analytic; there are no sweeps or tuned constants beyond the declared knobs.
    Total donor mass is conserved by the renormalisation of the weights, i.e.
    whatever mass the eligible group gains is withdrawn from the non-erythroid
    lineages in proportion to their parent probabilities (exact restoration).
    """
    if not (np.isfinite(interval) and np.isfinite(horizon)) or interval <= 0 or horizon <= 0:
        return None
    F = float(min(horizon / interval, 2.0))
    s = float(min(horizon / interval, 1.0))
    if eligible.sum() < MIN_ELIGIBLE or F <= 0:
        return None
    w = np.exp(0.25 * F * flow.log_growth)
    total = float(w.sum())
    if not np.isfinite(total) or total <= 0:
        return None
    p = w / total
    f = float(p[eligible].sum())
    if not (0.0 < f < 1.0):
        return None
    m_odds = float(max_odds) ** s
    m_supply = _odds_cap_from_fraction(f)
    m0 = float(min(m_odds, m_supply))
    q0 = m0 * f / (1.0 - f + m0 * f)
    q_budget = float(f + float(mass_budget) * s)
    q = float(min(q0, q_budget))
    if not (q > f and q < 1.0):
        return None
    m = q * (1.0 - f) / (f * (1.0 - q))
    if not (np.isfinite(m) and m > 1.0):
        return None
    return dict(F=F, s=s, f=f, q=q, m=float(m), q0=float(q0),
                q_budget=q_budget,
                m0=m0, m_odds=float(m_odds), m_supply=float(m_supply),
                mass_budget=float(mass_budget), max_odds=float(max_odds),
                mass_binding=bool(q0 > q_budget),
                supply_binding=bool(m_supply < m_odds),
                draws_per_donor=float(q / max(f, 1e-12)),
                ess_before=float(1.0 / np.sum(p ** 2)),
                ess_after=float(1.0 / np.sum((p * np.where(eligible, m, 1.0) /
                                              (1.0 + (m - 1.0) * f)) ** 2)))
