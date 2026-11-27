"""Frozen AgenticScientist evaluator. NOT editable by agents (part of the AgenticScientist lock).

Scores a free-form workspace (program.py + any helper .py) on a split set.

  .venv/bin/python agentic_scientist/evaluate.py --workspace W --set dev|holdout|quick [--splits a,b] --out result.json

proxy = T1 + T3 + 0.5*heart + 0.5*embryo, each board the mean over its splits in the set.
"""
import argparse
import importlib.util
import json
import multiprocessing as mp
import os
import re
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault('OMP_NUM_THREADS', '2')
os.environ.setdefault('OPENBLAS_NUM_THREADS', '2')

from shinka_ve import harness  # noqa: E402
from agentic_scientist.artifacts import write_json  # noqa: E402

# Long-horizon heart forecast (1 day past the last input, like the E10.5 test horizon): catches extrapolations that overshoot.
harness.SPLITS['heart_long'] = dict(board='heart', task='T2', setting='heart', inputs=['T2/E8.25_late.h5ad', 'T2/E8.5.h5ad'],
                                    times=[8.25, 8.5], target='T2/E9.5.h5ad', time=9.5)
# Different knockout gene, WT stages only: tests cross-gene generalisation of the T3 model.
harness.SPLITS['mab21l2_e95'] = dict(board='perturbation', task='T3', inputs=['T2/E8.75.h5ad', 'T2/E9.5.h5ad'],
                                     times=[8.75, 9.5], target='T3/E9.5_mab21l2_ko.h5ad', time=9.5,
                                     knockout='Mab21l2', weight=2)  # one split = one gene; Gata4's two replicates weigh 1 each
# External knockout validation (public, wild type matched in the same experiment, all stages <= E9.5; built by
# scripts/build_ko_validation.py; disclosed in docs/EXTERNAL_SOURCES.md). scRNA-seq heart-region dissections: panel genes
# only, no coordinates (obsm['spatial_3D'] is all zeros), cell types by label transfer from the released MERFISH stages.
_KO = '../external/ko_validation'
harness.SPLITS['hand2_e825'] = dict(board='perturbation', task='T3', inputs=[f'{_KO}/hand2/wt_E7.75.h5ad', f'{_KO}/hand2/wt_E8.25.h5ad'],
                                    times=[7.75, 8.25], target=f'{_KO}/hand2/ko_E8.25.h5ad', time=8.25, knockout='Hand2')
harness.SPLITS['hand2_e925'] = dict(board='perturbation', task='T3', inputs=[f'{_KO}/hand2/wt_E8.25.h5ad', f'{_KO}/hand2/wt_E9.25.h5ad'],
                                    times=[8.25, 9.25], target=f'{_KO}/hand2/ko_E9.25.h5ad', time=9.25, knockout='Hand2')
# One more external knockout gene (same layout, built by scripts/build_ko_validation.py mef2c):
# Mef2c-null heart tube snRNA (GSE280543, 2 embryos per genotype per stage). Same shape as gata4_*: WT brackets -> KO.
# (Nkx2-5, GSE76118, was built and dropped: too few cells per cell type for the official T3 scorer.)
harness.SPLITS['mef2c_e90'] = dict(board='perturbation', task='T3', inputs=[f'{_KO}/mef2c/wt_E8.5.h5ad', f'{_KO}/mef2c/wt_E9.h5ad'],
                                   times=[8.5, 9.0], target=f'{_KO}/mef2c/ko_E9.h5ad', time=9.0, knockout='Mef2c')
# Forward-time Mef2c E8.5 split (fixed for Run #2 using GSE280543 E7.75 WT replicates GSM8600334/GSM8600337).
harness.SPLITS['mef2c_e85'] = dict(board='perturbation', task='T3', inputs=[f'{_KO}/mef2c/wt_E7.75.h5ad', f'{_KO}/mef2c/wt_E8.5.h5ad'],
                                   times=[7.75, 8.5], target=f'{_KO}/mef2c/ko_E8.5.h5ad', time=8.5, knockout='Mef2c')
