"""Build leakage-free no-change backtests and score with the community multi-seed runner."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.data import ROOT, load_stage, sample

SPLITS = {
    'temporal': ('T1', None, 'T1/E8.5_RNA.h5ad', 'T1/E9.5_RNA.h5ad'),
    'embryo': ('T2', 'embryo', 'T2/E6.75.h5ad', 'T2/E7.25.h5ad'),
    'heart': ('T2', 'heart', 'T2/E8.75.h5ad', 'T2/E9.5.h5ad'),
    'perturbation': ('T3', None, 'T2/E9.5.h5ad', 'T3/E9.5_mab21l2_ko.h5ad'),
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--task', choices=SPLITS, required=True)
    parser.add_argument('--seeds', nargs='+', type=int, default=[0, 1, 2, 3, 4])
    args = parser.parse_args()
    task, setting, ref, truth = SPLITS[args.task]
    directory = ROOT / 'submissions/backtests' / args.task
    directory.mkdir(parents=True, exist_ok=True)
    reference, target = load_stage(ref), load_stage(truth)
    genes = reference.var_names[reference.var_names.isin(target.var_names)]
    reference, target = reference[:, genes].copy(), target[:, genes].copy()
    pred = sample(reference)
    for name, a in [('reference', reference), ('target', target), ('pred', pred)]:
        a.write_h5ad(directory / (name + '.h5ad'), compression='gzip')
    (directory / 'split.json').write_text(json.dumps(dict(reference=ref, target=truth,
        method='wt_identity' if task == 'T3' else 'copy_last',
        warning='No-change sanity check; no temporal dynamics fitted. T3 is not a transferable KO backtest.'), indent=2))
    command = [sys.executable, '-m', 'vec_local_score', '--task', task,
               '--pred', str(directory / 'pred.h5ad'), '--target', str(directory / 'target.h5ad'),
               '--wt' if task == 'T3' else '--reference', str(directory / 'reference.h5ad'),
               '--seeds', *map(str, args.seeds), '--json', str(directory / 'scores.json')]
    if setting:
        command += ['--setting', setting]
    subprocess.run(command, check=True)

if __name__ == '__main__':
    main()
