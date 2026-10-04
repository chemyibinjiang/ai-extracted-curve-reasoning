HER TEMPLATE COMPOSITION VIEWER
4 October 2026

Open the viewer
1. Extract the entire ZIP into a folder.
2. Open index.html in Chrome, Edge, Firefox or Safari.

No installation, server, Python or internet connection is needed for
the interactive viewer, its figures, filters or CSV exports. Keep the
included files together so figure and data links continue to work.
Opening publication DOI links requires internet access.

Views
Tafel curves & slopes: linked individual observed curves and local-slope
distributions, using the same element and template filters. The distribution
view has potential/current windows, paper/curve weighting, linear/logarithmic
slope axes, and CSV exports. No full-window coverage or model extrapolation
is required. See tafel/METHODS.md for the estimator and data provenance.

Heatmap: cell color and text indicate a percentage.
Bubble map: bubble AREA indicates the raw number of matching curves;
color indicates the percentage. The size scale is fixed across filters.
PCA map: one bubble per template at its archived Figure 7 shape-PCA
coordinates, with the same count-area and percentage-color encoding.
Select an element; the positions remain fixed when filters change.
With equal-paper weighting, colors change but bubble counts stay raw.
Hover or select a cell for exact percentages and underlying counts.

In the matrix and bar views, the six PGM-rich templates are on the left;
the other ten are on the right. PCA positions follow the original model.
Composition filters distinguish element-containing curves with and without
recorded PGM. PGM means Pt, Pd, Rh, Ru, Ir or Os, not Au or Ag.

Data
1,343 unique extracted curves, 402 papers and 16 existing templates.
The two denominators are explained in METHODS.txt. Elements and template
memberships overlap; percentages across rows or columns need not sum to 100%.
The separate Pt/C reference families are not added to this catalog.
The Tafel explorer additionally includes the full Figure 4 prepared cohort:
3,033 curves from 473 papers. Template filtering is optional there, and Pt/C
is shown separately. Geometric-area normalization is its default selection.

Included
- The same HTML viewer and its embedded data.
- PNG, PDF and SVG exports of the three summary figures.
- Detailed CSV tables and an additional JSON copy of the data.
- Archived template PCA coordinates as a separate CSV.
- Methods, source hashes and verification of the original calculations.
- The self-contained tafel/ viewer, prepared points, local derivatives,
  curve-window statistics and its local Plotly JavaScript dependency.

This is a self-contained viewing package, not the full analysis repository.
Developer scripts and workstation screenshots are intentionally excluded.
The build.py and viewer.html mentioned in METHODS.txt refer to the original
analysis source, not files needed to open this package.

Online viewer:
https://chemyibinjiang.github.io/ai-extracted-curve-reasoning/

Research repository:
https://github.com/chemyibinjiang/ai-extracted-curve-reasoning
