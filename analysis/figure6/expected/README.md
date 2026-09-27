# Figure 6: Expected Results

These six tables contain the numerical results underlying Figure 6. Their
SHA-256 hashes are recorded in `reproducibility/manifest.json`. The analysis
compares recalculated results with these tables without overwriting them.

| Table | Contents |
| --- | --- |
| `COVERAGE_BARS.csv` | Empirical coverage for independently optimized template budgets 1 to 10. |
| `PARAMETER_COORDINATES.csv` | Eight representative empirical and effective VHT parameter coordinates. |
| `RATE_CONTROL_FAMILY_GRID.csv` | V/H/T controls for every family on the saved half-mV grids. |
| `RATE_CONTROL_MEAN_SD.csv` | Equal-family means and sample SD, plus common-support masks. |
| `CONTROL_CROSSINGS.csv` | Dominant-control crossings for individual families and means. |
| `MEAN_CONTROL_CROSSINGS.csv` | The mean-only subset of the crossing table. |

The family grid uses A1-A4 for acid and B1-B4 for KOH. The validator checks
all eight family identities explicitly.

## Correct denominators and interpretation

The nonlinear empirical populations contain 73 acid and 234 KOH curves. Four
acid templates cover 59/73; four KOH templates cover 188/234. These are not
fractions of all 348 original Pt/C curves, nor VHT acceptance rates. The separate
linear class and eligibility filters precede nonlinear template selection.

The eight parameter points are representative template coordinates, not a
per-curve parameter distribution. The shared acid T/V ratio is an imposed model
constraint. Its fitted reference value is 2.2584675346368877.

Rate control is the logarithmic current sensitivity to scaling both forward and
reverse rates of one step, preserving its equilibrium constant and re-solving
steady-state coverage. Mean and SD use equal family weights, with sample SD
(N-1 denominator). They are not posterior uncertainty or confidence intervals.

Only rows with `inside_fitted_support=True` enter individual plotted lines;
`all_families_supported=True` selects plotted means and SD. The tables retain
unplotted model continuation rows for audit, not for claims beyond fitted support.

The acid mean has no dominant Tafel/Volmer crossover, but A4 has two near 34 and
90 mV. All four KOH templates have dominant-control crossings; the KOH mean
crosses near 31 and 155 mV. A crossing describes redistribution of control within
the selected VHT model, not proof of a pathway switch or uniquely identified
rate-determining step.

## Run the audit

From the repository root, using Python 3.10 or newer:

```text
python scripts/validate_figures.py
python -m unittest discover -s tests -p test_figure_tables.py -v
```

The validator independently recomputes means, sample SD, support masks, and
linearly interpolated dominant-control crossings. It also checks the parameter
coordinate transform and coverage counts. This is an audit of frozen numerical
results, not an end-to-end extraction or optimization run. The Figure 6
[analysis guide](../README.md) documents coordinate-based reconstruction,
template discovery, and kinetic refitting as separate operations.