# Unseen-gene T3 check (final selection only): one more knockout gene, never shown to agents. Its files AND its identity
# (unseen_spec.json: gene, stages) are encrypted in data/holdout.enc and exist only while final.sh runs, so nothing in
# the repo names the gene. Used as a VETO on the dev-best T3 code (orchestrator.unseen_veto), never to select.
_UNSEEN = Path(__file__).resolve().parents[1] / 'data/raw/T3/unseen_spec.json'
if os.environ.get('MG_PRIVATE_FINAL') == '1' and _UNSEEN.exists():
    _u = json.loads(_UNSEEN.read_text())
    harness.SPLITS['unseen_t3'] = dict(board='perturbation', task='T3', inputs=['T3/unseen_wt_a.h5ad', 'T3/unseen_wt_b.h5ad'],
                                       times=_u['times'], target='T3/unseen_ko.h5ad', time=_u['time'], knockout=_u['knockout'])
# Heart, different target stage (E8.75): heart gains must hold on more than one target (all other heart dev splits hit E9.5).
harness.SPLITS['heart_e875'] = dict(board='heart', task='T2', setting='heart', inputs=['T2/E8.25_late.h5ad', 'T2/E8.5.h5ad'],
                                    times=[8.25, 8.5], target='T2/E8.75.h5ad', time=8.75)
# Holdout only: 2-day heart jump (E8.25+E8.5 -> E10.5), the closest allowed analogue of the E12.5 test.
harness.SPLITS['heart_e105_long'] = dict(board='heart', task='T2', setting='heart', inputs=['T2/E8.25_late.h5ad', 'T2/E8.5.h5ad'],
                                         times=[8.25, 8.5], target='T2/E10.5.h5ad', time=10.5)
# Sanity (no truth): 3-day forecasts past the last released stage; checked for plausibility, never scored.
harness.SPLITS['temporal_3d'] = dict(board='temporal', task='T1', inputs=['T1/E8.5_RNA.h5ad', 'T1/E9.5_RNA.h5ad'],
                                     times=[8.5, 9.5], target='T1/E9.5_RNA.h5ad', time=12.5,
                                     sampling='heart_chambers')
harness.SPLITS['heart_3d'] = dict(board='heart', task='T2', setting='heart', inputs=['T2/E8.75.h5ad', 'T2/E9.5.h5ad'],
                                  times=[8.75, 9.5], target='T2/E9.5.h5ad', time=12.5,
                                  sampling='heart_dissected')
import json as _json  # noqa: E402
_T1MAP = _json.loads((ROOT / 'agentic_scientist/data/t1_celltype_map.json').read_text())
# T1 protocol-matched split: the E12.5 test target is the heart chambers only (organisers), so the E10.5 target is
# restricted to cardiac cell types and the program is told sampling='heart_chambers'.
harness.SPLITS['temporal_heartonly'] = dict(harness.SPLITS['temporal_val'], target_types=_T1MAP['cardiac'],
                                            sampling='heart_chambers', weight=0.80)
harness.SPLITS['temporal_val']['weight'] = 0.20
# Normandy: composition-matched T1 Dev target (see harness target_match). The unmatched heart-only split
# rewarded continuing the E9.5->E10.5 lineage jump, which the TEST punished; it is no longer in the Dev set (three parallel T1 jobs exceed a fleet host's memory).
harness.SPLITS['temporal_matched'] = dict(harness.SPLITS['temporal_heartonly'], target_match='t1_lineage', weight=0.80)
harness.SPLITS['temporal_heartonly']['weight'] = 0.10
# True 2-day dissected-heart T1 holdout (Landlock-protected Feulner E14.5+E16.5 -> E18.5).
harness.SPLITS['t1_guard_2d'] = dict(board='temporal', task='T1',
                                     inputs=['T1/guard_E14.5.h5ad', 'T1/guard_E16.5.h5ad'],
                                     times=[14.5, 16.5], target='T1/guard_E18.5.h5ad', time=18.5,
                                     sampling='heart_chambers')
