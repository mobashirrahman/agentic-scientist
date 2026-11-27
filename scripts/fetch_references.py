"""Cache public paper PDFs and the reference tables for the scGPT audit."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
SCGPT_REVISION = 'cebd6fae655b9c585a4807daa3ac31bb764f06b4'
ASSETS = {
    'docs/papers/cache/trajectorynet.pdf': 'https://proceedings.mlr.press/v119/tong20a/tong20a.pdf',
    'docs/papers/cache/moscot.pdf': 'https://www.nature.com/articles/s41586-024-08453-2.pdf',
    'docs/papers/cache/nicheformer.pdf': 'https://www.nature.com/articles/s41592-025-02814-z.pdf',
    'docs/papers/cache/tigon.pdf': 'https://www.nature.com/articles/s42256-023-00763-w.pdf',
    'docs/papers/cache/foundation-zero-shot.pdf':
        'https://genomebiology.biomedcentral.com/counter/pdf/10.1186/s13059-025-03574-x.pdf',
    'docs/papers/cache/linear-perturbation-baselines.pdf': 'https://www.nature.com/articles/s41592-025-02772-6.pdf',
    'data/checkpoints/scgpt/public_vocab.json': (
        f'https://raw.githubusercontent.com/bowang-lab/scGPT/{SCGPT_REVISION}/scgpt/tokenizer/default_gene_vocab.json'
    ),
    'data/checkpoints/scgpt/mgi_homology.tsv':
        'https://www.informatics.jax.org/downloads/reports/HOM_MouseHumanSequence.rpt',
}


def fetch(item):
    path, url = item
    target = ROOT / path
    request = Request(url, headers={'User-Agent': 'AgenticScientist reference cache'})
    with urlopen(request, timeout=30) as response:
        payload = response.read()
    if target.suffix == '.pdf' and not payload.startswith(b'%PDF-'):
        raise ValueError(f'{url} did not return a PDF')
    if target.suffix == '.json':
        json.loads(payload)
    if target.suffix == '.tsv' and not payload.startswith(b'DB Class Key\t'):
        raise ValueError(f'{url} did not return the MGI homology report')
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(payload)
    return {'path': path, 'url': url, 'bytes': len(payload), 'sha256': hashlib.sha256(payload).hexdigest()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--audit-only', action='store_true', help='Fetch reference tables only')
    args = parser.parse_args()
    items = [i for i in ASSETS.items() if not args.audit_only or not i[0].endswith('.pdf')]
    with ThreadPoolExecutor(max_workers=4) as pool:
        submitted = {pool.submit(fetch, item): item for item in items}
        records = []
        for future, (path, url) in submitted.items():
            try:
                record = future.result()
            except (OSError, ValueError) as exc:
                record = {'path': path, 'url': url, 'error': str(exc)}
            records.append(record)
            print(json.dumps(record))
    report = ROOT / ('data/checkpoints/scgpt' if args.audit_only else 'docs/papers/cache') / 'manifest.json'
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(records, indent=2) + '\n')
    return int(any('error' in entry for entry in records))


if __name__ == '__main__':
    raise SystemExit(main())
