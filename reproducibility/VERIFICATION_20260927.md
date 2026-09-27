# Reproduction Check 27 September 2026

The numerical release was downloaded from GitHub into a separate checkout and
tested with a newly created Python 3.13.12 environment on Windows. Dependencies
were installed from `requirements-analysis.txt`. The reader-guide updates were
then checked in that checkout. No source-paper downloads, API calls, manuscript
folder, or analysis files elsewhere on the workstation were used by the runs.

| Check | Outcome |
| --- | --- |
| Complete dataset and provenance | 4,211 curves, 132,314 points, 1,035 panels; all checksum and join checks pass |
| Synthetic benchmark replay | All 137 curves replayed; maximum metric difference below 8e-13 pixels; rounded summaries 0.36 / 1.13 / 1.44 |
| Cohort rebuilt from complete dataset | 3,033 curves, 473 papers, 80,399 points; coordinates and exclusion ledger match |
| Full population refit | 6,066 fits; accepted counts 1,588 BV and 2,361 BV+jR |
| NiMo independent fits | Voltage RMSE 2.095907 / 0.427313 / 0.660728 mV for BV / BV+jR / VHT; held-out checks also match |
| Pt/C reconstruction | 12 starts per electrolyte/sharing scheme (96 starts); principal kinetic parameters and raw replay counts agree with Figure 6 |
| Full finite-grid search | 276,551 candidates per electrolyte; K=1..10 coverage counts certified; four templates cover 59/73 and 188/234, with the same selected candidate indices |
| Unit and isolated-package tests | 39 existing tests and two added reader-reproduction tests pass |
| Artwork | All six figures regenerated in a separate output directory using Inkscape; published 18-asset integrity/numerical audit passes |
| Supporting information | Selection and parameter tables checked against fresh outputs at displayed precision; all pages inspected after Word rendering; prior tracked edits retained |

The full candidate search was also completed in a clean Python 3.12 environment
with the same pinned direct dependencies. Counts and selected templates agree.
This is an additional compatibility check, not a requirement to install two
Python versions. Tests on macOS/Linux were not performed.

Dataset line endings are preserved by `.gitattributes` so the checksum manifest
works across checkout settings. Numerical CSV records and values were not
changed by that packaging correction. The 20 label differences recorded during
cohort preparation are reported in `LABEL_DIFFERENCES.csv`; they do not change
the fitted coordinates or selected cohort.

## Review Scope

Synthetic distances and HER analyses are calculated from supplied numerical
inputs. Literature-review percentages are arithmetic summaries of recorded
assessments. Confidential claim cards and reviewed publisher-figure geometry
are not in the public repository, so those judgments are not independently
re-adjudicated by these checks. The distinction is also stated in SI Sections
3.3 and 4.2 and the [Figure 3 guide](../analysis/figure3/README.md).

Commands and output locations are in [Reproducibility](../REPRODUCIBILITY.md)
and the [result map](RESULT_MAP.md).
