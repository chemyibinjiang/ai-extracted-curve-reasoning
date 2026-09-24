# Figure 5

**Evidence for multiple contributions to apparent jR behavior and current
rescaling.** A, published MoS2 polarization before and after 85% compensation,
the matched-current voltage difference, and apparent resistance from Tafel+jR
fits. The hatched 100% bar is a conditional estimate assuming the same constant
compensation resistance, not a measurement of residual solution resistance.
B, five successive Ni HER CV branches fitted with BV+jR, their corresponding
EIS traces, and the association between fitted Rapp and EIS-derived
high-frequency Rs. The two resistances retain their distinct units; numerical
equality is not asserted. C, a qualitative Volmer-Heyrovsky-Tafel schematic and
independent fits of the same experimental NiMo polarization to BV, BV+jR and
reversible VHT without an explicit resistance term or voltage offset. The
rightmost panel shows hydrogen coverage calculated from symmetry-related fitted
VHT parameters that produce identical polarization. These curves are model
predictions, not measured or digitized source-paper coverage. D, NiFeP
layer-dependent polarization and Ni-C-N polarization with and without KSCN,
with independent fitted NiFeP resistances versus inverse layer count and the
KSCN/control current ratio. Schematics do not establish a unique mechanism or
partition apparent resistance into physical contributions.

## Panel C Methods and Limits

- Source: Bao et al., *ChemElectroChem* 8, 195-208 (2021),
  [doi:10.1002/celc.202001436](https://doi.org/10.1002/celc.202001436).
  The 223 nm electrodeposited NiMo sample was measured in 0.5 M H2SO4;
  the source reports 100% post-hoc iR correction. This does not establish that
  every operating-state electrical contribution is absent.
- All three fits use the same 40 digitized experimental points from source
  Figure 4, spanning 2.019-23.926 mA/cm2 and 67.55-149.28 mV. The objective is
  unweighted voltage-space least squares. No fitting to another model's output
  is used in this comparison.
- Voltage RMSE: BV, 2.403 mV; BV+jR, 0.427 mV; VHT, 0.661 mV.
  The empirical BV+jR fit gives Rapp=1.250 ohm cm2. VHT gives R2=0.99920.
  These residuals describe digitized-curve agreement, not experimental error bars.
- VHT enforces steady-state coverage and detailed balance at 298.15 K, with
  alphaV=alphaH=0.5. Four base-10 quantities are fitted: kH/kV, kT/kV,
  equilibrium adsorption ratio K, and a current scale. The BV fits retain the
  repository's n_eff=2 convention; their effective alpha is not an elementary
  V/H transfer coefficient.
- Fit 1 uses the increasing-coverage representative, theta=0.350-0.928 over
  the plotted voltage range. Fit 2 is the parameter-symmetry counterpart,
  theta'=1-theta, evaluated from its transformed rate parameters. Both give
  the same LSV. The choice of increasing coverage is a display convention,
  not evidence that either coverage branch is uniquely identified.
- One fitted rate ratio reaches its bound; widening the bounds changes
  predicted voltages by less than 0.00001 mV. A no-Tafel VH limit gives an
  almost identical RMSE of 0.669 mV. Thus the example does not establish that
  a nonzero Tafel pathway is required.
- Interleaved five-fold held-out voltage RMSE is 2.453, 0.443 and 0.697 mV
  for BV, BV+jR and VHT. This checks within-curve prediction, not validation
  against independent experiments. Fits over three restricted current
  windows also retain lower error for BV+jR and VHT than for BV.

The supported conclusion is that this LSV curvature is compatible with both
an empirical BV+jR description and a resistance-free surface-kinetic
description. It does not establish a unique coverage, microscopic pathway,
or quantitative kinetic fraction of the fitted resistance.

## Other Sources

- A: Zhang et al., *Nature Communications* 11, 3724 (2020),
  [doi:10.1038/s41467-020-17121-8](https://doi.org/10.1038/s41467-020-17121-8).
- B: Logar et al., *ACS Catalysis* 15, 6380 (2025),
  [doi:10.1021/acscatal.5c00144](https://doi.org/10.1021/acscatal.5c00144).
- D, NiFeP: [doi:10.1002/adma.201908201](https://doi.org/10.1002/adma.201908201).
- D, KSCN: [doi:10.1021/jacs.6b09351](https://doi.org/10.1021/jacs.6b09351).

The Figure 5 analysis guide supplies point-selection rules and reproducible
commands. Rows A, B and D were not changed by the direct NiMo-fit update.
