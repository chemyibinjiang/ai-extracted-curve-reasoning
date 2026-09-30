# Figure 6 Pt/C Families and HER Kinetics

```text
python analysis/figure6/run.py --workers 6 --starts 12
python analysis/effective_bv/search.py --output build/effective-bv-search
```

The first command reoptimizes current amplitudes against the selected empirical
templates, refits VHT sharing schemes, and recomputes individual-curve replay,
coverage, and rate control. It is equivalent to the `families` stage of the
[common analysis entry point](../effective_bv/README.md).
The second performs the full finite-grid template search from coordinates.
These calculations correspond to SI Sections 7-8.

| Population | Acid | KOH |
| --- | ---: | ---: |
| All Pt/C curves | 81 | 267 |
| Window-eligible | 78 | 263 |
| Through-origin linear | 5 | 29 |
| Nonlinear family analysis | 73 | 234 |
| Empirical coverage | 59 | 188 |
| Selected families | 4 | 4 |
| VHT individual-curve coverage | 48/59 | 165/188 |

The windows are 0-200 mV and 0-300 mV. Curves require at least five original
points with nonzero potential variance. Linear and template fits use voltage
R2 >= 0.99; no observations are extrapolated to expand a curve's support.

Templates have three shape coordinates: alpha_a, alpha_c, and Q=j0 Rapp.
Only a positive current amplitude varies for each curve. Four templates first
exceed 80% coverage in both electrolytes. Figure 6D shows the bBV/Q projection,
not the full three-dimensional shape space. The 276,551-candidate search
optimizes K=1..10 separately; its count certificate applies to that finite grid.

Resistance-free VHT uses reversible Volmer, Heyrovsky and Tafel steps with
detailed balance, V-H-2T=0, and alphaV=alphaH=0.5. Acid shares H/V and T/V and
varies adsorption energy and current amplitude. KOH shares H/V and additionally
varies T/V. The maximum template RMSE is 0.762 mV for acid and 1.442 mV for KOH;
the corresponding pooled RMSE values are 0.566 and 1.242 mV. All sharing schemes
minimize the same equal-template pooled voltage error. See the
[unified protocol and SI comparisons](../effective_bv/README.md#figure-6).

Rate control perturbs forward and reverse constants together at fixed
thermodynamics, then resolves coverage. Means weight the four families equally;
SD uses ddof=1. Both are displayed only over common fitted support. Within the
VHT reconstruction, the acidic families exhibit predominantly Tafel-controlled
kinetics, with a potential-dependent contribution from the Volmer step. A4 has
two dominant crossings. Every alkaline family has at least one crossing.

`inputs/` retains curve coordinates and source metadata. `control_core.py`,
`sharing.py`, and `vendor/` contain the numerical functions used by the current
pipeline. `expected/` contains the plotted tables checked by
`scripts/validate_figures.py`. Selected templates and optimization seeds are
under `../effective_bv/reference/`. None of these commands imports the archive.
