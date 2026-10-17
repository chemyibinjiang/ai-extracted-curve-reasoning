# Release Checklist

Reviewer-facing checks, 17 October 2026. Manuscript and SI files are maintained
separately and were not edited during this repository review.
The review package is distributed from the default branch, `main`.

## Verified

- [x] Run all 83 regression tests in a fresh Windows checkout with Python 3.13.12 and pinned dependencies.
- [x] Replay the 137-curve Figure 3 benchmark and recorded review-count arithmetic.
- [x] Verify the released ZIP and rebuild all 4,211 curves into the 3,033-curve fitting cohort.
- [x] Refit all 6,066 BV/BV+jR models; reproduce 1,588 and 2,361 accepted fits.
- [x] Repeat the 12-start VHT family fitting protocol and its sharing-model comparisons.
- [x] Repeat Figure 7's 24 tuning fits, final model, native residual checks and selected-template coverage.
- [x] Reproduce the complete-window SI sensitivity tables.
- [x] Reproduce Figure 8 from all 561 native records, retaining 524 eligible curves.
- [x] Check all eight manuscript SVG/PNG pairs and six numerical tables against their manifest.
- [x] Check the live Tafel viewer against all eight recorded source hashes and its builder hash.
- [x] Correct the Co-V instrument/geometric-area conversion; verify against the source eta10 value without changing submitted shape results.
- [x] Protect Figure 8 source and reference folders from output overwrites.
- [x] Update navigation, data links, clone instructions and the complete test-data download list.
- [x] Preserve submitted numerical results and figure assets.
- [x] Record the separate [PCA grid-rounding sensitivity evaluation](reproducibility/NUMERICAL_SENSITIVITY_20261017.md), without replacing submitted code, results or figures.

## Follow-up

- [ ] Confirm a repository-wide software license and third-party redistribution terms.
- [ ] Coordinate any numerical changes with manuscript/SI revisions; no automatic document updates are made here.
- [ ] Create a version tag and record an archive identifier when available.
