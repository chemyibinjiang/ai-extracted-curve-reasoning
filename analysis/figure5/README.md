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

The NiFeP calculation retains 61 of 63 points; the two excluded initial points
remain in the source table and exclusion ledger. The inverse-layer coefficient
is 17.772 ohm cm2 per inverse-layer unit. KSCN uses 18 treated points to calibrate
a current multiplier of 0.407851, then evaluates the other 22 points.

See [the common protocol](../effective_bv/README.md) and SI Section 6.
Use `analysis/effective_bv/artwork.py` to update all affected manuscript panels.
