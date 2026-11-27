"""Search arXiv. Usage: python agentic_scientist/tools/arxiv_search.py "query words" [max=8]"""
import sys, urllib.parse, urllib.request, xml.etree.ElementTree as ET
q = sys.argv[1]; n = int(sys.argv[2]) if len(sys.argv) > 2 else 8
url = 'https://export.arxiv.org/api/query?' + urllib.parse.urlencode(
    dict(search_query=f'all:{q}', start=0, max_results=n, sortBy='relevance'))
ns = {'a': 'http://www.w3.org/2005/Atom'}
root = ET.fromstring(urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'research-tool'}), timeout=60).read())
for e in root.findall('a:entry', ns):
    t = ' '.join(e.find('a:title', ns).text.split())
    au = ', '.join(a.find('a:name', ns).text for a in e.findall('a:author', ns)[:4])
    print(f"## {t}\n{e.find('a:published', ns).text[:10]} | {au}\n{e.find('a:id', ns).text}\n"
          f"{' '.join(e.find('a:summary', ns).text.split())[:900]}\n")
