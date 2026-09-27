# Effective BV Analysis

This is the analysis entry point for the revised Figures 4-6. Figure 1D uses the
same alkaline family curves and kinetic coordinates as Figure 6. Both effective
coefficients are fitted; their sum is not fixed. The report contains only this
parameterization and its BV versus BV+jR comparison.

```text
python analysis/effective_bv/run.py all --workers 6 --starts 12
python tests/test_effective_bv.py
```

The stages `population`, `examples`, `families`, and `report` can also be run
separately. Outputs default to `build/effective-bv-20260927/`. No source PDFs,
external working directories, or exploration outputs are runtime dependencies.

## Empirical Form

For positive cathodic current magnitude j,

```text
j = j0 [exp(alpha_c F eta_star / RT) - exp(-alpha_a F eta_star / RT)]
eta_star = |eta| - j Rapp
```

`analysis/common/effective_bv.py` evaluates the exact inverse and its analytic
Jacobian. Optimization coordinates are log(j0), alpha_c/(alpha_a+alpha_c),
log(alpha_a+alpha_c), and optionally Rapp. All fits minimize equal-point voltage
SSE and have zero voltage offset. Numerical bounds are j0 in [1e-12, 1e8]
mA cm^-2, coefficient sum in [0.001, 2], cathodic fraction in [0.01, 0.99], and
Rapp in [0, 100] ohm cm^2. The small positive lower bounds avoid degenerate
zero-current solutions. Near-endpoint sensitivity was checked separately in
the parameterization assessment, not included as a second model here.

The effective-BV motivation is [Prats and Chan (2021)](https://doi.org/10.1039/D1CP04134G).
The application here is empirical comparison of published polarization curves;
the added linear-in-current term belongs to this analysis.

## Figure 4

The unchanged input population has 3,033 curves from 473 papers and 80,399
points. Every curve is reoptimized for both models, with multistart optimization
and the supplied variable-coefficient solutions as additional feasible starts.
The resistance model also includes the BV optimum as a nested start.

Accepted counts at R2 >= 0.99 are 1,588 and 2,361. Parameter distributions,
three example curves, and the modeled local-slope decomposition are recomputed.
Observed local derivatives depend on the data, not the empirical formula.
Use `python analysis/figure4/run.py prepare --output build/cohort-check` to
independently rebuild this same cohort from all 4,211 extracted curves.

## Figure 5

- Compensation: rerun the Tafel+jR regression and compensation accounting.
- Cycle/EIS example: refit every BV and BV+jR curve and the resistance trend.
- NiMo: fit both empirical models and resistance-free VHT to the same 40 points;
  recompute coverage, exact complementary symmetry, five-fold predictions,
  window checks, VH limit, and enlarged VHT bounds.
- NiFeP: refit the shared layer-normalized response and all independent layer
  curves; recalculate inverse-layer resistance scaling.
- KSCN: retain its independent kinetic model; recalculate scale calibration
  and held-out predictions. This model does not contain the BV coefficient sum.

## Figure 6

The explicit variable-coefficient candidate search completed for this revision
provides the selected templates and K=1..10 coverage counts. The included
reference library has four acidic and four alkaline templates, covering 59/73
and 188/234 nonlinear curves. This stage reoptimizes every current amplitude
against every selected template and checks memberships on the original points.
It does not repeat the finite-grid search. To search all 276,551 candidates
from coordinates, run `python analysis/effective_bv/search.py`. This separately
profiles every nonlinear curve and optimizes coverage for K=1..10. Use
`--grid-only` to inspect the candidate library without running the search.

VHT reconstruction is optimized from 12 starts per condition and parameter
sharing scheme. Each family is checked on a 1,000-point template grid. Previously
optimized seeds are retained if no new search improves the minimax error;
`selected_stage` and `optimizer_converged` distinguish that from new convergence.
The main representation uses DeltaG alone in acid and DeltaG plus T/V in KOH.
H/V and independent sharing schemes are additional kinetic controls.

The main solutions are replayed on individual member curves, and their coverage,
rate controls, equal-family means and sample SD are recomputed. Empirical
family coverage and kinetic replay coverage are reported separately.

## Reference and Output Integrity

`reference/MANIFEST.json` checks source coordinates and optimization seeds.
The seeds contain only variable-coefficient solutions. Their import record is
preserved in the analysis archive; no archive or original working directory is
needed to use them. Population and VHT checkpoints reject code/input changes.

The generated report is a numerical review set. Manually edited publication
SVGs, the figure checksum manifest, and Word documents are not overwritten.
The committed artwork and SI V25 use these results. Earlier analysis workflows
are preserved in `exploration/archive/` and are not runtime dependencies.
