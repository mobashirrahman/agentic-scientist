"""Build the Task 3 gene-annotation prior from the Gene Ontology (CC BY 4.0).

Organiser ruling (Slack): general pathway/gene-set databases are allowed; a gene set built from a knockout or
perturbation experiment of the held-out gene (Gata4, Ctnnb1) is not. GO annotations made from mutant or expression
experiments could be exactly that, so we keep only evidence that is not a perturbation or expression readout:

  dropped evidence codes: IMP, IGI, IEP, HMP, HGI, HEP (mutant phenotype, genetic interaction, expression pattern,
                          and their high-throughput forms)
  kept:                   e.g. IDA, IPI, ISS, ISO, IBA, TAS, NAS, IC, IEA, ...

Annotations whose 'with/from' or reference field names Ctnnb1 or Gata4 are also dropped (belt and braces).
Output: data/external/go_prior/go_prior.json = {release, dropped_evidence, gene_terms, term_names, term_parents}.
Run: .venv/bin/python -I scripts/v2/prepare_go_prior.py
"""
import gzip
import hashlib
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / 'data/external/go_raw'
OUT = ROOT / 'data/external/go_prior'
DROP = {'IMP', 'IGI', 'IEP', 'HMP', 'HGI', 'HEP'}
HELD_OUT = ('ctnnb1', 'gata4', 'mgi:88276', 'mgi:95664')  # gene symbols and MGI ids of the held-out knockouts


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    gene_terms, release, kept, dropped = defaultdict(set), None, 0, 0
    with gzip.open(RAW / 'MOUSE-mod.gaf.gz', 'rt') as f:
        for line in f:
            if line.startswith('!'):
                if line.startswith('!date-generated'):
                    release = release or line.strip('! \n')
                continue
            c = line.rstrip('\n').split('\t')
            if len(c) < 15 or 'NOT' in c[3]:
                continue
            symbol, term, ref, evidence, withfrom = c[2], c[4], c[5], c[6], c[7]
            if evidence in DROP or any(h in (withfrom + ref).lower() for h in HELD_OUT):
                dropped += 1
                continue
            gene_terms[symbol].add(term)
            kept += 1
    names, parents, cur = {}, defaultdict(list), None
    for line in (RAW / 'go-basic.obo').read_text().splitlines():
        if line == '[Term]':
            cur = None
        elif line.startswith('id: GO:'):
            cur = line[4:]
        elif cur and line.startswith('name: '):
            names[cur] = line[6:]
        elif cur and line.startswith('is_a: '):
            parents[cur].append(line[6:16])
        elif cur and line.startswith('relationship: part_of '):
            parents[cur].append(line[22:32])
    out = dict(source='Gene Ontology Consortium, MOUSE-mod.gaf + go-basic.obo (CC BY 4.0)', release=release,
               dropped_evidence=sorted(DROP), dropped_held_out_refs=list(HELD_OUT), kept=kept, dropped=dropped,
               gene_terms={g: sorted(t) for g, t in gene_terms.items()}, term_names=names,
               term_parents={k: v for k, v in parents.items()})
    p = OUT / 'go_prior.json'
    p.write_text(json.dumps(out))
    (OUT / 'manifest.json').write_text(json.dumps(dict(files={p.name: dict(
        sha256=hashlib.sha256(p.read_bytes()).hexdigest(), genes=len(gene_terms), terms=len(names),
        kept=kept, dropped=dropped, release=release)}), indent=1))
    print(release, 'genes', len(gene_terms), 'kept', kept, 'dropped', dropped)


if __name__ == '__main__':
    main()
