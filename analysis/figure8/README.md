# Figure 8 Experimental Response Shapes

Figure 8 compares measured responses from an electrodeposited catalyst library
with the literature shape model in Figure 7. It examines two patterns: similar
LSV shapes after current rescaling, and the relative spread of PGM-containing
and non-PGM responses. Methods are described in SI Section 11.

## Reproduce

From the repository root, after installing `requirements-analysis.txt`:

```text
git lfs pull --include="analysis/figure8/inputs/*.zip" --exclude=""
python analysis/figure8/run.py
```

The command reads the original screening records, repeats curve selection and
series grouping, projects curves into the fixed Figure 7 model, recalculates
the dispersion comparisons, and checks the results against the figure data.
It writes tables and PNG/SVG/PDF figures to `build/figure8/`. Use `--output PATH`
for another destination or `--no-figure` for numerical results only. Runs are
offline once the inputs and Python dependencies are installed. Arial is used
when available; other systems use DejaVu Sans. The approved manuscript artwork
in `figures/manuscript/` is not overwritten.

## Data and Measurement Conditions

The input ZIP contains the 561 initial-screening LSV records and the original
metadata table from [Wang-Group/HD_separation](https://github.com/Wang-Group/HD_separation/tree/8dc5de3d8101cd86455626e4f710d96c3c2cd38e),
commit `8dc5de3d8101cd86455626e4f710d96c3c2cd38e`. The metadata table also lists
later experiments; only records labelled `initial_screening_561` enter Figure 8.
Files retain their original bytes and paths. `inputs/manifest.json` records
their SHA-256 checksums and the Figure 7 model checksum.

The library comprises single-metal controls and two-precursor formulations
electrodeposited on carbon paper. Screening LSVs were measured in 1.0 M KOH
containing 10% D2O at 2 mV/s with 90% iR compensation. Labels such as Mo-Pt
identify nominal precursor combinations; Pt-Pt is the single-metal Pt control.
The source's +0.9268 V conversion from Hg/HgO to RHE and geometric electrode
areas are retained. No additional resistance correction is applied.

These experimental data are attributed to the Wang-Group source repository;
this package does not assign new ownership or reuse terms to them.

## Calculations

- **Preparation:** retain the scan after its initial minimum in current
  magnitude, within 0.2-500 mA/cm2. Evaluate log10 current on the 20-300 mV
  grid at 10 mV increments, interpolating only across measured gaps of at most
  20 mV. At least four native points and four grid positions spanning 30 mV
  are required. This retains 524 curves: 60 PGM-containing and 464 non-PGM.
- **Series (A-C):** compare all initial-screening curves supported throughout
  50-250 mV on a 5 mV grid. For each pair, subtract the mean log-current
  difference, equivalent to fitting one current multiplier. Complete-linkage
  groups require every pair to have RMS residual at most 0.02 decades and
  maximum residual at most 0.05 decades. The three displayed groups also meet
  these criteria over 50-300 mV. Insets divide current by its observed or
  interpolated value at 50 mV.
- **Shape maps (D-E):** reuse the mean, loadings, residual variance and coordinate
  scales from `analysis/figure7/reference/MODEL.npz`. Only each new curve's
  current offset, coordinates and uncertainty are estimated. Panel D contains
  1,666 alkaline literature curves; panel E contains the 524 experimental curves.
- **Dispersion (F):** compare curves observed throughout each stated window,
  estimating their coordinates using only that window. Spread is the RMS
  distance from the group centre in all three coordinates, including score
  uncertainty. Papers receive equal weight within each literature class;
  unordered nominal element combinations receive equal weight within each
  experimental class. The PGM-containing literature class includes Pt/C.
  Intervals use 1,999 joint cluster resamples and conditional score draws.

The Figure 7 model is intentionally held fixed: Figure 8 evaluates experimental
responses in the literature-derived coordinate system. The original Figure 7
fitting and validation remain reproducible through `analysis/figure7/run.py`.

## Outputs

| Result | File in `build/figure8/` |
| --- | --- |
| Inclusion decisions for all 561 records | `experimental_selection.csv` |
| Complete-linkage series from the library | `all_series.csv` |
| Figure 8A-C displayed curves | `panel_ABC_native_profiles.csv` |
| Pairwise similarity checks; Table S31 | `panel_ABC_series_checks.csv` |
| Figure 8D-E coordinates | `panel_D_literature_scores.csv`, `panel_E_experimental_scores.csv` |
| Figure 8F; Table S32 | `matched_support_dispersion.csv` |
| Coordinates used for each matched-window comparison | `matched_support_scores.csv` |
| Numerical checks against the approved figure | `verification.json` |

`reference/` contains the corresponding approved numerical results. Reference
tables are used only for verification, not as inputs to the calculations.
