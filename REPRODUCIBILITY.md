# Reproducibility Notes

This document records the practical rerun order for the public paper companion package. It is not a replacement for the Methods section.

## Environment

Typical dependencies include:

- Python 3 with `pandas`, `numpy`, `scipy`, `matplotlib`, `seaborn`, and `python-docx`
- Node/HTML rendering where figure-specific HTML/SVG workflows are used
- Microsoft Word for final visual inspection of `.docx` files

The frozen framework archive includes its own environment files:

`code_reference/peeragent_code_dc6189f6bc0a.zip`

## Input Data

Public package-relative data roots:

| Data root | Purpose |
|---|---|
| `data_literature/zenodo_extracted_curve_dataset_v1` | Publishable extracted HER polarization-curve dataset with DOI/panel/catalyst provenance. |
| `benchmark_data/benchmark_curve_extraction` | Synthetic benchmark cases and ground-truth data for curve-extraction evaluation. |

Original publication figures, publisher HTML, raw source archives, and DOI-linked proof-card material are not included in this public repository draft.

The public `analysis` folder is a curated audit record for reported Figure 5
and Figure 6 results, not a complete rerun workspace for every interactive
analysis session. Some historical working scripts depended on internal
canonical source tables and private validation/context files that are
intentionally excluded.

## Recommended Rerun Order

1. Inspect the extracted-curve release under `data_literature/zenodo_extracted_curve_dataset_v1`.
2. Use `analysis/01_bvir_eoffset_fitting` to audit Figure 5 model counts,
   fitted descriptors, and the iR-only control.
3. Use `analysis/02_same_panel_ptc_relative` to audit Figure 6 same-panel Pt/C
   eta10/eta50, posterior, interval-decomposition, branch, and metadata-rule
   summaries.
4. Run benchmark/figure scripts only if Figure 1 or Figure 3 assets need regeneration.
5. Use `figures/Figure_05_bvir` and `figures/Figure_06_ptc_relative/main_text_figure6_package_20260619_panelF_bv_interval` for manuscript-facing graphic files.
6. Regenerate the Zenodo extracted-curve package, if needed:

   `python data_literature/build_zenodo_extracted_curve_dataset.py`

7. Run a final manuscript/SI consistency audit before submission.

## Current Manuscript-Facing Analysis Notes

- Figure 5 uses strict-BV fitting with fixed `n_eff = 2` and broad alpha bounds for the main BV/BV+iR/BV+Eoffset/BV+iR+Eoffset comparison.
- The iR-only control is included in the SI to show that linear resistance alone does not explain the broad BV+iR+Eoffset rescue rate.
- Figure 6 uses strict-BV n_eff = 2 same-panel Pt/C analysis. The current manuscript graphic is the 2026-06-19 package that replaces panel F bottom-right with the exact strict-BV interval contribution.
- Public SI claim-validation material is anonymized. DOI-linked cards are retained only as reviewer/internal evidence outside this repository.
- The public Zenodo curve package is limited to the `primary_main_HER` publication dataset and excludes original source figures, publisher HTML, screenshots, original captions, and internal validation records.
