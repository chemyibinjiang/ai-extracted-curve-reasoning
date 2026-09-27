# Figure 5 Apparent Resistance and Current Scaling

```text
python analysis/figure5/run.py
python analysis/figure5/refit_nimo.py
```

The first command is equivalent to `analysis/effective_bv/run.py examples`.
It writes all panels to `build/effective-bv-20260927/figure5/`; the second
independently runs the NiMo comparison in `build/figure5-nimo/`.
Both use the same variable-coefficient empirical BV implementation.

| Panel | Calculation | Source DOI |
| --- | --- | --- |
| A | MoS2 compensation accounting and high-current Tafel+jRapp fits | 10.1038/s41467-020-17121-8 |
| B | Five Ni polarization fits and EIS intercepts during cycling | 10.1021/acscatal.5c00144 |
| C | Independent BV, BV+jRapp, and resistance-free VHT fits to NiMo | 10.1002/celc.202001436 |
| D | NiFeP loading dependence and Ni-C-N/KSCN current scaling | 10.1002/adma.201908201; 10.1021/jacs.6b09351 |

All digitized inputs are under `inputs/`. The MoS2 comparison uses 181 matched
currents. The inferred removal is 0.0340 ohm cm2; the full-compensation value
0.115 ohm cm2 is an estimate, not another measured trace. Ni fits use 5-20
mA/cm2, and EIS extrapolation uses -Im(Z)=1.4-6 ohm. Rapp (ohm cm2) and the
EIS series resistance Rs (ohm) are distinct quantities; their trend has R2=0.9857.

The NiMo comparison uses the same 40 experimental points from Figure 4 of
Bao et al., a 223 nm film in 0.5 M H2SO4 with source-reported iR correction.
Coverage is calculated from the VHT fit, not digitized from the paper.

| Model | Fitted parameters | Voltage RMSE (mV) | Held-out RMSE (mV) |
| --- | ---: | ---: | ---: |
| BV | 3 | 2.096 | 2.141 |
| BV+jRapp | 4 | 0.427 | 0.443 |
| VHT without resistance | 4 | 0.661 | 0.697 |

BV+jRapp gives Rapp=1.250 ohm cm2. VHT includes detailed balance, alphaV=
alphaH=0.5, and steady-state V-H-2T=0; current is proportional to V+H. Its
equivalent parameter transformation gives complementary coverage and the same
polarization. Diagnostics include 64 starts, five interleaved held-out folds,
restricted windows, enlarged bounds, and the zero-Tafel limit. Held-out points
test interpolation within this trace, not independent experimental replication.

## NiFeP Layer Number

The [63 original points](inputs/NiFeP_ORIGINAL_DATA.csv) include all three
12-, 18-, and 24-layer traces from Peng et al., Figure 4c. The
[exclusion ledger](inputs/NiFeP_EXCLUDED_DATA.csv) identifies the two ambiguous
initial points of the 12-layer trace by database curve index and native point
index. Both models use the same remaining 61 points, with independent effective
coefficients and the bounds in the common protocol.

| Layers | Points | BV voltage RMSE (mV) | BV+jRapp voltage RMSE (mV) | Rapp (ohm cm2) |
| --- | ---: | ---: | ---: | ---: |
| 12 | 24 | 17.497 | 1.075 | 1.486 |
| 18 | 20 | 14.990 | 0.591 | 1.024 |
| 24 | 17 | 13.660 | 0.955 | 0.680 |
| Shared shape, current j/N | 61 | 20.826 | 5.134 | Layer-dependent |

Independent fits give approximately Rapp = 17.772/N ohm cm2. The shared fit
uses one parameter set for all three layer-normalized traces; it is an
approximate common shape, not an exact collapse. Its normalized resistance
coefficient is 18.666 ohm cm2, distinct from the 17.772 coefficient obtained
by regressing the independently fitted resistances against 1/N.

The [checked model comparison](reference/NIFEP_MODEL_COMPARISON.csv) and
[point predictions](reference/NIFEP_POINT_PREDICTIONS.csv) can be inspected
without running Python. They are expected outputs, not optimizer inputs.
`python analysis/figure5/run.py` recomputes them from the coordinates as
`D_NIFEP_MODEL_COMPARISON.csv` and `D_NIFEP_PREDICTIONS.csv` under the output
directory above. The generated HTML report also displays the comparison.

Parameter units and current normalization:

- Fits use q = j/N. `j0_per_layer_mA_cm2` and `R_per_layer_ohm_cm2` refer to q.
  For geometric current j, j0 = N*j0_per_layer and Rapp = R_per_layer/N.
  The common fitting bounds are applied to the q-based parameters.
- `Rapp_geometric_ohm_cm2` is the resistance reported in the table and Figure 5D.
  Geometric parameters are blank for the pooled shared fit because they depend on N.
- In `D_NIFEP_FITS.csv`, `j0` and `R` refer to q; `independent_R` and
  `predicted_R` are geometric Rapp from the independent and shared fits.
- In the point table, `shared_eta_mV` and `independent_eta_mV` are BV+jRapp
  predictions; the two columns containing `_BV_` are BV-only predictions.
  All errors are voltage errors in mV, evaluated at the observed current.

## KSCN Current Scaling

KSCN uses 18 treated points to calibrate a current multiplier of 0.407851,
then evaluates the other 22 points.

See [the common protocol](../effective_bv/README.md) and SI Section 6.
Use `analysis/effective_bv/artwork.py` to update all affected manuscript panels.
