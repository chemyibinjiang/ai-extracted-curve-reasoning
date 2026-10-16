# Reproducing the Figures

## Environment

Follow the [repository setup](README.md#run-the-analyses), including Git LFS
and a virtual environment. Numerical dependencies are pinned in
`requirements-analysis.txt`; the reference environment uses Python 3.13.12.
Run commands from the repository root. Results go to ignored `build/`
directories and do not replace the supplied data or manuscript artwork.

Start with the [quick checks](README.md#quick-checks). Then choose the figure
or calculation needed below; there is no need to run every command.

## Data and Figures 3-6

| Task | Command |
| --- | --- |
| Verify the 4,211-curve release and its source links | `python scripts/validate_dataset.py` |
| Rebuild preparation from the coordinate ZIP and check Pt/C and Figure 7 inputs | `python scripts/audit_raw_to_analysis.py` |
| Replay all 137 synthetic benchmark curves and tabulate recorded literature-review counts | `python analysis/figure3/run.py` |
| Rebuild the 3,033-curve fitting cohort, with every inclusion decision | `python analysis/figure4/run.py prepare --output build/figure4-preparation` |
| Refit all 6,066 BV/BV+jR models and recalculate Figure 4 summaries | `python analysis/effective_bv/run.py population --workers 6` |
| Refit the Figure 5 case studies and current-scaling comparisons | `python analysis/effective_bv/run.py examples` |
| Refit current amplitudes and VHT reconstructions for the selected Figure 6 families | `python analysis/effective_bv/run.py families --workers 6 --starts 12` |
| Build review plots after the preceding three fitting stages | `python analysis/effective_bv/run.py report` |

Alternatively, `python analysis/effective_bv/run.py all --workers 6 --starts 12`
runs `population`, `examples`, `families` and `report` in order. Do not repeat
those stages separately if using `all`. Their default output is
`build/effective-bv-20260930/`.

The population refit uses multistart optimization, with the supplied fitted
parameters as additional feasible starts. It independently checks voltage
objectives and that BV is nested within BV+jR. The accepted counts are 1,588
and 2,361, respectively. Figure 6 reuses the supplied selected families.
To repeat its full 276,551-candidate grid search and K=1-10 selection, use the
separate `python analysis/effective_bv/search.py` command. This is substantially
more work than refitting the selected families.

See the [analysis protocol](analysis/effective_bv/README.md) for fit bounds,
seed provenance and output definitions. Figure-specific `analysis/figure4/run.py`,
`analysis/figure5/run.py` and `analysis/figure6/run.py` call these same current
stages. Historical workflows under `exploration/` are not runtime dependencies.

## Figure 7 and SI Section 9

Choose **one** of the following:

```text
python analysis/figure7/run.py replay
```

This rebuilds the observed-data cohort, refits the final population model
using the supplied tuning results, and recalculates projections, uncertainty
and support checks, native template residuals, achieved coverage and figures.

```text
python analysis/figure7/run.py cv
```

This additionally repeats all 24 whole-paper tuning fits before the final
model fit. Both commands reproduce the observed-current and growth comparisons
in SI Section 9.9, Table S30 and Figure S21. Outputs default to `build/figure7`.

For the additional complete-window sensitivity analysis in Tables S28-S29:

```text
python analysis/figure7/run.py complete-window
```

The 17,005-candidate library and selected K=1-30 sets are supplied inputs.
Neither `replay` nor `cv` constructs a new library or selects new template sets:
they recount the selected unions and independently evaluate every selected
native match in voltage space. See the [Figure 7 guide](analysis/figure7/README.md)
and [method details](analysis/figure7/METHODS.md).

## Figure 8 and SI Section 11

```text
python analysis/figure8/run.py
```

This starts from native experimental records, rebuilds selection and response
series, projects observations into the **fixed Figure 7 model**, and recalculates
the matched-window dispersion comparisons. It produces all six panels and
Tables S31-S32 in `build/figure8/`, checking against supplied numerical references.
Use `--no-figure` for tables only, or `--output PATH` for a separate destination.
The [Figure 8 guide](analysis/figure8/README.md) links the original data and
describes the measurements and calculations.

## Tests

```text
python -m unittest discover -s tests -v
```

This is a full test-suite run, not a quick installation check. It runs all
Figures 4-6 stages in an isolated copy with a reduced two-start test setting,
and reproduces Figure 8 from native data. Use `--starts 12` in the analysis
commands for the stated VHT fitting protocol.
Tests also cover source hashes, cohort selection, local derivatives, weighting,
kinetic Jacobians, current scaling, partial-observation inference and plotting
with a fallback font. They require the LFS assets listed in the setup instructions.
Once those assets and dependencies are installed, the numerical tests use no network.

## Artwork

The current eight SVG/PNG pairs are in [figures/manuscript/](figures/manuscript/).
Validate them and export their final layouts with:

```text
python scripts/validate_figures.py
python scripts/render_final_figures.py --inkscape /path/to/inkscape --output build/figures
```

The validator checks all eight SVG/PNG pairs and six Figure 6 result tables
against `reproducibility/manifest.json`, and independently checks the table
summaries. Inkscape exports at 3,000 pixels wide; add `--format pdf` and select
a separate output directory for vector PDF. The manuscript layouts require
Arial. Font or renderer differences can change text placement and pixels.
Artwork export does not rerun the numerical analyses.

**Optional historical review layouts:**
`python analysis/effective_bv/artwork.py --data build/effective-bv-20260930 --output build/manuscript-figures --inkscape /path/to/inkscape`
updates the older six-figure layouts. Its Figure 1D is historical and Figures
2-3 are copied from that baseline. Use the export commands above for the
current manuscript set, or the Figure 7/8 analysis commands for newly drawn plots.

## Scope and Outputs

Literature analyses start from released extracted coordinates; Figure 8 starts
from native experimental records. Reproduction does not redigitize publisher
figures or repeat human claim adjudication. Figure 3 benchmark distances are
recalculated from coordinates; literature-review percentages use recorded
review counts. See the [Figure 3 guide](analysis/figure3/README.md) for that scope.

The [result map](reproducibility/RESULT_MAP.md) identifies the input and output
behind each figure panel and SI table. Lower `--workers` to reduce CPU demand;
retain `--starts 12` for the stated VHT fitting protocol. After changing code or
inputs, use a new output directory rather than reusing cached fits.

Compare optimizer outputs within numerical tolerances, not by file hashes.
Input coordinates, cohort counts and acceptance rules should agree exactly.
Different selected template sets can achieve the same coverage; supplied sets
keep the published family labels stable. Reproducing their coverage does not
establish a unique or globally minimal set of continuous shapes.
