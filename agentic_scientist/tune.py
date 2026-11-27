"""Harness-side knob tuning (part of the AgenticScientist lock; no LLM, no human in the loop). Deterministic, on demand.

Agents may declare up to MAX_KNOBS continuous/integer knobs per board in `<board>_knobs.json` next to their program:
    {"tilt": {"low": 0.3, "high": 1.0, "default": 0.75},
     "k":    {"low": 30,  "high": 200, "default": 100, "type": "int", "log": true}}
and read them in predict() as `context['params'].get('tilt', 0.75)` (an empty dict means: use the defaults).

When: whenever a candidate's `<board>_knobs.json` is new or differs from the spec its `<board>_tuned.json` was tuned for
(orchestrator.maybe_tune: after the candidate evaluates correctly, before its paired race). The outcome is written to
`<board>_tuned.json` (a board file, so it moves with the board's code when tasks are composed); children that keep the
knob spec inherit the values without re-tuning. Agents never write `<board>_tuned.json` (the harness restores it).

Search (batch-synchronous: the result depends only on the evaluation results, never on fleet timing; resumable):
  0. Every search trial uses ONE (prediction, fit) seed pair (common random numbers), disjoint from the race and holdout
     pairs, so differences between settings are not swamped by resampling noise.
  1. Round 0: the current values (inherited tuned values, else the defaults), the defaults, and a seeded scrambled Sobol
     design filling one fleet-wide batch.
  2. Rounds 1..R: Gaussian-process Bayesian optimisation (Optuna GPSampler: Matern-5/2 ARD kernel with a fitted noise
     term, log expected improvement), a whole batch per round via the constant-liar heuristic (each proposal is told the
     worst observed value in a shadow study, so the batch spreads out). Seeded multivariate TPE if the GP fails.
  3. Finalists (the current values and the `top` best other settings) are re-scored on `reseed_pairs` fresh seed pairs.
     Winner = the largest lower confidence bound (mean - 1 SE) of the PAIRED gain over the current values on those pairs
     only (the search pair chose the finalists, so it is excluded). Adopted only if that bound is > 0.
  4. The orchestrator re-screens the candidate with the chosen values and runs the ordinary paired race against the
     parent on the race seed pairs; the end-of-run holdout selection still decides.
"""
import hashlib
import json
import math
import shutil
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

from agentic_scientist.artifacts import digest, read_cached, workspace_manifest, write_json

MAX_KNOBS = 4
TUNABLE_BOARDS = ('temporal', 'heart', 'embryo', 'perturbation')
SEARCH_PAIR = (911, 9)  # race pairs are (101,0)..(808,7), holdout pairs (202,0)..(535,3)
RESEED_PAIRS = ((1013, 10), (1117, 11), (1219, 12))


def read_knobs(ws, board):
    """Validated knob spec from <board>_knobs.json, or None. Raises ValueError on a malformed spec."""
    f = Path(ws) / f'{board}_knobs.json'
    if not f.exists():
        return None
    spec = json.loads(f.read_text())
    if not isinstance(spec, dict) or not spec:
        raise ValueError(f'{f.name}: expected a non-empty object of knobs')
    if len(spec) > MAX_KNOBS:
        raise ValueError(f'{f.name}: {len(spec)} knobs; at most {MAX_KNOBS} (few knobs = little overfitting)')
    out = {}
    for name, s in spec.items():
        lo, hi, d = float(s['low']), float(s['high']), float(s['default'])
        typ, log = s.get('type', 'float'), bool(s.get('log', False))
        if not lo < hi or not lo <= d <= hi or typ not in ('float', 'int') or (log and lo <= 0):
            raise ValueError(f'{f.name}: bad range for {name!r}: {s}')
        out[name] = dict(low=lo, high=hi, default=int(round(d)) if typ == 'int' else d, type=typ, log=log)
    return out


