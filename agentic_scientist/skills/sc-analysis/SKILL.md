---
name: sc-analysis
description: One-call single-cell analysis of released and external data (info, markers, composition, compare/calibrate, cluster+UMAP, spatial neighbourhoods, GO gene-set scores). Read-only; held-out files refused.
---
# Single-cell analysis tool

`$MG_ROOT/.venv/bin/python $MG_ROOT/agentic_scientist/tools/sc_tool.py <command> DATA ... [options]`

DATA: a released file relative to data/raw (`T1/E9.5_RNA.h5ad`, `T2/E8.75.h5ad`, `T3/E8.75_gata4_ko_1.h5ad`), or the
external data exactly as your program receives it: `ext:temporal`, `ext:heart`, `ext:embryo`, `ext_spatial:heart`.
Never open files under data/external directly; this tool goes through the harness's rule filters.

| Command | Use it to |
|---|---|
| `info DATA` | see columns, value scale, top genes, group sizes |
| `markers DATA --n 15` | marker genes per cell type (Wilcoxon) |
| `composition A B ...` | compare cell-type fractions across stages/sources |
| `compare A B [--pair "ours=theirs"]` | pseudobulk fold change B vs A, overall and per matched type: **calibrate an external platform before using its levels** |
| `cluster DATA --png out.png` | Leiden clusters + UMAP image (e.g. external data has no shared labels) |
| `spatial DATA --k 10` | neighbourhood enrichment z-scores and per-type radius (MERFISH 3D or Slide-seq 2D) |
| `geneset DATA --go GO:0060070` | mean GO-set score per type (filtered GO prior, descendants included) |

Options: `--filter "stage_days == 14.5"` (pandas query; skipped for datasets lacking the column), `--groupby col`,
`--max-cells 30000` (seeded subsample). Examples:
- `compare T1/E10.5_RNA.h5ad ext:temporal --filter "group == 'anchor'"`: how far the E15 anchor is from our latest stage.
- `spatial ext_spatial:heart --filter "sample == 'e14_1'"` vs `spatial T2/E9.5.h5ad`: how late heart neighbourhoods differ.
Spend at most a few calls per hypothesis; analysis is for deciding what to build, not a substitute for the paired test.
