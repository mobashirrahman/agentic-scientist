"""Compare scGPT with matched-gene PCA for cross-stage heart cell retrieval."""
import argparse
import json
from pathlib import Path

import anndata as ad
import numpy as np
from sklearn.decomposition import PCA
from sklearn.metrics import balanced_accuracy_score, f1_score
from sklearn.neighbors import KNeighborsClassifier
from sklearn.preprocessing import normalize

from scgpt_audit import REFERENCE, ROOT, digest, one_to_one


def donor_sample(stage, panel, labels, per_type, rng):
    selected = []
    for name in labels:
        rows = np.flatnonzero(stage.obs['celltype'].astype(str).to_numpy() == name)
        selected.extend(rng.choice(rows, min(per_type, len(rows)), replace=False))
    return stage[sorted(selected), panel].to_memory()


def metrics(x_train, x_test, train, test):
    classifier = KNeighborsClassifier(n_neighbors=15, metric='cosine', weights='distance')
    classifier.fit(normalize(x_train), train.obs['celltype'])
    predicted = classifier.predict(normalize(x_test))
    return {
        'macro_f1': float(f1_score(test.obs['celltype'], predicted, average='macro')),
        'balanced_accuracy': float(balanced_accuracy_score(test.obs['celltype'], predicted)),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model-dir', type=Path, help='Audited official checkpoint directory')
    parser.add_argument('--device', default='cpu')
    parser.add_argument('--upstream-source', type=Path, default=ROOT / 'vendor/scGPT')
    parser.add_argument('--out', type=Path, default=ROOT / 'results/scgpt_heart_retrieval.json')
    args = parser.parse_args()
    vocab_file = args.model_dir / 'vocab.json' if args.model_dir else REFERENCE / 'public_vocab.json'
    vocab = set(json.loads(vocab_file.read_text()))
    mapping = one_to_one(REFERENCE / 'mgi_homology.tsv')
    sources = [ROOT / f'data/raw/T2/{day}.h5ad' for day in ('E9.5', 'E10.5')]
    earlier, later = [ad.read_h5ad(path, backed='r') for path in sources]
    genes = [gene for gene in earlier.var_names if gene in later.var_names and mapping.get(gene) in vocab]
    labels = sorted(
        set(earlier.obs['celltype'].value_counts().loc[lambda s: s >= 30].index)
        & set(later.obs['celltype'].value_counts().loc[lambda s: s >= 30].index)
        - {'Unknown', 'unknown', 'nan'}
    )
    rng = np.random.default_rng(42)
    try:
        train, test = [donor_sample(stage, genes, labels, 100, rng) for stage in (earlier, later)]
    finally:
        earlier.file.close()
        later.file.close()
    pca = PCA(n_components=32, svd_solver='randomized', random_state=42)
    x_train = train.X.toarray() if hasattr(train.X, 'toarray') else train.X
    x_test = test.X.toarray() if hasattr(test.X, 'toarray') else test.X
    results = {'log_expression': metrics(x_train, x_test, train, test),
               'pca32': metrics(pca.fit_transform(x_train), pca.transform(x_test), train, test)}
    checkpoint = None
    if args.model_dir:
        checkpoint = {f: digest(args.model_dir / f) for f in ('vocab.json', 'args.json', 'best_model.pt')}
        from scgpt_frozen import scgpt_embeddings

        frozen, random, parameter_count = scgpt_embeddings(
            np.vstack((x_train, x_test)), [mapping[name] for name in genes], args.model_dir,
            args.device, args.upstream_source,
        )
        for name, values in [('scgpt', frozen), ('scgpt_random_weights', random)]:
            if not np.isfinite(values).all():
                raise RuntimeError(f'{name} returned nonfinite embeddings')
            results[name] = metrics(values[:train.n_obs], values[train.n_obs:], train, test)
        checkpoint['loaded_encoder_tensors'] = parameter_count
        checkpoint['source_files'] = {
            str(path.relative_to(args.upstream_source)): digest(path)
            for path in sorted(args.upstream_source.rglob('*.py')) if '__pycache__' not in path.parts
        }
    report = {
        'scope': 'Cell-type retrieval from observed E10.5 expression. This is a representation diagnostic.',
        'labels': labels, 'genes': len(genes), 'seed': 42,
        'train_cells': train.n_obs, 'test_cells': test.n_obs,
        'sources': {str(path.relative_to(ROOT)): digest(path) for path in sources},
        'vocabulary_sha256': digest(vocab_file), 'checkpoint': checkpoint, 'metrics': results,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(results, indent=2))


if __name__ == '__main__':
    main()
