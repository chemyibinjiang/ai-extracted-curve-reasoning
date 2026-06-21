# Code And Package Organization

This repository is organized as a paper-specific companion package for reproducing the public analyses and data products behind the manuscript.

## Public Release Boundary

Public-facing material:

- `figures`
- `benchmark_data/benchmark_curve_extraction`
- `data_literature`
- `analysis`
- `code_reference`
- package-level README, reproducibility notes, and release checklist

Excluded material:

- Original publication figures and publisher source HTML/assets.
- DOI-linked manual-proof records.
- Raw claim-validation HTML/card pages.
- Long session screenshots/transcripts.
- Massive raw source archives.
- Temporary render-QA outputs.
- Manuscript and supporting-information Word files, which are kept in the
  submission package rather than inside this repository.

## Data Release Convention

`data_literature` contains the publication-ready extracted-curve package intended for a separate Zenodo record:

`data_literature/zenodo_extracted_curve_dataset_v1.zip`

The package includes normalized curve points and DOI/panel/catalyst provenance. It excludes original publication figures, publisher HTML, screenshots, original captions, internal validation material, and DOI-linked claim-validation cards.

## Analysis Folder Convention

The public `analysis/` folder contains only curated reported-results tables,
source rows, and lightweight scripts that correspond directly to the manuscript
and SI:

- `analysis/01_bvir_eoffset_fitting`
- `analysis/02_same_panel_ptc_relative`

The folder also includes `analysis/raw_agent_analysis_archive`, a faithful raw
working archive for process provenance. That archive intentionally contains
historical drafts, exploratory plots, large posterior/grid-search tables, and
absolute local paths; it is not the clean reproducibility entry point.

## Figure Folder Convention

Figure folders keep final manuscript-facing graphics, source scripts, and summary tables where practical.

For Figure 6 manuscript graphics, use:

`figures/Figure_06_ptc_relative/main_text_figure6_package_20260619_panelF_bv_interval`

## Code Archive Policy

The frozen framework code is stored under:

`code_reference/peeragent_code_dc6189f6bc0a.zip`

The archive contains tracked source files only and intentionally excludes `.git`, virtual environments, caches, and untracked temporary outputs. See `code_reference/PEERAGENT_REPO.md` for commit and checksum provenance.

## Git/LFS Policy

Use normal Git for source, Markdown, scripts, CSV/JSON tables, and small text files.

Use Git LFS for large or binary publication artifacts:

- Word files
- PowerPoint/Excel files
- PDFs
- PNG/JPEG/TIFF images
- ZIP archives

The `.gitattributes` file defines these patterns.
