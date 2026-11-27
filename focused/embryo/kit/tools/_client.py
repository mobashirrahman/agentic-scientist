"""Spool client for the evaluation service (do not modify)."""
import json
import os
import sys
import time
import uuid
from pathlib import Path

Q = Path(os.environ.get('FM_EVALQ', ''))


def request(kind, note='', wait_s=7200):
    if not Q or not (Q / 'req').is_dir():
        sys.exit('evaluation service not reachable (FM_EVALQ unset)')
    rid = f'{int(time.time())}_{uuid.uuid4().hex[:8]}'
    tmp = Q / 'req' / f'.{rid}.tmp'
    tmp.write_text(json.dumps(dict(id=rid, kind=kind, note=note, created=time.time())))
    tmp.rename(Q / 'req' / f'{rid}.json')
    res = Q / 'res' / f'{rid}.json'
    t0 = time.time()
    while not res.exists():
        if time.time() - t0 > wait_s:
            sys.exit('timed out waiting for the evaluation service')
        time.sleep(3)
    time.sleep(0.5)
    return json.loads(res.read_text())
