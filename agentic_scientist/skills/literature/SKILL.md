---
name: literature
description: Search and read whole papers through official APIs (no bot walls): PubMed, Europe PMC (+bioRxiv), OpenAlex, arXiv, GEO metadata, Semantic Scholar. Use for mechanisms, methods and priors; cite what you read.
---
# Literature

Available as MCP tools on server `lit` (search, pubmed, openalex, arxiv, geo, abstract, fulltext, page, related) and as a CLI:
`$MG_ROOT/.venv/bin/python $MG_ROOT/agentic_scientist/tools/lit.py <cmd> ...`
- `pubmed "Mef2c[tiab] AND heart AND mouse" --n 10`: NCBI PubMed, full query syntax
- `search "second heart field Mesp1 beta-catenin" --n 10 [--preprints]`: Europe PMC (PubMed + PMC + preprints) with abstracts
- `openalex "unbalanced optimal transport single cell" --n 10`: all fields, citation counts, open-access links
- `arxiv "flow matching trajectories" --n 8`: methods papers
- `geo "Hand2 knockout heart" --n 10`: GEO series metadata (do not download data into programs)
- `abstract 34567890`: abstract by PMID
- `fulltext <PMCID | PMID | DOI | arXiv id | PPR id> [--grep Tal1] [--offset 0] [--max 15000]`: the whole paper
  from PMC / Europe PMC XML, preprint XML, arXiv PDF, or a legal open-access copy; page with --offset
- `page <url> [--grep X]`: any web page or PDF as text; says so when a site blocks automated access (do not retry it)
- `related <arXiv id | DOI | PMID>`: Semantic Scholar recommendations
Prefer `fulltext` over WebFetch for papers: publisher sites (Cell, Elsevier, bioRxiv HTML) block automated access.

Good sources: mouse gastrulation/organogenesis atlases (Pijuan-Sala 2019, Qiu 2024), heart development single-cell and
spatial studies, conditional knockout phenotype papers, OT/trajectory methods (Waddington-OT, moscot, TrajectoryNet),
spatial alignment (PASTE). Cite only papers you actually opened, as URLs in hypothesis evidence.