def _from_unit(u, s):
    """Map u in [0,1) to the knob's range (log-uniform if requested)."""
    if s['log']:
        v = math.exp(math.log(s['low']) + u * (math.log(s['high']) - math.log(s['low'])))
    else:
        v = s['low'] + u * (s['high'] - s['low'])
    return int(round(v)) if s['type'] == 'int' else float(v)


def board_splits(dev_splits, splits_meta, board):
    return [s for s in dev_splits if splits_meta[s]['board'] == board]


def knobs_sha(ws, board):
    f = Path(ws) / f'{board}_knobs.json'
    return hashlib.sha256(f.read_bytes()).hexdigest()[:16] if f.exists() else None


def tuned_file(ws, board):
    return Path(ws) / f'{board}_tuned.json'


def needs_tuning(ws, board):
    """True when the board declares knobs (raises ValueError on a malformed spec) that its <board>_tuned.json was not
    tuned for."""
    if board not in TUNABLE_BOARDS or read_knobs(ws, board) is None:
        return False
    try:
        return json.loads(tuned_file(ws, board).read_text()).get('knobs_sha') != knobs_sha(ws, board)
    except (OSError, ValueError, AttributeError):
        return True


def write_tuned(ws, board, params, **info):
    write_json(tuned_file(ws, board), dict(knobs_sha=knobs_sha(ws, board), params=params, **info))


def restore_tuned(parent_ws, ws, board):
    """Agents never set tuned values: the candidate's <board>_tuned.json is reset to the parent's. True if it changed."""
    src, dst = tuned_file(parent_ws, board), tuned_file(ws, board)
    if src.exists():
        if dst.exists() and dst.read_bytes() == src.read_bytes():
            return False
        shutil.copy(src, dst)
        return True
    if dst.exists():
        dst.unlink()
        return True
    return False


def current_values(ws, board, knobs):
    """The values the program runs with now: inherited tuned values (clipped to the declared ranges), else defaults."""
    try:
        old = json.loads(tuned_file(ws, board).read_text()).get('params') or {}
    except (OSError, ValueError, AttributeError):
        old = {}
    out = {}
    for n, s in knobs.items():
        v = old.get(n, s['default'])
        v = min(max(float(v), s['low']), s['high'])
        out[n] = int(round(v)) if s['type'] == 'int' else float(v)
    return out


def _key(params):
    return json.dumps(params, sort_keys=True)


def _mse(d):
    n = len(d)
    if not n:
        return float('nan'), float('inf'), float('-inf')
    m = float(np.mean(d))
    se = float(np.std(d, ddof=1) / math.sqrt(n)) if n > 1 else float('inf')
    return m, se, m - se


