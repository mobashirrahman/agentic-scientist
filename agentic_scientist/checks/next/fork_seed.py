"""Fork a program into per-task modules (option C): each board gets its own copy of every helper it uses.

  .venv/bin/python agentic_scientist/checks/next/fork_seed.py SRC_WS DST_WS

Result layout (the rule the agents and the combiner rely on):
  program.py          frozen dispatcher: predict() -> <board>.predict_<board>()
  <board>.py          that board's code (a full copy of the original program.py)
  <board>_<name>.py   that board's private copies of helpers (workspace helpers and src/v2 modules)
A board's files may import only its own <board>_* files, src.v2 is no longer used, so editing one board's
code can never change another board's predictions. Dev scores are unchanged by the fork (verified by eval).
"""
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BOARDS = ('temporal', 'heart', 'embryo', 'perturbation')
DISPATCH = '''"""Frozen dispatcher (do not edit). Each board's code lives in <board>.py and its private <board>_*.py helpers."""
import temporal
import heart
import embryo
import perturbation

_FN = {'temporal': temporal.predict_temporal, 'heart': heart.predict_heart,
       'embryo': embryo.predict_embryo, 'perturbation': perturbation.predict_perturbation}


def predict(board, inputs, times, target_time, context):
    return _FN[board](inputs, times, target_time, context)
'''


def sources(src):
    """Module name -> source text for every module the program can reach (workspace helpers + src/v2)."""
    mods = {p.stem: p.read_text() for p in src.glob('*.py') if p.name != 'program.py'}
    v2 = ROOT / 'src/v2'
    todo = [src / 'program.py'] + [src / f'{m}.py' for m in mods]
    seen = set()
    while todo:
        text = todo.pop().read_text()
        for m in re.findall(r'from\s+(?:src\.v2\.|\.)(\w+)\s+import', text) + re.findall(r'import\s+src\.v2\.(\w+)', text):
            if m not in seen and (v2 / f'{m}.py').exists():
                seen.add(m)
                mods.setdefault(m, (v2 / f'{m}.py').read_text())
                todo.append(v2 / f'{m}.py')
    return mods


def rewrite(text, board, names):
    for m in names:
        text = re.sub(rf'from\s+(?:src\.v2\.|\.)?{m}\s+import', f'from {board}_{m} import', text)
        text = re.sub(rf'^import\s+(?:src\.v2\.)?{m}\s+as\s+', f'import {board}_{m} as ', text, flags=re.M)
        text = re.sub(rf'^import\s+(?:src\.v2\.)?{m}\b(?!\s+as\b)', f'import {board}_{m} as {m}', text, flags=re.M)
    return text


def prune(dst):
    """Drop top-level functions that trip the program screen (e.g. src/v2/anchor.load_external, which the frozen
    harness uses to load T1's external data) when nothing in the forked program calls them."""
    sys.path.insert(0, str(ROOT))
    from agentic_scientist.evaluate import EXTRA_FORBIDDEN
    from shinka_ve import harness
    files = list(dst.glob('*.py'))
    for f in files:
        text = f.read_text()
        blocks = re.split(r'(?m)^(?=\S)', text)
        keep = []
        for blk in blocks:
            m = re.match(r'def (\w+)', blk)
            bad = m and (harness.screen(blk) or any(re.search(p, blk) for p in EXTRA_FORBIDDEN))
            used = m and any(re.search(rf'(?<!def )\b{m.group(1)}\b', g.read_text()) for g in files)
            if bad and not used:
                print(f'pruned {f.name}:{m.group(1)}()')
                continue
            keep.append(blk)
        f.write_text(''.join(keep))


def fork(src, dst):
    src, dst = Path(src), Path(dst)
    prog = (src / 'program.py').read_text()
    if prog.strip() == DISPATCH.strip():
        sys.exit('already forked')
    mods = sources(src)
    if dst.exists():
        shutil.rmtree(dst)
    dst.mkdir(parents=True)
    for b in BOARDS:
        assert re.search(rf'^def predict_{b}\b', prog, re.M), f'program.py has no predict_{b}'
        (dst / f'{b}.py').write_text(rewrite(prog, b, mods))
        for m, text in mods.items():
            (dst / f'{b}_{m}.py').write_text(rewrite(text, b, mods))
    (dst / 'program.py').write_text(DISPATCH)
    prune(dst)
    for p in src.iterdir():  # non-python assets (rare)
        if p.is_file() and p.suffix != '.py':
            shutil.copy(p, dst / p.name)
    print(f'forked {src} -> {dst}: {sorted(x.name for x in dst.glob("*.py"))}')


if __name__ == '__main__':
    fork(sys.argv[1], sys.argv[2])