# Unfiltered E10.5 MERFISH is the closest released whole-organ dissection.
# The E9.5 organ labels provide a development-only approximation of that protocol.
harness.SPLITS['heart_e105']['sampling'] = 'heart_dissected'
harness.SPLITS['heart_e105_long']['sampling'] = 'heart_dissected'
harness.SPLITS['heart_organ_proxy'] = dict(harness.SPLITS['heart_late'], target_filter='t2_organ',
                                          sampling='heart_dissected')
# Dissected E8.75 heart (organ-resident cells only) and 1-day long-horizon dissected E9.5 heart.
harness.SPLITS['heart_e875_organ'] = dict(harness.SPLITS['heart_e875'], target_filter='t2_organ',
                                          sampling='heart_dissected')
harness.SPLITS['heart_long_organ'] = dict(harness.SPLITS['heart_long'], target_filter='t2_organ',
                                          sampling='heart_dissected')
HEART_TARGETS = {'e875': ['heart_e875'], 'e95': ['heart_early', 'heart_late', 'heart_long'],
                 'organ_proxy': ['heart_organ_proxy'], 'e875_organ': ['heart_e875_organ'],
                 'long_organ': ['heart_long_organ']}
# Embryo: guard_embryo_e80 (E7.25+E8.25_late -> E8.0, full depth & full shape scoring) carries 65% of Embryo Dev;
# embryo_early (E6.75+E8.0 -> E7.25, shallow E6.75) carries 35% with no_shape, and native_occupancy >= 0.97 is gated.
harness.SPLITS['embryo_early']['score_mode'] = 'no_shape'
harness.SPLITS['embryo_early']['weight'] = 0.35
harness.SPLITS['guard_embryo_e80'] = dict(board='embryo', task='T2', setting='embryo', inputs=['T2/E7.25.h5ad', 'T2/E8.25_late.h5ad'],
                                          times=[7.25, 8.25], target='T2/E8.0.h5ad', time=8.0, weight=0.65)
SETS = {
    'dev': dict(splits=['temporal_val', 'temporal_matched', 'heart_early', 'heart_late', 'heart_long', 'heart_e875', 'heart_organ_proxy', 'heart_e875_organ', 'heart_long_organ', 'embryo_early', 'guard_embryo_e80', 'gata4_1', 'gata4_2', 'mab21l2_e95', 'hand2_e825', 'hand2_e925', 'mef2c_e90', 'mef2c_e85'],
                seed=101, scoring_seeds=[101, 102, 103]),
    # Test-aligned holdouts for T1 (2-day dissected E14.5+E16.5 -> E18.5), Heart (dissected E10.5 organ/long), Embryo (E7.5).
    'holdout': dict(splits=['t1_guard_2d', 'heart_e105_organ', 'heart_e105_long_organ', 'heart_e105_long_region', 'embryo_late'],
                    seed=202, scoring_seeds=[201, 202, 203]),
}
harness.SPLITS['heart_e105_organ'] = dict(harness.SPLITS['heart_e105'], target_filter='t2_organ', sampling='heart_dissected', weight=0.02)  # ladder: ranks a whole-section copy (public 48.8) above the organ crops (TEST 65-66)
harness.SPLITS['heart_e105_long_organ'] = dict(harness.SPLITS['heart_e105_long'], target_filter='t2_organ',
                                               sampling='heart_dissected', weight=0.49)
harness.SPLITS['heart_e105_region'] = dict(harness.SPLITS['heart_e105'], target_filter='t2_region', sampling='heart_dissected')
harness.SPLITS['heart_e105_long_region'] = dict(harness.SPLITS['heart_e105_long'], target_filter='t2_region',
                                                sampling='heart_dissected', weight=0.49)  # spatial (label-free) target: the least circular fold
