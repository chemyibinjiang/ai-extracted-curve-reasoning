# Figure and SI Result Map

All paths below are relative to the repository root. Numerical outputs default
to `build/effective-bv-20260930/`, abbreviated `RESULTS/` below. The complete
manuscript artwork is `figures/manuscript/Figure1.svg` through `Figure6.svg`.
Older source-composition folder numbers are not manuscript figure numbers.

| Paper result | Inputs or command | Output / check |
| --- | --- | --- |
| Figures 1A-C, 2; SI Section 1 | Extraction workflow illustrations; `code_reference/` | Schemes/worked example, not separate population analyses |
| Figure 3 benchmark; SI Tables S5-S6 | `python analysis/figure3/run.py`; included synthetic truth, anchors and extracted points | `build/figure3/BENCHMARK_CURVES.csv`, `SUMMARY.json`; 60 panels, 137 curves; rounded distances 0.36, 1.13, 1.44 pixels |
| Figure 3 literature validation; SI Tables S8, S10-S14 | Released metadata plus `analysis/figure3/REVIEW_SUMMARY.json` | Dataset counts and review-percentage arithmetic; human judgments/source-specific claim evidence are not independently replayed |
| Figure 4 cohort; SI Table S15 | `python analysis/figure4/run.py prepare --output build/figure4-preparation` | `build/figure4-preparation/`; 3,033 curves, 473 papers, 80,399 points; exclusion reasons for all 4,211 curves |
| Figure 4A-C; SI Section 5 | `population` stage; `analysis/figure4/inputs/`, effective-BV seeds | `RESULTS/figure4/FITS.csv`, `MODEL_SUMMARY.csv`, `PARAMETER_SUMMARY.csv`, `LOCAL_SLOPES.csv`, `EXAMPLE_METRICS.csv`; 1,588/2,361 accepted BV/BV+jR fits |
| Figure 5A,B,D; SI Sections 6.1, 6.2, 6.4 | `examples` stage; `analysis/figure5/inputs/` | `RESULTS/figure5/RESULTS.json`, `B_CYCLE_R.csv`, `D_NIFEP_FITS.csv`, `D_KSCN_HELDOUT.csv` |
| Figure 5D NiFeP model comparison | Same `examples` stage; 63 original points and two-point exclusion ledger | `RESULTS/figure5/D_NIFEP_MODEL_COMPARISON.csv`, `D_NIFEP_PREDICTIONS.csv`; directly inspectable copies in `analysis/figure5/reference/NIFEP_MODEL_COMPARISON.csv` and `NIFEP_POINT_PREDICTIONS.csv` |
| Figure 5C; SI Table S16 | Same `examples` stage; NiMo `C_PRIMARY_DATA.csv` | `RESULTS/figure5/nimo/C_NIMO_METRICS.csv`, `C_NIMO_CROSS_VALIDATION.csv`, `C_NIMO_PREDICTED_COVERAGE.csv`, `C_NIMO_LIMIT_CHECKS.json`; RMSE 2.096 / 0.427 / 0.661 mV |
| Figure 6A-D; SI Tables S17-S18 | `families` stage; acidic/alkaline `analysis/figure6/inputs/`; selected effective-BV references | `RESULTS/figure6/{acid,KOH}/COHORT_FLOW.csv`, `TEMPLATES.csv`, `ASSIGNMENTS.csv`, `POINT_PREDICTIONS.csv`; coverage 59/73 and 188/234 |
| Figure 6C full template selection | `python analysis/effective_bv/search.py` | `build/effective-bv-search/CANDIDATES.csv`, `{acid,KOH}/COVERAGE_SCAN.csv`, `SELECTED.json`; 276,551 candidates, smallest K meeting 80% is four in each condition |
| Figures 1D, 6E-F; SI Table S19 | `families` stage and VHT seeds | `RESULTS/figure6/KINETIC_PARAMETERS.csv`, `KINETIC_SUMMARY.csv`, `TEMPLATE_RECONSTRUCTION.csv`, `RAW_VHT_REPLAY.csv`, `RATE_CONTROL.csv`, `RATE_CONTROL_MEAN_SD.csv` |

| SI Section 8.5; Tables S20-S21; Figures S14-S15 | Same `families` stage and `kinetic_comparison.py`; no separate fit | `RESULTS/figure6/ALL_MODEL_RATE_CONTROL.csv`, `GHT_DUAL_PARAMETERS.csv`, `comparison/`; checked copies of all Figure 6 numerical results in `analysis/effective_bv/published/` |

## Joining a Curve to Its Source

`curve_uid` joins `curve_points_long.csv` to `curve_metadata.csv` in
`data_literature/zenodo_extracted_curve_dataset_v1/`. `panel_uid` then joins to
`panel_metadata.csv`; `source_record_id` joins to `source_publication_records.csv`.
The latter supplies DOI and article title. `curve_uid` includes the article
record, figure/panel, and curve identifier; it is a database index, not a DOI.
Keep `source_record_id` distinct from DOI when counting repeated article records.
Figure 5 case-study coordinates were digitized separately; their references
are specified in SI Section 6 and `analysis/figure5/README.md`.

## Units and Denominators

Prepared fits use mA cm^-2 and mV, so Rapp is in ohm cm^2 and Q=j0 Rapp in mV.
The Figure 5B EIS intercept Rs is in ohm, not ohm cm^2. Empirical alpha_a/alpha_c
are distinct from the fixed elementary-step alphaV/alphaH=0.5. A positive
cathodic magnitude is used; no fitted potential offset is present.

The complete dataset (4,211), fitting cohort (3,033), Pt/C electrolyte subset
(348), nonlinear template cohorts (73/234), empirical members (59/188), and
kinetic replay counts (48/165) answer different questions. They must not be
used interchangeably. Figure 6 means give equal weight to families and SD uses
n-1, rather than weighting by member counts. Both use common fitted support.
