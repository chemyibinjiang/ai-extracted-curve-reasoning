# Figure 7 population shapes and empirical templates

This module reproduces the partial-observation shape analysis in Figure 7 and
SI Section 9. It compares overlapping response-shape populations, not exclusive
chemical clusters. VHT interpretation remains in the separate Figure 6/SI
Section 8 workflow.

## Run

From the repository root, with `requirements-analysis.txt` installed:

```text
python analysis/figure7/run.py validate
python analysis/figure7/run.py replay
python analysis/figure7/run.py cv
python analysis/figure7/run.py complete-window
```

- `validate` checks every frozen input/reference file against its SHA-256 hash.
- `replay` (also named `refit`) reuses archived tuning results, but rebuilds the
  observations, refits the selected final model, and recomputes projections,
  uncertainty/support diagnostics, native-match residuals, coverage, and figures.
- `cv` additionally reruns all 24 whole-paper tuning fits. It is the full
  population-analysis reproduction, not a new search for empirical templates.
- `complete-window` independently rebuilds the older raw-profile sensitivity
  comparisons in SI Tables S28-S29 from native data, without latent scores.
- `figures` redraws from an existing output directory.

Use `--output PATH` to choose a separate output directory. The default is
`build/figure7`. Numerical reproduction needs no network or original workstation
paths. Arial is used when installed; otherwise plots use DejaVu Sans. The
published artwork preserves the manuscript's Arial typography.

## Two Different Populations

| Analysis | Eligibility and denominator |
| --- | --- |
| Population shape model, Figure 7A/B/E | 2,361 geometric-area LSVs from 435 papers: 411 Pt/C, 873 other PGM, 1,077 non-PGM; acidic/alkaline; supported observations over 20-300 mV; no template gate |
| Empirical template discovery, Figure 7C/D/F | 2,267 non-Pt/C nonlinear records; 1,667 pass empirical BV+jR adequacy; 16 templates cover 1,343 unique records (80.6%) |
| Complete-window sensitivity, SI S28-S29 | Separate 2,267-record, composition-known, non-Pt/C nonlinear source; 458 meet the primary 50-150 mV complete-window criteria |

PGM means a recorded Pt, Pd, Rh, Ru, Ir or Os. Pt/C is separated first. Non-PGM
means none of these elements is recorded; it is not an independent measurement
of elemental absence. Au and Ag alone are not PGMs. A record is an extracted
curve, not necessarily a unique material or independent experiment.

## Method and Interpretation

[METHODS.md](METHODS.md) details preprocessing, the observed-only factor model,
native-point masking, score uncertainty, template projection and limitations.
Each paper has equal total fitting weight, shared by its curves. Longer observed
segments still contribute more information. Composition and template labels do
not enter fitting or tuning.

Rank 3 and smoothing 1,000 were selected by a one-standard-error rule. The first
two coordinates explain 97.0% of **fitted latent shape variance**, not 97.0% of
raw-current variance. Short profiles can shrink toward the population prior;
their conditional covariance is retained in quantitative comparisons.

After support balancing, pooled non-PGM/PGM dispersion is 1.43 (95% interval
1.25-1.63), and non-PGM/Pt/C is 1.58 (1.35-1.86). Intervals combine whole-paper
resampling and score draws **with the basis and balancing target fixed**.
Tail-150 and tail-200 predictive coverage is only 87.9% and 82.4%. These results
do not establish exact missing tails, mechanisms, or absence of current-related
operating losses.

## Inputs and Frozen References

- `inputs/POINTS.csv`, `CURVES.csv`: the prepared 3,033-curve fitting source,
  traceable to `analysis/figure4` and the full public extracted-coordinate dataset.
- `canonical_curves.csv`, `CATALYST_AUDIT.csv`: only the metadata columns needed
  for group/condition eligibility and the established Pt/C classification.
- `METADATA_CORRECTIONS.json`: source-checked annotations applied after loading
  the original metadata. Figure 1c, curve 5 of DOI 10.1021/jacs.3c05287 is ScCo2
  before chronoamperometry in 6.0 M KOH (non-PGM), confirmed by the accompanying
  text and Figure 1e. Raw coordinates and compatibility factors are unchanged.
- `CANDIDATES.csv`, `LIBRARY_COMPATIBILITY.npz`, `REDUCED_LIBRARY.npz`,
  `solutions/K01.json` through `K30.json`: the frozen 17,005-candidate library,
  coverage matrix, reduction and independently selected achieved sets.
- `TEMPLATES.csv`: 16 empirical shapes and 8 Pt/C families with supported ranges.
- `MEMBER_COMPATIBILITY.csv`, `NATIVE_CURVES.npz`, `RESCALED_NATIVE_POINTS.csv`:
  native values and positive amplitude factors for all 2,028 selected matches.
- `reference/`: numerical comparison targets, including full tuning errors,
  the selected fit, individual posterior scores and key SI tables.
  `OBSERVED_CURRENT_GROWTH.csv` verifies the Section 9.9 summaries and sample sizes.
- `input_manifest.json`: exact hashes, including preserved CSV line endings.

Coverage is replayed from frozen candidate compatibility; the command does not
regenerate the 17,005 candidates or optimize a new library. Every selected match
is independently re-evaluated in voltage space, and all 30 selected unions are
recounted. These are achieved coverages, not global minimality certificates.
Overlapping membership is retained. The six-template PGM union is 542/695;
the ten-template non-PGM union is 495/648. All 1,343 covered records now have a
composition classification. Individual bars cannot be added to obtain unique-curve coverage.

## Outputs and SI Map

Outputs below are relative to `build/figure7`:

| Figure or SI item | Numerical output |
| --- | --- |
| Figure 7A/B; Table S22 | `08_PARTIAL_PCA_CANDIDATE/COHORT.csv`, `SCORES.csv`, `OBSERVATIONS.npz` |
| Tables S23-S24; Figure S17 | `CV_SUMMARY.csv`, `CV_PAPER_SUMMARY.csv`, `CV_ERRORS.csv` in that same folder |
| Figure 7E; Table S25 | `TEMPLATE_PROJECTIONS.csv`, `TEMPLATE_POSTERIOR.npz`, `PTC_NEAREST_TEMPLATES.csv` |
| Table S26; Figures S18-S20 | `DISPERSION_RATIOS.csv`, `GROUP_DIAGNOSTICS.csv`, `IDENTICAL_SHAPES_MASK_CONTROL.csv`, `HIGH_INFORMATION_CHECK.csv` |
| Figure 7C | `04_TABLES/template_coverage_scan.csv`, `coverage_validation.json` |
| Figure 7D | `02_DATA/template_profiles.csv`, `08_PARTIAL_PCA_CANDIDATE/TEMPLATE_NATIVE_POINTS.csv` |
| Figure 7F; Table S27 | `04_TABLES/template_composition.csv`, `template_composition_union.csv` |
| Tables S28-S29 | `04_TABLES/complete_window_dispersion.csv` |
| Section 9.9; Table S30; Figure S21 | `04_TABLES/observed_current_growth_summary.csv` and `observed_current_growth_records.csv` |
| Figure 7 and Figures S16-S20 | `08_PARTIAL_PCA_CANDIDATE/figures/` |
| Figure S21 | `05_FIGURES/SUPPORTING/SI_observed_current_growth.*` |

Published [Figure 7](../../figures/manuscript/Figure7.png) and supporting
[Figures S16-S21](../../figures/supporting/figure7/) are included separately.
The frozen reference package contains coordinates and numerical metadata, not
publisher article images, article text, private prompts, or manuscript files.
