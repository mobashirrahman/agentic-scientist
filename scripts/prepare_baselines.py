"""Reproducible no-change submissions; never uploads or unlocks data."""
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.data import ROOT, load_stage, sample

SOURCES = {
    'T1:test': 'T1/E9.5_RNA.h5ad',
    'T2:heart:test_extrap': 'T2/E9.5.h5ad',
    'T2:embryo:test_interp': 'T2/E7.25.h5ad',
    'T3:bcatenin': 'T2/E8.75.h5ad',
}


def main():
    panels = json.loads((ROOT / 'data/panels/index.json').read_text())
    destination = ROOT / 'submissions/first'
    destination.mkdir(parents=True, exist_ok=True)
    manifest = {}
    for board, source in SOURCES.items():
        stage = load_stage(source)
        contract = panels[board]
        genes = (ROOT / 'data/panels' / contract['genes_file']).read_text().splitlines()
        pred = sample(stage[:, genes], n=3000)
        pred.uns['method'] = 'wt_identity' if board.startswith('T3') else 'copy_last'
        path = destination / (board.replace(':', '__') + '.h5ad')
        pred.write_h5ad(path, compression='gzip')
        manifest[board] = dict(file=str(path.relative_to(ROOT)), source=source,
            source_sha256=hashlib.file_digest(open(ROOT / 'data/raw' / source, 'rb'), 'sha256').hexdigest(),
            sha256=hashlib.file_digest(open(path, 'rb'), 'sha256').hexdigest(),
            cells=pred.n_obs, genes=pred.n_vars, seed=42,
            removed_duplicates=stage.uns['removed_duplicates'], method=pred.uns['method'])
        print(board, path, flush=True)
    (destination / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')

if __name__ == '__main__':
    main()
