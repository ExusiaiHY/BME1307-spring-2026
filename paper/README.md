# IEEE Paper Project

This directory contains the IEEE-style course paper draft.

## Build

Install a LaTeX distribution first:

- macOS: MacTeX or BasicTeX plus `latexmk`
- Linux: TeX Live
- Online: upload this `paper/` directory to Overleaf

Then run from the repository root:

```bash
make paper
```

or from this directory:

```bash
latexmk -pdf main.tex
```

The source expects report figures under `paper/figures/`. Regenerate them from repository outputs with:

```bash
make report-figures
```

## Files

- `main.tex`: IEEE-style paper draft.
- `references.bib`: BibTeX database.
- `figures/`: report-ready PNG figures copied from `outputs/report_figures/`.
- `latexmkrc`: local build settings.

The author block currently contains placeholders; replace them with the final group member names before submission.
