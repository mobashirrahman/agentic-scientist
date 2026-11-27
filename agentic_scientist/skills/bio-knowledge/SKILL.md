---
name: bio-knowledge
description: Mouse gene facts, GO processes, Reactome pathways, MGI knockout phenotypes (with PMIDs) and gene sets by pathway. Use to design biologically grounded, GENERIC perturbation and development mechanisms.
---
# Bio knowledge

`$MG_ROOT/.venv/bin/python $MG_ROOT/agentic_scientist/tools/bioknow.py ...`
- `gene Ctnnb1`: summary, GO biological processes, Reactome pathways
- `phenotypes Gata4 --grep heart --n 40`: MGI mutant/knockout phenotypes with PMIDs (Alliance of Genome Resources)
- `targets "canonical Wnt signaling pathway"`: mouse genes annotated to a GO term or pathway
- `compare Gata4 Ctnnb1 Mab21l2`: shared vs specific processes. Use it to reason about what a GENERIC knockout model must capture.

Rules: knowledge may shape the mechanism (e.g. "a knockout of a gene required in lineage L depletes L and delays its maturation"). Programs must not hard-code answers for Ctnnb1 (the test knockout) or Gata4 (the dev knockout). The program receives the gene name in context['knockout']; anything gene-specific must be computed from the input data (e.g. which cells express the gene, which programs co-vary with it).
