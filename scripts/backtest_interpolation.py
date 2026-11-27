"""Hold out E7.25 completely; predict from E6.75 and E8.0."""
from pathlib import Path
import sys
import subprocess
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.data import ROOT, load_stage
from src.models import interpolate

directory = ROOT / 'submissions/backtests/embryo'
left = load_stage('T2/E6.75.h5ad')
right = load_stage('T2/E8.0.h5ad')
# The held-out stage is only read by the scorer, never by the model.
pred = interpolate(left, right, (7.25 - 6.75) / (8.0 - 6.75))
pred = pred[:, left.var_names].copy()
pred.write_h5ad(directory / 'interpolation.h5ad', compression='gzip')
subprocess.run([sys.executable, '-m', 'vec_local_score', '--task', 'T2', '--setting', 'embryo',
    '--pred', str(directory / 'pred.h5ad'), '--pred', str(directory / 'interpolation.h5ad'),
    '--reference', str(directory / 'reference.h5ad'), '--target', str(directory / 'target.h5ad'),
    '--seeds', '0', '1', '2', '--json', str(directory / 'interpolation_comparison.json')], check=True)
