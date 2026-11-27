"""focused_morphogen_t2_embryo orchestrator. One launch, no human decisions afterwards.

round 0: builder builds a model from the starting program.
rounds 1..2: improver, each starting from the best-validation checkpoint so far.
final: guard and validation scores for every checkpoint -> pre-registered pick -> test export -> evidence package.
Resumable: rerunning with the same run id continues from state.json (lock-verified).

  python -I fm/orchestrator.py --run RUN_ID
"""
import argparse
import json
import os
import shutil
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

os.environ.setdefault('OMP_NUM_THREADS', '4')
os.environ.setdefault('OPENBLAS_NUM_THREADS', '4')
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fm import lock  # noqa: E402
from fm.agents import Agent  # noqa: E402
from fm.common import FM, NATIVE_OCCUPANCY_MIN, RUNS, now, read_json, write_json  # noqa: E402
from fm.evaluation import EvalService, format_check, snapshot  # noqa: E402

GATE = ['guard', 'test']  # must run (format only, unscored) for a snapshot to be a checkpoint


class Run:
    def __init__(self, run_id):
        self.id = run_id
        self.dir = RUNS / run_id
        self.cfg = json.loads((FM / os.environ.get('FM_CONFIG', 'config.json')).read_text())
        self.state_path = self.dir / 'state.json'
        self.state = read_json(self.state_path) or dict(id=run_id, phase='rounds', rounds={}, created=now())
        self.deadline = datetime.fromisoformat(self.cfg['deadline']).timestamp()
        self.lk = threading.Lock()
        self._fleet = None

    @property
    def fleet(self):
        if self._fleet is None:
            from fm.fleet import Fleet
            self._fleet = Fleet(self.cfg.get('fleet_hosts', []), self.log)
        return self._fleet

    def save(self):
        with self.lk:
            write_json(self.state_path, self.state)

    def log(self, msg):
        line = f'{now()} {msg}'
        with self.lk, (self.dir / 'run.log').open('a') as f:
            f.write(line + '\n')
        print(line, flush=True)

    def attention(self, msg):
        self.log('ATTENTION ' + msg)
        (self.dir / 'ATTENTION.txt').write_text(f'{now()} {msg}\n')

    # ---------- rounds ----------
    def roles(self, k):
        return self.cfg['builder'] if k == 0 else self.cfg['improver']

    def best_checkpoint(self):
        cps = [r['checkpoint'] for r in self.state['rounds'].values() if r.get('checkpoint')]
        return max(cps, key=lambda c: (c['validation'], c['round'])) if cps else None

    def history(self, k, ws):
        h = ws / 'history'
        h.mkdir(exist_ok=True)
        lines = ['# Previous rounds (validation only; held-out results are never shown)', '',
                 '| round | model | start validation | checkpoint validation | val | native occupancy | evaluations |',
                 '|---|---|---|---|---|---|---|']
        for j in range(k):
            r = self.state['rounds'].get(str(j), {})
            c = r.get('checkpoint') or {}
            sp = c.get('splits') or {}
            lines.append(f"| {j} | {r.get('model')} | {r.get('start_validation')} | {c.get('validation')} | "
                         f"{(sp.get('val') or {}).get('score')} | {(sp.get('val') or {}).get('native_occupancy')} | "
                         f"{r.get('evaluations')} |")
            rd = self.dir / 'rounds' / f'r{j:02d}'
            if (rd / 'workspace/NOTES.md').exists():
                shutil.copy2(rd / 'workspace/NOTES.md', h / f'r{j:02d}_NOTES.md')
            rows = ['eval\tvalidation\tval\tnative_occupancy\tnote']
            for x in (json.loads(t) for t in (rd / 'evals.jsonl').read_text().splitlines()) if (rd / 'evals.jsonl').exists() else []:
                if x['kind'] == 'validate':
                    s = (x.get('splits') or {}).get('val') or {}
                    rows.append(f"{x['n']}\t{x.get('validation')}\t{s.get('score')}\t"
                                f"{s.get('native_occupancy')}\t{x.get('note', '')}")
            (h / f'r{j:02d}_evals.tsv').write_text('\n'.join(rows) + '\n')
        (h / 'ROUNDS.md').write_text('\n'.join(lines) + '\n')

    def init_workspace(self, k, rd):
        ws = rd / 'workspace'
        if ws.exists():
            return ws
        ws.mkdir(parents=True)
        if k == 0:
            shutil.copy2(FM / 'kit/program.py', ws / 'program.py')
            (ws / 'NOTES.md').write_text('# Research notes (round 0)\n')
        else:
            best = self.best_checkpoint()
            shutil.copytree(self.dir / best['snapshot'], ws, dirs_exist_ok=True)
            notes = ws / 'NOTES.md'
            prev = notes.read_text() if notes.exists() else ''
            notes.write_text(f'# Research notes (round {k})\n\nStarted from round {best["round"]} checkpoint '
                             f'(validation {best["validation"]:.3f}). Previous notes are in history/.\n')
            if prev:
                (ws / 'history').mkdir(exist_ok=True)
            self.history(k, ws)
        shutil.copytree(FM / 'kit/tools', ws / 'tools', dirs_exist_ok=True)
        shutil.copytree(FM / 'kit/prior_knowledge', ws / 'prior_knowledge', dirs_exist_ok=True)
        shutil.copy2(rd / 'TASK.md', ws / 'TASK.md')
        return ws

    def render(self, name, **kw):
        text = (FM / 'prompts' / name).read_text()
        for key, val in kw.items():
            text = text.replace('{{' + key + '}}', str(val))
        return text

    def do_round(self, k):
        key = str(k)
        rs = self.state['rounds'].setdefault(key, dict(status='new'))
        if rs['status'] == 'done':
            return
        role = self.roles(k)
        rd = self.dir / 'rounds' / f'r{k:02d}'
        rd.mkdir(parents=True, exist_ok=True)
        budget = self.cfg['round_seconds'][0 if k == 0 else 1]
        evals = self.cfg['max_evals'][0 if k == 0 else 1]
        n_rounds = self.cfg['improve_rounds']
        best = self.best_checkpoint()
        (rd / 'TASK.md').write_text(self.render('task_brief.md', BUDGET_H=f'{budget / 3600:g}', MAX_EVALS=evals,
                                                MAX_TESTCHECKS=self.cfg['max_testchecks']))
        ws = self.init_workspace(k, rd)
        rs.update(status='running', model=role['model'], cli=role['cli'], budget_s=budget,
                  start_validation=best and round(best['validation'], 4), started=rs.get('started') or now())
        rs.setdefault('active_s', 0.0)
        self.save()
        self.log(f'round {k} start ({role["cli"]}:{role["model"]}) budget {budget}s used {rs["active_s"]:.0f}s')
        cur = dict(t0=None)

        def remaining():  # active agent time only; waits never count; rounds are never skipped or cut
            used = rs['active_s'] + ((time.time() - cur['t0']) if cur['t0'] else 0)
            return max(0.0, budget - used)

        svc = EvalService(rd, evals, self.cfg['max_testchecks'], lambda: dict(remaining_s=remaining()), self.log)
        svc.start()
        if k == 0:
            first = self.render('builder.md', BUDGET_H=f'{budget / 3600:g}', MAX_EVALS=evals)
        else:
            first = self.render('improver.md', ROUND=k, N_ROUNDS=n_rounds, BUDGET_H=f'{budget / 3600:g}',
                                MAX_EVALS=evals, START_ROUND=best['round'], START_VAL=f"{best['validation']:.3f}")
        roles = {'primary': role, 'fallback': self.cfg['fallback']}
        agents = {n: Agent(r, rd, self.log) for n, r in roles.items()}
        rs.setdefault('session_ids', {})
        rs.setdefault('active_role', 'primary')
        fails, conts = 0, rs.get('continuations', 0)
        wait_s = self.cfg.get('retry_wait_s', 600)
        while remaining() > 120:
            name = rs['active_role']
            r = roles[name]
            sid = rs['session_ids'].get(name)
            if not rs.get('started_session'):
                prompt, label = first, 'start'
            elif sid is None:  # this model has not worked in this round yet: full brief plus a takeover note
                prompt = first + '\n\n' + self.render('continue.md', REMAINING_MIN=int(remaining() / 60),
                                                       REASON=rs.pop('resume_reason', 'You are taking over this round.'))
                label = 'takeover'
            else:
                prompt = self.render('continue.md', REMAINING_MIN=int(remaining() / 60),
                                     REASON=rs.pop('resume_reason', 'You stopped early.'))
                label = 'continue'
            cur['t0'] = time.time()
            res = agents[name].run(prompt, remaining(), f'{label}_{name}', resume_id=sid)
            rs['active_s'] += time.time() - cur['t0']
            cur['t0'] = None
            rs['started_session'] = True
            if res.session_id:
                rs['session_ids'][name] = res.session_id
            rs.setdefault('sessions', []).append(dict(label=label, role=name, cli=r['cli'], model=r['model'],
                                                      kind=res.kind, seconds=round(res.elapsed),
                                                      session=res.session_id, ended=now()))
            self.save()
            if res.kind == 'timeout':
                break
            if res.kind in ('limited', 'auth', 'error'):
                fails += 1
                if res.kind == 'error' and fails % 2 == 0:
                    rs['session_ids'].pop(name, None)  # a broken session may be the cause: next attempt starts fresh
                if fails >= 2:  # second consecutive failure of this model: switch to the other one
                    other = 'fallback' if name == 'primary' else 'primary'
                    rs['active_role'] = other
                    rs['resume_reason'] = (f'The previous agent ({r["model"]}) became unavailable ({res.kind}); you are '
                                           f'continuing this round in the same workspace.')
                    fails = 0
                    self.log(f'round {k}: {r["model"]} {res.kind} twice; switching to {roles[other]["model"]}')
                else:
                    rs['resume_reason'] = f'Your session was interrupted ({res.kind}) and has resumed.'
                if res.kind == 'auth':
                    self.attention(f'{r["cli"]} authentication failed in round {k}: log in again on bio06 '
                                   f'(codex login --device-auth, or claude /login). The run keeps retrying.')
                self.log(f'round {k}: {r["model"]} {res.kind}; waiting {wait_s}s before retrying')
                rs['waiting_until'] = time.time() + wait_s
                self.save()
                time.sleep(wait_s)
                rs.pop('waiting_until', None)
                continue
            fails = 0
            left_evals = evals - svc.counts()[0]
            if remaining() > self.cfg['continue_if_remaining_s'] and conts < self.cfg['max_continuations'] and left_evals > 0:
                conts += 1
                rs['continuations'] = conts
                rs['resume_reason'] = 'You ended your session while substantial time remains.'
                continue
            break
        # drain in-flight requests, then close the service
        t0 = time.time()
        while any((rd / 'evalq/req').glob('*.json')) and time.time() - t0 < 1800:
            time.sleep(5)
        svc.stop_flag.set()
        svc.join(timeout=3600)
        rs['checkpoint'] = self.pick_checkpoint(k, rd, svc)
        rs['evaluations'] = svc.counts()[0]
        rs.update(status='done', ended=now())
        self.save()
        c = rs['checkpoint']
        self.log(f'round {k} done: checkpoint {c and c["snapshot"]} validation {c and c["validation"]}')

    def tune_round(self, k, rd, svc):
        """Optuna knob tuning of the round's best validated program (fm/tune.py); adds a 'tuned' candidate."""
        if not self.cfg.get('tune_trials'):
            return
        recs = [r for r in svc.records() if r['kind'] in ('validate', 'final') and r.get('validation') is not None]
        if not recs or (rd / 'tune/summary.json').exists():
            return
        top = max(recs, key=lambda r: r['validation'])
        from fm.tune import tune
        from fm import score as S
        from fm.common import VALIDATION, VAL_SCORING_SEEDS
        from fm.evaluation import content_hash
        try:
            tuned = tune(rd / 'snapshots' / top['snapshot'], rd, self.fleet, self.log, self.cfg['tune_trials'])
        except Exception as e:  # noqa: BLE001 - tuning is optional; never lose the round
            self.log(f'round {k}: tuning failed: {e!r}')
            return
        if tuned is None:
            return
        n = len(svc.records()) + 1
        snap = rd / 'snapshots' / f's{n:03d}_tuned'
        shutil.copytree(tuned, snap)
        res = self.fleet.score(snap, VALIDATION, [0], VAL_SCORING_SEEDS, rd / 'work/tuned')
        rec = dict(n=n, kind='tuned', counted=False, time=now(), snapshot=snap.name, hash=content_hash(snap),
                   note=f"harness Optuna tuning of {top['snapshot']}", validation=S.combine(res, VALIDATION), splits=res)
        with svc.ledger.open('a') as f:
            f.write(json.dumps(rec, default=float) + '\n')
        self.log(f"round {k}: tuned {top['snapshot']} -> {snap.name} validation {rec['validation']}")

    def pick_checkpoint(self, k, rd, svc):
        recs = svc.records()
        last_hash = next((r['hash'] for r in reversed(recs) if r['kind'] == 'validate'), None)
        try:
            import tempfile
            with tempfile.TemporaryDirectory(dir=rd) as td:
                h = snapshot(rd / 'workspace', Path(td) / 'x')
            if h != last_hash:
                svc.evaluate_workspace('final', 'orchestrator: final workspace', counted=False)
        except Exception as e:  # noqa: BLE001
            self.log(f'round {k}: final workspace not evaluable: {e}')
        self.tune_round(k, rd, svc)
        cands = sorted((r for r in svc.records() if r['kind'] in ('validate', 'final', 'tuned') and r.get('validation') is not None),
                       key=lambda r: -r['validation'])
        seen = set()
        for r in cands:
            if r['hash'] in seen:
                continue
            seen.add(r['hash'])
            occ = ((r.get('splits') or {}).get('val') or {}).get('native_occupancy')
            if occ is None or occ < NATIVE_OCCUPANCY_MIN:
                self.log(f"round {k}: {r['snapshot']} native occupancy {occ} below {NATIVE_OCCUPANCY_MIN}")
                continue
            snap = rd / 'snapshots' / r['snapshot']
            gate = format_check(snap, GATE, rd / 'work')
            self.log(f"round {k}: gate {r['snapshot']} validation {r['validation']:.3f} "
                     f"occupancy {occ:.3f} -> { {s: g['ok'] for s, g in gate.items()} }")
            if all(g['ok'] for g in gate.values()):
                return dict(round=k, snapshot=str(snap.relative_to(self.dir)), hash=r['hash'],
                            validation=r['validation'], splits={s: {kk: v.get(kk) for kk in
                                                                     ('score', 'metrics', 'native_occupancy')}
                                                                for s, v in r['splits'].items()},
                            model=self.roles(k)['model'], gate=gate)
            if len(seen) >= 6:
                break
        if k == 0:  # pre-registered fallback: the copy_last template
            snap = rd / 'snapshots' / 'template'
            shutil.rmtree(snap, ignore_errors=True)
            snap.mkdir(parents=True)
            shutil.copy2(FM / 'kit/program.py', snap / 'program.py')
            r = svc.records()
            from fm.evaluation import score_snapshot
            from fm import score as S
            from fm.common import VALIDATION, VAL_SCORING_SEEDS
            res = score_snapshot(snap, VALIDATION, [0], VAL_SCORING_SEEDS, rd / 'work')
            return dict(round=0, snapshot=str(snap.relative_to(self.dir)), hash='template',
                        validation=S.combine(res, VALIDATION), splits=res, model='template (copy_last)')
        return None

    # ---------- main ----------
    def main(self):
        self.dir.mkdir(parents=True, exist_ok=True)
        lock.ensure(self.dir)
        self.log(f'orchestrator start pid {os.getpid()} phase {self.state["phase"]}')
        write_json(self.dir / 'orchestrator.pid.json', dict(pid=os.getpid(), started=now()))
        if self.state['phase'] == 'rounds':
            for k in range(0, self.cfg['improve_rounds'] + 1):
                if time.time() > self.deadline:
                    self.attention('the planned finish time has passed; rounds continue (none are skipped)')
                self.do_round(k)
            self.state['phase'] = 'final'
            self.save()
        if self.state['phase'] == 'final':
            from fm.final import finalize
            finalize(self)
            self.state['phase'] = 'done'
            self.save()
        self.log('run complete')


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--run', required=True)
    Run(ap.parse_args().run).main()
