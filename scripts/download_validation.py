"""Download the officially unlocked P2 files. Never unlocks or requests hidden test data."""
import hashlib
import json
from pathlib import Path
import sys
import urllib.request
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.ve_api import ROOT, get


def main():
    if not get('/challenge/data/validation/state')['unlocked']:
        raise RuntimeError('Validation answers are not unlocked')
    manifest = get('/challenge/data/validation/manifest')
    (ROOT / 'docs/api/validation_manifest.json').write_text(json.dumps(manifest, indent=2))
    audit_path = ROOT / 'data/validation_downloads.json'
    audit = json.loads(audit_path.read_text()) if audit_path.exists() else {}
    for item in manifest['files']:
        key = item['key']
        dest = ROOT / 'data/raw' / key
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists() and dest.stat().st_size == item['bytes']:
            with dest.open('rb') as stream:
                digest = hashlib.file_digest(stream, 'sha256').hexdigest()
            if audit.get(key, {}).get('sha256') == digest:
                print('Verified cached', key, flush=True)
                continue
        link = get('/challenge/data/validation/link', key=key)
        print('Downloading', key, flush=True)
        temporary = dest.with_suffix('.h5ad.part')
        digest = hashlib.sha256()
        with urllib.request.urlopen(link['url'], timeout=180) as response, temporary.open('wb') as stream:
            while chunk := response.read(4 << 20):
                stream.write(chunk)
                digest.update(chunk)
        if temporary.stat().st_size != item['bytes']:
            raise RuntimeError(f'Wrong file size: {key}')
        expected = link.get('sha256') or item.get('sha256')
        if expected and digest.hexdigest() != expected:
            raise RuntimeError(f'Hash mismatch: {key}')
        temporary.replace(dest)
        audit[key] = dict(bytes=dest.stat().st_size, sha256=digest.hexdigest(),
                          published_sha256=expected,
                          integrity='published hash matched' if expected else 'size verified; local hash recorded')
        audit_path.write_text(json.dumps(audit, indent=2) + '\n')
        print('Downloaded', key, audit[key]['integrity'], flush=True)

if __name__ == '__main__':
    main()
