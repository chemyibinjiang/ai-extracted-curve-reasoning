# Curve Extraction and Electrochemical Analysis

Data, code, and figures for extracting numerical evidence from scientific plots,
checking reported claims, and analyzing hydrogen-evolution polarization curves.

## Figures

The manuscript artwork is in [figures/manuscript/](figures/manuscript/).
Each figure has an editable SVG and a PNG preview.

| Figure | Subject | Data and computation |
| --- | --- | --- |
| 1 | Overview: extraction, verification, response shapes, and kinetic interpretation | Conceptual scheme |
| 2 | Worked example of axis calibration, curve extraction, and verification | Extraction workflow |
| 3 | Extraction benchmark, literature validation, and claim comparisons | [Benchmark data and evaluation](benchmark_data/benchmark_curve_extraction/README.md) |
| 4 | Local slopes, BV/BV+jR fit quality, and effective parameters | [Figure 4 analysis](analysis/figure4/README.md) |
| 5 | Apparent resistance and current rescaling | [Figure 5 analysis](analysis/figure5/README.md) |
| 6 | Pt/C response families and kinetic reconstruction | [Figure 6 analysis](analysis/figure6/README.md) |

## Run the Analyses

Use Python 3.13. Run these commands from the repository root:

```text
python -m pip install -r requirements-analysis.txt
python analysis/figure4/run.py
python analysis/figure5/run.py --refit-kscn
python analysis/figure6/run.py
python -m unittest discover -s tests -v
```

Results are written to `build/`. The commands use the included numerical inputs
without a network connection, source-paper downloads, or workstation-specific
paths. Figure 4 rebuilds its cohort from all extracted curves, verifies the
supplied BV/BV+jR fits, and recalculates local slopes;
Figure 5 reruns case-study fits and scaling; Figure 6 reconstructs responses and
rate controls from the supplied kinetic parameters. Separate optimization
commands are documented in [Reproducibility](REPRODUCIBILITY.md).

## Complete Curve Dataset

All **4,211 extracted curves (132,314 points)** are included, not just the curves
selected for fitting:

- [All coordinates](data_literature/zenodo_extracted_curve_dataset_v1/curve_points_long.csv)
- [Curve metadata](data_literature/zenodo_extracted_curve_dataset_v1/curve_metadata.csv)
- [Source publications](data_literature/zenodo_extracted_curve_dataset_v1/source_publication_records.csv)
- [Figure 4 inclusion/exclusion record](analysis/figure4/reference/COHORT_SELECTION.csv)

These are coordinates extracted from published plots, not original instrument
files supplied by the source authors. Figure 4 selects 3,033 curves from 473
papers. The remaining curves stay in the complete dataset. Rebuild the selection
or refit both models on the full fitting cohort with:

```text
python analysis/figure4/run.py prepare --output build/figure4-preparation
python analysis/figure4/run.py refit --workers 4 --output build/figure4-refit
```

Both commands start from the complete coordinate dataset. The refit uses
multistart optimization without seeding from the reference fit parameters and
checks the resulting objectives and pass assignments against Figure 4.

## Data and Files

- [Literature dataset](data_literature/zenodo_extracted_curve_dataset_v1/README.md):
  extracted coordinates and paper/panel/curve provenance.
- [Analysis guide](analysis/README.md): inputs, calculations, and output tables.
- [Repository structure](CODE_ORGANIZATION.md): where to find each component.
- [Figure validation](reproducibility/README.md): checksums and numerical checks.
- `code_reference/`: extraction-framework source and provenance.
- [Exploration](exploration/README.md): catalyst-performance and BV+jR
  investigation records, separate from the figure-reproduction workflow.

Large binary assets use Git LFS; the curve CSV files use ordinary Git.
Retrieve the manuscript figures with:

```text
git lfs pull --include="figures/manuscript/**" --exclude=""
python scripts/validate_figures.py
```

The manuscript and supporting-information documents are maintained separately.
Software licensing and third-party reuse terms must be confirmed before release;
the presence of a file does not grant a blanket license to its source material.
