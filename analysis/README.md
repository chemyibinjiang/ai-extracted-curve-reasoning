# Figure Analyses

| Figure | Calculation | Guide |
| --- | --- | --- |
| 3 | Synthetic benchmark replay and recorded literature-review counts | [Figure 3](figure3/README.md) |
| 4 | Local slopes, effective BV/BV+jR fit metrics, parameter distributions, and examples | [Figure 4](effective_bv/README.md#figure-4) |
| 5 | Compensation, bubble/EIS trend, surface kinetics, and current rescaling | [Figure 5](effective_bv/README.md#figure-5) |
| 6 | Pt/C response families, VHT reconstruction, and rate control | [Figure 6](effective_bv/README.md#figure-6) |
| 7 | Partial-observation shape PCA, empirical template projection, coverage, and SI Section 9 controls | [Figure 7](figure7/README.md) |
| 8 | Experimental series, fixed-model projection and matched-window dispersion; SI Section 11 | [Figure 8](figure8/README.md) |

## Setup and Run

Follow the [repository setup](../README.md#run-the-analyses), then choose a
figure-specific guide above. The [reproduction guide](../REPRODUCIBILITY.md)
separates quick validation, model refits, template searches and the full tests.

These commands need only the included numerical inputs and Python dependencies.
Figure 8 starts from native experimental records and writes to `build/figure8/`.
The Figure 4 cohort-preparation command reads all 4,211 curves under
`data_literature/`; the refit uses the verified 3,033-curve prepared coordinates.
The commands do not require source-paper PDFs, image downloads, agent logs, or browser
state. Literature analyses start from extracted coordinates; Figure 8 starts
from native experimental records. Figures 4-6 write to
`build/effective-bv-20260930/figure4/`, `figure5/` and `figure6/`, with an HTML
report at that output root. Figure 7 writes to `build/figure7/`.

The default now reoptimizes both variable-coefficient empirical models and the
affected case studies. Figure 6 reuses the completed template search, reoptimizes
current amplitudes, and refits VHT sharing models. Manually edited final figures
are not overwritten. The [analysis protocol](effective_bv/README.md) records
the numerical bounds, seed provenance and each recalculation.

`SOURCE_MANIFEST.json` records the numerical input/code provenance and hashes.
Source locations in that record describe provenance, not runtime dependencies.
The benchmark used in Figure 3 is documented separately under
[benchmark_data/benchmark_curve_extraction/](../benchmark_data/benchmark_curve_extraction/README.md).
