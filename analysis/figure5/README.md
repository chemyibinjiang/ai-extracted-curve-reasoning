# Figure 5: apparent resistance and current rescaling

```text
python analysis/figure5/run.py
python analysis/figure5/run.py --refit-kscn
```

Default output: `build/figure5/RESULTS.json` and panel-level CSVs. The second
command also reruns the KSCN control multistart fit and saves it separately as
`KSCN_NEW_FIT.json`; the published representative remains the reference for the
plotted scaling comparison. No input or reference fit is overwritten.

| Panel | Included calculation | Input |
| --- | --- | --- |
| A: electrical compensation | Match raw/85%-compensated MoS2 coordinates at 181 currents, fit Tafel+jR, calculate removed resistance and estimate 100% compensation | `A_SOURCE_ENDPOINTS.csv` |
| B: bubbles | Refit five Ni polarization branches with zero-offset BV+jR; estimate each EIS real-axis intercept with the original quadratic window; regress apparent resistance against EIS resistance | `B_POLARIZATION.csv`, `B_EIS_NATIVE_DATA.csv` |
| C: surface kinetics | Fit the same experimental NiMo points with BV, BV+jR and resistance-free VHT; compute symmetry-related coverage and validation checks | Experimental rows of `C_PRIMARY_DATA.csv` |
| D: current rescaling | Refit shared/independent NiFeP layer curves, regress R against inverse layer count; replay/refit finite-Volmer KSCN control and calibrate its current factor | `NiFeP_*.csv`, `KSCN_DATA.csv` |

All inputs are in `inputs/`; reference results and methods are in `reference/`.
`../SOURCE_MANIFEST.json` records file provenance and integrity hashes.
The source DOIs are recorded in `ABC_PROVENANCE.json` and `D_PROVENANCE.json`:
`10.1038/s41467-020-17121-8` (A), `10.1021/acscatal.5c00144` (B),
`10.1002/celc.202001436` (C), `10.1002/adma.201908201` (D, NiFeP), and
`10.1021/jacs.6b09351` (D, KSCN).

## Interpretation and selection

- A's 100% compensation value is an estimate from the published 85% correction,
  not a new measurement or proof that the remaining term is electrical resistance.
- B uses j=5-20 mA/cm2 for polarization fits and -Im(Z)=1.4-6 ohm for EIS
  extrapolation. EIS Rs is in ohms; Rapp is in ohm cm2. The five-cycle trend
  does not equate these quantities or identify electrode area.
- C's coverage is calculated from an independent VHT fit to the experimental
  LSV. Its complementary branch is calculated using an equivalent parameter
  set, not measured coverage or a digitized source-model trace. Neither branch
  establishes a unique pathway; the no-Tafel limit fits almost as well.
- D retains 61 of 63 NiFeP points. The two explicitly listed ambiguous 12-layer
  points (native indices 0 and 1) remain in the original input and exclusion table.
- KSCN uses 18 treated points for scale calibration and reserves the other 22.
  Their predictions and roles are exported separately. The published scale is
  0.4078511511; ln(JT) and alpha_V reach fit bounds, so this is a constrained
  representative, not uniquely identified elementary kinetics.

The default reruns the A-C fits and NiFeP fits, not just their saved summaries.
C includes 64 VHT starts, five-fold validation and window/limiting-model checks;
its outputs are in `build/figure5/nimo/`.
Assertions compare predicted voltages and fit errors, allowing minor numerical
variation in correlated parameters. Both commands have been tested with the
pinned environment. A new KSCN optimum is recorded separately from the parameter
set used in the figure.

## NiMo: direct comparison of empirical and kinetic fits

```text
python analysis/figure5/refit_nimo.py
```

