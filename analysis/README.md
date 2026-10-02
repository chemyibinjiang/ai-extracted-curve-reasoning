# Figure Analyses

| Figure | Calculation | Guide |
| --- | --- | --- |
| 3 | Synthetic benchmark replay and recorded literature-review counts | [Figure 3](figure3/README.md) |
| 4 | Local slopes, effective BV/BV+jR fit metrics, parameter distributions, and examples | [Figure 4](effective_bv/README.md#figure-4) |
| 5 | Compensation, bubble/EIS trend, surface kinetics, and current rescaling | [Figure 5](effective_bv/README.md#figure-5) |
| 6 | Pt/C response families, VHT reconstruction, and rate control | [Figure 6](effective_bv/README.md#figure-6) |
| 7 | Partial-observation shape PCA, empirical template projection, coverage, and SI Section 9 controls | [Figure 7](figure7/README.md) |

## Setup and Run

Use Python 3.13 from the repository root:

```text
python -m pip install -r requirements-analysis.txt
python analysis/effective_bv/run.py all --workers 6 --starts 12
python analysis/figure7/run.py cv
python analysis/figure7/run.py complete-window
python -m unittest discover -s tests -v
```

These commands need only the included coordinate inputs and Python dependencies.
The Figure 4 cohort-preparation command reads all 4,211 curves under
`data_literature/`; the refit uses the verified 3,033-curve prepared coordinates.
The commands do not require source-paper PDFs, image downloads, agent logs, or browser
state. They start from digitized coordinates, not from image extraction.
Outputs are written to `build/effective-bv-20260930/figure4/`, `figure5/`, and
`figure6/`, with an HTML numerical review report at the output root.

The default now reoptimizes both variable-coefficient empirical models and the
affected case studies. Figure 6 reuses the completed template search, reoptimizes
current amplitudes, and refits VHT sharing models. Manually edited final figures
are not overwritten. The [analysis protocol](effective_bv/README.md) records
the numerical bounds, seed provenance and each recalculation.

`SOURCE_MANIFEST.json` records the numerical input/code provenance and hashes.
Source locations in that record describe provenance, not runtime dependencies.
The benchmark used in Figure 3 is documented separately under
[benchmark_data/benchmark_curve_extraction/](../benchmark_data/benchmark_curve_extraction/README.md).
