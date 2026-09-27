# Curve Extraction and Electrochemical Analysis

Data, code, and figures for extracting numerical evidence from scientific plots,
checking reported claims, and analyzing hydrogen-evolution polarization curves.

## Figures

The manuscript artwork is in [figures/manuscript/](figures/manuscript/).
Each figure has an editable SVG and a PNG preview.
The current numerical revision uses the effective-BV analysis below. The
manually edited artwork has been synchronized to these fits without changing
the plot types or overall layout. See [the figure update](figures/DATA_UPDATE_20260927.md).

| Figure | Subject | Data and computation |
| --- | --- | --- |
| 1 | Overview: extraction, verification, response shapes, and kinetic interpretation | Scheme; panel D uses the [Figure 6 alkaline families](figures/DATA_UPDATE_20260927.md#figure-1) |
| 2 | Worked example of axis calibration, curve extraction, and verification | Extraction workflow |
| 3 | Extraction benchmark, literature validation, and claim comparisons | [Benchmark data and evaluation](benchmark_data/benchmark_curve_extraction/README.md) |
| 4 | Local slopes, effective BV/BV+jR fit quality, and effective parameters | [Figure 4 analysis](analysis/effective_bv/README.md#figure-4) |
| 5 | Apparent resistance and current rescaling | [Figure 5 analysis](analysis/effective_bv/README.md#figure-5) |
| 6 | Pt/C response families and kinetic reconstruction | [Figure 6 analysis](analysis/effective_bv/README.md#figure-6) |

## Run the Analyses

Use Python 3.13. Run these commands from the repository root:

```text
python -m pip install -r requirements-analysis.txt
python analysis/effective_bv/run.py all --workers 6 --starts 12
python -m unittest discover -s tests -v
```

Results are written to `build/`. The commands use the included numerical inputs
without a network connection, source-paper downloads, or workstation-specific
paths. Figure 4 refits both models on all 3,033 selected curves and recalculates
their distributions, examples and local slopes. Figure 5 reruns affected
case-study fits and scaling. Figure 6 reprofiles the selected response families,
refits VHT reconstructions and recomputes rate controls. Both effective
coefficients vary; their sum is not fixed. Stage-specific commands are in
[Reproducibility](REPRODUCIBILITY.md).

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
python analysis/effective_bv/run.py population --workers 6
```

The preparation command starts from the complete coordinate dataset. The refit
uses the verified prepared coordinates, multistart optimization, and supplied
variable-coefficient fits as additional feasible seeds. It independently checks
every resulting objective and the nesting of BV within BV+jR.

## Data and Files

- [Literature dataset](data_literature/zenodo_extracted_curve_dataset_v1/README.md):
  extracted coordinates and paper/panel/curve provenance.
- [Analysis guide](analysis/README.md): inputs, calculations, and output tables.
- [Repository structure](CODE_ORGANIZATION.md): where to find each component.
- [Figure validation](reproducibility/README.md): checksums and numerical checks.
- `code_reference/`: extraction-framework source and provenance.
- [Exploration](exploration/README.md): catalyst-performance and BV+jR
  investigation records, separate from the figure-reproduction workflow.
- [Analysis archive](exploration/archive/README.md): recoverable snapshots of
  superseded workflows; not used by the current analysis commands.

Large binary assets use Git LFS; the curve CSV files use ordinary Git.
Retrieve the manuscript figures with:

```text
git lfs pull --include="figures/manuscript/**" --exclude=""
python scripts/validate_figures.py
```

The manuscript and supporting-information documents are maintained separately.
Software licensing and third-party reuse terms must be confirmed before release;
the presence of a file does not grant a blanket license to its source material.
