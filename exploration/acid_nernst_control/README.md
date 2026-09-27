# Acidic Pt/C Concentration-Polarization Control

This exploration tests the HER branch of the reversible concentration-polarization
expression in Prats and Chan, PCCP 2021, DOI 10.1039/D1CP04134G (Eq. 4; SI S2-S3).
It does not change the manuscript, published artwork or current fitted references.

For positive cathodic current and overpotential magnitudes:

`u_mV = (1000 RT / 2F) ln(1 + J/jL) + J R`.

The first term is the analytic effective-BV boundary at alpha_c = 2, alpha_a = 0.
The added linear term is our empirical control, not an equation supplied by the paper.
Agreement means shape compatibility, not that a particular experiment was transport limited.

## Matched Comparisons

- All 73 nonlinear acidic Pt/C curves, original 0-200 mV points, voltage SSE,
  R2 >= 0.99, no offset; Nernst (1 parameter), Nernst+jR (2), BV (3), BV+jR (4).
- Three interleaved held-out-point folds per curve, with training-only initialization.
- Existing VHT DeltaG-only replay on the same 59 accepted family members. This is
  not an independently optimized VHT fit to every curve or a held-out VHT result.
- Reconstruction of the four current empirical templates on the same 1,000-point
  log-current grids used for the VHT error audit.
- Maximum-coverage libraries with one shape parameter Q = jL R and a separate
  amplitude per member, including matched/refined Q grids and paper-blocked transfer.

The current BV numerical fraction bound [0.01,0.99] excludes the exact Nernst
endpoint. Comparisons must not claim strict numerical nesting of those two runs.
The cohort metadata do not establish H2 saturation, hydrodynamics or scan-rate
independence. The physical assumptions of the concentration-polarization limit
therefore remain to be checked against the source experiments.

## Run

From the repository root with the analysis dependencies installed:

```console
python exploration/acid_nernst_control/test_model.py
python exploration/acid_nernst_control/run.py --workers 4
python exploration/acid_nernst_control/audit.py
```

The input is `build/effective-bv-20260927`. The output is
`build/acid-nernst-control-20260927/index.html`, with numerical CSVs, protocol
hashes and review plots. The reference calculation uses the 298.15 K convention
of the existing analysis; it does not substitute measured temperatures per paper.
