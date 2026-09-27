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

The manuscript SVG/PNG files include the effective-BV numerical revision.
Figure 1A-C and Figures 2-3 are unchanged. Figures 1D and 4-6 retain their manually edited plot types,
frames, fonts and overall layout, with updated data artists and numeric labels.
The four alkaline family plots occupy the same four-column grid as the acid row.

After the numerical analysis, regenerate the data updates into a review folder:

```text
python analysis/effective_bv/artwork.py --data build/effective-bv-20260927 --output build/manuscript-figures --inkscape /path/to/inkscape
```

This command uses the included compressed SVG templates and does not overwrite
the published figures. Its output includes the six figures, an HTML gallery,
Figure 6 audit tables and `ARTWORK_CHECKS.json`. To validate or export the
published figures directly:

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
