"""Literature search and full-text reading through official APIs (no bot-checked web pages).

  python lit.py search "second heart field Mesp1" [--n 10] [--preprints]   Europe PMC (PubMed + PMC + preprints)
  python lit.py pubmed "Mef2c[tiab] AND heart AND mouse" [--n 10]           NCBI PubMed (full PubMed query syntax)
  python lit.py openalex "unbalanced optimal transport single cell" [--n 10]  OpenAlex (all fields, OA links)
  python lit.py arxiv "flow matching single-cell trajectories" [--n 8]
  python lit.py geo "Hand2 knockout heart single cell" [--n 10]              NCBI GEO series (metadata only)
  python lit.py abstract 34567890                                           abstract by PMID
  python lit.py fulltext <PMCID | PMID | DOI | arXiv id | PPR id> [--grep Mesp1] [--offset 0] [--max 15000]
  python lit.py page <url> [--grep X] [--offset 0] [--max 15000]           any page or PDF as text (reports bot walls)
  python lit.py related <arXiv id | DOI | PMID>                             Semantic Scholar recommendations
Full text comes from PMC / Europe PMC XML (incl. preprints with a licence), arXiv PDFs, or the open-access copy
OpenAlex knows about. Optional keys (env): NCBI_API_KEY (10 req/s instead of 3), S2_API_KEY.
Cite what you actually read (URL) in hypothesis.json evidence.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from html.parser import HTMLParser

UA = {'User-Agent': 'agentic_scientist-research-tool (academic literature client)'}
EPMC = 'https://www.ebi.ac.uk/europepmc/webservices/rest'
EUTILS = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils'
BOT_MARKS = ('just a moment', 'cf-chl', 'captcha', 'are you a robot', 'verify you are human', 'access denied',
             'enable javascript and cookies', 'error code: 1015', 'unusual traffic')


class Blocked(Exception):
    pass


def fetch(url, tries=4, raw=False, headers=None, soft=False):
    """GET with retries. raw: False=json, True=bytes, 'meta'=(bytes, content-type). soft=True returns None on failure."""
    h = dict(UA, **(headers or {}))
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=60) as r:
                b = r.read(40_000_000)
                ctype = r.headers.get('Content-Type', '')
            if raw == 'meta':
                return b, ctype
            return b if raw else json.loads(b)
        except urllib.error.HTTPError as e:
            if (e.code == 429 or e.code >= 500) and i < tries - 1:
                time.sleep(min(60, int(e.headers.get('Retry-After') or 0) or 5 * 2 ** i))
                continue
            if soft:
                return None
            if e.code in (401, 403, 429):
                raise Blocked(f'HTTP {e.code} (site refuses automated access) for {url[:120]}')
            sys.exit(f'HTTP {e.code} for {url[:120]}')
        except Exception as e:  # noqa: BLE001
            if i == tries - 1:
                if soft:
                    return None
                sys.exit(f'request failed: {e}')
            time.sleep(3)


def ncbi(path, **params):
    if os.environ.get('NCBI_API_KEY'):
        params['api_key'] = os.environ['NCBI_API_KEY']
    params.setdefault('tool', 'agentic_scientist')
    return f'{EUTILS}/{path}?' + urllib.parse.urlencode(params)


def strip_tags(s):
    return re.sub('<[^>]+>', '', s or '')


# ---------------- search ----------------
def search(q, n, preprints):
    query = q + (' AND SRC:PPR' if preprints else '')
    d = fetch(f'{EPMC}/search?' + urllib.parse.urlencode(dict(query=query, format='json', pageSize=n, resultType='core',
                                                              sort='RELEVANCE')), soft=True)
    if d is None:
        print('(Europe PMC unavailable right now; falling back to NCBI PubMed)\n')
        return pubmed(q, n)
    for r in d.get('resultList', {}).get('result', []):
        ids = ' '.join(f'{k}:{r[k]}' for k in ('pmid', 'pmcid', 'doi') if r.get(k))
        if r.get('source') == 'PPR':
            ids += f" PPR:{r.get('id')}"
        url = f"https://europepmc.org/article/{r.get('source')}/{r.get('id')}"
        ft = 'full-text' if r.get('fullTextIdList') or r.get('pmcid') else ''
        print(f"## {r.get('title')}\n{r.get('pubYear')} | {r.get('journalTitle') or r.get('bookOrReportDetails', {}).get('publisher', '')} | "
              f"{(r.get('authorString') or '')[:80]} | {ids} {ft}\n{url}\n{strip_tags(r.get('abstractText'))[:900]}\n")


def pubmed(q, n):
    ids = fetch(ncbi('esearch.fcgi', db='pubmed', term=q, retmode='json', retmax=n, sort='relevance'))
    ids = ids.get('esearchresult', {}).get('idlist', [])
    if not ids:
        return print('no results')
    s = fetch(ncbi('esummary.fcgi', db='pubmed', id=','.join(ids), retmode='json'))['result']
    for i in ids:
        r = s.get(i, {})
        aid = {a['idtype']: a['value'] for a in r.get('articleids', [])}
        extra = ' '.join(f'{k}:{aid[k]}' for k in ('pmc', 'doi') if aid.get(k))
        print(f"## {r.get('title')}\n{r.get('pubdate')} | {r.get('fulljournalname')} | "
              f"{', '.join(a['name'] for a in r.get('authors', [])[:4])} | PMID:{i} {extra}\nhttps://pubmed.ncbi.nlm.nih.gov/{i}/\n")
    print('Abstracts: lit.py abstract <PMID>; full text: lit.py fulltext <PMID or PMCID>')


def geo(q, n):
    ids = fetch(ncbi('esearch.fcgi', db='gds', term=q, retmode='json', retmax=n))['esearchresult'].get('idlist', [])
    if not ids:
        return print('no results')
    s = fetch(ncbi('esummary.fcgi', db='gds', id=','.join(ids), retmode='json'))['result']
    for i in ids:
        r = s.get(i, {})
        print(f"## {r.get('accession')} {r.get('title')}\n{r.get('taxon')} | {r.get('gdstype')} | {r.get('n_samples')} samples | "
              f"{r.get('pdat')}\n{(r.get('summary') or '')[:700]}\nhttps://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc={r.get('accession')}\n")
    print('Metadata only: downloading external data into the program is not allowed (see brief).')


def openalex(q, n):
    d = fetch('https://api.openalex.org/works?' + urllib.parse.urlencode({'search': q, 'per-page': n}))
    for w in d.get('results', []):
        oa = w.get('open_access') or {}
        inv = w.get('abstract_inverted_index') or {}
        ab = ' '.join(t for _, t in sorted((p, t) for t, ps in inv.items() for p in ps))[:900]
        print(f"## {w.get('display_name')}\n{w.get('publication_year')} | "
              f"{((w.get('primary_location') or {}).get('source') or {}).get('display_name', '')} | "
              f"{w.get('cited_by_count')} cites | {w.get('doi') or w.get('id')} | OA:{oa.get('oa_status')} {oa.get('oa_url') or ''}\n{ab}\n")


def arxiv(q, n):
    url = 'https://export.arxiv.org/api/query?' + urllib.parse.urlencode(dict(search_query=f'all:{q}', max_results=n))
    root = ET.fromstring(fetch(url, raw=True))
    ns = {'a': 'http://www.w3.org/2005/Atom'}
    for e in root.findall('a:entry', ns):
        print(f"## {' '.join(e.find('a:title', ns).text.split())}\n{e.find('a:published', ns).text[:10]} | "
              f"{e.find('a:id', ns).text}\n{' '.join(e.find('a:summary', ns).text.split())[:900]}\n")


def abstract(pmid):
    d = fetch(f'{EPMC}/search?' + urllib.parse.urlencode(dict(query=f'EXT_ID:{pmid}', format='json', resultType='core')))
    for r in d.get('resultList', {}).get('result', [])[:1]:
        print(f"## {r.get('title')} ({r.get('pubYear')}) PMID {pmid} {r.get('pmcid', '')}\n"
              f"{strip_tags(r.get('abstractText'))}\nhttps://pubmed.ncbi.nlm.nih.gov/{pmid}/")


def related(pid):
    key = f'arXiv:{pid}' if re.match(r'^\d{4}\.\d{4,5}', pid) else f'DOI:{pid}' if pid.startswith('10.') else f'PMID:{pid}'
    fields = 'title,year,externalIds,url,citationCount'
    hdr = {'x-api-key': os.environ['S2_API_KEY']} if os.environ.get('S2_API_KEY') else None
    rec = fetch(f'https://api.semanticscholar.org/recommendations/v1/papers/forpaper/{urllib.parse.quote(key)}?limit=12&fields={fields}',
                headers=hdr)
    for p in rec.get('recommendedPapers', []):
        print(f"- {p.get('title')} ({p.get('year')}, {p.get('citationCount')} cites) {p.get('url')}")


# ---------------- full text ----------------
def jats_text(xml):
    root = ET.fromstring(xml)
    out = []
    t = next(root.iter('article-title'), None)
    if t is not None:
        out.append('# ' + ' '.join(''.join(t.itertext()).split()))
    ab = next(root.iter('abstract'), None)
    if ab is not None:
        out.append('### Abstract\n' + ' '.join(''.join(ab.itertext()).split()))
    for sec in root.iter('sec'):
        title = ''.join(sec.find('title').itertext()) if sec.find('title') is not None else ''
        paras = [' '.join(''.join(p.itertext()).split()) for p in sec.findall('p')]
        paras += ['[Figure] ' + ' '.join(''.join(f.itertext()).split()) for f in sec.findall('fig')]
        if paras:
            out.append(f'### {title}\n' + '\n'.join(paras))
    return '\n\n'.join(out)


class _Text(HTMLParser):
    SKIP = {'script', 'style', 'nav', 'header', 'footer', 'noscript', 'svg', 'form'}

    def __init__(self):
        super().__init__()
        self.parts, self.skip = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skip += 1
        elif tag in ('p', 'h1', 'h2', 'h3', 'h4', 'li', 'tr', 'br', 'div', 'section'):
            self.parts.append('\n')

    def handle_endtag(self, tag):
        if tag in self.SKIP and self.skip:
            self.skip -= 1

    def handle_data(self, d):
        if not self.skip:
            self.parts.append(d)


def html_text(b):
    p = _Text()
    p.feed(b.decode('utf-8', errors='replace'))
    return re.sub(r'\n\s*\n+', '\n\n', re.sub(r'[ \t]+', ' ', ''.join(p.parts))).strip()


def pdf_text(b):
    with tempfile.TemporaryDirectory() as d:
        f = os.path.join(d, 'a.pdf')
        with open(f, 'wb') as fh:
            fh.write(b)
        r = subprocess.run(['pdftotext', '-q', f, '-'], capture_output=True, timeout=120)
        return r.stdout.decode('utf-8', errors='replace')


def url_text(url):
    b, ctype = fetch(url, raw='meta')
    if b[:5] == b'%PDF-' or 'pdf' in ctype:
        return pdf_text(b)
    low = b[:20000].decode('utf-8', errors='replace').lower()
    if len(b) < 60000 and any(m in low for m in BOT_MARKS):
        raise Blocked(f'bot check at {url[:120]}')
    if 'xml' in ctype and b'<article' in b[:5000]:
        return jats_text(b)
    return html_text(b)


def _epmc_record(q):
    d = fetch(f'{EPMC}/search?' + urllib.parse.urlencode(dict(query=q, format='json', resultType='core')), soft=True)
    res = (d or {}).get('resultList', {}).get('result', [])
    return res[0] if res else None


def fulltext_sources(pid):
    """Yield (source url, callable returning text) in order of preference."""
    pid = pid.strip()
    doi = pmid = pmcid = ppr = arx = None
    if re.match(r'(?i)^pmc\d+$', pid):
        pmcid = pid.upper()
    elif re.match(r'(?i)^ppr\d+$', pid):
        ppr = pid.upper()
    elif re.match(r'^\d{4}\.\d{4,5}(v\d+)?$', pid) or pid.lower().startswith('arxiv:'):
        arx = pid.split(':')[-1]
    elif pid.isdigit():
        pmid = pid
    elif pid.startswith('10.') or 'doi.org/' in pid:
        doi = pid.split('doi.org/')[-1]
    if doi and doi.lower().startswith('10.48550/arxiv.'):
        arx = doi.split('rxiv.')[-1]
    if not (pmcid or ppr or arx):
        r = _epmc_record(f'DOI:"{doi}"' if doi else f'EXT_ID:{pmid} AND SRC:MED')
        if r:
            pmcid = r.get('pmcid')
            doi = doi or r.get('doi')
            if r.get('source') == 'PPR':
                ppr = r.get('id')
    if pmcid:
        src = f'https://pmc.ncbi.nlm.nih.gov/articles/{pmcid}/'
        yield src, lambda: jats_text(fetch(f'{EPMC}/{pmcid}/fullTextXML', raw=True))
        yield src, lambda: jats_text(fetch(ncbi('efetch.fcgi', db='pmc', id=pmcid), raw=True))
    if ppr:
        yield f'https://europepmc.org/article/PPR/{ppr}', lambda: jats_text(fetch(f'{EPMC}/{ppr}/fullTextXML', raw=True))
    if arx:
        yield f'https://arxiv.org/abs/{arx}', lambda: pdf_text(fetch(f'https://arxiv.org/pdf/{arx}', raw=True))
    if doi:
        w = fetch(f'https://api.openalex.org/works/doi:{urllib.parse.quote(doi)}', soft=True) or {}
        urls = []
        for loc in [w.get('best_oa_location') or {}] + (w.get('locations') or []):
            if loc.get('is_oa'):
                urls += [loc.get('pdf_url'), loc.get('landing_page_url')]
        urls += [(w.get('open_access') or {}).get('oa_url'), f'https://doi.org/{doi}']
        for u in dict.fromkeys(u for u in urls if u):
            yield u, (lambda u=u: url_text(u))


def show(text, src, grep, offset, mx):
    if grep:
        blocks = [b for b in re.split(r'\n\s*\n|\n(?=### )', text) if grep.lower() in b.lower()]
        text = '\n\n'.join(blocks) or f'(no paragraph mentions "{grep}")'
    total = len(text)
    print(text[offset:offset + mx])
    nxt = f'; more with --offset {offset + mx}' if offset + mx < total else ''
    print(f'\n[chars {offset}-{min(total, offset + mx)} of {total}{nxt}]\nsource: {src}')


def fulltext(pid, grep, offset, mx):
    notes = []
    for src, get in fulltext_sources(pid):
        try:
            text = get()
        except (Blocked, SystemExit) as e:
            notes.append(str(e))
            continue
        except Exception as e:  # noqa: BLE001
            notes.append(f'{src}: {type(e).__name__} {e}'[:200])
            continue
        if text and len(text.strip()) > 1500:
            return show(text, src, grep, offset, mx)
        notes.append(f'{src}: too little text ({len(text or "")} chars; paywall or landing page)')
    print('No open full text reachable. Tried:\n- ' + '\n- '.join(notes or ['no identifiers resolved']))
    print('Use the abstract (lit.py abstract <PMID>), or look for an open version (PMC author manuscript, preprint).')


def page(url, grep, offset, mx):
    try:
        show(url_text(url), url, grep, offset, mx)
    except Blocked as e:
        print(f'{e}. Do not retry this site; for papers use lit.py fulltext <DOI/PMID>.')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('cmd', choices=['search', 'pubmed', 'openalex', 'geo', 'arxiv', 'read', 'abstract', 'fulltext', 'page',
                                    'related'])
    ap.add_argument('q', nargs='+')
    ap.add_argument('--n', type=int, default=10)
    ap.add_argument('--preprints', action='store_true')
    ap.add_argument('--grep')
    ap.add_argument('--offset', type=int, default=0)
    ap.add_argument('--max', type=int, default=15000)
    a = ap.parse_args()
    q = ' '.join(a.q)
    cmds = {'search': lambda: search(q, a.n, a.preprints), 'pubmed': lambda: pubmed(q, a.n),
            'openalex': lambda: openalex(q, a.n), 'geo': lambda: geo(q, a.n), 'arxiv': lambda: arxiv(q, a.n),
            'abstract': lambda: abstract(q), 'read': lambda: fulltext(q, a.grep, a.offset, a.max),
            'fulltext': lambda: fulltext(q, a.grep, a.offset, a.max), 'page': lambda: page(q, a.grep, a.offset, a.max),
            'related': lambda: related(q)}
    try:
        cmds[a.cmd]()
    except Blocked as e:
        print(str(e))


if __name__ == '__main__':
    main()
