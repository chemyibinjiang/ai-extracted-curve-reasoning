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
- [x] Preserve submitted numerical results and figure assets; keep the endpoint correction check separate.

## Follow-up

- [ ] If a numerical revision is undertaken, resolve endpoint rounding before regenerating the Figure 7 model and its dependent results.
- [ ] Confirm a repository-wide software license and third-party redistribution terms.
- [ ] Coordinate any numerical changes with manuscript/SI revisions; no automatic document updates are made here.
- [ ] Create a version tag and record an archive identifier when available.

### Endpoint Rounding

The Figure 7/8 observation routines check a near-exact grid match only on the
right of the insertion point. A native endpoint infinitesimally below a grid
position can therefore be marked missing. Four curves in the existing
literature shape cohort gain one grid observation under a two-sided check:

| Curve ID | Grid position (mV) |
| --- | --- |
| `batch0/case54/figure_5__panel_b/curve_3` | 150 |
| `batch1/case89/figure_3__d/curve_orange_dashed` | 140 |
| `batch3/case466/figure_5__panel_e2/curve_pure_water_black` | 270 |
| `batch5/case799/figure_3__panel_a/curve_5` | 200 |

A check of all 3,033 prepared source curves found no additional affected masks
and no inclusion changes: the population remains 2,361 curves from 435 papers.

With the submitted Figure 7 model held fixed, a separate two-sided check leaves
all six Figure 8F cohorts and ratios unchanged to numerical precision. Individual
full-support coordinates do change. This correction check is separate from the
submitted analysis: the model, reference tables and figures remain unchanged.
No model refit with corrected masks was performed, so its effect has not been
assessed. Reproducing the submitted tables does not resolve the endpoint issue.
