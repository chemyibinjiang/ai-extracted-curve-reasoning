# Reproducing the Figures

## Figure 7 and SI Section 9

The 2 October population-to-template analysis is independently packaged in
[`analysis/figure7`](analysis/figure7/README.md). After installing the dependencies:

```text
python analysis/figure7/run.py cv
python analysis/figure7/run.py complete-window
```

The first command rebuilds the partially observed cohort, all 24 whole-paper
tuning fits, the selected final model, posterior and template coordinates,
support/uncertainty controls, native residual checks, achieved coverage and
plots. The second reproduces the earlier complete-window SI sensitivity tables.
`replay` skips retuning but still refits the final population model. Outputs
default to `build/figure7`; `--output` accepts an independent destination.

Candidate-library construction and new template selection are not rerun:
compatibility and selected K=1-30 sets are frozen inputs whose unions and
selected native residuals are re-evaluated. See the
[Figure 7 methods](analysis/figure7/METHODS.md) and
[2 October verification record](reproducibility/VERIFICATION_20261002.md).

See the [30 September unified-fitting record](reproducibility/VERIFICATION_20260930.md)
for the clean-checkout checks and their scope.

## Environment

Follow the [fresh-clone setup](README.md#run-the-analyses), including Git LFS and
a virtual environment. Use Python 3.13 and the pinned numerical dependencies:

```text
python -m pip install -r requirements-analysis.txt
```

Run commands from the repository root. The complete extracted dataset is under
`data_literature/zenodo_extracted_curve_dataset_v1/`; figure-specific inputs and
references are under `analysis/`. Results go to ignored `build/` directories.
The records under `exploration/` provide investigation context; none of the
figure-analysis commands requires those records or their archives.

## Numerical Analysis

| Command | Operation |
| --- | --- |
| `python scripts/validate_dataset.py` | Verify released file hashes, 4,211 curves/132,314 points, and source-panel-curve joins |
| `python scripts/audit_raw_to_analysis.py` | Start from the published ZIP, rebuild preparation, and check all native Pt/C and Figure 7 inputs against it |
| `python analysis/figure3/run.py` | Replay all 137 synthetic benchmark curves and tabulate recorded literature-review counts |
| `python analysis/figure4/run.py prepare --output build/figure4-preparation` | Read all 4,211 extracted curves, rebuild the 3,033-curve cohort, and record every selection decision |
| `python analysis/effective_bv/run.py population --workers 6` | Refit all 6,066 variable-coefficient BV/BV+jR models; recompute metrics, distributions, examples and local slopes |
| `python analysis/effective_bv/run.py examples` | Refit cycle/EIS, NiMo and NiFeP examples; calculate compensation, current scaling, VHT coverage and predictive checks |
| `python analysis/effective_bv/run.py families --workers 6 --starts 12` | Reprofile the selected templates, refit VHT sharing models, replay member curves and recompute rate controls |
| `python analysis/effective_bv/search.py` | Profile the complete 276,551-template grid and repeat maximum-coverage selection for K=1..10 |
| `python analysis/effective_bv/run.py report` | Generate updated numerical review plots and an HTML summary |
| `python analysis/effective_bv/run.py all --workers 6 --starts 12` | Run all four stages in order |

See the [analysis guide](analysis/README.md) for inputs, outputs, fixed assumptions,
and interpretation. Reconstructing a supplied fit is not the same as estimating
its parameters again. Refit outputs are kept separate from figure references.

The Figure 3 synthetic benchmark and evaluation commands are documented in
[the Figure 3 guide](analysis/figure3/README.md).
Figures 1 and 2 explain the conceptual and worked extraction workflows; they
are not additional population-fitting analyses.

## Tests

```text
python -m unittest discover -s tests -v
```

Tests cover source hashes, cohort preparation from all extracted curves, local derivatives, weighting, kinetic Jacobians,
current scaling, independent mass-action solutions, support masks, sample SD,
and dominant-control crossings. Isolated-copy tests check that the figure-analysis
entry points and the complete Figure 4 refit do not depend on files outside the
included package. No network connection is used by these analyses.

The effective-BV revision refits all 6,066 population models and independently
checks their voltage objectives. Accepted counts are 1,588 for BV and 2,361 for
BV+jR. Affected Figure 5 fits and the VHT sharing search on the new Figure 6
templates have also been rerun. Selected variable-coefficient templates and
the completed finite-grid coverage search are supplied as checked reference
data; the `families` stage does not repeat that search. Current amplitudes and
VHT models are reoptimized. See the [current analysis protocol](analysis/effective_bv/README.md)
for numerical bounds, checkpoints and the distinction between a retained
optimized seed and a newly converged fit.

Figure-specific `analysis/figure4/run.py`, `analysis/figure5/run.py`, and
`analysis/figure6/run.py` call the same current fitting stages. Earlier workflows
are archived separately; they cannot be selected by a default analysis command.
After archiving, all 6,066 population fits and the 12-start VHT sharing search
were rerun on September 27, 2026. The principal kinetic parameters matched the
Figure 6/SI tables exactly. An isolated-copy test also runs without exploration
files or archived analyses.

## Artwork

The manuscript SVG/PNG files include the effective-BV numerical revision and
the current Figure 1/3/7 layouts. Figure 1D uses the Figure 7 population and
templates, aligned at 20 mV. Figure 3 contains benchmark and claim-comparison
examples. See [current artwork notes](figures/UPDATE_20261002.md).

After the numerical analysis, regenerate the data updates into a review folder:

```text
python analysis/effective_bv/artwork.py --data build/effective-bv-20260930 --output build/manuscript-figures --inkscape /path/to/inkscape
```

This command uses the 30 September compressed layouts and does not overwrite
the published figures. Its Figure 1D layout is historical; Figures 2 and 3 are
copied from the baseline rather than regenerated. It produces six review figures,
Figure 6 audit tables and `ARTWORK_CHECKS.json`. To validate or export all
seven current manuscript figures directly:

```text
git lfs pull --include="figures/manuscript/**,analysis/effective_bv/artwork_templates.zip" --exclude=""
python scripts/validate_figures.py
python scripts/render_final_figures.py --inkscape /path/to/inkscape --output build/figures
```

The validator checks all seven SVG/PNG pairs and the six Figure 6 result tables
against `reproducibility/manifest.json`. It also independently recalculates means,
sample SD, support masks, parameter transforms, coverage counts, and crossings.

Inkscape exports the final SVG layouts at 3,000 pixels wide. For vector PDF,
add `--format pdf` and choose a separate output directory. Inkscape and Arial
fonts are required; renderer/font differences can change text layout and pixels.
Artwork export does not rerun numerical analyses.

## Scope

Numerical reproduction starts from the provided digitized coordinates and
documented selection rules. It does not redigitize publisher figures or repeat manual
claim adjudication. Figure 3 benchmark distances are replayed from coordinates.
Literature quality/claim percentages are recomputed from recorded review counts,
not independently re-reviewed. Publisher images and confidential case evidence
are not distributed; see the [Figure 3 scope](analysis/figure3/README.md).

## Reading the Outputs

The [result map](reproducibility/RESULT_MAP.md) links figure panels and SI tables
to input and output files. `report` must follow all three numerical stages in
the same output directory. Lower `--workers` to reduce CPU demand; retain
`--starts 12` for the stated VHT protocol. Changed code or inputs invalidate
checkpoints: choose a new `--output` directory rather than reusing them.

Use tolerances rather than byte equality for optimizer outputs. Curves, cohort
counts, acceptance thresholds, and certified coverage counts must agree.
Multiple template sets can attain the same maximum coverage. The supplied
selected set fixes the A/B family labels for the published artwork; a fresh
search is not automatically substituted into that artwork. The finite grid
does not certify a global optimum over all continuous shapes. Optimization
seeds are additional feasible starts, not held-out observations or independent
measurements. `selected_stage` distinguishes a retained seed from a new optimum.