SETS['holdout_t3'] = dict(splits=['unseen_t3'], seed=202, scoring_seeds=[201, 202, 203])  # veto only, see orchestrator.unseen_veto
# Hidden guard splits (kept defined for compatibility).
harness.SPLITS['guard_heart_e85'] = dict(board='heart', task='T2', setting='heart', inputs=['T2/E8.0.h5ad', 'T2/E8.25_late.h5ad'],
                                         times=[8.0, 8.25], target='T2/E8.5.h5ad', time=8.5)
harness.SPLITS['guard_heart_e85_dis'] = dict(harness.SPLITS['guard_heart_e85'], sampling='heart_dissected', target_filter='t2_organ')
SETS['guard'] = dict(splits=['guard_heart_e85', 'guard_heart_e85_dis', 'guard_embryo_e80'], seed=301,
                     scoring_seeds=[301, 302, 303])
GUARD = {'heart': ['guard_heart_e85', 'guard_heart_e85_dis'], 'embryo': ['guard_embryo_e80']}
# Test-aligned Heart Dev weights: 75% dissected (long_organ 0.30, organ_proxy 0.25, e875_organ 0.20), 25% whole-section.
for _s, _w in dict(heart_long_organ=0.30, heart_organ_proxy=0.25, heart_e875_organ=0.20,
                   heart_e875=0.10, heart_early=0.05, heart_late=0.05, heart_long=0.05).items():
    harness.SPLITS[_s]['weight'] = _w
SETS['sanity'] = dict(splits=['temporal_3d', 'heart_3d'], seed=101, scoring_seeds=[101])
harness.SPLITS['temporal_test_composition'] = dict(
    board='temporal', task='T1', inputs=['T1/E8.5_RNA.h5ad', 'T1/E9.5_RNA.h5ad', 'T1/E10.5_RNA.h5ad'],
    times=[8.5, 9.5, 10.5], time=12.5, sampling='heart_chambers')
SETS['composition'] = dict(splits=['temporal_test_composition'], seed=42, scoring_seeds=[])
SETS['quick'] = dict(splits=SETS['dev']['splits'], seed=101, scoring_seeds=[101])
WEIGHTS = harness.WEIGHTS
EXTRA_FORBIDDEN = [r'load_stage', r'\bharness\b', r'SPLITS', r'src\.data', r'sys\.modules', r'globals\s*\(',
                   r'vec_local_score', r'score_many', r'\binspect\b', r'agentic_scientist\.evaluate', r'\bopen\s*\(']


def screen_workspace(ws: Path, *, historical=False):
    files = sorted(ws.rglob('*.py'))
    if not (ws / 'program.py').exists():
        return 'program.py missing'
    for f in files:
        src = f.read_text(errors='replace')
        err = harness.screen(src)
        if not err:
            err = next((f'Forbidden pattern in program: {p}' for p in EXTRA_FORBIDDEN if re.search(p, src)), None)
        if not err and not historical and f.stem.split('_')[0] == 'temporal':
            if re.search(r'14\.7\s*%|0\.147\b|23\.5\s*%|0\.235\b', src):
                err = 'literal T1 target fraction from historical diagnostics'
        if err:
            return f'{f.relative_to(ws)}: {err}'
    return None


