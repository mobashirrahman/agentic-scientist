"""Launch one locked ShinkaEvolve run for the Virtual Embryo task.

  .venv/bin/python shinka_ve/run_evo.py --lock shinka_ve/locks/<lock>.json --run-name bio06_a

Refuses to start unless every locked file hash still matches (Agent-track lock).
"""
import argparse, hashlib, json, os, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from shinka.core import EvolutionConfig, ShinkaEvolveRunner
from shinka.database import DatabaseConfig
from shinka.launch import LocalJobConfig


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--lock', required=True)
    ap.add_argument('--run-name', required=True)
    a = ap.parse_args()
    lock = json.loads(Path(a.lock).read_text())
    for rel, h in lock['files'].items():
        if sha(ROOT / rel) != h:
            sys.exit(f'Lock violation: {rel} changed since lock')
    cfg = lock['config']
    task = ROOT / 'shinka_ve'
    os.environ.update({
        'VE_ROOT': str(ROOT), 'VE_SCORING_SEEDS': cfg['scoring_seeds'],
        'VE_EVAL_WORKERS': str(cfg['eval_workers_per_job']),
        'SHINKA_HEADLESS_COMMAND': f'{sys.executable} {task / "limit_wrapper.py"}',
        'SHINKA_HEADLESS_TIMEOUT': str(cfg['limit_max_wait_s'] + 3600),
        'VE_LIMIT_WAIT_STEP': str(cfg['limit_wait_step_s']), 'VE_LIMIT_MAX_WAIT': str(cfg['limit_max_wait_s']),
    })
    for agent in ('codex', 'claude'):
        if cfg['fallback'].get(f'{agent}_model'):
            os.environ[f'VE_FALLBACK_{agent.upper()}_MODEL'] = cfg['fallback'][f'{agent}_model']
    results = ROOT / 'shinka_ve/runs' / f"{lock['lock_id']}_{a.run_name}"
    results.mkdir(parents=True, exist_ok=True)
    os.environ['VE_LIMIT_LOG'] = str(results / 'limit_events.jsonl')
    evo = EvolutionConfig(
        task_sys_msg=(task / 'task_prompt.md').read_text(),
        patch_types=cfg['patch_types'], patch_type_probs=cfg['patch_type_probs'],
        num_generations=cfg['num_generations'], llm_models=cfg['llm_models'],
        llm_dynamic_selection=cfg['llm_dynamic_selection'], embedding_model=cfg['embedding_model'],
        use_text_feedback=cfg['use_text_feedback'], max_api_costs=cfg['max_api_costs'],
        init_program_path=str(task / 'initial.py'), results_dir=str(results), language='python',
        job_type='local')
    job = LocalJobConfig(eval_program_path=str(task / 'fleet_evaluate.py'), time=cfg['eval_time_limit'])
    db = DatabaseConfig(db_path='evolution_db.sqlite', num_islands=cfg['num_islands'],
                        archive_size=cfg['archive_size'])
    ShinkaEvolveRunner(evo_config=evo, job_config=job, db_config=db,
                       max_evaluation_jobs=cfg['max_evaluation_jobs'],
                       max_proposal_jobs=cfg['max_proposal_jobs'], verbose=True).run()


if __name__ == '__main__':
    main()
