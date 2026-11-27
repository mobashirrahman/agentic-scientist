"""Preflight before launch: refuses to start a run that would fail later."""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fm import landlock  # noqa: E402
from fm.common import FM, RUNS, STAGES, VALIDATION, VAL_SCORING_SEEDS, panel_genes, read_json, sha256  # noqa: E402


def fail(msg):
    print('PREFLIGHT FAIL:', msg)
    sys.exit(1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--run', required=True)
    ap.add_argument('--skip-agents', action='store_true')
    a = ap.parse_args()
    cfg = json.loads((FM / 'config.json').read_text())
    st = read_json(RUNS / a.run / 'state.json')
    if st and st.get('phase') == 'done':
        fail('run already complete')
    pid = read_json(RUNS / a.run / 'orchestrator.pid.json')
    if pid and Path(f"/proc/{pid['pid']}").exists():
        fail(f"orchestrator already running (pid {pid['pid']})")
    if landlock.abi() < 4:
        fail('Landlock ABI >= 4 required')
    for n, s in STAGES.items():
        if not s['file'].exists() or sha256(s['file']) != s['sha256']:
            fail(f'stage {n} missing or checksum mismatch')
    if len(panel_genes()) != 500:
        fail('panel')
    if shutil.disk_usage(FM).free < 50 << 30:
        fail('less than 50 GB free')
    print('data, landlock, disk: ok')
    if not st:  # first launch: the template must run in every configuration
        from fm.evaluation import format_check, score_snapshot
        from fm import score as S
        with tempfile.TemporaryDirectory(dir=FM / 'runs') as td:
            snap = Path(td) / 'snap'
            snap.mkdir()
            shutil.copy2(FM / 'kit/program.py', snap / 'program.py')
            g = format_check(snap, ['ho_long', 'ho_heart', 'test'], Path(td))
            if not all(x['ok'] for x in g.values()):
                fail(f'template fails a configuration: {g}')
            v = S.combine(score_snapshot(snap, VALIDATION, [0], VAL_SCORING_SEEDS, Path(td)), VALIDATION)
            if v is None or not 0 < v <= 100:
                fail(f'template validation {v} outside the scorer range')
            print(f'pipeline: template runs everywhere, validation {v:.2f}')
    if a.skip_agents:
        return
    roles = list({(role['cli'], role['model']): role
                  for role in (cfg['builder'], cfg['improver'], cfg['fallback'])}.values())
    for r in roles:
        if r['cli'] == 'codex':
            out = subprocess.run(['codex', 'login', 'status'], capture_output=True, text=True)
            if 'logged in' not in (out.stdout + out.stderr).lower() or 'not logged in' in (out.stdout + out.stderr).lower():
                fail('codex is not logged in: run  codex login --device-auth')
            if not Path.home().joinpath('.codex/auth.json').exists():
                fail('~/.codex/auth.json missing (file credential store needed)')
        if r['cli'] == 'claude':
            if not Path.home().joinpath('.claude/.credentials.json').exists():
                fail('claude credentials missing')
    target = STAGES['E10.5']['file']
    allowed = STAGES['E9.5']['file']
    check = subprocess.run([sys.executable, '-I', str(FM / 'fm/landlock.py'), '--ro', str(allowed), '--',
                            '/bin/bash', '-c', 'head -c 1 "$1" >/dev/null && ! head -c 1 "$2" 2>/dev/null', 'probe',
                            str(allowed), str(target)], capture_output=True)
    if check.returncode:
        fail('direct sandbox probe did not isolate the target from the allowed stage')
    print('sandbox stage-access probe: ok')
    # live probe of each CLI inside the agent sandbox
    from fm.agents import Agent
    for r in roles:
        if r['cli'] == 'fake':
            continue
        with tempfile.TemporaryDirectory(dir=FM / 'runs') as td:
            rd = Path(td) / 'rounds' / 'probe'
            (rd / 'workspace').mkdir(parents=True)
            (rd / 'evalq').mkdir()
            ag = Agent(dict(r, effort='low'), rd, print)
            res = ag.run(f'Use the shell to run: head -c 1 {target} >/dev/null 2>&1. '
                         'Reply OK if the command fails, or LEAK if it succeeds. '
                         'Use this exact command, which prints no file contents.', 150, 'probe')
            if res.kind == 'limited':
                print(f"{r['cli']}: usage-limited now (the run will pause until {res.reset_at}); continuing")
            elif res.kind != 'done' or res.final_text.strip().upper() != 'OK':
                fail(f"{r['cli']} probe failed: kind={res.kind} text={res.final_text[:200]} detail={res.detail[-500:]}")
            else:
                print(f"{r['cli']} {r['model']}: probe ok ({res.final_text.strip()[:40]})")
    print('PREFLIGHT OK')


if __name__ == '__main__':
    main()
