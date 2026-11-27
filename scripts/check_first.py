"""Check prepared files locally and optionally request free portal format checks."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.upload_gate import authorize

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--portal', action='store_true')
    parser.add_argument('--directory', type=Path, default=ROOT / 'submissions/first')
    parser.add_argument('--board')
    parser.add_argument('--approval')
    args = parser.parse_args()
    directory = args.directory.resolve()
    manifest = json.loads((directory / 'manifest.json').read_text())
    if args.board:
        manifest = {args.board: manifest[args.board]}
    if args.portal:
        if not args.board:
            parser.error('--portal requires --board')
        authorize(directory, args.board, ROOT / manifest[args.board]['file'], 'format', args.approval)
        from src.ve_api import BASE, KEY, get
    env = dict(os.environ, VEC_PANELS_DIR=str(ROOT / 'data/panels'))
    previous = directory / 'portal_checks.json'
    results = json.loads(previous.read_text()) if args.portal and previous.exists() else {}
    before = get('/challenge/integration/quota') if args.portal else None
    for board, item in manifest.items():
        path = ROOT / item['file']
        import hashlib
        with path.open('rb') as stream:
            if hashlib.file_digest(stream, 'sha256').hexdigest() != item['sha256']:
                raise RuntimeError(f'File changed since preparation: {path}')
        report = directory / (board.replace(':', '__') + '.local.json')
        subprocess.run([sys.executable, '-m', 'vec_submit_check', '--board', board,
                        str(path), '--json', str(report)], env=env, check=True)
        if args.portal:
            import requests
            parts = board.split(':')
            fields = dict(task=parts[0], format_only='true', confirm_final='false',
                          model='historical-entry first preparation: ' + item['method'])
            if parts[0] == 'T2':
                fields.update(setting=parts[1], split='test', mode=parts[2].removeprefix('test_'))
            elif parts[0] == 'T3':
                fields.update(target=parts[1], split='test')
            else:
                fields['split'] = parts[1]
            with path.open('rb') as stream:
                response = requests.post(BASE + '/challenge/submissions',
                    headers={'Authorization': 'Bearer ' + KEY}, data=fields,
                    files={'file': (path.name, stream, 'application/octet-stream')}, timeout=180)
            if not response.ok:
                raise RuntimeError(f'Portal {response.status_code}: {response.text}')
            receipt = response.json()
            if not receipt.get('format_only') or not receipt.get('ok') or receipt.get('sha256') != item['sha256']:
                raise RuntimeError(f'Unexpected portal receipt for {board}: {receipt}')
            results[board] = receipt
            (directory / 'portal_checks.json').write_text(json.dumps(results, indent=2) + '\n')
            print(board, json.dumps(results[board]), flush=True)
    if args.portal:
        (directory / 'quota_check.json').write_text(json.dumps(
            dict(before=before, after=get('/challenge/integration/quota')), indent=2) + '\n')

if __name__ == '__main__':
    main()
