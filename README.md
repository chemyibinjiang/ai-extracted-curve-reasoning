# From Figure Pixels to Quantitative Evidence: AI-Extracted Curves for Scientific Reasoning

This is the GitHub-repository draft for the paper companion package.

The repository contains curated data tables, benchmark curve-extraction data, final figure packages, the literature extracted-curve data package, and a frozen archive of the framework code used for the study. The manuscript and supporting information Word files are kept outside this repository folder in the submission package.

## Current Files

| Component | Location |
|---|---|
| Benchmark curve-extraction dataset | `benchmark_data/benchmark_curve_extraction` |
| Zenodo-ready literature extracted-curve dataset | `data_literature/zenodo_extracted_curve_dataset_v1.zip` |
| Curated manuscript/SI analysis summaries | `analysis` |
| Final/publishable figure packages | `figures` |
| Frozen framework-code archive | `code_reference/peeragent_code_dc6189f6bc0a.zip` |

## Public Data Boundary

This repository intentionally excludes original publication figures, publisher HTML/source asset folders, raw proof records, DOI-linked claim-validation cards, long session transcripts/screenshots, and massive raw source archives.

The extracted-curve dataset in `data_literature` contains normalized curve coordinates and DOI/panel/catalyst provenance. It is intended for a separate Zenodo record; the GitHub repository keeps a local copy for convenience.

The manuscript, supporting information, and reviewer-only claim-validation cards are not included here. They should be shared separately from the public repository.

## Analysis Scope

The public `analysis` folder contains curated manuscript/SI-facing analysis
modules for Figure 5 and Figure 6. It also contains
`analysis/raw_agent_analysis_archive`, a faithful copy of the raw working
analysis folder and placeholders for the two interactive agent-session screen
records. The raw archive is included for process provenance and should not be
used as the preferred source for final manuscript/SI numbers.

## Reproducibility

Start with:

- `REPRODUCIBILITY.md` for the practical rerun order.
- `CODE_ORGANIZATION.md` for the folder map.
- `analysis/README.md` for the curated Figure 5/Figure 6 analysis layer.
- `data_literature/zenodo_extracted_curve_dataset_v1/README.md` for the extracted-curve release.
- `figures/Figure_06_ptc_relative/main_text_figure6_package_20260619_panelF_bv_interval/README.md` for the current Figure 6 package.
