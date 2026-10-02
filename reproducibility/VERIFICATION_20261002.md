# Figure 7 and SI Section 9 verification

Verified on 2 October 2026 with Python 3.13, NumPy 2.4.2, pandas 3.0.1,
SciPy 1.17.1, Matplotlib 3.10.8 and pypdf 6.7.5.

## Numerical Reproduction

`python analysis/figure7/run.py cv` rebuilt the cohort, all 24 cross-validation
fits, selected final model, template coordinates, uncertainty/support controls,
coverage tables and plots. All fits converged. The final rank-three model
converged after 2,282 iterations. Frozen-reference comparisons passed for all
individual scores, template projections, dispersion ratios/intervals, and
cross-validation summary means/standard errors.

| Check | Result |
| --- | --- |
| Population | 2,360 curves, 435 papers; 411 Pt/C, 873 other PGM, 1,076 non-PGM |
| Tuning | 4,350 native-point mask tasks; three paper folds; rank 3, smoothing 1,000 selected |
| Fitted latent variance | 78.5019%, 18.4886%, 3.0095% |
| Amplitude invariance | Curve-specific constant log-current shifts leave shape coordinates unchanged within numerical tolerance |
| Uncertainty | Positive conditional covariance; missing-cell mask controls and support-balanced comparisons reproduced |
| Pooled balanced dispersion | non-PGM/PGM 1.4314 [1.2503, 1.6409]; non-PGM/Pt/C 1.5802 [1.3510, 1.8575] |
| Template neighbors | All eight Pt/C families have a nearest neighbor among the six PGM-rich templates in all three coordinates |
| Coverage | Every archived K=1-30 union recounted; K=16 gives 1,343/1,667 |
| Native matches | All 2,028 voltage-space R2 values re-evaluated; maximum reference difference 6.7e-16 |
| Complete-window sensitivity | All five windows, both normalizations, and pooled/acidic/alkaline results reproduce SI Tables S28-S29 |
| Artwork | Figure integrity/numerical validator accepts 20 assets; main Figure 7 and five SI diagnostics included |
| Tests | All 57 repository unit tests passed, including six Figure 7 input-integrity and model checks |

## Isolation Check

A temporary directory contained **only** a copy of `analysis/figure7`, without
the original Downloads package, workspace analysis outputs, exploration archive,
or manuscript files. `replay` and `complete-window` both succeeded, including
all reference regressions and figure exports. The machine-readable record is
[figure7-isolated-validation.json](figure7-isolated-validation.json).

The prepared `CURVES.csv`/`POINTS.csv` source remains separately reproducible
through the established Figure 4 preparation workflow. Frozen metadata and
template candidate compatibility are explicit analysis inputs, not independently
redetermined literature classifications.

## Scope

The population model is refitted and tuned; the candidate template library is
not regenerated. Coverage checks replay frozen sets, and native-match checks
evaluate archived amplitude factors rather than reoptimizing every factor.
The complete-window analysis is independent of the latent model but uses the
same underlying literature corpus, not an external validation dataset.

Score/bootstrap intervals condition on the fitted basis and support target.
Late-tail predictive intervals under-cover and missingness can be informative.
Neither visual compactness nor amplitude separation establishes a mechanism or
rules out current-dependent losses. These limitations are included in SI
Section 9 and [the public methods](../analysis/figure7/METHODS.md).

Figures 1-6 retain their earlier public release assets in this commit. This
release adds Figure 7 and its supporting analyses; it does not revise VHT fits.
