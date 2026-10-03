# Population shape model and template comparison

This is the executable-method companion to SI Section 9. The model is an
observed-only penalized probabilistic functional factor model: missing profiles
are not completed before fitting.

## Observations

Prepared coordinates inherit the Section 5.1 current window of 0.2-500 mA/cm2.
An endpoint near 500 is therefore not evidence of physical saturation. All
comparisons condition on the observations surviving source preparation.

Finite positive currents are transformed to base-10 logarithms. Duplicate
potentials are combined by median log current. A 10 mV grid spans 20-300 mV.
A grid position contributes if it is observed directly or bracketed by native
points at most 20 mV apart. No extrapolation, monotonicity enforcement, or
template-compatibility gate is applied. Inclusion requires four supported grid
cells, 30 mV of supported span and four native in-window observations.

## Latent Model

At the observed cells of curve i:

$$y_i = a_i\mathbf{1} + B_i\mu + B_i L z_i + \epsilon_i,
\quad z_i\sim N(0,I),\quad \epsilon_i\sim N(0,\sigma^2 I).$$

The unrestricted intercept removes one multiplicative current scale. It is not
an exchange current density and cannot remove current-dependent shape changes.
Cubic splines use the normalized coordinate u=(eta-20)/280, boundary knots
repeated four times, and internal knots 0.2, 0.4, 0.6, 0.8. Centering and
orthonormalization over a 1,001-point full-domain quadrature leave seven
nonconstant basis functions. P is their integrated squared-second-derivative
matrix normalized to unit trace. Mean and loading coefficients share the
quadratic roughness penalty.

With M_i=I-11^T/n_i, G_i=B_i^T M_i B_i and h_i=B_i^T M_i y_i:

$$C_i=(I+L^T G_i L/\sigma^2)^{-1},\qquad
\bar z_i=C_i L^T(h_i-G_i\mu)/\sigma^2.$$

An EM fit gives each paper equal total weight, divided among its curves. Cell
contributions are not divided by observed segment length. Residual SD is at
least 0.02 log10 units. Convergence uses relative changes below 1e-4 in the mean,
loading covariance and residual variance after at least 17 iterations. All
initialization constants and updates are in `lib/partial_model.py`.

## Tuning Without Native-Point Leakage

Three whole-paper folds (seed 20261031) compare ranks 1-4 and smoothing strengths
10 and 1,000. Masks are applied to native observations **before** interpolation.
Tail cutoffs are 100, 150, 200 mV; internal blocks remove the middle third of
native potentials. Train/target grids use disjoint native points. Removed
internal-block grid positions are explicitly excluded from training.

Errors average mask tasks within curve, curves within paper, then papers.
Among converged settings within one standard error of the best mean RMSE, the
lowest rank and then strongest smoothing is selected: rank 3, smoothing 1,000.
These are tuning diagnostics, not a nested post-selection generalization test.
Interpolated cells are correlated; nominal Gaussian uncertainty is consequently
checked empirically rather than assumed to be perfectly calibrated.

| Mask | Paper-mean RMSE | Coverage of nominal 95% predictions |
| --- | --- | --- |
| Internal block | 0.0215 | 92.7% |
| Above 100 mV | 0.1761 | 95.4% |
| Above 150 mV | 0.1252 | 88.0% |
| Above 200 mV | 0.1121 | 82.4% |

## Shape Coordinates and Projection

After orthogonalizing L, let s_k be its column norms. Coordinates are
x_ik=s_k zbar_ik; covariance is V_i=diag(s) C_i diag(s). The first two modes carry
78.5% and 18.5% of fitted latent variance. The third mode remains in distance
and dispersion calculations. Short-support posterior means can shrink toward
the shared prior. They are estimates, not completely observed shape vectors.

Templates never train the population model. The same frozen mean, loadings,
noise level, intercept elimination and regularized scoring operator project
each template using only its supported cells. Acidic Pt/C templates end at
190 or 200 mV; their upper tails are not supplied. Projection covariance is
conditional on the population model, not template-parameter uncertainty.
All eight Pt/C families have a nearest neighbor among the six PGM-rich shapes
in the full three-coordinate space.