This independently fits BV, BV+jR, and resistance-free VHT to the **same 40
experimental NiMo points**, selected by `source=figure4_experiment` in
`C_PRIMARY_DATA.csv`. Neither the digitized source-model red curve nor the
source-model coverage enters this fit. All three models minimize equally
weighted voltage residuals over 2.019-23.926 mA/cm2, with no voltage offset.
The source is [Bao et al., ChemElectroChem (2021)](https://doi.org/10.1002/celc.202001436),
Figure 4, 223 nm electrodeposited NiMo in 0.5 M H2SO4; the authors report
iR-corrected polarization. Digitized points are not raw instrument observations.

Outputs in `build/figure5-nimo/` include a standalone three-panel comparison in
SVG/PNG/PDF, observations and predictions, voltage residuals, newly calculated
coverage, all 64 optimization starts, five-fold cross-validation, current-window
checks, a no-Tafel limit, and wider-bound checks. `--no-plot` skips rendering;
`--skip-checks` skips the diagnostics. The command does not overwrite input
coordinates, manuscript artwork, or its reference results. The main Figure 5
uses this comparison with the empirical fits in the middle column and the
VHT fit and calculated coverage side by side on the right.

To regenerate Figure 5 from its edited layout while changing only the C plots:

```text
python analysis/figure5/update_nimo_artwork.py --inkscape /path/to/inkscape
```

This uses `build/figure5-nimo/` and writes `build/figure5-updated/`. After the
default all-panel analysis, use `--data build/figure5/nimo`. The builder checks
that A, B, D and the C concept drawing remain structurally and visually
unchanged. It does not replace the manuscript assets automatically.
The current [caption](../../figures/Figure5_caption.md) documents the model
assumptions and inference limits.

| Model | Parameters fitted | Voltage RMSE (mV) | Interleaved held-out RMSE (mV) |
| --- | --- | --- | --- |
| BV | 2 | 2.403 | 2.453 |
| BV+jR | 3 | 0.427 | 0.443 |
| VHT, without resistance | 4 | 0.661 | 0.697 |

BV+jR gives Rapp=1.250 ohm cm2. VHT gives R2=0.99920, but does not outperform
BV+jR. All five held-out folds refit their training points without initializing
from the full-data fit. Because adjacent points come from one digitized trace,
this checks within-curve prediction, **not independent experimental validation**.
The three restricted current windows also retain lower error for BV+jR and VHT
than for BV.

### Kinetic assumptions

`nimo_vht.py` reuses the tested steady-state solver from
`../figure6/vendor/vht/independent_model.py`; no new resistance term is added.
At 298.15 K, define u=F|eta|/(RT), h=kH/kV, t=kT/kV,
K=theta_eq/(1-theta_eq), and c=1000 F kV in mA/cm2. Dimensionless net rates are

```text
V = (1-theta) exp(u/2) - theta exp(-u/2)/K
H = h theta exp(u/2) - h K (1-theta) exp(-u/2)
T = t theta^2 - t K^2 (1-theta)^2
V - H - 2T = 0;   |j| = c(V+H)
```

Forward and reverse coefficients therefore obey detailed balance. Both
elementary transfer coefficients are fixed at 0.5; the fitted BV alpha retains
the repository's n_eff=2 convention and is not equated to either elementary
coefficient. Optimized base-10 parameters (h,t,K,c) have respective bounds
[-5,5], [-5,5], [-3,3], [-6,6]. The audit also widens these to [-7,7], [-7,7],
[-4,4], [-8,8]. Seed and every start's convergence/bound status are exported.

### What the comparison establishes

The same LSV curvature is compatible with an empirical BV+jR description and a
surface-kinetic description without explicit series resistance. This supports
the possibility of a kinetic contribution to apparent resistance; it does not
prove the source data contain no residual physical resistance or uniquely
identify microscopic kinetics.

The best finite-parameter fit reaches the h upper bound. Widening the bounds
changes predicted voltages by less than 0.00001 mV. A zero-Tafel VH limit gives
RMSE=0.669 mV, almost the same as full VHT. Thus the LSV does **not** provide
strong evidence that a nonzero Tafel pathway is required.

The plotted increasing-coverage representative predicts theta=0.350 to 0.928
over the observed 67.55-149.28 mV interval. This branch is a display convention,
not measured coverage. Under

```text
h' = 1/h; t' = t K^2/h; K' = 1/K; c' = c h
```

the same steady-state equations produce identical polarization and
theta'=1-theta. Both parameter sets are exported and plotted. A representative
after this transformation can lie outside the optimizer's original bounds;
the untransformed optimum and its bounds remain recorded. Near-optimal
increasing branches (within 1% of best SSE) are reported as a sensitivity range,
not a confidence interval. None of these are the source authors' fitted
parameters or digitized coverage curves.
