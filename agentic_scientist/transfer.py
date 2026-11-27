"""Split a candidate's dev gain into the kinds of metric that do and do not transfer to a hidden target.

Idea from vecbench's metric map (github.com/AJK0921/vecbench), applied to our own scores:
  distribution  compare predicted cells with target cells directly (mmd_u, variogram, d2_shape, occupancy_dice,
                neighborhood_mmd). A local gain is real evidence for the hidden target.
  de_based      defined on the genes that differ in THIS target (de_score, de_direction, severity_slope). Another
                target has another gene set, so a local gain is weak evidence (T3 dev is Gata4, the test is Ctnnb1).
  size          one unknown number about the target (scale_log_ratio). A local test cannot rank it.
Each value is the weighted change in board points (official metric weights, averaged over the board's splits).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'vendor/vec-community-kit'))
from vec_local_score.local_score import WEIGHTS  # noqa: E402

from shinka_ve import harness  # noqa: E402
from agentic_scientist import evaluate as _register_splits  # noqa: F401  (dev/holdout splits live there)

KIND = {'mmd_u': 'distribution', 'variogram': 'distribution', 'd2_shape': 'distribution',
        'occupancy_dice': 'distribution', 'neighborhood_mmd': 'distribution',
        'de_score': 'de_based', 'de_direction': 'de_based', 'severity_slope': 'de_based',
        'scale_log_ratio': 'size'}
KINDS = ('distribution', 'de_based', 'size')


def transfer(parent_eval, cand_eval):
    """{board: {kind: points}, 'total': {kind: points}} from two evaluate() results on the same splits."""
    ps, cs = (parent_eval or {}).get('splits', {}), (cand_eval or {}).get('splits', {})
    per_board = {}
    for split, c in cs.items():
        p = ps.get(split)
        if not p or 'metrics' not in c or 'metrics' not in p:
            continue
        task = harness.SPLITS[split]['task']
        w = WEIGHTS[task]
        row = {k: 0.0 for k in KINDS}
        for m, wt in w.items():
            if m in c['metrics'] and m in p['metrics'] and m in KIND:
                row[KIND[m]] += wt * (c['metrics'][m] - p['metrics'][m])
        per_board.setdefault(harness.SPLITS[split]['board'], []).append((row, float(harness.SPLITS[split].get('weight', 1))))
    out = {b: {k: round(sum(r[k] * w for r, w in rows) / sum(w for _, w in rows), 3) for k in KINDS} for b, rows in per_board.items()}
    out['total'] = {k: round(sum(v[k] for b, v in out.items()), 3) for k in KINDS}
    return out


def text(t):
    """One line for the knowledge bank and reports."""
    if not t:
        return ''
    tot = t.get('total', {})
    return (f"transfer: distribution {tot.get('distribution', 0):+.2f}, DE-based {tot.get('de_based', 0):+.2f}, "
            f"size {tot.get('size', 0):+.2f}")