## Dispersion and Support

Group-normalized equal-paper weights w_i give centroid xbar=sum(w_i x_i).
Expected squared dispersion includes conditional score uncertainty:

$$D^2=\sum_i w_i\|x_i-\bar x\|^2+
\sum_i w_i(1-w_i)\operatorname{tr}(V_i).$$

Support strata combine condition and first/last supported potential in 50 mV
bins. Let M_gs be the original group-weighted mass. A target q_s proportional
to min_g M_gs is normalized on shared positive-support strata. Weights are
multiplied by q_s/M_gs. This balances observed support, not current or slope.
The target population is the shared-support subset, not the entire corpus.

Intervals use 999 coupled whole-paper resamples and full conditional score
draws (seed 20261083), holding the fitted basis and support target fixed. They
exclude basis uncertainty and do not correct current-dependent termination or
publication selection. Identical-shape masking uses the same 75 complete donor
curves from 61 papers for every group. Masks alone do not reproduce the wider
non-PGM pattern. Reliability >=0.9 comparisons provide a further sensitivity check.

## Empirical Templates

The separate nonlinear non-Pt/C discovery population has 2,267 records, of which
1,667 pass empirical BV+jR voltage-space R2>=0.99. A frozen 17,005-candidate
library and amplitude-only compatibility matrix underpin the achieved-coverage
scan. For eta=F(j), a match evaluates F(j/beta), beta>0, with no potential shift
or shape refit. The objective counts each compatible curve at most once in a
selected union. Independent selections for K=1-30 need not be nested.

Removing duplicate/subset coverage rows and collapsing repeated curve patterns
leaves 4,804 candidate rows and 1,660 column patterns with integer multiplicities.
The public replay verifies this reduction and every achieved union, but does
not search a new candidate library.

Native points in Figure 7D use log10[j_obs/(beta*f(50 mV))]; template lines use
log10[f(eta)/f(50 mV)]. The reference current is fitted, not an exchange current.
Native potentials and residuals are retained. All 50,127 matched point records
are archived; 37,299 fall in the displayed 50-300 mV interval. Membership is
overlapping, so bar counts and native-point records are not unique-curve totals.
Figure 1D and the TOC instead align template lines at 20 mV. The TOC's j0 label
denotes that alignment reference, not the fitted BV exchange-current parameter.

## Independent Complete-Window Check

SI Tables S28-S29 use the separate 2,267-record, composition-known, non-Pt/C nonlinear
source, without a BV or template gate. Curves must bracket the requested window,
contain eight native in-window points, and have no bracketing gap >20 mV.
Positive log current is interpolated to 41 positions and mean-centered; an
alternative divides current by its within-window RMS. Five windows are tested.

Dispersion is RMS profile distance between curves from **different original
papers**, with equal paper/within-paper curve weights. Same-paper pairs remain
excluded when resampling repeats a paper. The 3,000 coupled whole-paper
bootstrap draws use seed 20260946. This pair-distance metric is distinct from
the latent centroid metric above. The pooled analysis also includes 36
other/unclassified-condition curves in its 458-curve primary cohort.

## Observed Current and Relative Growth

SI Section 9.9 uses the population cohort without a template gate. At each
potential, only locally bracketed log-current values enter the distribution;
there is no extrapolation or full-range requirement. Papers have equal weight
within each condition and composition group, and curves share their paper's
weight. Exponentiating the mean log current gives a geometric-mean current.

Growth is 100 times the change in log10 current divided by the potential-window
width in mV. Each eligible curve must bracket both endpoints, have at least four
native in-window points, and have no bracketing native gap above 20 mV. Windows
are 20-50, 50-100, 100-150, 150-200, 200-250 and 250-300 mV. Growth is calculated
within each curve, not by differentiating the changing population mean.
Pointwise 95% intervals use 1,999 paper-bootstrap resamples (seed 20261104).
Sample composition can change with potential; these are observed-support
comparisons, not evidence of a unique flattening mechanism.
