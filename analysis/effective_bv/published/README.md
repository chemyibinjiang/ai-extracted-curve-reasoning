# Unified Pt/C VHT Results

These checked outputs are the single source for Figure 6, Figure 1D, and SI
Sections 8.2-8.5 (30 September 2026). They replace the previous minimax-selected
kinetic snapshot. The empirical templates and curve assignments are unchanged.

Every sharing scheme uses elementary alphaV=alphaH=0.5, no added resistance,
and equal-template pooled voltage least squares. Empirical BV coefficients
remain independently fitted and are not elementary symmetry factors.

| File | Contents |
| --- | --- |
| KINETIC_PROTOCOL.json | Objective, bounds, starts, grids and acceptance criteria |
| KINETIC_PARAMETERS.csv | All 32 family/scheme parameter records, with units in headers |
| KINETIC_SUMMARY.csv | Pooled and maximum error, adequacy and raw-curve replay counts |
| TEMPLATE_RECONSTRUCTION.csv | Empirical and kinetic voltage predictions on 5,000 points per template |
| RAW_VHT_REPLAY.csv | Amplitude-only fits on original member curves, with curve_uid and R2 |
| RATE_CONTROL.csv | Figure 6 family controls, H coverage and fitted-support flags |
| RATE_CONTROL_MEAN_SD.csv | Equal-family means and between-family sample SD |
| ALL_MODEL_RATE_CONTROL.csv | G, GH, GT and GHT profiles on fitted support |
| GHT_DUAL_PARAMETERS.csv | Exact complementary GHT representatives |
| GHT_DUAL_RATE_CONTROL.csv | Complementary coverage and exchanged V/H controls |
| VHT_SELECTED.json | Full precision selected records and optimizer provenance |
| comparison/ | SI Figures S14-S15 in PNG, SVG and PDF |

The Figure 6 choice is acid G and alkaline GT. The other schemes are comparisons,
not separate fitting protocols. Main kinetic replay counts are 48/59 and 165/188;
empirical template coverage is 59/73 and 188/234. Positive G in the displayed
fully relaxed solution is a representative convention, not a unique coverage
or mechanism assignment. `MANIFEST.json` records the checked file hashes.

Regenerate with `python analysis/effective_bv/run.py families --workers 6 --starts 12`.
Outputs are written under `build/effective-bv-20260930/figure6/`; committed files
are not silently overwritten. Run `python tests/test_unified_vht.py` to verify
hashes, shared constraints, errors, curve counts and exact complementary symmetry.
