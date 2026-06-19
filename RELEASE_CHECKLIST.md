# Release Checklist

Use this checklist before creating a submission or public-release tag.

## Manuscript And SI

- [ ] Current manuscript and public SI are kept in the submission package outside this repository folder.
- [ ] Repository README does not list manuscript or SI Word files as repository contents.
- [ ] Track changes/comments are accepted or intentionally retained for the target recipient.
- [ ] Page numbers, captions, references, and table/figure numbering are visually checked in Word.
- [ ] Public SI does not contain DOI-traceable claim-validation cards or raw proof paths.

## Data And Figures

- [ ] Figure 4 QC numbers match the manuscript/SI wording.
- [ ] Figure 5 strict-BV/BV+iR/BV+Eoffset/BV+iR+Eoffset numbers match the current analysis tables.
- [ ] Figure 6 n values and branch counts match the current analysis tables. The current manuscript package is `figures\Figure_06_ptc_relative\main_text_figure6_package_20260619_panelF_bv_interval`.
- [ ] Final figure files are present in `figures`.
- [ ] Benchmark data are present under `benchmark_data`.
- [ ] Separate Zenodo extracted-curve package is regenerated at `data_literature\zenodo_extracted_curve_dataset_v1.zip`.
- [ ] Zenodo extracted-curve package contains DOI/panel/catalyst provenance and no original publication figures, source HTML, screenshots, original captions, or raw proof material.

## Code And Analysis

- [ ] `code_reference\PEERAGENT_REPO.md` records the frozen framework archive, commit, and checksum.
- [ ] If `analysis\` is added later, it contains only compact manuscript/SI-facing summary tables and source rows.
- [ ] If `analysis\` is added later, no active analysis output depends on an external absolute path unless the dependency is explicitly documented.
- [ ] Git LFS is installed before committing large binary files.

## Public/Private Boundary

- [ ] Private validation/proof folders are not staged for a public repo.
- [ ] Raw claim-validation HTML/card folders are not staged for a public repo.
- [ ] Session screenshots/transcripts are not staged for a public repo.
- [ ] Massive raw Z-drive archives are not staged for a public repo.
- [ ] Reviewer-only evidence is packaged separately if needed.

## Final Snapshot

- [ ] Optional: generate a fresh file inventory/checksum list for internal archiving if needed.
- [ ] Record the Zenodo dataset DOI in the manuscript/SI and README after the Zenodo record is reserved or published.
- [ ] Run `git status --short` and inspect staged/untracked files.
- [ ] Create a release tag, for example `v1.0-submission`, only after the above checks pass.

