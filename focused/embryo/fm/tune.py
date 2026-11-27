"""Harness-side hyperparameter optimisation (Optuna), after every round's agent session. No LLM, no human.

A program may declare up to 4 knobs in `knobs.json` next to program.py:
    {"trend_damping": {"low": 0.2, "high": 1.0, "default": 0.6},
     "k_neighbours":  {"low": 10, "high": 200, "default": 50, "type": "int", "log": true}}
and read them as `context['params'].get('trend_damping', 0.6)`. The harness writes the chosen values to
`tuned_params.json` in a new snapshot; the runner passes them as context['params'].

Search: Optuna TPE (seeded, multivariate), first trial = the program's current values, batches the size of the fleet
via ask/tell, objective = validation score (val, prediction seed 0, scoring seeds 101-103).
Adoption: the best setting is re-scored with prediction seed 1 together with the untuned program; adopted only if it
beats the untuned program by >= MARGIN on BOTH seeds. The tuned snapshot then competes like any other candidate; the
held-out check still decides the final pick.
"""
import json
import shutil
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fm import score as S
from fm.common import VALIDATION, VAL_SCORING_SEEDS, now

MAX_KNOBS, MARGIN = 4, 0.25


def read_knobs(snap):
    f = Path(snap) / 'knobs.json'
    if not f.exists():
        return None
    spec = json.loads(f.read_text())
    if not isinstance(spec, dict) or not 0 < len(spec) <= MAX_KNOBS:
        raise ValueError(f'knobs.json must declare 1-{MAX_KNOBS} knobs')
    out = {}
    for name, s in spec.items():
        lo, hi, d = float(s['low']), float(s['high']), float(s['default'])
        typ, log = s.get('type', 'float'), bool(s.get('log', False))
        if not lo < hi or not lo <= d <= hi or typ not in ('float', 'int') or (log and lo <= 0):
            raise ValueError(f'bad knob {name}: {s}')
        out[name] = dict(low=lo, high=hi, default=d, type=typ, log=log)
    return out


def _with_params(snap, params, dest):
    if Path(dest).exists():
        shutil.rmtree(dest)
    shutil.copytree(snap, dest)
    (Path(dest) / 'tuned_params.json').write_text(json.dumps(params, indent=1))
    return Path(dest)


def tune(snap, rd, fleet, log, trials=32):
    """Returns a tuned snapshot path (adopted) or None. Writes rd/tune/summary.json."""
    import optuna
    optuna.logging.set_verbosity(optuna.logging.WARNING)
    try:
        knobs = read_knobs(snap)
    except (ValueError, KeyError, TypeError) as e:
        log(f'tune: invalid knobs.json in {snap}: {e}')
        return None
    if not knobs:
        return None
    td = Path(rd) / 'tune'
    td.mkdir(exist_ok=True)
    cur = json.loads((Path(snap) / 'tuned_params.json').read_text()) if (Path(snap) / 'tuned_params.json').exists() else {}
    start = {k: cur.get(k, v['default']) for k, v in knobs.items()}
    study = optuna.create_study(direction='maximize',
                                sampler=optuna.samplers.TPESampler(seed=0, multivariate=True, n_startup_trials=8))
    study.enqueue_trial(start)
    batch = max(1, len(fleet.hosts))
    rows = []

    def objective(params, i):
        s = _with_params(snap, params, td / f't{i:03d}')
        r = fleet.score(s, VALIDATION, [0], VAL_SCORING_SEEDS, td / f't{i:03d}_work')
        shutil.rmtree(s, ignore_errors=True)
        return S.combine(r, VALIDATION)

    i = 0
    while i < trials:
        asked = [study.ask() for _ in range(min(batch, trials - i))]
        params = []
        for t in asked:
            p = {}
            for k, v in knobs.items():
                if v['type'] == 'int':
                    p[k] = t.suggest_int(k, int(v['low']), int(v['high']), log=v['log'])
                else:
                    p[k] = t.suggest_float(k, v['low'], v['high'], log=v['log'])
            params.append(p)
        with ThreadPoolExecutor(len(asked)) as ex:
            vals = list(ex.map(objective, params, range(i, i + len(asked))))
        for t, p, v in zip(asked, params, vals):
            study.tell(t, v if v is not None else -1e9)
            rows.append(dict(trial=t.number, params=p, validation=v))
        i += len(asked)
        log(f'tune: {i}/{trials} trials, best {study.best_value:.3f}')
    best = study.best_params
    base, cand = rows[0]['validation'], study.best_value
    summary = dict(time=now(), knobs=knobs, start=start, trials=rows, best=best, best_value=cand, start_value=base)
    adopted = None
    if base is not None and best != start and cand >= base + MARGIN:
        s_best = _with_params(snap, best, td / 'confirm_best')
        s_base = _with_params(snap, start, td / 'confirm_base')
        rb = S.combine(fleet.score(s_best, VALIDATION, [1], VAL_SCORING_SEEDS, td / 'cb'), VALIDATION)
        r0 = S.combine(fleet.score(s_base, VALIDATION, [1], VAL_SCORING_SEEDS, td / 'c0'), VALIDATION)
        summary.update(confirm_seed1=dict(best=rb, start=r0))
        if rb is not None and r0 is not None and rb >= r0 + MARGIN:
            adopted = s_best
    summary['adopted'] = adopted is not None
    (td / 'summary.json').write_text(json.dumps(summary, indent=1, default=float))
    log(f'tune: start {base} best {cand} adopted={adopted is not None}')
    return adopted