def load(ws: Path):
    sys.path.insert(0, str(ws))
    spec = importlib.util.spec_from_file_location('bra_program', ws / 'program.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _cpu():
    """CPU seconds of this worker process (user + system, all threads). Each job runs in its own process
    (maxtasksperchild=1), so this is the job's compute, independent of how loaded the fleet host is."""
    import resource
    r = resource.getrusage(resource.RUSAGE_SELF)
    return round(r.ru_utime + r.ru_stime, 1)


def load_params(ws):
    """{board: knob values} for context['params']: <board>_tuned.json (written only by the harness tuner) restricted to
    the knobs <board>_knobs.json still declares; the legacy shared tuned_params.json is the fallback."""
    ws, out = Path(ws), {}
    legacy = ws / 'tuned_params.json'
    if legacy.exists():
        out = json.loads(legacy.read_text())
    for f in ws.glob('*_tuned.json'):
        b = f.name[:-len('_tuned.json')]
        kf = ws / f'{b}_knobs.json'
        declared = set(json.loads(kf.read_text())) if kf.exists() else set()
        out[b] = {k: v for k, v in (json.loads(f.read_text()).get('params') or {}).items() if k in declared}
    return out


def _one(args):
    ws, split, seed, scoring_seeds, fit_seed = args
    t0 = time.time()
    try:
        mod = load(Path(ws))
        params = load_params(ws)  # knob values chosen by the harness tuner (agentic_scientist/tune.py); {} = defaults
        pred, ref = harness.run_split(mod, split, seed, fit_seed, params)
        if split == 'temporal_test_composition':
            from agentic_scientist.composition import blood_guard
            # Blood guard: the E12.5 forecast's blood-like share may not exceed the last input's (E10.5).
            return dict(split=split, board='temporal', composition=blood_guard(pred, ref))
        if split.endswith('_3d'):
            from agentic_scientist.sanity import plausibility
            return dict(split=split, board=harness.SPLITS[split]['board'], sanity=plausibility(pred, split),
                        seconds=round(time.time() - t0, 1))
        # Score each scoring seed separately so the knowledge bank can judge effects against noise.
        per_seed, per_metrics = [], []
        for s in scoring_seeds:
            sc, m = harness.score_split(pred, ref, split, [s])
            per_seed.append(sc)
            per_metrics.append(m)
        score = sum(per_seed) / len(per_seed)
        metrics = {k: sum(m.get(k, 0) for m in per_metrics) / len(per_metrics) for k in per_metrics[0]}
        sd = (sum((x - score) ** 2 for x in per_seed) / (len(per_seed) - 1)) ** .5 if len(per_seed) > 1 else None
        out_board = harness.SPLITS[split]['board']
        if out_board == 'embryo':  # official occupancy of the prediction against each input embryo (1 = native)
            from agentic_scientist.native import native_occupancy
            metrics['native_occupancy'] = native_occupancy(pred, [harness.load_stage(p) for p in harness.SPLITS[split]['inputs']],
                                                           times=harness.SPLITS[split]['times'], target_time=harness.SPLITS[split]['time'])
        out = dict(split=split, board=out_board, score=score, metrics=metrics if out_board != 'temporal' else {},
                   seed_scores=per_seed, seed_sd=sd)
        if out['board'] == 'perturbation':
            try:
                out['severity'] = harness.severity_diag(pred, ref, split)
            except Exception as e:  # noqa: BLE001 - diagnostic only
                out['severity'] = dict(error=str(e)[:200])
        out['seconds'] = round(time.time() - t0, 1)
        out['cpu_seconds'] = _cpu()
        return out
    except Exception as e:  # noqa: BLE001 - reported to the agent
        return dict(split=split, board=harness.SPLITS[split]['board'], error=f'{type(e).__name__}: {e}',
                    trace=traceback.format_exc()[-3000:], seconds=round(time.time() - t0, 1))


def aggregate(splits):
    boards = {}
    for split, r in splits.items():
        if 'score' in r:
            boards.setdefault(r['board'], []).append((r['score'], float(harness.SPLITS.get(split, {}).get('weight', 1))))
    board_scores = {b: sum(x * w for x, w in v) / sum(w for _, w in v) for b, v in boards.items()}
    proxy = sum(WEIGHTS[b] * s for b, s in board_scores.items())
    # Standard error of each board mean from scoring-seed spread (prediction seed is fixed and paired).
    var = {}
    for split, r in splits.items():
        if r.get('seed_sd') is not None:
            w = float(harness.SPLITS.get(split, {}).get('weight', 1))
            var.setdefault(r['board'], []).append((w * w * r['seed_sd'] ** 2 / len(r['seed_scores']), w))
    board_se = {b: (sum(x for x, _ in v) ** .5) / sum(w for _, w in v) for b, v in var.items()}
    proxy_se = sum((WEIGHTS[b] * s) ** 2 for b, s in board_se.items()) ** .5 if board_se else None
    return dict(boards=board_scores, proxy=proxy, board_se=board_se, proxy_se=proxy_se)


def evaluate(ws: Path, set_name: str, splits=None, workers=4, pred_seed=None, fit_seed=0, *, historical=False):
    if set_name in ('holdout', 'holdout_t3') and os.environ.get('MG_PRIVATE_FINAL') != '1':
        return dict(correct=False, error='holdout evaluation requires private finalization')
    cfg = dict(SETS[set_name])
    if pred_seed is not None:  # repeated paired evaluation (racing): vary prediction and fit randomness
        cfg['seed'] = pred_seed
    splits = splits or cfg['splits']
    allowed = SETS['dev']['splits'] + SETS['sanity']['splits'] if set_name in ('dev', 'quick', 'sanity') else cfg['splits']
    bad = [s for s in splits if s not in allowed or s not in harness.SPLITS]
    if bad:
        return dict(correct=False, error=f'unsupported split for {set_name}: {bad}')
    err = screen_workspace(ws, historical=historical)
    if err:
        return dict(correct=False, error=err)
    jobs = [(str(ws), s, cfg['seed'], cfg['scoring_seeds'], fit_seed) for s in splits]
    with mp.get_context('spawn').Pool(min(workers, len(jobs)), maxtasksperchild=1) as pool:
        rows = pool.map(_one, jobs, chunksize=1)
    errors = {r['split']: r['error'] for r in rows if 'error' in r}
    if set_name == 'composition':
        return dict(correct=not errors, error=errors or None, set=set_name,
                    plausible=not errors and all(not r['composition']['failures'] for r in rows),
                    splits={r['split']: r for r in rows})
    if set_name == 'sanity':
        fails = [f"{r['split']}: {m}" for r in rows for m in (r.get('sanity') or {}).get('fails', [])]
        return dict(correct=not errors, error='; '.join(f'{k}: {v}' for k, v in errors.items()) or None, set='sanity',
                    plausible=not errors and not fails, fails=fails, splits={r['split']: r for r in rows})
    results = {r['split']: {k: v for k, v in r.items() if k != 'split'} for r in rows}
    return dict(aggregate(results), correct=not errors, error='; '.join(f'{k}: {v}' for k, v in errors.items()) or None,
                set=set_name, pred_seed=cfg['seed'], fit_seed=fit_seed, splits=results, **({'proxy': 0.0} if errors else {}))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--workspace', required=True)
    ap.add_argument('--set', default='dev', choices=list(SETS))
    ap.add_argument('--splits')
    ap.add_argument('--out')
    ap.add_argument('--pred-seed', type=int)
    ap.add_argument('--fit-seed', type=int, default=0)
    ap.add_argument('--verdict-only', action='store_true')
    ap.add_argument('--workers', type=int, default=int(os.environ.get('VE_EVAL_WORKERS', '4')))
    a = ap.parse_args()
    res = evaluate(Path(a.workspace).resolve(), a.set, a.splits.split(',') if a.splits else None, a.workers,
                   a.pred_seed, a.fit_seed)
    if a.verdict_only:
        if a.set != 'composition':
            ap.error('--verdict-only requires the composition set')
        res = {key: res.get(key) for key in ('correct', 'set', 'plausible')}
    text = json.dumps(res, indent=1, default=float)
    if a.out:
        write_json(a.out, res)
    print(text)


if __name__ == '__main__':
    main()