class Tuner:
    """Tune one board's knobs of one workspace. `evaluate(ws, out, pred_seed, fit_seed, splits)` -> evaluation dict with
    ev['boards'][board] (the orchestrator passes the fleet evaluator; `parallel` = the whole fleet)."""

    def __init__(self, ws, board, splits, out_dir, evaluate, log, rounds=3, parallel=14, top=3,
                 search_pair=SEARCH_PAIR, reseed_pairs=RESEED_PAIRS, seed=0, eval_revision=None):
        self.ws, self.board, self.splits = Path(ws), board, list(splits)
        self.out = Path(out_dir)
        self.evaluate, self.log = evaluate, log
        self.rounds, self.parallel, self.top = int(rounds), max(2, int(parallel)), int(top)
        self.search_pair, self.reseed_pairs = tuple(search_pair), [tuple(p) for p in reseed_pairs]
        self.seed = int(seed)
        self.knobs = read_knobs(ws, board)
        self.names = list(self.knobs)
        self.revision = digest([eval_revision, workspace_manifest(ws), self.splits])

    def _workspace(self, tag, values):
        d = self.out / tag
        pf = d / 'params.json'
        identity = dict(params=values, revision=self.revision)
        if d.exists() and (not pf.exists() or json.loads(pf.read_text()) != identity):
            shutil.rmtree(d)  # resumed with different proposals: never reuse another setting's results
        ws = d / 'ws'
        if not ws.exists():
            shutil.copytree(self.ws, ws, ignore=shutil.ignore_patterns('__pycache__', '*_evals', '.quick_eval_runs'))
            write_tuned(ws, self.board, values)
            write_json(pf, identity)
        return ws

    def _score(self, tag, values, pair):
        ws = self.out / tag / 'ws'
        out = self.out / tag / f'eval_{pair[0]}_{pair[1]}.json'
        key = digest([self.revision, values, pair])
        ev = read_cached(out, key)
        if ev is None:
            ev = self.evaluate(ws, out, pair[0], pair[1], self.splits)
            write_json(out, dict(ev, cache_key=key))
        if not ev.get('correct'):
            return None
        return float(ev['boards'][self.board])

    def _dist(self):
        import optuna
        return {n: (optuna.distributions.IntDistribution(int(s['low']), int(s['high']), log=s['log']) if s['type'] == 'int'
                    else optuna.distributions.FloatDistribution(s['low'], s['high'], log=s['log']))
                for n, s in self.knobs.items()}

    def _propose(self, trials, k, rnd):
        """k new settings from a shadow study holding every finished trial (failed ones as the worst value)."""
        import optuna
        from optuna.trial import create_trial
        dist = self._dist()
        ok = [t['score'] for t in trials if t['score'] is not None]
        lie = min(ok)
        frozen = [create_trial(params=t['params'], distributions=dist, value=t['score'] if t['score'] is not None else lie)
                  for t in trials]
        for kind in ('gp', 'tpe'):
            try:
                if kind == 'gp':
                    sampler = optuna.samplers.GPSampler(seed=self.seed + rnd, n_startup_trials=0, deterministic_objective=False)
                else:
                    sampler = optuna.samplers.TPESampler(multivariate=True, group=True, constant_liar=True,
                                                         seed=self.seed + rnd, n_startup_trials=0)
                shadow = optuna.create_study(direction='maximize', sampler=sampler)
                shadow.add_trials(frozen)
                out = []
                for _ in range(k):
                    t = shadow.ask(dist)
                    out.append({n: (int(t.params[n]) if self.knobs[n]['type'] == 'int' else float(t.params[n]))
                                for n in self.names})
                    shadow.tell(t, lie)  # constant liar: the batch spreads out instead of repeating one point
                return out, kind
            except Exception as e:  # noqa: BLE001
                self.log(f'tune {self.board}: {kind} proposal failed ({e!r})')
        raise RuntimeError('no sampler could propose')

    def _batch(self, trials, settings, rnd, kind):
        known = {_key(t['params']): t['score'] for t in trials}
        rows = [dict(trial=len(trials) + k, round=rnd, sampler=kind, params=p) for k, p in enumerate(settings)]
        todo, fresh = [], set()
        for r in rows:  # score each distinct new setting once (also within this batch)
            k = _key(r['params'])
            if k not in known and k not in fresh:
                fresh.add(k)
                todo.append(r)
        for r in todo:
            self._workspace(f"trial{r['trial']:03d}", r['params'])
        with ThreadPoolExecutor(min(self.parallel, max(1, len(todo)))) as pool:
            scores = list(pool.map(lambda r: self._score(f"trial{r['trial']:03d}", r['params'], self.search_pair), todo))
        for r, sc in zip(todo, scores):
            r['score'] = sc
        known.update({_key(r['params']): r['score'] for r in todo})
        for r in rows:
            if 'score' not in r:  # duplicate setting: same seed pair, same score
                r['score'], r['duplicate'] = known[_key(r['params'])], True
        trials.extend(rows)
        good = [r['score'] for r in rows if r['score'] is not None]
        best = max((t for t in trials if t['score'] is not None), key=lambda t: t['score'], default=None)
        self.log(f"tune {self.board} round {rnd} ({kind}): {len(rows)} settings, {len(good)} ok, round best "
                 f"{max(good) if good else float('nan'):.2f}; overall best {best['score'] if best else float('nan'):.2f} "
                 f"{best['params'] if best else ''}")

    def run(self):
        """Returns the result dict (also written to <out>/tune.json): chosen params, improved flag, all trials."""
        import optuna
        import warnings
        from scipy.stats import qmc
        warnings.filterwarnings('ignore', category=optuna.exceptions.ExperimentalWarning)
        warnings.filterwarnings('ignore', message='.*balance properties of Sobol.*')
        optuna.logging.set_verbosity(optuna.logging.WARNING)
        self.out.mkdir(parents=True, exist_ok=True)
        cur = current_values(self.ws, self.board, self.knobs)
        default = {n: s['default'] for n, s in self.knobs.items()}
        start = [cur] + ([default] if _key(default) != _key(cur) else [])
        n0 = max(self.parallel - len(start), 2 * len(self.names) + 2)
        sob = qmc.Sobol(d=len(self.names), scramble=True, seed=self.seed).random(n0)
        start += [{n: _from_unit(float(x), self.knobs[n]) for n, x in zip(self.names, u)} for u in sob]
        trials = []
        self._batch(trials, start, 0, 'sobol')
        base = trials[0]
        result = dict(board=self.board, knobs=self.knobs, search_pair=self.search_pair, reseed_pairs=self.reseed_pairs,
                      seed=self.seed, current=cur, trials=trials, finalists=[], chosen=cur, improved=False)
        if base['score'] is None:
            result['reason'] = 'the current values fail to evaluate'
        else:
            for rnd in range(1, self.rounds + 1):
                settings, kind = self._propose(trials, self.parallel, rnd)
                self._batch(trials, settings, rnd, kind)
            seen, fin = {_key(cur)}, []
            for t in sorted((t for t in trials if t['score'] is not None), key=lambda t: -t['score']):
                if _key(t['params']) not in seen:
                    seen.add(_key(t['params']))
                    fin.append(t)
                if len(fin) == self.top:
                    break
            jobs = [(t, p) for t in [base] + fin for p in self.reseed_pairs]
            with ThreadPoolExecutor(min(self.parallel, len(jobs))) as pool:
                sc = list(pool.map(lambda tp: self._score(f"trial{tp[0]['trial']:03d}", tp[0]['params'], tp[1]), jobs))
            for (t, _), s in zip(jobs, sc):
                t.setdefault('reseed', []).append(s)
            for t in fin:
                d = [a - b for a, b in zip(t['reseed'], base['reseed']) if a is not None and b is not None]
                t['gain'], t['gain_se'], t['gain_lcb'] = _mse(d)
                t['gain_n'] = len(d)
            complete = [t for t in fin if t['gain_n'] == len(self.reseed_pairs)]  # a crash on any fresh pair disqualifies
            best = max(complete, key=lambda t: t['gain_lcb'], default=None)
            result['finalists'] = [dict(trial=t['trial'], params=t['params'], search=t['score'], reseed=t['reseed'],
                                        gain=t['gain'], gain_se=t['gain_se'], gain_lcb=t['gain_lcb']) for t in fin]
            if best is not None and best['gain_lcb'] > 0:
                result.update(chosen=best['params'], improved=True, gain=best['gain'], gain_se=best['gain_se'])
                self.log(f"tune {self.board}: chose {best['params']} (paired gain {best['gain']:+.2f} ± {best['gain_se']:.2f} "
                         f"over {cur} on {best['gain_n']} fresh seed pairs); the race against the parent decides")
            else:
                result['reason'] = 'no finalist beat the current values by more than 1 SE on fresh seeds'
                bt = 'none' if best is None else f"{best['gain']:+.2f} ± {best['gain_se']:.2f}"
                self.log(f'tune {self.board}: kept {cur} (best finalist paired gain {bt})')
        write_json(self.out / 'tune.json', result)
        return result
