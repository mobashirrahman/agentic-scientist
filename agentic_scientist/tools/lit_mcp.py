"""Minimal stdio MCP server exposing lit.py (literature search and full text) as tools. Standard library only.

Each tool call runs `python -I lit.py <cmd> ...` in a subprocess, so the MCP tools and the CLI behave identically.
"""
import json
import os
import subprocess
import sys

LIT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'lit.py')
Q = {'type': 'string'}
N = {'type': 'integer', 'description': 'number of results (default 10)'}
PAGE = {'grep': {'type': 'string', 'description': 'keep only paragraphs containing this text'},
        'offset': {'type': 'integer', 'description': 'character offset for paging (default 0)'},
        'max': {'type': 'integer', 'description': 'characters to return (default 15000)'}}
TOOLS = {
    'search': ('Europe PMC search (all of PubMed, PMC and bioRxiv/medRxiv preprints) with abstracts and IDs.',
               {'query': Q, 'n': N, 'preprints': {'type': 'boolean', 'description': 'preprints only'}}),
    'pubmed': ('NCBI PubMed search; accepts full PubMed syntax, e.g. "Mef2c[tiab] AND heart AND mouse".',
               {'query': Q, 'n': N}),
    'openalex': ('OpenAlex search across all disciplines (methods, ML, biology) with citation counts and open-access links.',
                 {'query': Q, 'n': N}),
    'arxiv': ('arXiv search (methods: optimal transport, flow matching, single-cell ML).', {'query': Q, 'n': N}),
    'geo': ('NCBI GEO series search (metadata only; downloading data into programs is not allowed).',
            {'query': Q, 'n': N}),
    'abstract': ('Abstract for a PubMed ID.', {'query': {'type': 'string', 'description': 'PMID'}}),
    'fulltext': ('Full text of a paper from PMC / Europe PMC XML, preprint XML, arXiv PDF or a legal open-access copy. '
                 'Accepts PMCID, PMID, DOI, arXiv id or PPR id. Pages with offset/max; filter with grep.',
                 dict({'query': {'type': 'string', 'description': 'PMCID | PMID | DOI | arXiv id | PPR id'}}, **PAGE)),
    'page': ('Fetch any web page or PDF as plain text; reports bot walls instead of returning them.',
             dict({'query': {'type': 'string', 'description': 'URL'}}, **PAGE)),
    'related': ('Semantic Scholar recommendations for a paper (arXiv id, DOI or PMID).', {'query': Q}),
}


def run(name, args):
    cmd = [sys.executable, '-I', LIT, name, str(args.get('query', '')).strip() or '-']
    for k in ('n', 'grep', 'offset', 'max'):
        if args.get(k) not in (None, ''):
            cmd += [f'--{k}', str(args[k])]
    if args.get('preprints'):
        cmd.append('--preprints')
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        out = (p.stdout + ('\n' + p.stderr[-2000:] if p.returncode else '')).strip()
        return out or '(no output)', p.returncode != 0
    except subprocess.TimeoutExpired:
        return 'timed out after 300 s', True


def reply(id_, result=None, error=None):
    msg = {'jsonrpc': '2.0', 'id': id_}
    msg.update({'error': error} if error else {'result': result})
    sys.stdout.write(json.dumps(msg) + '\n')
    sys.stdout.flush()


def main():
    for line in sys.stdin:
        try:
            req = json.loads(line)
        except ValueError:
            continue
        method, id_ = req.get('method'), req.get('id')
        if id_ is None:
            continue  # notification
        if method == 'initialize':
            reply(id_, {'protocolVersion': req.get('params', {}).get('protocolVersion', '2024-11-05'),
                        'capabilities': {'tools': {}}, 'serverInfo': {'name': 'lit', 'version': '1.0'}})
        elif method == 'tools/list':
            reply(id_, {'tools': [{'name': k, 'description': d,
                                   'inputSchema': {'type': 'object', 'properties': props, 'required': ['query']}}
                                  for k, (d, props) in TOOLS.items()]})
        elif method == 'tools/call':
            p = req.get('params', {})
            if p.get('name') not in TOOLS:
                reply(id_, error={'code': -32602, 'message': f"unknown tool {p.get('name')}"})
                continue
            text, err = run(p['name'], p.get('arguments') or {})
            reply(id_, {'content': [{'type': 'text', 'text': text}], 'isError': err})
        elif method == 'ping':
            reply(id_, {})
        else:
            reply(id_, error={'code': -32601, 'message': f'method not found: {method}'})


if __name__ == '__main__':
    main()
