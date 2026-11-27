"""Measure mouse panels' strict one-to-one ortholog coverage in an scGPT vocabulary."""
import argparse
from collections import defaultdict
import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / 'data/checkpoints/scgpt'
PANELS = ('T1__test', 'T2__heart__test_extrap', 'T2__embryo__test_interp', 'T3__bcatenin')


def one_to_one(path):
    groups = defaultdict(lambda: defaultdict(set))
    classes_by_gene = defaultdict(set)
    with path.open(newline='') as stream:
        for row in csv.DictReader(stream, delimiter='\t'):
            group, taxon, symbol = (row[k] for k in ('DB Class Key', 'NCBI Taxon ID', 'Symbol'))
            if taxon in ('9606', '10090') and symbol:
                groups[group][taxon].add(symbol)
                classes_by_gene[taxon, symbol].add(group)
    mapping = {}
    for group in groups.values():
        if len(group['9606']) == len(group['10090']) == 1:
            human, = group['9606']
            mouse, = group['10090']
            if len(classes_by_gene['9606', human]) == len(classes_by_gene['10090', mouse]) == 1:
                mapping[mouse] = human
    return mapping


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--vocab', type=Path, default=REFERENCE / 'public_vocab.json')
    parser.add_argument('--orthologs', type=Path, default=REFERENCE / 'mgi_homology.tsv')
    parser.add_argument('--out', type=Path, default=ROOT / 'results/scgpt_public_vocab.json')
    args = parser.parse_args()
    vocab = set(json.loads(args.vocab.read_text()))
    mapping = one_to_one(args.orthologs)
    output = {}
    for name in PANELS:
        path = ROOT / 'data/panels' / f'{name}.genes.txt'
        genes = path.read_text().split()
        mapped = {gene: mapping[gene] for gene in genes if gene in mapping and mapping[gene] in vocab}
        output[name] = dict(genes=len(genes), mapped=len(mapped), coverage=len(mapped) / len(genes),
                            panel_sha256=digest(path))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({
        'scope': 'Input vocabulary audit only. Default software vocabulary is a proxy for the checkpoint vocabulary.',
        'vocabulary_sha256': digest(args.vocab),
        'ortholog_report_sha256': digest(args.orthologs),
        'mapping': 'One mouse and one human symbol per MGI class, with both symbols unique across classes.',
        'panels': output,
    }, indent=2) + '\n')
    print(json.dumps(output, indent=2))


if __name__ == '__main__':
    main()
