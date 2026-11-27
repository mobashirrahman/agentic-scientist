"""Regression tests for AgenticScientist's selection and restart behavior."""
import json
import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from agentic_scientist import orchestrator
from agentic_scientist.artifacts import write_json


class MorphogenTest(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.run = orchestrator.Run.__new__(orchestrator.Run)
        self.run.dir = self.root
        self.run.state_path = self.root / 'state.json'
        self.run.cfg = dict(acceptance={'alpha': 0.05}, holdout_margin=0.25,
                            holdout_seed_pairs=[[202, 0], [313, 1], [424, 2], [535, 3]], shortlist=3)
        self.run.state = dict(accepted=[], workers={}, impl_stats={}, cost_usd=0, calls=0, global_best=120)
        self.run.eval_revision = 'fixture'
        self.run.lock = {'lock_id': 'fixture'}
        self.run.log = lambda _: None
        self.run.pair_locks = {}

    def workspace(self, name, heart='seed', t3='seed'):
        ws = self.root / name
        ws.mkdir(parents=True)
        (ws / 'program.py').write_text('# Frozen dispatcher\n')
        (ws / 'heart.py').write_text(heart)
        (ws / 'perturbation.py').write_text(t3)
        return ws

    def test_score_worker_failure_leaves_no_plaintext(self):
        import anndata as ad
        import numpy as np
        from shinka_ve import harness
        from vec_local_score import local_score

        stage = ad.AnnData(np.ones((20, 3)))
        other = self.root / 'other-run'
        other.touch()

        def fail(task, preds, target, reference, *, seed, cache, **kwargs):
            for key in [*preds, target, reference]:
                x, *_ = local_score.load_arrays(key, False, np.random.default_rng(seed), 1, 20, cache=cache)
                np.testing.assert_array_equal(x, stage.X)
            raise RuntimeError('injected worker failure')

        with patch.object(harness, 'ROOT', self.root), patch.object(harness, 'load_stage', return_value=stage), \
                patch.object(local_score, 'score_many', side_effect=fail), \
                patch.object(ad.AnnData, 'write_h5ad', side_effect=AssertionError('unexpected write')), \
                self.assertRaisesRegex(RuntimeError, 'injected worker failure'):
            harness.score_split(stage, stage, 'temporal_val', [101])
        self.assertEqual(list(self.root.iterdir()), [other])

    def test_replay_accepted_cycle_once(self):
        seed = self.workspace('seed')
        ws = self.workspace('cycles/w0_c00/ws', t3='candidate')
        start = {'id': 'seed', 'ws': str(seed), 'eval': {'proxy': 120}}
        self.run.state['workers']['w0'] = dict(cycle=0, history=[], fails=0, best=start)
        write_json(ws.parent / 'eval.json', {'proxy': 122})
        write_json(ws.parent / 'outcome.json', dict(verdict='accepted', ws=str(ws),
                                                   proxy=122, boards={}, implementer='test'))
        self.run.cycle('w0', 0)
        self.run.cycle('w0', 0)
        state = json.loads(self.run.state_path.read_text())
        self.assertEqual(state['workers']['w0']['cycle'], 1)
        self.assertEqual(state['workers']['w0']['best']['id'], 'w0_c00')
        self.assertEqual(len(state['accepted']), 1)
        self.assertEqual(state['impl_stats']['test'], [1, 1])

    def test_cache_invalidates_on_workspace_and_lock_changes(self):
        ws = self.workspace('candidate')
        out = self.root / 'eval.json'
        with patch.object(orchestrator.fleet, 'evaluate', return_value={'correct': True}) as evaluate:
            self.run.evaluate_cached(ws, 'dev', out)
            self.run.evaluate_cached(ws, 'dev', out)
            self.assertEqual(evaluate.call_count, 1)
            (ws / 'heart.py').write_text('changed')
            self.run.evaluate_cached(ws, 'dev', out)
            self.run.eval_revision = 'updated scorer'
            self.run.evaluate_cached(ws, 'dev', out)
            self.assertEqual(evaluate.call_count, 3)

    def test_tuning_resume_invalidates_when_program_changes(self):
        from agentic_scientist.tune import Tuner, current_values, read_knobs

        ws = self.workspace('candidate')
        write_json(ws / 'heart_knobs.json', {'tilt': {'low': 0, 'high': 2, 'default': 0.5}})
        scores = []

        def evaluate(workspace, out, *_):
            knobs = read_knobs(workspace, 'heart')
            tilt = current_values(workspace, 'heart', knobs)['tilt']
            scores.append(tilt)
            return {'correct': True, 'boards': {'heart': tilt}}

        def tune():
            return Tuner(ws, 'heart', ['heart_late'], self.root / 'tune', evaluate, self.run.log,
                         rounds=0, parallel=2, top=1, eval_revision='fixture').run()

        original = tune()
        self.assertTrue(original['improved'])
        count = len(scores)
        self.assertEqual(tune()['chosen'], original['chosen'])
        self.assertEqual(len(scores), count)
        (ws / 'heart.py').write_text('changed')
        tune()
        self.assertEqual(len(scores), count * 2)

    def test_resume_does_not_overbook_reserved_cycles(self):
        self.run.cfg.update(workers=4, cycles_per_worker=25, min_cycles_per_worker=16, patience_cycles=12)
        self.run.inflight = {'w0': 34}
        self.run.stop = False
        self.run.state['workers'] = {f'w{i}': {'cycle': c} for i, c in enumerate((35, 34, 8, 8))}
        self.assertFalse(self.run.claim_cycle('w0'))
        self.assertTrue(self.run.claim_cycle('w2'))

    def test_researchers_rotate_and_stagger_across_workers(self):
        self.run.cfg = json.loads((orchestrator.MG / 'config.json').read_text())
        self.run.state['workers'] = {f'w{i}': {'cycle': 0} for i in range(4)}
        for cycle in range(4):
            for i, (worker, state) in enumerate(self.run.state['workers'].items()):
                state['cycle'] = cycle
                role = self.run.role(worker, 'ideator')
                expected = ['gpt-6.2-sol', 'claude-sonnet-5-5'][(i + cycle) % 2]
                self.assertEqual(role['model'], expected)
        self.assertEqual(self.run.cfg['ideator_cycle'][0]['effort'], 'medium')
        self.assertIn('deepseek', self.run.cfg['overflow']['model'])

    def test_composition_respects_threshold_and_all_veto_fallback(self):
        from agentic_scientist.evaluate import SETS, harness

        seed = self.workspace('seed')
        ws = self.workspace('candidate', heart='small gain', t3='vetoed')
        candidate = dict(id='candidate', ws=str(ws), proxy=125)
        self.run.rank_boards = lambda *_: {'heart': [(candidate, 51)], 'perturbation': [(candidate, 60)]}
        (self.root / 'agentic_scientist/library').mkdir(parents=True)
        target = self.root / 'data/raw/t3_fixture'
        target.parent.mkdir(parents=True)
        target.touch()

        def fake_evaluate(workspace, set_name, out, *args, **kwargs):
            if set_name == 'holdout_t3':
                board, score = 'perturbation', 50 if workspace == seed else 47
            else:
                board, score = 'heart', 50 if workspace == seed else 50.01
            return dict(correct=True, boards={board: score}, proxy=score,
                        splits={'heart_e105': dict(board='heart', score=score)})

        with patch.object(orchestrator, 'ROOT', self.root), \
                patch.dict(SETS, holdout={'splits': ['heart_e105']}), \
                patch.dict(harness.SPLITS, unseen_t3=dict(inputs=[], target='t3_fixture')), \
                patch.object(orchestrator.fleet, 'evaluate', side_effect=fake_evaluate):
            self.run.final(seed, {'proxy': 120})
            target.unlink()
            with self.assertRaisesRegex(RuntimeError, 'required T3 veto input'):
                self.run.final(seed, {'proxy': 120})
        final = json.loads((self.root / 'final/final.json').read_text())
        self.assertEqual(final['chosen'], 'seed')
        self.assertTrue(self.run.state['unseen_gene']['candidate']['veto'])
        self.assertEqual((self.root / 'final/selected/perturbation.py').read_text(), 'seed')

    def test_export_uses_selected_tuned_artifact_and_rejects_edits(self):
        import anndata as ad
        import numpy as np
        import scipy.sparse as sp
        import pandas as pd
        from agentic_scientist.artifacts import digest, workspace_manifest
        from scripts import export_agent_submission as export

        name = 'mglock_20261118_000000_fixture'
        run = self.root / 'agentic_scientist/runs' / name
        selected = run / 'final/selected'
        selected.mkdir(parents=True)
        (selected / 'program.py').write_text(
            "def predict(board, stages, times, target, context):\n"
            "    out = stages[0].copy()\n"
            "    out.X[:, 0] = context['params']['tilt']\n"
            "    return out\n")
        write_json(selected / 'perturbation_knobs.json', {'tilt': {'low': 0, 'high': 2, 'default': 0.5}})
        tuned = selected / 'perturbation_tuned.json'
        write_json(tuned, {'params': {'tilt': 1.25}})
        lock_dir = self.root / 'agentic_scientist/locks'
        lock_dir.mkdir()
        lock_id = 'mglock_20261118_000000'
        write_json(lock_dir / f'{lock_id}.json', dict(lock_id=lock_id, evaluator={}, files={}))
        write_json(run / 'final/final.json', dict(lock_id=lock_id, chosen='seed',
                   selected_sha256=digest(workspace_manifest(selected))))
        shutil.copytree(export.ROOT / 'data/panels', self.root / 'data/panels')
        spec = export.BOARDS['T3:bcatenin']
        for name_ in spec['inputs']:
            source = self.root / 'data/raw' / name_
            source.parent.mkdir(parents=True, exist_ok=True)
            source.touch()
        genes = (self.root / 'data/panels/T3__bcatenin.genes.txt').read_text().split()
        stage = ad.AnnData(np.zeros((1000, len(genes)), dtype=np.float32), var=pd.DataFrame(index=genes))
        stage.obsm['spatial_3D'] = np.zeros((1000, 3), dtype=np.float32)
        stage.obsm['spatial_3D'][:, 0] = np.arange(1000)
        with patch.object(export, 'ROOT', self.root), patch.object(export, 'BOARDS', {'T3:bcatenin': spec}), \
                patch.object(export, 'load_stage', return_value=stage), \
                patch.object(export, 'external_context', return_value={}), \
                patch.object(sys, 'argv', ['export', '--run', str(run)]):
            export.main()
            output = next((self.root / 'submissions/agent').rglob('T3__bcatenin.h5ad'))
            self.assertTrue((ad.read_h5ad(output).X[:, 0] == 1.25).all())
            write_json(tuned, {'params': {'tilt': 0.25}})
            with self.assertRaisesRegex(SystemExit, 'workspace differs'):
                export.main()

    def test_config_path_and_digest_bound_on_resume(self):
        from agentic_scientist.artifacts import file_sha
        mg = self.root / 'agentic_scientist'
        mg.mkdir()
        paths = ['agentic_scientist/config.json', 'agentic_scientist/smoke.json']
        for name in paths:
            write_json(self.root / name, {})
        lock = self.root / 'lock.json'
        write_json(lock, dict(lock_id='fixture', files={n: file_sha(self.root / n) for n in paths}))
        with patch.object(orchestrator, 'ROOT', self.root), patch.object(orchestrator, 'MG', mg):
            first = orchestrator.Run(lock, 'run', paths[1])
            self.assertEqual(orchestrator.Run(lock, 'run').state['effective_config']['path'], paths[1])
            with self.assertRaisesRegex(SystemExit, 'Effective config'):
                orchestrator.Run(lock, 'run', paths[0])
            first.state['effective_config']['sha256'] = 'wrong'
            first.save()
            with self.assertRaisesRegex(SystemExit, 'Effective config'):
                orchestrator.Run(lock, 'run', paths[1], final_only=True)
            del first.state['effective_config']
            first.save()
            with self.assertRaisesRegex(SystemExit, 'Effective config'):
                orchestrator.Run(lock, 'run', paths[1])

    def test_evidence_collects_expected_files_and_requires_every_locked_file(self):
        from scripts import package_evidence as evidence
        run = self.root / 'runs/testlock_fixture'
        export = self.root / 'export'
        cycle = run / 'cycles/w0_c00'
        (cycle / 'ws').mkdir(parents=True)
        export.mkdir()
        for file in ('outcome.json', 'ideate.0.prompt.json', 'ideate.0.jsonl', 'unknown.prompt.json',
                     'ws/heart.py', 'ws/extra.txt', 'ws/.env', 'private.log'):
            (cycle / file).touch()
        (cycle / 'hypothesis.json').symlink_to(cycle / 'private.log')
        (export / 'private.json').touch()
        (export / 'manifest.json').touch()
        lock = dict(lock_id='testlock', files={})
        with patch.object(evidence, 'ROOT', self.root):
            kinds = evidence.collect(run, export, lock)
            self.assertEqual({p.name for _, p in kinds['trajectory']}, {'ideate.0.jsonl', 'outcome.json', 'heart.py'})
            self.assertEqual([p.name for _, p in kinds['prompts']], ['ideate.0.prompt.json'])
            self.assertEqual([p.name for _, p in kinds['other']], ['manifest.json'])
            lock['files']['missing.py'] = 'abc'
            self.assertEqual(evidence.verify_harness(kinds, lock), ['missing.py'])
            with self.assertRaisesRegex(FileNotFoundError, 'missing.py'):
                evidence.collect(run, export, lock)

    def test_stream_scan_large_transcript_across_chunk_boundary(self):
        from scripts import package_evidence as evidence
        path = self.root / 'agent.jsonl'
        with path.open('wb') as stream:
            stream.seek(21 * evidence.CHUNK - 4)
            stream.write(b' sk-' + b'X' * 40 + b'\n')
        kinds = dict(trajectory=[('log', path)])
        self.assertEqual(evidence.scan(kinds), ['log: OpenAI-style API key'])
        path.write_bytes(b'OPENAI_API_KEY' + b' ' * 500 + b'=' + b'Y' * 20)
        with patch.object(evidence, 'CHUNK', 32):
            self.assertEqual(evidence.scan(kinds), ['log: API key assignment'])
            for offset in range(32):
                path.write_bytes(b'x' * offset + b'-----BEGIN ' + b'A' * 600 + b' PRIVATE KEY-----')
                self.assertEqual(evidence.scan(kinds), ['log: private key'])

    def test_synthetic_evidence_package_round_trip(self):
        import tarfile
        from scripts import package_evidence as evidence
        lock_id = 'mglock_20000101_000000'
        run = self.root / 'agentic_scientist/runs' / (lock_id + '_fixture')
        export = self.root / 'export'
        cycle = run / 'cycles/w0_c00'
        cycle.mkdir(parents=True)
        export.mkdir()
        (self.root / 'agentic_scientist/locks').mkdir()
        locked = self.root / 'agentic_scientist/config.json'
        write_json(locked, {})
        write_json(self.root / 'agentic_scientist/locks' / (lock_id + '.json'),
                   dict(lock_id=lock_id, files={'agentic_scientist/config.json': evidence.sha256(locked)}))
        write_json(run / 'state.json', {})
        write_json(cycle / 'ideate.0.prompt.json', {})
        write_json(export / 'manifest.json', {})
        with patch.object(evidence, 'ROOT', self.root), patch.object(sys, 'argv', [
                'package', '--run', str(run), '--export', str(export)]):
            evidence.main()
        out = export / 'evidence'
        manifest = json.loads((out / 'MANIFEST.json').read_text())
        for kind, path in [('trajectory', 'run/state.json'), ('harness', 'code/agentic_scientist/config.json'),
                           ('other', 'export/manifest.json'), ('prompts', 'rendered/cycles/w0_c00/ideate.0.prompt.json')]:
            archive = out / (kind + '.tar.gz')
            self.assertEqual(evidence.sha256(archive), manifest['files'][archive.name]['sha256'])
            with tarfile.open(archive) as tar:
                self.assertEqual(json.load(tar.extractfile(path)), {})

    def test_final_shell_propagates_failure_and_removes_plaintext(self):
        repo = self.root / 'repo'
        mg = repo / 'agentic_scientist'
        run = mg / 'runs/fixture_run'
        run.mkdir(parents=True)
        from agentic_scientist.artifacts import file_sha
        write_json(mg / 'alternate.json', {'local_evaluation_only': True})
        binding = dict(path='agentic_scientist/alternate.json', sha256=file_sha(mg / 'alternate.json'))
        write_json(mg / 'other.json', {})
        write_json(repo / 'fixture.json', dict(files={binding['path']: binding['sha256'],
                                                    'agentic_scientist/other.json': file_sha(mg / 'other.json')}))
        write_json(run / 'state.json', dict(phase='awaiting_holdout', effective_config=binding))
        shutil.copyfile(orchestrator.MG / 'artifacts.py', mg / 'artifacts.py')
        shutil.copyfile(orchestrator.MG / 'final.sh', mg / 'final.sh')
        (mg / 'orchestrator.py').write_text("import sys\nassert sys.argv[sys.argv.index('--config') + 1] == 'agentic_scientist/alternate.json'\nraise SystemExit(23)\n")
        (repo / 'shinka_ve').mkdir()
        (repo / 'shinka_ve/fleet_hosts.txt').touch()
        (repo / '.venv/bin').mkdir(parents=True)
        (repo / '.venv/bin/python').symlink_to(sys.executable)
        store = repo / 'data/holdout.enc'
        store.mkdir(parents=True)
        secret = b'fixture-passphrase\n'
        payload = b'fixture holdout'
        source = self.root / 'fixture'
        source.write_bytes(payload)
        encrypted = store / 'fixture.enc'
        subprocess.run(['openssl', 'enc', '-aes-256-cbc', '-pbkdf2', '-iter', '300000', '-pass', 'stdin',
                        '-in', str(source), '-out', str(encrypted)], input=secret, check=True)
        from agentic_scientist.artifacts import file_sha
        (store / 'manifest.tsv').write_text(f'data/raw/fixture\tfixture.enc\t{file_sha(source)}\n')
        # Exercise both host states deterministically inside the synthetic checkout.
        fake_bin = self.root / 'bin'
        fake_bin.mkdir()
        probe = fake_bin / 'pgrep'
        probe.write_text('#!/bin/sh\nexit "$FIXTURE_PGREP_STATUS"\n')
        probe.chmod(0o755)
        env = dict(os.environ, PATH=f"{fake_bin}:{os.environ['PATH']}", FIXTURE_PGREP_STATUS='0')
        cmd = ['bash', str(mg / 'final.sh'), 'fixture.json', 'run', '--no-export']
        refused = subprocess.run(cmd, input=secret, capture_output=True, env=env)
        self.assertIn(b'agent is still running', refused.stdout)
        self.assertFalse((repo / 'data/raw/fixture').exists())
        env['FIXTURE_PGREP_STATUS'] = '1'
        wrong = subprocess.run([*cmd[:-1], 'agentic_scientist/other.json'], input=b'', capture_output=True, env=env)
        self.assertNotEqual(wrong.returncode, 0)
        self.assertIn(b'Effective config', wrong.stderr)
        self.assertFalse((repo / 'data/raw/fixture').exists())
        proc = subprocess.run(cmd, input=secret, capture_output=True, env=env)
        self.assertEqual(proc.returncode, 23, proc.stdout + proc.stderr)
        self.assertFalse((repo / 'data/raw/fixture').exists())

    def test_quick_eval_counter_is_not_a_program_change(self):
        """Turing rejected every cycle: quick_eval's .quick_eval_runs counter counted as a stray workspace file."""
        parent = self.workspace('parent')
        child = self.workspace('child', heart='changed')
        (child / '.quick_eval_runs').write_text('2')
        (child / 'CHANGES.md').write_text('notes')
        (child / 'heart_knobs.json').write_text('{}')
        self.run.cfg['focus'] = {'w1': 'heart'}
        self.run.cfg['free_roam'] = False
        self.run.state['workers'] = {'w1': dict(cycle=0, fails=0, history=[])}
        with patch.object(orchestrator.Run, 'forked', return_value=True):
            self.assertIsNone(self.run.scope('w1', parent, child))
            self.assertEqual(self.run.diff_boards(parent, child), {'heart'})
            (child / 'stray.txt').write_text('x')
            self.assertIn('stray.txt', self.run.scope('w1', parent, child))

    def test_metric_signature_is_checked_against_dev_deltas(self):
        """The knowledge bank records whether the metrics the ideator predicted actually moved."""
        from agentic_scientist.knowledge import line, signature
        split = lambda b, **m: dict(board=b, metrics=m)  # noqa: E731
        parent = dict(correct=True, splits=dict(a=split('heart', mmd_u=40, variogram=50, scale_log_ratio=70),
                                                b=split('heart', mmd_u=42, variogram=52, scale_log_ratio=72),
                                                t=split('temporal', mmd_u=10)))
        cand = dict(correct=True, splits=dict(a=split('heart', mmd_u=45, variogram=49, scale_log_ratio=70.1),
                                              b=split('heart', mmd_u=47, variogram=51, scale_log_ratio=72.1),
                                              t=split('temporal', mmd_u=99)))
        hyp = dict(target_boards=['heart'], metric_signature={'mmd_u': '+', 'variogram': '+', 'scale_log_ratio': '=',
                                                              'occupancy_dice': '+', 'de_score': 'up'})
        sig = signature(hyp, parent, cand)
        self.assertEqual((sig['board'], sig['hit'], sig['n']), ('heart', 2, 3))  # unknown metric / bad symbol skipped
        self.assertFalse(sig['checks']['variogram']['ok'])
        self.assertIsNone(signature(dict(target_boards=['heart']), parent, cand))
        self.assertIsNone(signature(hyp, parent, dict(correct=False)))
        self.assertIn('signature 2/3', line(dict(id='w1_c00', status='confirmed', signature=sig)))

    def test_curation_never_blocks_the_worker(self):
        """GLM curator timeouts held every Turing worker for 15 min per cycle; curation now runs in the background."""
        import threading
        import time as T
        gate, seen = threading.Event(), []
        self.run.curate = lambda cdir, entry: (gate.wait(5), seen.append(entry['id']))
        t0 = T.time()
        self.run.request_curation(self.root, dict(id='c1'))
        self.run.request_curation(self.root, dict(id='c2'))
        self.run.request_curation(self.root, dict(id='c3'))
        self.assertLess(T.time() - t0, 1.0)
        gate.set()
        for _ in range(100):
            if self.run.curate_thread is None:
                break
            T.sleep(0.05)
        self.assertIsNone(self.run.curate_thread)
        self.assertEqual(seen[-1], 'c3')  # coalesced: the newest request is always curated
        self.assertLessEqual(len(seen), 2)

    def test_leaderboard_tool_redacts_target_like_tokens(self):
        sys.path.insert(0, str(Path(orchestrator.ROOT) / 'agentic_scientist/tools'))
        import leaderboard as L
        self.assertEqual(L.clean('P3R4_HEART_CXB_BULKO20_N11547_R5105'), 'P3R4_HEART_CXB_BULKO20_<target-like>_<target-like>')
        self.assertEqual(L.clean('ARC-G v22-e125h-heartward-rms520'), 'ARC-G v22-e125h-heartward-<target-like>')
        self.assertEqual(L.clean('t3-x3-d230'), 't3-x3-d230')
        self.assertEqual(L.family('P3DL8_T3_S50'), L.family('P3DL_T3_C2'))
        self.assertAlmostEqual(L.spearman([1, 2, 3], [10, 20, 30]), 1.0)

    def test_slow_candidates_are_never_rejected_for_speed(self):
        """w3_c07 (Turing) was rejected for taking 802 vs 750 CPU s; runtime is advisory now."""
        self.run.cfg['max_slowdown'] = None
        self.run.seed_eval = dict(splits=dict(temporal_val=dict(cpu_seconds=500)))
        self.assertIsNone(self.run.too_slow(dict(splits=dict(temporal_val=dict(cpu_seconds=5000)))))

    def test_screen_pairs_changed_split_draws_after_splicing(self):
        from agentic_scientist.evaluate import aggregate
        def result(**rows):
            return dict(aggregate(rows), splits=rows, correct=True)
        def split(board, scores):
            from statistics import stdev, mean
            return dict(board=board, score=mean(scores), seed_scores=scores, seed_sd=stdev(scores))

        same = split('temporal', [0, 100, 50])
        parent = result(temporal_val=same, heart_e875=split('heart', [20, 50, 80]),
                        heart_organ_proxy=split('heart', [40, 40, 40]))
        changed = dict(heart_e875=split('heart', [17, 48, 79]), heart_organ_proxy=parent['splits']['heart_organ_proxy'])
        full = result(temporal_val=same, **changed)
        scoped = self.run.splice(parent, result(**changed))
        self.assertEqual(full, scoped)
        stats = self.run.screen_stats(scoped, parent, .05)
        # The two registered heart splits are weighted equally; heart is half of this proxy.
        self.assertAlmostEqual(stats['proxy']['mean'], -0.5)
        self.assertAlmostEqual(stats['proxy']['se'], 0.25 / 3 ** .5)
        self.assertEqual(stats['temporal']['se'], 0)
        self.assertEqual(stats, self.run.screen_stats(full, parent, .05))

    def test_dense_and_sparse_expression_validation(self):
        import anndata as ad
        import numpy as np
        from scipy.sparse import csr_matrix
        from shinka_ve.harness import check

        for wrap in (np.asarray, csr_matrix):
            for value in (1., -1., float('nan'), float('inf')):
                with self.subTest(matrix=wrap, value=value):
                    x = np.ones((1000, 1))
                    x[0, 0] = value
                    pred = ad.AnnData(wrap(x))
                    if value == 1.:
                        check(pred, dict(board='temporal'), pred.var_names)
                    else:
                        with self.assertRaisesRegex(ValueError, 'finite and non-negative'):
                            check(pred, dict(board='temporal'), pred.var_names)

    def test_official_cell_limits_are_enforced_on_dev(self):
        """Turing's T3 emitted 12000 cells, which the official format check rejects (max 7449)."""
        import anndata as ad
        import numpy as np
        import scipy.sparse as sp
        from shinka_ve import harness
        genes = ['a', 'b']
        ok = ad.AnnData(sp.csr_matrix(np.ones((7449, 2), np.float32))); ok.var_names = genes
        big = ad.AnnData(sp.csr_matrix(np.ones((7450, 2), np.float32))); big.var_names = genes
        for a in (ok, big):
            a.obsm['spatial_3D'] = np.zeros((a.n_obs, 3), np.float32)
        harness.check(ok, dict(board='perturbation'), genes)
        with self.assertRaisesRegex(ValueError, '1000-7449'):
            harness.check(big, dict(board='perturbation'), genes)
        harness.check(big, dict(board='heart'), genes)

    def test_t2_structure_gate_reproduces_the_leaderboard(self):
        """Shape credit x min(1, neighbourhood skill/50): the official T2 headline (Astra review, 2026-11-18)."""
        import json
        from shinka_ve.harness import t2_gated
        W = {"de_score": .125, "de_direction": .125, "mmd_u": .15, "variogram": .10, "d2_shape": .25 / 3,
             "occupancy_dice": .25 / 3, "scale_log_ratio": .25 / 3, "neighborhood_mmd": .25}
        f = orchestrator.ROOT / 'tests/fixtures/t2_heart_p3_2026-11-18.json'
        n = 0
        for r in json.loads(f.read_text())['rows']:
            m = r['metrics']
            if r.get('headline') is None or any(m.get(k) is None for k in W):
                continue
            rows = [dict(metric=k, skill=m[k] / 100, points=100 * W[k] * m[k] / 100) for k in W]
            self.assertAlmostEqual(t2_gated(rows), r['headline'], places=3)
            n += 1
        self.assertGreater(n, 100)

    def test_few_target_boards_need_their_own_margin(self):
        A = dict(margin=0.25, board_drop=0.5, board_margin={'heart': 0.5})
        st = dict(proxy=dict(mean=0.3, lb=0.26, ub=0.4, n=9), heart=dict(mean=0.6, lb=0.3, ub=0.9, n=9))
        self.assertFalse(orchestrator.Run.decide(st, A, final=True)[0])
        st['heart']['lb'] = 0.55
        self.assertTrue(orchestrator.Run.decide(st, A, final=True)[0])

    def test_lineage_limit_restarts_from_an_earlier_parent(self):
        self.run.cfg.update(lineage_max=2, elites=3)
        seed = dict(ws='s', eval=dict(proxy=1), id='seed', rank=1)
        deep = dict(ws='d', eval=dict(proxy=3), id='w0_c05', rank=3)
        self.run.state['workers']['w0'] = dict(best=dict(deep), elites=[deep, seed], fails=0)
        self.run.state['depth'] = {'w0_c05': 2}
        parent, note = self.run.choose_parent('w0', 0)
        self.assertEqual(parent['id'], 'seed')
        self.assertIn('DIFFERENT', note)

    def test_lineage_limit_applies_to_rotating_elites(self):
        self.run.cfg.update(lineage_max=2, elites=3)
        pool = [dict(ws=name, id=name, eval=dict(proxy=rank), rank=rank)
                for name, rank in [('best', 3), ('deep', 2), ('seed', 1)]]
        worker = dict(best=pool[0], elites=pool, fails=0)
        self.run.state['workers']['w0'] = worker
        self.run.state['depth'] = dict(best=1, deep=2, seed=0)
        self.assertEqual(self.run.choose_parent('w0', 2)[0]['id'], 'seed')
        worker['fails'] = 2
        self.assertEqual(self.run.choose_parent('w0', 0)[0]['id'], 'seed')

    def test_ablation_prefers_an_equally_good_parent(self):
        """A stacked edit that does not beat its own accepted parent on the holdout by ablation_tol is dropped."""
        import json
        seed = self.workspace('seed')
        a = self.workspace('a', heart='a')
        b = self.workspace('b', heart='b')
        c = self.workspace('c', heart='c')
        fdir = self.root / 'final'
        fdir.mkdir()
        self.run.cfg.update(holdout_margin=0.0, ablation_tol=0.25)
        self.run.state['parent'] = {'b': 'a', 'a': 'seed'}
        for name, h in [('seed', 50.0), ('a', 52.0), ('b', 52.1), ('c', 51.7)]:
            for j in range(4):
                (fdir / f'holdout_{name}_pair{j}.json').write_text(json.dumps(
                    dict(correct=True, proxy=h / 2 + 0.01 * j, boards=dict(heart=h + 0.01 * j))))
        rows = [dict(id='seed', ws=str(seed), holdout=1, holdout_boards={'heart': 50}),
                dict(id='a', ws=str(a), holdout=1), dict(id='b', ws=str(b), holdout=1)]
        from itertools import permutations
        rows.append(dict(id='c', ws=str(c), holdout=1))
        for order in permutations(rows[1:]):
            ranked = [rows[0], *order]
            self.assertEqual(self.run.per_board(ranked, fdir, 4)['heart'][0]['id'], 'a')
            with patch.object(self.run, 'guard_ok', side_effect=lambda r, *_: r['id'] != 'a'):
                self.assertEqual(self.run.per_board(ranked, fdir, 4)['heart'][0]['id'], 'b')

    def test_guard_cache_binds_inputs(self):
        from agentic_scientist.evaluate import GUARD
        row = dict(id='a', ws=str(self.workspace('a')))
        self.run.cfg['guard'] = dict(boards=['heart'], pairs=[[301, 0], [302, 1]])
        result = dict(correct=True, proxy=10, boards={'heart': 20})
        with patch.object(orchestrator.fleet, 'evaluate', return_value=result) as evaluate:
            self.run.guard_ok(row, row, 'heart', self.root)
            self.run.guard_ok(row, row, 'heart', self.root)
            self.assertEqual(evaluate.call_count, 2)
            (Path(row['ws']) / 'heart.py').write_text('new')
            self.run.guard_ok(row, row, 'heart', self.root)
            self.run.eval_revision = 'new'
            self.run.guard_ok(row, row, 'heart', self.root)
            self.run.cfg['guard']['pairs'][0] = [303, 1]
            self.run.guard_ok(row, row, 'heart', self.root)
            with patch.dict(GUARD, heart=['another_split']):
                self.run.guard_ok(row, row, 'heart', self.root)
            self.assertEqual(evaluate.call_count, 9)

    def test_brief_and_focus_follow_configured_board_transition(self):
        self.run.cfg = json.loads((orchestrator.MG / 'config.json').read_text())
        brief = self.run.render_brief()
        self.assertIn(', '.join(r['model'] for r in self.run.cfg['ideator_cycle']), brief)
        self.assertIn('w3 — embryo → embryo → temporal', brief)
        self.assertIn('earlier bracket for embryo', brief)
        for i, board in enumerate(['embryo', 'embryo', 'temporal', 'temporal']):
            self.run.state['workers']['w3'] = dict(cycle=i, fails=0)
            self.assertIn(f'**{board}**', self.run.focus_text('w3'))
            self.assertIn(self.run.cfg['directives']['w3'][board], self.run.focus_text('w3'))
        self.assertIn('gene-blind', self.run.cfg['directives']['w1'])
        self.run.cfg['focus']['w3'] = 'heart'
        self.assertIn('w3 — heart', self.run.render_brief())

    def test_planner_runs_after_every_n_finished_cycles(self):
        calls = []
        def fake_agent(role, prompt, cwd, transcript, **kwargs):
            calls.append(role['model'])
            (Path(cwd) / 'plan.md').write_text('failed draft' if len(calls) == 1 else 'T3: keep response magnitude')
            return len(calls) > 1
        self.run.agent = fake_agent
        self.run.cfg.update(planner_every=2, planner=dict(cli='codex', model='gpt-6.2-sol', timeout_s=60), curator=dict(model='c'))
        ev = dict(boards=dict(heart=50.0))
        self.run.state['workers'] = {w: dict(history=[], best=dict(id='seed', eval=ev)) for w in ('w0', 'w1')}
        self.run.focus = lambda w: 'heart'
        self.run.maybe_plan()
        self.assertEqual(calls, [])
        for w in ('w0', 'w1'):
            self.run.state['workers'][w]['history'].append(dict(title='t', verdict='rejected', reason='r'))
        self.run.maybe_plan()
        self.run.plan_thread.join(10)
        self.assertEqual(calls, ['gpt-6.2-sol'])
        self.assertFalse((self.root / 'plan.md').exists())
        self.assertNotIn('planned', self.run.state)
        self.run.maybe_plan()
        self.run.plan_thread.join(10)
        self.assertEqual(json.loads(self.run.state_path.read_text())['planned'], 1)
        self.assertIn('response magnitude', (self.root / 'plan.md').read_text())
        self.run.maybe_plan()
        self.assertEqual(len(calls), 2)

    def test_feulner_target_partition_and_replicate_weighting(self):
        import anndata as ad
        import numpy as np
        from agentic_scientist.tools.feulner_forecast import forecast
        from shinka_ve import harness

        path = self.root / harness.FEULNER
        a = ad.AnnData(np.ones((3000, 2), dtype=np.float32))
        a.var_names = ['Myl7', 'Gata1']
        a.obs['stage_days'] = np.repeat([14.5, 16.5, 18.5], 1000)
        a.obs['replicate'] = ['r1'] * 2900 + ['r2'] * 100
        a.X[-100:, 1] = 40
        a.write_h5ad(path)
        write_json(self.root / 'manifest.json', dict(files={path.name: dict(
            stages_days=[14.5, 16.5, 18.5], values='counts', perturbation=False)}))
        inputs = harness.load_anchor(self.root, [path], a.var_names)
        self.assertEqual(set(inputs.obs.stage_days), {14.5, 16.5})
        predicted = []
        def predict(board, stages, times, day, ctx):
            self.assertEqual((times, day), ([14.5, 16.5], 18.5))
            self.assertEqual([s.n_obs for s in stages], [1000, 1000])
            self.assertIsNone(ctx['external'])
            self.assertIsNone(ctx['external_spatial'])
            pred = stages[-1].copy()
            pred.X[:, 0] *= 0.5
            predicted.append(True)
            return pred
        def target():
            self.assertTrue(predicted)
            return harness.load_anchor(self.root, [path], a.var_names, feulner_days=[18.5])
        report = forecast(predict, inputs[:1000], inputs[1000:], target, 101, {})
        gains = [r['profiles']['all']['gain'] for r in report['replicates'].values()]
        self.assertNotEqual(gains[0], gains[1])
        self.assertAlmostEqual(report['gain'], sum(gains) / 2)

    def test_wall_budget_counts_quota_pauses_and_bounds_fleet(self):
        import time
        cfg = json.loads((orchestrator.MG / 'config.json').read_text())
        self.run.cfg.update(cfg)
        self.run.stop = False
        self.run.inflight = {}
        self.run.state.update(research_started=1000, paused_s=24 * 3600)
        self.run.state['workers'] = {f'w{i}': dict(cycle=0) for i in range(4)}
        clock = [1000 + 24 * 3600]
        def advance(seconds):
            clock[0] += seconds
        deadline = 1000 + 28 * 3600
        with patch.object(time, 'time', side_effect=lambda: clock[0]), patch.object(time, 'sleep', side_effect=advance):
            self.assertFalse(self.run.claim_cycle('w0'))
            with patch.object(orchestrator.fleet, 'evaluate', return_value={}) as evaluate:
                self.run.evaluate('ws', 'dev', 'out')
                self.assertEqual(evaluate.call_args.kwargs['deadline'], deadline)
            self.run.state['limited_until'] = dict(codex=deadline + 3600)
            self.run.cfg.pop('overflow', None)
            clock[0] = deadline - 2
            with self.assertRaises(orchestrator.fleet.DeadlineReached):
                self.run.unlimited_role(dict(cli='codex', timeout_s=60), ideation=False)
            self.assertEqual(clock[0], deadline)
            with patch.object(orchestrator.fleet, 'claim') as claim:
                with self.assertRaises(orchestrator.fleet.DeadlineReached):
                    self.run.evaluate(self.root, 'dev', self.root / 'out')
                claim.assert_not_called()
            self.run.final_only = True
            self.assertIsNone(self.run.research_deadline())

    def test_usage_limit_pauses_until_reset(self):
        """No downgrade: with every ideator out of quota the worker sleeps until the earliest reset, then resumes."""
        import time as T
        self.run.cfg.update(workers=4, ideator_cycle=[dict(cli='codex', model='g'), dict(cli='claude', model='c')],
                            implementers=[dict(cli='opencode', model='ds')])
        self.run.state['claude_off'] = True
        self.run.save = lambda: None
        self.run.stop = False
        self.run.mark_limited('codex', 'You have hit your usage limit ... try again at 4:40 AM.')
        self.assertTrue(self.run.limited('codex'))
        self.run.mark_limited('codex', '', until=T.time() + 2)
        self.run.state['limited_until']['codex'] = T.time() + 2
        t0 = T.time()
        role = self.run.unlimited_role(dict(cli='codex', model='g', timeout_s=9), ideation=True)
        self.assertGreaterEqual(T.time() - t0, 1.5)
        self.assertEqual((role['cli'], role['model'], role['timeout_s']), ('codex', 'g', 9))
        self.assertGreater(self.run.state['paused_s'], 0)
        self.run.state['claude_off'] = False
        self.run.state['limited_until']['codex'] = T.time() + 999
        role = self.run.unlimited_role(dict(cli='codex', model='g', timeout_s=9), ideation=True)
        self.assertEqual(role['cli'], 'claude')  # another ideator with quota is used without waiting

    def test_lit_mcp_protocol_offline(self):
        import subprocess as sp
        srv = str(Path(__file__).resolve().parents[1] / 'agentic_scientist/tools/lit_mcp.py')
        msgs = [dict(jsonrpc='2.0', id=1, method='initialize', params=dict(protocolVersion='2025-06-18')),
                dict(jsonrpc='2.0', method='notifications/initialized'),
                dict(jsonrpc='2.0', id=2, method='tools/list'),
                dict(jsonrpc='2.0', id=3, method='tools/call', params=dict(name='nope', arguments={}))]
        out = sp.run([sys.executable, '-I', srv], input='\n'.join(json.dumps(m) for m in msgs) + '\n',
                     capture_output=True, text=True, timeout=30).stdout.splitlines()
        r = [json.loads(x) for x in out]
        self.assertEqual([x['id'] for x in r], [1, 2, 3])
        self.assertEqual(r[0]['result']['serverInfo']['name'], 'lit')
        names = {t['name'] for t in r[1]['result']['tools']}
        self.assertTrue({'pubmed', 'search', 'fulltext', 'page', 'openalex', 'arxiv'} <= names)
        self.assertIn('error', r[2])
