# Unified VHT Verification

The 30 September release unifies Pt/C VHT reconstruction, Figure 6, the
Figure 1D overview and the SI model comparisons. It does not reselect the
empirical families or change Figures 2-5.

## Fitting Protocol

All eight condition/model combinations use elementary alphaV = alphaH = 0.5,
the same bounds and support, and equal-template pooled voltage MSE. Each uses
12 multistart candidates, followed by dense-grid refinement and evaluation.
The supplied reference is retained when no new candidate improves its pooled
error. This is a reproducible multistart result, not a proof of global optimality.

| Electrolyte | Model | Pooled RMSE (mV) | Maximum family RMSE (mV) | Raw-curve R2 >= 0.99 |
| --- | --- | ---: | ---: | ---: |
| Acid | G | 0.565898 | 0.762333 | 48/59 |
| Acid | GH | 0.500603 | 0.709390 | 48/59 |
| Acid | GT | 0.533955 | 0.743122 | 48/59 |
| Acid | GHT | 0.496328 | 0.708351 | 48/59 |
| KOH | G | 3.448208 | 4.334628 | 128/188 |
| KOH | GH | 1.746775 | 2.407230 | 160/188 |
| KOH | GT | 1.241923 | 1.442071 | 165/188 |
| KOH | GHT | 1.123593 | 1.299094 | 165/188 |

Figure 6 uses acid G and KOH GT. The empirical-template counts remain 59/73
and 188/234; these have different denominators from the kinetic raw-curve
transfer counts in the last column. The effective-BV fit counts remain
1,588/3,033 (BV) and 2,361/3,033 (BV+jR).

## Reproduction Checks

Run from the repository root:

```text
python -m unittest discover -s tests -v
python scripts/validate_figures.py
python scripts/validate_release_inventory.py
```

The 51-test suite checks numerical derivatives, detailed balance, current
scaling, cohort construction, full effective-BV reanalysis in an isolated
package, Figure 6 parameters and controls, exact GHT complementary solutions,
dataset joins, benchmark replay, manifests and documentation links. The
isolated test copies only the public package inputs and code, not local
exploratory results or workstation data. It reproduces all 6,066 population
fits, the empirical family coverage and the 48/59 and 165/188 main kinetic
transfer counts.

The figure validator checks 18 asset records and the Figure 6 numerical
tables, including 8 parameter records, 3,992 family-grid records, 998
mean/SD records, and fitted-support crossing checks. The artwork audit
checks preserved layout and protected elements; only Figures 1 and 6 are
replaced in the published figure set.

SI Figures S14-S15 are generated directly from the same parameter records.
The complementary-solution test compares amplitude-scaled currents, not
arbitrary gauge-dependent currents, and checks exchanged V/H sensitivities
with unchanged Tafel sensitivity.

## Checked Outputs

[Published numerical results](../analysis/effective_bv/published/README.md)
include parameters, all reconstructions, raw-curve replays and control
profiles. Their manifest checks file integrity. The
[figure data update](../figures/DATA_UPDATE_20260930.md) identifies the
updated panels, and [RESULT_MAP.md](RESULT_MAP.md) maps results to inputs
and commands. The older dated update is historical, not a second active fit.

The complete release inventory hashes canonical Git blob bytes or the LFS
payload identified by each pointer. This avoids treating platform-dependent
text checkout line endings as changed data. Its validator reads the Git index;
run it on an unmodified checkout. The numerical and figure manifests retain
exact byte checks for their checksum-authoritative snapshots.

The MS and SI are maintained separately from this public code release. The
document update preserves existing manuscript revisions, provides clean and
tracked versions, and aligns SI authorship with the latest manuscript.
