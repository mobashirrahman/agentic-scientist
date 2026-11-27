"""Agent-track lock for a AgenticScientist run: hashes of every file that defines the run (no human edits after this)."""
import json
import sys
import time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from agentic_scientist.artifacts import file_sha  # noqa: E402
from agentic_scientist.preflight import fingerprint, versions  # noqa: E402

FILES = sorted({str(p.relative_to(ROOT)) for pat in ('agentic_scientist/*.py', 'agentic_scientist/*.sh', 'agentic_scientist/config*.json', 'agentic_scientist/tools/*.py',
                'agentic_scientist/prompts/*.md', 'agentic_scientist/skills/*/*.md', 'agentic_scientist/skills/*/*.py', 'agentic_scientist/skills/INDEX.md',
                'agentic_scientist/seed/*', 'agentic_scientist/seed_final/*', 'agentic_scientist/seed_final_v2/*', 'agentic_scientist/seed_dday/*', 'agentic_scientist/seed_normandy/*', 'agentic_scientist/seed_overlord/*', 'agentic_scientist/data/*', 'agentic_scientist/checks/next_calibration.json', 'agentic_scientist/checks/first_bundle/*.py', 'agentic_scientist/checks/enigma_t3/*', 'humantrack/t2_heart/program.py', 'humantrack/t2_embryo/program.py', 'agentic_scientist/elites/*/*', 'src/**/*.py', 'data/panels/*', 'requirements*.txt',
                'docs/leaderboard/*/*.json')
                for p in ROOT.glob(pat) if p.is_file() and p.name != 'dashboard.py'}
               | {'shinka_ve/harness.py', 'shinka_ve/dynamics.py', 'shinka_ve/fleet_evaluate.py', 'shinka_ve/fleet_hosts.txt',
                  'scripts/export_agent_submission.py', 'scripts/build_coexpr_prior.py', 'scripts/package_evidence.py',
                  'data/external/qiu2024/manifest.json', 'data/external/qiu2024/manifest_late.json', 'data/external/heart_anchor/manifest.json', 'data/external/heart_spatial/manifest.json', 'data/external/embryo_anchor/manifest.json', 'data/external/go_prior/manifest.json', 'data/external/expression_prior/manifest.json', 'data/external/coexpr_prior/manifest.json', 'data/external/ko_validation/manifest.json', 'docs/external_provenance.json', 'agentic_scientist/data/t1_celltype_map.json', 'data/holdout.enc/manifest.tsv', 'agentic_scientist/final.sh', 'agentic_scientist/library/entries.jsonl', 'agentic_scientist/library/global.md', 'agentic_scientist/library/lessons.md', 'agentic_scientist/library_build.py'})
lock_id = time.strftime('mglock_%Y%m%d_%H%M%S')
rec = dict(lock_id=lock_id, created=time.strftime('%Y-%m-%dT%H:%M:%S%z'), note=' '.join(sys.argv[1:]),
           config=json.loads((ROOT / 'agentic_scientist/config.json').read_text()),
           evaluator=fingerprint(), tuner=versions(('optuna', 'torch')),
           files={f: file_sha(ROOT / f) for f in FILES if (ROOT / f).is_file()})
out = ROOT / 'agentic_scientist/locks' / f'{lock_id}.json'
out.parent.mkdir(exist_ok=True)
out.write_text(json.dumps(rec, indent=2) + '\n')
print(out)
