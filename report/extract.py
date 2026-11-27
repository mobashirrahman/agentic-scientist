import json, glob, os, sys, collections
from pathlib import Path
ROOT = Path(sys.argv[2]) if len(sys.argv) > 2 else Path('agentic_scientist/runs')  # run directories
OUT = Path(sys.argv[1])
runs = {'run1': 'mglock_20261123_131906_final', 'run2': 'mglock_20261124_004757_final_v2',
        'dday': 'mglock_20261124_042523_dday', 'normandy': 'mglock_20261125_033537_normandy'}
res = {}
for name, d in runs.items():
    R = ROOT / d
    st = json.loads((R / 'state.json').read_text())
    cyc = []
    for c in sorted(glob.glob(str(R / 'cycles/*/outcome.json'))):
        o = json.loads(open(c).read())
        cid = c.split('/')[-2]
        s = (o.get('stats') or {})
        started = None
        sp = Path(c).parent / 'started'
        if sp.exists():
            try: started = float(sp.read_text())
            except Exception: pass
        cyc.append(dict(id=cid, worker=cid.split('_')[0], verdict=o.get('verdict'), title=(o.get('title') or '')[:160],
                        reason=(o.get('reason') or '')[:200], board=o.get('board'), researcher=o.get('researcher') or o.get('implementer'),
                        intended=o.get('researcher_intended'), substitute=o.get('substitute'),
                        finished=o.get('finished'), started=started, seconds=o.get('cycle_seconds'),
                        dev_board=o.get('dev_board'), parent_dev_board=o.get('parent_dev_board'),
                        proxy=o.get('proxy'), parent_proxy=o.get('parent_proxy'), parent=o.get('parent_id'),
                        d_mean=(s.get('proxy') or {}).get('mean'), d_lb=(s.get('proxy') or {}).get('lb'),
                        d_n=(s.get('proxy') or {}).get('n'),
                        review=(o.get('review') or {}).get('verdict') if isinstance(o.get('review'), dict) else None,
                        reviewer=(o.get('review') or {}).get('reviewer') if isinstance(o.get('review'), dict) else None,
                        boards=o.get('boards')))
    calls = []
    p = R / 'agent_calls.jsonl'
    if p.exists():
        for l in p.read_text().splitlines():
            try: j = json.loads(l)
            except Exception: continue
            calls.append({k: j.get(k) for k in ('t', 'seconds', 'cycle', 'label', 'role', 'intended', 'substitute', 'exit', 'limited', 'cost_usd')})
    fin = None
    fp = R / 'final/final.json'
    if fp.exists():
        f = json.loads(fp.read_text())
        rows = []
        for c in f.get('candidates', []):
            rows.append({k: c.get(k) for k in ('id', 'proxy', 'boards', 'holdout', 'holdout_pairs', 'holdout_boards', 'parts', 'dev_only_parts', 'dev_proxy')})
        fin = dict(rule=f.get('rule'), chosen=f.get('chosen'), candidates=rows, cost_usd=f.get('cost_usd'), agent_calls=f.get('agent_calls'),
                   extra={k: v for k, v in f.items() if k not in ('candidates',)})
        # paired holdout per board
        pairs = {}
        for hp in glob.glob(str(R / 'final/holdout_*_pair*.json')):
            b = os.path.basename(hp)
            if b.endswith('_sub.json'): continue
            cid, j = b[len('holdout_'):-5].rsplit('_pair', 1)
            e = json.loads(open(hp).read())
            pairs.setdefault(cid, {})[int(j)] = dict(boards=e.get('boards'), proxy=e.get('proxy'),
                                                     splits={k: dict(score=v.get('score'), metrics=v.get('metrics')) for k, v in (e.get('splits') or {}).items()})
        fin['pairs'] = pairs
    seed_dev = json.loads((R / 'seed_dev.json').read_text()) if (R / 'seed_dev.json').exists() else {}
    res[name] = dict(dir=d, calls_n=st.get('calls'), cost_usd=st.get('cost_usd'), impl_stats=st.get('impl_stats'),
                     accepted=[{k: a.get(k) for k in ('id', 'proxy', 'boards')} for a in st.get('accepted', [])],
                     parent=st.get('parent'), cycles=cyc, calls=calls, final=fin, research_started=st.get('research_started'),
                     checkpoints=[{k: c.get(k) for k in ('stamp', 'ok', 'parts', 't')} for c in st.get('checkpoints', [])],
                     seed_dev=dict(proxy=seed_dev.get('proxy'), boards=seed_dev.get('boards'),
                                   splits={k: dict(score=v.get('score'), board=v.get('board'), metrics=v.get('metrics')) for k, v in (seed_dev.get('splits') or {}).items()}),
                     unseen_gene=st.get('unseen_gene'), tunes=st.get('tunes'), phase=st.get('phase'))
    print(name, 'cycles', len(cyc), collections.Counter(c['verdict'] for c in cyc), 'calls', len(calls), 'cost', st.get('cost_usd'), 'final', fin and fin['chosen'])
OUT.write_text(json.dumps(res))
