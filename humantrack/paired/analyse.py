"""Paired verdict with the locked acceptance rule: board gain one-sided 95% LB > 0.5 (heart, embryo);
heart target groups (e875, e95, organ_proxy) each mean >= -0.25."""
import json, glob, statistics as st
from scipy import stats
O = '/scratch/user/ve-next/humantrack/paired'
G = {'e875': ['heart_e875'], 'e95': ['heart_early', 'heart_late', 'heart_long'], 'organ_proxy': ['heart_organ_proxy']}
H = sum(G.values(), [])
seeds = sorted({int(p.split('_')[-1][:-5]) for p in glob.glob(f'{O}/enigma_*.json')})
rows = []
for s in seeds:
    try:
        e = json.load(open(f'{O}/enigma_{s}.json'))['splits']
        h = json.load(open(f'{O}/heart_{s}.json'))['splits']
        b = json.load(open(f'{O}/embryo_{s}.json'))['splits']
    except Exception:
        continue
    d = {k: h[k]['score'] - e[k]['score'] for k in H}
    d['embryo_early'] = b['embryo_early']['score'] - e['embryo_early']['score']
    d['heart'] = st.mean(d[k] for k in H)
    for g, ks in G.items():
        d['g_' + g] = st.mean(d[k] for k in ks)
    d['abs_heart_codex'] = st.mean(h[k]['score'] for k in H); d['abs_heart_enigma'] = st.mean(e[k]['score'] for k in H)
    d['abs_embryo_codex'] = b['embryo_early']['score']; d['abs_embryo_enigma'] = e['embryo_early']['score']
    rows.append(d)
n = len(rows); print('seed pairs:', n)
def lb(xs):
    m = st.mean(xs); se = st.stdev(xs) / len(xs) ** .5 if len(xs) > 1 else float('inf')
    return m, m - stats.t.ppf(0.95, len(xs) - 1) * se if len(xs) > 1 else float('nan')
for k in ['heart', 'g_e875', 'g_e95', 'g_organ_proxy'] + H + ['embryo_early']:
    m, l = lb([r[k] for r in rows]); print(f'{k:18s} mean {m:+.2f}  LB95 {l:+.2f}')
for k in ['abs_heart_codex', 'abs_heart_enigma', 'abs_embryo_codex', 'abs_embryo_enigma']:
    print(k, round(st.mean(r[k] for r in rows), 2))
hm, hl = lb([r['heart'] for r in rows]); em, el = lb([r['embryo_early'] for r in rows])
groups_ok = all(st.mean(r['g_' + g] for r in rows) >= -0.25 for g in G)
print('HEART  :', 'ACCEPT' if hl > 0.5 and groups_ok else 'REJECT', f'(LB {hl:+.2f} vs 0.5; groups ok={groups_ok})')
print('EMBRYO :', 'ACCEPT' if el > 0.5 else 'REJECT', f'(LB {el:+.2f} vs 0.5)')
