"""Mouse gene and knockout knowledge (literature-derived; use it to design GENERIC mechanisms).

  python bioknow.py gene Ctnnb1                     summary, GO biological processes, Reactome pathways
  python bioknow.py phenotypes Ctnnb1 [--grep heart] [--n 40]   MGI knockout/mutant phenotypes (+ genotype, PMID)
  python bioknow.py targets "Wnt signaling" [--n 40]            mouse genes annotated to a GO term / pathway name
  python bioknow.py compare Gata4 Ctnnb1 Mab21l2              shared GO processes and phenotype themes

Rules: knowledge may shape a program's mechanism, but programs must not hard-code gene lists for the test
knockout (Ctnnb1) or the dev knockout (Gata4); derive responses from the inputs (lineages, timing, programs).
"""
import argparse
import json
import re
import sys
import time
import urllib.parse
import urllib.request

UA = {'User-Agent': 'agentic_scientist-research-tool'}


def get(url, tries=3):
    for i in range(tries):
        try:
            return json.loads(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60).read())
        except Exception as e:  # noqa: BLE001
            if i == tries - 1:
                sys.exit(f'request failed: {e} ({url[:120]})')
            time.sleep(3 * (i + 1))


def mygene(sym, fields='MGI,name,summary,go.BP,pathway.reactome,entrezgene,alias'):
    q = urllib.parse.urlencode(dict(q=f'symbol:{sym}', species='mouse', fields=fields))
    hits = get(f'https://mygene.info/v3/query?{q}').get('hits', [])
    if not hits:
        sys.exit(f'unknown mouse gene {sym}')
    return hits[0]


def as_list(x):
    return x if isinstance(x, list) else [x] if x else []


def gene(sym):
    h = mygene(sym)
    print(f"# {sym} ({h.get('name')}) {h.get('MGI')} entrez {h.get('entrezgene')}")
    if h.get('summary'):
        print(h['summary'][:1500])
    bp = sorted({g['term'] for g in as_list((h.get('go') or {}).get('BP'))})
    print(f'\n## GO biological process ({len(bp)})\n' + '; '.join(bp[:80]))
    rx = sorted({p['name'] for p in as_list((h.get('pathway') or {}).get('reactome'))})
    print(f'\n## Reactome ({len(rx)})\n' + '; '.join(rx[:40]))


def genotype_names(obj):
    out = set()
    s = json.dumps(obj)
    for m in re.finditer(r'"(?:name|displayName)": "([^"]*<[^"]*>[^"]*)"', s):
        out.add(m.group(1))
    return sorted(out)[:3]


def phenotypes(sym, grep=None, n=40):
    mgi = mygene(sym, 'MGI').get('MGI')
    d = get(f'https://www.alliancegenome.org/api/gene/{mgi}/phenotypes?limit=500')
    rows = []
    for r in d.get('results', []):
        st = r.get('phenotypeStatement', '')
        if grep and grep.lower() not in json.dumps(r).lower():
            continue
        pm = [p.get('displayName') for p in r.get('pubmedPublications') or []][:2]
        rows.append((st, genotype_names(r.get('primaryAnnotations')), pm))
    print(f'# {sym} {mgi}: {d.get("total")} phenotype annotations' + (f', {len(rows)} matching "{grep}"' if grep else ''))
    for st, gt, pm in rows[:n]:
        print(f'- {st}' + (f' | {", ".join(gt)}' if gt else '') + (f' | {", ".join(pm)}' if pm else ''))


def targets(term, n=40):
    q = urllib.parse.urlencode(dict(q=f'go.BP.term:"{term}" OR pathway.reactome.name:"{term}"', species='mouse',
                                    fields='symbol,name', size=min(n, 1000)))
    d = get(f'https://mygene.info/v3/query?{q}')
    print(f'# {d.get("total")} mouse genes annotated to "{term}" (first {n})')
    print(', '.join(h.get('symbol', '?') for h in d.get('hits', [])))


def compare(syms):
    sets = {}
    for s in syms:
        h = mygene(s)
        sets[s] = {g['term'] for g in as_list((h.get('go') or {}).get('BP'))}
    common = set.intersection(*sets.values()) if sets else set()
    print(f'# shared GO biological processes across {", ".join(syms)}: {len(common)}')
    print('; '.join(sorted(common)[:60]))
    for s in syms:
        print(f'\n## only {s} ({len(sets[s] - common)}): ' + '; '.join(sorted(sets[s] - common)[:25]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('cmd', choices=['gene', 'phenotypes', 'targets', 'compare'])
    ap.add_argument('args', nargs='+')
    ap.add_argument('--grep')
    ap.add_argument('--n', type=int, default=40)
    a = ap.parse_args()
    if a.cmd == 'gene':
        gene(a.args[0])
    elif a.cmd == 'phenotypes':
        phenotypes(a.args[0], a.grep, a.n)
    elif a.cmd == 'targets':
        targets(' '.join(a.args), a.n)
    else:
        compare(a.args)


if __name__ == '__main__':
    main()
