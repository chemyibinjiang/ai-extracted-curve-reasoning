# Figure 4 Polarization Shapes and Empirical Fits

```text
python analysis/figure4/run.py prepare
python analysis/figure4/run.py --workers 6
```

The first command rebuilds the 3,033-curve cohort from all 4,211 extracted
curves. The second refits both effective-BV models and is equivalent to
`python analysis/effective_bv/run.py population --workers 6`.
Fit outputs are in `build/effective-bv-20260927/figure4/`.

The retained cohort contains 473 papers and 80,399 points. Selection requires
linear axes, interpretable current density and potential reference, at least
five prepared points, current and voltage spans of at least 5 mA/cm2 and 5 mV,
and a maximum current density of at least 20 mA/cm2. Coordinates are restricted
to 0.2-500 mA/cm2 and 0-2,000 mV. Duplicate DOIs retain the first eligible source
record. All excluded curves remain in the complete dataset.

| Selection outcome | Curves |
| --- | ---: |
| Nonlinear axes | 59 |
| Unsupported current-density axes | 168 |
| Unsupported potential reference | 114 |
| Insufficient points or range | 336 |
| Maximum prepared current below 20 mA/cm2 | 403 |
| Duplicate publication record | 98 |
| Included | 3,033 |

`prepare.py` regenerates the decision for every curve, verifies all prepared
points, and writes `PREPARATION_CHECKS.json`. `local_slopes.py` evaluates
nine-point quadratic derivatives on the irregular log-current grid.
Window summaries weight papers equally and curves equally within each paper.

The empirical models independently fit alpha_a and alpha_c, with their sum
between 0.001 and 2. At R2 >= 0.99, BV describes 1,588 curves (52.4%) and
BV+jRapp describes 2,361 (77.8%). Accepted-fit medians are 77.6 mV/dec for
bBV, 0.428 ohm cm2 for Rapp, and 1.87 mA/cm2 for j0.

The [analysis protocol](../effective_bv/README.md) gives bounds, optimization,
and output definitions. The scientific methods correspond to SI Section 5.
