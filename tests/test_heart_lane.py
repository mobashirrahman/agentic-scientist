"""Regression tests for the active isolated lane."""
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'focused/heart'))

from fm import common, final
from fm.evaluation import snapshot


class ReplayTests(unittest.TestCase):
    def test_snapshot_excludes_linked_files_and_directories(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace = root / 'workspace'
            workspace.mkdir()
            (workspace / 'program.py').write_text('pass\n')
            (root / 'outside.txt').write_text('outside')
            (workspace / 'linked.txt').symlink_to(root / 'outside.txt')
            (workspace / 'linked_dir').symlink_to(root, target_is_directory=True)
            copied = root / 'snapshot'
            snapshot(workspace, copied)
            self.assertEqual(sorted(p.name for p in copied.iterdir()), ['program.py'])

    def test_final_selection_rejects_seed_regression(self):
        def values(score, seeds=None):
            return dict(score=score, pred_seed_scores=seeds or [score, score])

        class Fleet:
            hosts = []

            @staticmethod
            def score(snap, splits, *args):
                primary = {'copy_last': 50, 'crop': 55, 'crop_scale': 56,
                           'historical_focused': 60, 'run_a': 63, 'run_b': 64}[snap.name]
                if 'val_heart' in splits:
                    return {'val_heart': values(62), 'val_all': values(60)}
                seeds = [59, 69] if snap.name == 'run_b' else None
                return {'ho_long': values(primary, seeds), 'ho_heart': values(61)}

        with TemporaryDirectory() as tmp:
            run = type('RunFixture', (), {'dir': Path(tmp), 'fleet': Fleet(), 'log': staticmethod(lambda *args: None)})()
            run.state = {'rounds': {
                str(i): {'checkpoint': {'snapshot': name, 'round': i, 'hash': str(i), 'model': 'fixture'}}
                for i, name in enumerate(('run_a', 'run_b'))
            }}
            folder = run.dir / 'final'
            folder.mkdir()
            path = folder / 'selection.json'
            final.select(run, folder, path)
            selected = common.read_json(path)
            self.assertEqual(selected['reference'], 'final/controls/historical_focused')
            self.assertEqual(selected['selected'], 'run_a')
            self.assertNotIn('run_b', selected['ranking'])
            self.assertNotIn(selected['reference'], selected['ranking'])


if __name__ == '__main__':
    unittest.main()
