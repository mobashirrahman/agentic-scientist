"""Fetch and verify the official checkpoint and pinned inference source for the local probe."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import tempfile
from urllib.request import urlopen

from fetch_references import ROOT, SCGPT_REVISION

UPSTREAM = 'https://raw.githubusercontent.com/bowang-lab/scGPT'
SOURCE = (
    'LICENSE', 'scgpt/model/model.py', 'scgpt/model/dsbn.py', 'scgpt/model/grad_reverse.py',
    'scgpt/model/flash_attn_compat.py', 'scgpt/data_collator.py', 'scgpt/preprocess.py',
)


def sha256(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def fetch(item):
    target, url, expected = item
    if target.is_file() and sha256(target) == expected:
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as stream:
        temporary = Path(stream.name)
        try:
            with urlopen(url, timeout=60) as response:
                while chunk := response.read(1 << 20):
                    stream.write(chunk)
            stream.close()
            if expected and sha256(temporary) != expected:
                raise ValueError(f'Checksum mismatch for {target.name}')
            temporary.replace(target)
        finally:
            temporary.unlink(missing_ok=True)


def main():
    files = json.loads((ROOT / 'results/scgpt_checkpoint.json').read_text())['files']
    probe = json.loads((ROOT / 'results/scgpt_heart_checkpoint_probe.json').read_text())
    sources = probe['checkpoint']['source_files']
    dest = ROOT / 'data/checkpoints/scgpt/whole-human'
    jobs = [(dest / name, item['url'], item['sha256']) for name, item in files.items()]
    jobs += [(ROOT / 'vendor/scGPT' / name, f'{UPSTREAM}/{SCGPT_REVISION}/{name}', sources.get(name)) for name in SOURCE]
    with ThreadPoolExecutor(max_workers=5) as pool:
        list(pool.map(fetch, jobs))
    print('Official checkpoint and pinned inference source are staged for the local probe.')


if __name__ == '__main__':
    main()
