# Figure Analyses

| Figure | Calculation | Guide |
| --- | --- | --- |
| 4 | Local slopes, BV/BV+jR fit metrics, parameter distributions, and examples | [Figure 4](figure4/README.md) |
| 5 | Compensation, bubble/EIS trend, surface kinetics, and current rescaling | [Figure 5](figure5/README.md) |
| 6 | Pt/C response families, VHT reconstruction, and rate control | [Figure 6](figure6/README.md) |

## Setup and Run

Use Python 3.13 from the repository root:

```text
python -m pip install -r requirements-analysis.txt
python analysis/figure4/run.py
python analysis/figure5/run.py --refit-kscn
python analysis/figure6/run.py
python -m unittest discover -s tests -v
```

These commands need only the included coordinate inputs and Python dependencies.
Figure 4 also reads the complete 4,211-curve dataset under `data_literature/` and
rebuilds its fitting cohort; its guide links the full inclusion/exclusion record.
The commands do not require source-paper PDFs, image downloads, agent logs, or browser
state. They start from digitized coordinates, not from image extraction.
Outputs are written to `build/figure4/`, `build/figure5/`, and `build/figure6/`.

Each guide distinguishes recalculation using supplied fit parameters from new
parameter optimization. Reference parameters and final figures are not
overwritten by a refit. Model assumptions, data selection, normalization, and
interpretation limits are documented alongside the corresponding analysis.

`SOURCE_MANIFEST.json` records the numerical input/code provenance and hashes.
Source locations in that record describe provenance, not runtime dependencies.
The benchmark used in Figure 3 is documented separately under
[benchmark_data/benchmark_curve_extraction/](../benchmark_data/benchmark_curve_extraction/README.md).
