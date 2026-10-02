# Curve Extraction and Electrochemical Analysis

**2 October 2026:** Current Figures 1, 3 and 7 are synchronized with the manuscript.
[Figure 7 and SI Section 9](analysis/figure7/README.md) include partial-observation
population PCA, template projection and coverage, and support/uncertainty controls.
The [raw-data audit](reproducibility/REVIEW_20261002.md) traces the downloadable
coordinate ZIP through preparation to the analysis inputs and rerun results.


Data, code, and figures for extracting numerical evidence from scientific plots,
checking reported claims, and analyzing hydrogen-evolution polarization curves.

## Figures

The manuscript artwork is in [figures/manuscript/](figures/manuscript/).
Each figure has an editable SVG and a PNG preview.
Figures 1 and 7 connect observed LSVs, population shape coordinates and recurring
templates. Figure 3 pairs the extraction benchmark with four claim-comparison
examples. Figures 2 and 4-6 retain their 30 September versions.
See the [current artwork notes](figures/UPDATE_20261002.md) and the
[effective-BV numerical revision](figures/DATA_UPDATE_20260930.md).

| Figure | Subject | Data and computation |
| --- | --- | --- |
| 1 | Overview: extraction, verification, LSVs and recurring shapes | Panel D uses the [Figure 7 population and templates](analysis/figure7/README.md) |
| 2 | Worked example of axis calibration, curve extraction, and verification | Extraction workflow |
| 3 | Extraction benchmark, literature validation, and claim comparisons | [Figure 3 evaluation](analysis/figure3/README.md) |
| 4 | Local slopes, effective BV/BV+jR fit quality, and effective parameters | [Figure 4 analysis](analysis/effective_bv/README.md#figure-4) |
| 5 | Apparent resistance and current rescaling | [Figure 5 analysis](analysis/effective_bv/README.md#figure-5) |
| 6 | Pt/C response families and kinetic reconstruction | [Figure 6 analysis](analysis/effective_bv/README.md#figure-6) |
| 7 | Population response shapes and empirical templates | [Figure 7 analysis and SI Section 9](analysis/figure7/README.md) |

For the multilayer NiFeP example, see the [model comparison and complete point tables](analysis/figure5/README.md#nifep-layer-number), including both BV and BV+jR fits.

## Run the Analyses

Start with Git, Git LFS, and Python 3.13 installed. Clone the repository rather
than downloading individual files. The first command defers large binary
downloads so the next command can retrieve only the assets needed here:

```text
git -c filter.lfs.smudge= -c filter.lfs.process= -c filter.lfs.required=false clone https://github.com/chemyibinjiang/ai-extracted-curve-reasoning.git
cd ai-extracted-curve-reasoning
git lfs install
git lfs pull --include="data_literature/*.zip,figures/manuscript/**,figures/supporting/figure7/**,analysis/effective_bv/artwork_templates.zip,exploration/archive/**,benchmark_data/benchmark_curve_extraction/**" --exclude=""
python -m venv .venv
```

Activate with `.venv\Scripts\Activate.ps1` in Windows PowerShell or
`source .venv/bin/activate` on macOS/Linux. On Windows, `py -3.13 -m venv .venv`
explicitly selects Python 3.13; on macOS/Linux use `python3.13 -m venv .venv`.
If PowerShell blocks activation, use `.venv\Scripts\python.exe` instead of
`python` in the commands below. Run them from the repository root:

```text
python -m pip install -r requirements-analysis.txt
python scripts/validate_dataset.py
python scripts/audit_raw_to_analysis.py
python analysis/figure3/run.py
python analysis/figure4/run.py prepare --output build/figure4-preparation
python analysis/effective_bv/run.py all --workers 6 --starts 12
python analysis/figure7/run.py cv
python analysis/figure7/run.py complete-window
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

The separate `python analysis/effective_bv/search.py` command repeats the full
template search; `all` refits the supplied selected families but does not search
the candidate grid. See [the result map](reproducibility/RESULT_MAP.md) for the
exact output behind each figure and SI table. Internet access is needed for
installation/download only. Numerical runs require neither an AI subscription
nor access to the original workstation. Inkscape is needed only for artwork export.

## Complete Curve Dataset

All **4,211 extracted curves (132,314 points)** are included, not just the curves
selected for fitting:

- [All coordinates](data_literature/zenodo_extracted_curve_dataset_v1/curve_points_long.csv)
- [Curve metadata](data_literature/zenodo_extracted_curve_dataset_v1/curve_metadata.csv)
- [Source publications](data_literature/zenodo_extracted_curve_dataset_v1/source_publication_records.csv)
- [Downloadable coordinate ZIP](data_literature/zenodo_extracted_curve_dataset_v1.zip)
- [Figure 4 inclusion/exclusion record](analysis/figure4/reference/COHORT_SELECTION.csv)

These are coordinates extracted from published plots, not original instrument
files supplied by the source authors. Figure 4 selects 3,033 curves from 473
papers. The remaining curves stay in the complete dataset. Rebuild the selection
or refit both models on the full fitting cohort with:

```text
python analysis/figure4/run.py prepare --output build/figure4-preparation
python analysis/effective_bv/run.py population --workers 6
```

`scripts/audit_raw_to_analysis.py` starts from the ZIP, verifies that every member
matches the unpacked release, rebuilds preparation, and checks every native
Pt/C and Figure 7 input coordinate and the analysis composition fields. Its
report and complete selection ledger are written to `build/raw-to-analysis/`.
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
The LFS command above retrieves the coordinate ZIP, figures, artwork templates, benchmark images,
and the archive checked by the test suite. Without it, binary files may be small
LFS pointer files rather than usable assets. Validate the manuscript figures with:

```text
python scripts/validate_figures.py
```

The manuscript and supporting-information documents are maintained separately.
Software licensing and third-party reuse terms must be confirmed before release;
the presence of a file does not grant a blanket license to its source material.
