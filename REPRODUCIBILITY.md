# Reproducing the Figures

## Environment

Use Python 3.13 and the pinned numerical dependencies:

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
| `python analysis/figure4/run.py prepare --output build/figure4-preparation` | Read all 4,211 extracted curves, rebuild the 3,033-curve cohort, and record every selection decision |
| `python analysis/figure4/run.py` | Rebuild the cohort; verify supplied fits on all 80,399 fitting points; recompute slopes, fit metrics, distributions, and examples |
| `python analysis/figure5/run.py --refit-kscn` | Refit case-study models, calculate compensation/EIS trends and current scaling, and refit KSCN control |
| `python analysis/figure5/refit_nimo.py` | Fit identical experimental NiMo points with BV, BV+jR and resistance-free VHT; calculate coverage and diagnostics; export the C comparison separately |
| `python analysis/figure6/run.py` | Reprofile empirical current scales, reconstruct supplied VHT solutions, recalibrate amplitudes, and recompute rate controls |
| `python analysis/figure6/run.py discover --output build/figure6-discovery` | Rerun empirical template discovery and coverage optimization for K=1..10 |
| `python analysis/figure4/run.py refit --workers 4 --output build/figure4-refit` | Rebuild the cohort, refit all 6,066 BV/BV+jR models, and validate objectives and pass assignments |
| `python analysis/figure6/run.py refit --workers 4 --output build/figure6-refit` | Rerun VHT multistart optimization and the KOH parameter-sharing search |

See the [analysis guide](analysis/README.md) for inputs, outputs, fixed assumptions,
and interpretation. Reconstructing a supplied fit is not the same as estimating
its parameters again. Refit outputs are kept separate from figure references.

The Figure 3 synthetic benchmark and evaluation commands are documented in
[the benchmark guide](benchmark_data/benchmark_curve_extraction/README.md).
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

Verified calculations include the Figure 4 cohort preparation, full refit, reference-fit reconstruction and
derived statistics, Figure 5 case-study fits/scaling, Figure 6 empirical discovery,
Figure 6 reconstruction, and the full VHT multistart/parameter-sharing search.
The VHT refit recovered the supplied acid/KOH parameters and per-family errors
in the pinned environment. All 6,066 Figure 4 model fits succeeded; the 806 BV
and 2,351 BV+jR passing curves were unchanged. The refit command writes
`REFIT_CHECKS.json` with objective differences and pass-assignment checks.
An executed-run summary is in [reproducibility/figure4-validation.json](reproducibility/figure4-validation.json).

## Artwork

```text
git lfs pull --include="figures/manuscript/**" --exclude=""
python scripts/validate_figures.py
python scripts/render_final_figures.py --inkscape /path/to/inkscape --output build/figures
```

The validator checks all six SVG/PNG pairs and the six Figure 6 result tables
against `reproducibility/manifest.json`. It also independently recalculates means,
sample SD, support masks, parameter transforms, coverage counts, and crossings.

Inkscape exports the final SVG layouts at 3,000 pixels wide. For vector PDF,
add `--format pdf` and choose a separate output directory. Inkscape and Arial
fonts are required; renderer/font differences can change text layout and pixels.
Artwork export does not rerun numerical analyses.

## Scope

Numerical reproduction starts from the provided digitized coordinates and
documented selection rules. It does not redigitize publisher figures or repeat manual
claim adjudication. The Figure 3 benchmark, corpus summaries, and claim examples
must remain distinct evaluations; their integration into a single figure-level
reproduction command is not yet complete. A complete-paper reproduction claim
requires that check and a clean-checkout run.
