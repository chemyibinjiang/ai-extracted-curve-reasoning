# Sensitivity to Grid-Point Rounding

17 October 2026

**Summary.** A check of numerical rounding in the Figure 7/8 shape analysis
recovers one grid observation in each of four literature curves. Repeating
model selection and fitting leaves the PCA maps and group-comparison
conclusions effectively unchanged. This note records the measured differences;
the submitted figures, reference results and production analysis code are
unchanged.

## What Was Tested

The analysis represents each curve on a potential grid, using observations
within its measured range. A potential stored as `149.99999999999997` mV can
fall just below the nominal 150 mV grid position. The original routine checks
for a near-exact match on only one side of the insertion position, so it can
miss this observation at an endpoint or beside a large gap.

The sensitivity calculation checked both neighbouring points using the
existing tolerance of `1e-8` mV. The maximum interpolation gap remained 20 mV;
no extrapolation or new current correction was introduced. Across all 3,033
prepared literature curves, four gained one grid observation each. Three
were endpoints; the 140 mV observation was an interior point before a gap
wider than the interpolation limit.

| Curve label in the source data | Condition | Recovered position (mV) | Supported grid positions, submitted to checked |
| --- | --- | --- | --- |
| Pt@MOF-BCP | Acidic | 150 | 13 to 14 |
| Os NPs 5000th | Alkaline | 140 | 16 to 17 |
| Pure water | Alkaline | 270 | 17 to 18 |
| Pt/C | Alkaline | 200 | 17 to 18 |

The literature population remains **2,361 curves from 435 papers**, and the
experimental population remains **524 curves**. No experimental full-curve
support mask changes. Curve identifiers, source DOIs and individual coordinate
changes are in the [affected-curve table](numerical_sensitivity_20261017/affected_curve_details.csv).

## PCA Coordinates

The baseline refit reproduced the submitted model and diagnostics. Repeating
all 24 whole-paper held-out tuning fits with the revised matching rule still
selected three shape coordinates and smoothing 1000. The checked model was
aligned to the submitted axes by an orthogonal rotation, without translation
or rescaling, before comparing coordinates.

The following distances measure movement in the plotted PC1-PC2 plane, in
the same coordinate units as the original map. They are not percentages or
changes in current density.

| Population | Median coordinate displacement | Maximum coordinate displacement |
| --- | ---: | ---: |
| Literature curves | 0.00001284 | 0.00698310 |
| Experimental curves | 0.00001354 | 0.00003248 |
| Projected templates and Pt/C families | 0.00001344 | 0.00001351 |

For literature curves, 95% of displacements were at most 0.00002675. The
largest displacement belongs to the source curve labelled "Pure water".

| Shape coordinate | Submitted variance fraction | Checked variance fraction |
| --- | ---: | ---: |
| PC1 | 78.49400% | 78.49361% |
| PC2 | 18.49431% | 18.49482% |
| PC3 | 3.01168% | 3.01157% |

The nearest empirical-template assignment for every Pt/C family is unchanged.
The 118 identified experimental response series and the displayed Figure 8A-C
profiles are also unchanged. The current-rescaling template library and its
compatibility tests were held fixed; this check did not search for new templates.

## Group Comparisons

Figure 8F compares non-PGM dispersion with PGM-containing dispersion, including
Pt/C in the latter literature group. A ratio above one indicates broader
non-PGM responses. The six comparison populations are unchanged.

| Dataset | Potential window (mV) | Submitted ratio | Checked ratio |
| --- | --- | ---: | ---: |
| Literature | 50-150 | 1.400521 | 1.400512 |
| Literature | 50-250 | 1.488295 | 1.488296 |
| Literature | 100-250 | 1.627959 | 1.627968 |
| Experiment | 50-150 | 1.015130 | 1.015124 |
| Experiment | 50-250 | 1.230622 | 1.230619 |
| Experiment | 100-250 | 1.427608 | 1.427613 |

The largest absolute ratio change is 0.00000912 for Figure 8F and 0.00045155
for the Figure 7 dispersion diagnostics. Whether each 95% interval includes
one is unchanged. In particular, the experimental 50-150 mV interval still
includes one; this check does not turn that comparison into evidence of a
dispersion difference. The [Figure 8F table](numerical_sensitivity_20261017/figure8F_comparison.csv)
includes the intervals and sample counts.

## Held-Out Predictions

Shortened curves used for validation create additional endpoints. The revised
rule restores 15 training-grid observations across 15 cases and 11 held-out
observations across 11 cases. The same 4,352 validation cases are retained.
These are changes within validation cases, not additional curves entering
the PCA population.

RMSE is the root-mean-square error in log10 current, expressed in decades.
Coverage is the fraction of held-out observations inside the model's nominal
95% prediction interval. Both summaries below give equal weight to papers.

| Prediction test | Submitted RMSE | Checked RMSE | Submitted coverage | Checked coverage |
| --- | ---: | ---: | ---: | ---: |
| Internal gaps | 0.021522 | 0.021518 | 92.718% | 92.718% |
| Beyond 100 mV | 0.175787 | 0.175803 | 95.423% | 95.423% |
| Beyond 150 mV | 0.125217 | 0.125620 | 87.949% | 87.715% |
| Beyond 200 mV | 0.112197 | 0.112194 | 82.425% | 82.425% |

At one decimal place, coverage beyond 150 mV changes from **87.9% to 87.7%**.
The submitted reference values have not been replaced by these sensitivity
results.

## Supporting Records

This evaluation uses the submitted package at commit
[`a499ddf`](https://github.com/chemyibinjiang/ai-extracted-curve-reasoning/commit/a499ddf3369f433e771de649cfaa7c8adea7a32d).
The result snapshots below are separate from the inputs consumed by the
figure-analysis commands. The candidate implementation remains on the local
correction branch pending a possible revision; it is not merged into `main`.

- [Numerical summary and source hashes](numerical_sensitivity_20261017/summary.json).
- [Affected curves and coordinate changes](numerical_sensitivity_20261017/affected_curve_details.csv).
- [Figure 8F comparisons](numerical_sensitivity_20261017/figure8F_comparison.csv):
  `submitted` is the baseline, `fixed_model` applies the matching check without
  refitting, and `refit` repeats the model fit before projection.
- [Model-selection comparison](numerical_sensitivity_20261017/cv_comparison.csv):
  eight candidate settings, each evaluated across three paper folds.
- [Paper-weighted validation summary](numerical_sensitivity_20261017/comparison_CV_PAPER_SUMMARY.csv):
  coverage is stored as a fraction, rather than a percentage.

In these files, `corrected` and `new` denote the sensitivity calculation,
not a replacement of the submitted analysis.
