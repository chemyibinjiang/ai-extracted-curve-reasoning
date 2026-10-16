# Curve Extraction and Electrochemical Analysis

Data, code, and figures for **AI Agent Reveals Hidden Kinetic Structure in
Published Hydrogen Evolution Polarization Curves**. The study reconstructs
published hydrogen evolution reaction (HER) curves, compares their response
shapes, and examines related patterns in directly measured linear sweep
voltammetry (LSV) data.

**Review version:** Figures 1-8 and their analyses are on
[`codex/major-revision-20260922`](https://github.com/chemyibinjiang/ai-extracted-curve-reasoning/tree/codex/major-revision-20260922).
The clone command below selects this version explicitly.

## Start Here

- **Browse the results:** [Figures 1-8](figures/README.md), with SVG originals and PNG previews.
- **Explore materials:** [composition and template maps](https://chemyibinjiang.github.io/ai-extracted-curve-reasoning/)
  and [individual curves and Tafel-slope distributions](https://chemyibinjiang.github.io/ai-extracted-curve-reasoning/tafel/).
- **Get the data:** literature coordinates and native experimental records are linked below.
- **Reproduce a result:** use the figure-specific guides below or
  the [figure and supporting-information (SI) result map](reproducibility/RESULT_MAP.md).

## Data

The literature release contains **4,211 extracted curves (132,314 points)**,
including curves not selected for fitting:

- [All coordinates](data_literature/zenodo_extracted_curve_dataset_v1/curve_points_long.csv)
- [Curve metadata](data_literature/zenodo_extracted_curve_dataset_v1/curve_metadata.csv)
- [Source publications](data_literature/zenodo_extracted_curve_dataset_v1/source_publication_records.csv)
- [Coordinate ZIP](data_literature/zenodo_extracted_curve_dataset_v1.zip) and
  [field descriptions](data_literature/zenodo_extracted_curve_dataset_v1/SCHEMA.md)
- [Figure 4 inclusion/exclusion record](analysis/figure4/reference/COHORT_SELECTION.csv)

These are coordinates extracted from published plots, not source authors'
instrument files. Figure 4 selects 3,033 curves from 473 papers; the remaining
curves stay in the complete release. `curve_uid` links coordinates to metadata;
the [source-joining guide](reproducibility/RESULT_MAP.md#joining-a-curve-to-its-source)
explains the remaining identifiers.

Figure 8 instead uses [native experimental LSV records](analysis/figure8/inputs/initial_screening.zip)
from the electrodeposited catalyst library: 561 screening records, of which 524
meet the shape-analysis criteria. The [Figure 8 guide](analysis/figure8/README.md)
gives measurement conditions, the source repository and exact source commit.

## Figures and Analyses

| Figure | Subject | Guide |
| --- | --- | --- |
| 1 | Extraction, verification, observed curves and recurring shapes | Panel D uses the [Figure 7 population and templates](analysis/figure7/README.md) |
| 2 | Worked axis calibration, curve extraction and verification | [Extraction framework](code_reference/) |
| 3 | Extraction benchmark and literature claim comparisons | [Figure 3](analysis/figure3/README.md) |
| 4 | Local slopes and effective Butler-Volmer (BV) fits, with and without an apparent resistance term | [Figure 4](analysis/effective_bv/README.md#figure-4) |
| 5 | Apparent resistance and current rescaling | [Figure 5](analysis/effective_bv/README.md#figure-5) |
| 6 | Pt/C response families and Volmer-Heyrovsky-Tafel (VHT) reconstruction | [Figure 6](analysis/effective_bv/README.md#figure-6) |
| 7 | Population shape analysis and empirical templates | [Figure 7 and SI Section 9](analysis/figure7/README.md) |
| 8 | Experimental response series and literature-shape comparison | [Figure 8 and SI Section 11](analysis/figure8/README.md) |

## Run the Analyses

Install Git, Git LFS and Python 3.13. Clone the review branch, then retrieve the
binary assets needed for analysis, figure validation and the tests:

```text
git -c filter.lfs.smudge= -c filter.lfs.process= -c filter.lfs.required=false clone --branch codex/major-revision-20260922 https://github.com/chemyibinjiang/ai-extracted-curve-reasoning.git
cd ai-extracted-curve-reasoning
git lfs install
git lfs pull --include="data_literature/*.zip,figures/manuscript/**,figures/supporting/figure7/**,analysis/effective_bv/artwork_templates.zip,analysis/effective_bv/published/**,analysis/figure8/inputs/*.zip,exploration/archive/**,benchmark_data/benchmark_curve_extraction/**" --exclude=""
python -m venv .venv
```

Activate with `.venv\Scripts\Activate.ps1` in Windows PowerShell or
`source .venv/bin/activate` on macOS/Linux. If PowerShell blocks activation,
use `.venv\Scripts\python.exe` instead of `python` below. To select Python 3.13
explicitly, use `py -3.13 -m venv .venv` on Windows or
`python3.13 -m venv .venv` on macOS/Linux, when those launchers are installed.
Run all commands from the repository root.

### Quick Checks

These validate supplied data and artwork without refitting the models:

```text
python -m pip install -r requirements-analysis.txt
python scripts/validate_dataset.py
python scripts/validate_figures.py
python analysis/figure7/run.py validate
```

### Choose a Calculation

These are separate tasks, not a sequence that every reader needs to run.

| Task | Command |
| --- | --- |
| Trace the coordinate ZIP through preparation and analysis inputs | `python scripts/audit_raw_to_analysis.py` |
| Replay the extraction benchmark | `python analysis/figure3/run.py` |
| Refit Figures 4-6 using the supplied selected families | `python analysis/effective_bv/run.py all --workers 6 --starts 12` |
| Refit Figure 7 using supplied tuning results | `python analysis/figure7/run.py replay` |
| Reproduce Figure 8 from native measurements | `python analysis/figure8/run.py` |

Outputs go to `build/`, not over the inputs or manuscript artwork. These
numerical runs are offline after setup and need neither an AI subscription
nor source-paper downloads. Inkscape is needed only for artwork export.

For Figure 7, choose `cv` **instead of** `replay` to repeat all model-tuning
fits as well. The separate `complete-window` command reproduces SI Tables
S28-S29. Empirical-template coverage is recalculated using the supplied
candidate library and selected sets; it does not discover a new library.
The [reproduction guide](REPRODUCIBILITY.md) explains individual stages,
template-search scope, artwork export and the full test suite.

## Further Details

- [Repository structure](CODE_ORGANIZATION.md) and [analysis overview](analysis/README.md).
- [Tafel explorer methods and build command](analysis/tafel_explorer/README.md).
- [Verification records](reproducibility/README.md) and [October dataset update](reproducibility/UPDATE_20261003.md).
- [Release status and remaining follow-up](RELEASE_CHECKLIST.md).
- [Exploration records](exploration/README.md) and [superseded workflows](exploration/archive/README.md),
  separate from the figure-analysis commands.

Large binaries use Git LFS; a small text file beginning with `version https://git-lfs.github.com/spec/v1`
is a pointer, not the downloaded asset. Run the LFS retrieval command above
if a ZIP or image will not open.

The manuscript and SI documents are maintained separately. No repository-wide
software license has yet been specified. Source publications and third-party
data retain their own reuse terms; inclusion here does not grant additional rights.
