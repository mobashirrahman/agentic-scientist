# AgenticScientist method report

- `main.tex` is the article (pdfLaTeX, single pass plus one rerun for references). `colors.tex` holds the colour definitions.
- `fig_architecture.tex` (Fig. 1, architecture) and `fig_lineage.tex` (Fig. 2, provenance of the submitted files) are TikZ
  diagrams included by `main.tex`.
- `fig/fig_transfer.pdf` and `fig/fig_test.pdf` are Figs. 3 and 4. `fig/fig_dday.pdf` and `fig/fig_dynamics.pdf` belong to the
  longer 10-page version and are not included by the 6-page `main.tex`.
- `figs.py` redraws all four result figures from `data/*.json` (matplotlib, font Arimo).
- `extract.py` rebuilds `data/runs.json` from the four locked run directories; `data/leaderboard_tracks.json` is the
  public leaderboard as fetched on 26 Nov 2026, 20:56 UTC, after submissions closed.
