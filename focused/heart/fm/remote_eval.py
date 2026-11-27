"""Fleet worker entry: score a snapshot on splits (same code as local). Prints nothing; writes --out JSON."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fm.evaluation import score_snapshot  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument('--snap', required=True)
ap.add_argument('--splits', required=True)
ap.add_argument('--seeds', required=True)
ap.add_argument('--scoring', required=True)
ap.add_argument('--out', required=True)
a = ap.parse_args()
ints = lambda s: [int(x) for x in s.split(',')]
res = score_snapshot(a.snap, a.splits.split(','), ints(a.seeds), ints(a.scoring), Path(a.out).parent / 'work', parallel=2)
Path(a.out).write_text(json.dumps(res, default=float))
