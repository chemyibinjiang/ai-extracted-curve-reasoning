# Augmenting Scientific Reasoning with AI-Extracted Curves from Figures

This is the GitHub-repository draft for the paper companion package.

The repository contains curated data tables, benchmark curve-extraction data, final figure packages, the literature extracted-curve data package, and a frozen archive of the framework code used for the study. The manuscript and supporting information Word files are kept outside this repository folder in the submission package.

## Current Files

| Component | Location |
|---|---|
| Benchmark curve-extraction dataset | `benchmark_data/benchmark_curve_extraction` |
| Zenodo-ready literature extracted-curve dataset | `data_literature/zenodo_extracted_curve_dataset_v1.zip` |
| Final/publishable figure packages | `figures` |
| Frozen framework-code archive | `code_reference/peeragent_code_dc6189f6bc0a.zip` |

## Public Data Boundary

This repository intentionally excludes original publication figures, publisher HTML/source asset folders, raw proof records, DOI-linked claim-validation cards, long session transcripts/screenshots, and massive raw source archives.

The extracted-curve dataset in `data_literature` contains normalized curve coordinates and DOI/panel/catalyst provenance. It is intended for a separate Zenodo record; the GitHub repository keeps a local copy for convenience.

The manuscript, supporting information, and reviewer-only claim-validation cards are not included here. They should be shared separately from the public repository.

## Analysis Scope

The public analysis folder is intentionally not included in this draft. It can
be added later as a curated reported-results folder after a final audit against
the manuscript and SI. The local working analysis contains many exploratory
PDFs, posterior draws, and intermediate tables that should not be copied into
the public repository wholesale.

## Reproducibility

Start with:

- `REPRODUCIBILITY.md` for the practical rerun order.
- `CODE_ORGANIZATION.md` for the folder map.
- `data_literature/zenodo_extracted_curve_dataset_v1/README.md` for the extracted-curve release.
- `figures/Figure_06_ptc_relative/main_text_figure6_package_20260619_panelF_bv_interval/README.md` for the current Figure 6 package.
