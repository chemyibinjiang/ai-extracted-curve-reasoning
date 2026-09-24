# Figure 4: Polarization Shapes and BV+jR Fits

```text
python analysis/figure4/run.py
```

The entry point starts from all 4,211 extracted curves (132,314 points) in
[the complete dataset](../../data_literature/zenodo_extracted_curve_dataset_v1/README.md).
It rebuilds the 3,033-curve cohort from 473 papers and its 80,399 fitting points,
then verifies them against the supplied figure inputs. No source-paper download
or external working directory is required. Results are written to `build/figure4/`.

| Panel | Calculation | Output |
| --- | --- | --- |
| A | Nine-point local quadratic derivatives on the irregular log-current grid; per-curve medians within eight potential windows | `LOCAL_SLOPES.csv`, `CURVE_WINDOW_SLOPES.csv`, `WINDOW_SUMMARY.csv`, `HISTOGRAMS.csv` |
| B | Re-evaluate BV and BV+jR fits on every included point; summarize voltage errors and fit quality; calculate distributions of accepted BV+jR parameters | `FIT_METRICS.csv`, `CORPUS_FIT_METRIC_SUMMARY.csv`, `PARAMETER_SUMMARY.csv`, `PARAMETER_HISTOGRAM_BINS.csv` |
| C | Pt/C, N-Ni, and WO3 example data and model predictions | `EXAMPLE_CURVES.csv` |
| D | Observed and model-derived local slopes, including the BV and jR contributions | `EXAMPLE_SLOPES.csv` |

`inputs/POINTS.csv` contains the prepared figure-analysis coordinates, not the
complete extracted dataset.
`inputs/CURVES.csv` identifies the source paper, panel, curve, and normalization.
`reference/FIT_PARAMETERS.csv` contains the parameters used in the figure.
The default command verifies these parameters against the rebuilt points; it
does not reoptimize them. Local slopes and all summaries are recalculated.

## All Curves and Cohort Preparation

```text
python analysis/figure4/run.py prepare --output build/figure4-preparation
```

The complete dataset retains excluded curves and all their extracted coordinates.
`prepare` applies axis interpretation, unit conversion, current-sign branch
selection, point-range restrictions and publication deduplication. The same
preparation runs automatically before `analyse` and `refit`.

The [inclusion/exclusion record](reference/COHORT_SELECTION.csv) has one row for
every extracted curve. The command regenerates it as `COHORT_SELECTION.csv`,
alongside `PREPARED_CURVES.csv`, `PREPARED_POINTS.csv` and `PREPARATION_CHECKS.json`.
The following counts use the first failing rule in the listed order; the record
also retains each rule separately so overlapping exclusions remain visible.

| Outcome | Curves |
| --- | ---: |
| Nonlinear axes | 59 |
| Unsupported current-density axes | 168 |
| Unsupported potential reference | 114 |
| Insufficient prepared points or current/potential range | 336 |
| Prepared current does not reach 20 mA/cm2 | 403 |
| Duplicate publication record | 98 |
| Included in Figure 4 | 3,033 |
| Total extracted curves | 4,211 |

Duplicate DOIs retain the first included record in `source_publication_records.csv`
order, regardless of fit quality. Curves require at least five prepared points,
at least 5 mA/cm2 current span and 5 mV potential span. Currents equal after
rounding to six decimals are combined using mean current and median potential.
Ten curves have display-label differences between the dataset and fit table;
`LABEL_DIFFERENCES.csv` records both labels without modifying either source.
Curve IDs, selection, coordinates and numerical metadata agree.

## Refit

```text
python analysis/figure4/run.py refit --workers 4 --output build/figure4-refit
```

This optimizes zero-offset BV and BV+jR models with multistart initialization,
without using the reference fit parameters as starting values. Results go to
`REFITTED_PARAMETERS.csv`, separate from the figure reference. `REFIT_RUN.json`
records convergence and timing; `REFIT_CHECKS.json` validates recalculated
objectives, reference RMSE/R2 agreement and every R2 >= 0.99 pass assignment.
The command fails if any fit is unsuccessful or a validation check fails.
For a single-curve check:

```text
python analysis/figure4/run.py refit --workers 1 --curve batch8/case1831/figure_5__panel_a/curve_2 --output build/figure4-example-refit
```

A refit is a numerical robustness check: correlated parameters or alternative
local optima need not be bit-identical to the supplied representative.

## Selection and Interpretation

- Current and overpotential are the retained positive analysis coordinates:
  0.2-500 mA/cm2 and 0-2,000 mV; each cohort curve reaches at least 20 mA/cm2.
  Cohort membership is rebuilt from the complete coordinate dataset, not from
  publisher images.
- Models fix n_eff=2 and T=298.15 K, alpha in [0.01, 0.99], R in [0, 100]
  ohm cm2, and zero potential offset.
- R2 >= 0.99 is met by 806 BV and 2,351 BV+jR fits.
- Parameter histograms use the 2,351 accepted BV+jR curves from 460 papers.
  Percentages retain that denominator even when values fall outside the plotted
  axis. No histogram tail is silently removed.
- Fit statistics weight curves equally. Local-slope windows first use one median
  per curve, then weight papers equally and curves equally within each paper.
- Local derivatives require symmetric nine-point support and the documented
  width/conditioning gates in `local_slopes.py`. No extrapolation or restored
  low-current points enter these calculations.
- b_BV is an asymptotic fit coefficient, not the local derivative. Rapp and j0
  are effective model parameters, not independently identified physical constants.

The default analysis, complete coordinate-to-cohort preparation and all 6,066
model refits have been validated in the pinned environment. All fits succeeded,
and every pass assignment matched the figure reference (806 BV, 2,351 BV+jR).
