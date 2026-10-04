# Local Tafel slope explorer

This viewer connects recorded catalyst composition and Figure 7 template
membership to the original polarization curves and their local Tafel slopes.
Its source is the 3,033 prepared Figure 4 curves (473 papers, 80,399 observations).
Interactive views include the 3,030 composition-classified curves; three records
with empty recorded-element fields are omitted from plots, counts, catalogs and
selection exports. The full source tables remain available for reproduction.
It does not select by BV fit quality, PCA eligibility or template compatibility
unless a template filter is explicitly chosen.

## Reproduction

From the research repository's `codex/major-revision-20260922` branch:

```text
python analysis/tafel_explorer/build.py --output build/tafel-explorer
python -m unittest discover -s tests -p test_tafel_explorer.py
```

The builder requires NumPy and pandas, plus either Python Plotly or an existing
Plotly JavaScript bundle supplied with `--plotly-js path/to/plotly.min.js`.
Open the generated `index.html`
directly, with its adjacent files. No server or external JavaScript service is
required. Source hashes are recorded in `provenance.json`.

Optional browser checks require Node.js, Playwright and Chromium:

```text
npm install --no-save playwright
npx playwright install chromium
node analysis/tafel_explorer/test_browser.cjs <site-root-URL> build/tafel-browser-qa
```

The site root includes the existing composition viewer and the generated
`tafel/` directory. The check covers navigation between them, composition
filters, empty selections, individual curves, distributions, downloads and
mobile layout. It saves screenshots and a results file.

## Observed curves and local slopes

The Tafel view plots |eta| against log10|j|. Lines join prepared native points;
there is no extrapolation or fitted BV/VHT response in this view. Points outside
the selected window are not drawn. A curve is not required to cover the full
window. Curves with too few points for a derivative can still appear here.

Local slopes are b = d|eta|/d log10|j|, in mV/dec, calculated by the existing
Figure 4 nine-point, tricube-weighted quadratic fit on the irregular native
log-current grid. The four points at each end are excluded. A neighborhood is
excluded when its log-current radius exceeds 0.45 decades, span is below 0.04
decades, either side spans less than 15% of the radius, the weighted design
condition number exceeds 10,000, or effective support is below four points.
Negative estimates are retained. No resistance correction is newly applied.

Bins are assigned by the native derivative center's potential or current.
The fitting neighborhood may extend beyond that bin; these are local-center
summaries, not independent straight-line fits confined to each window.
Each curve contributes its median eligible derivative per bin. A single
eligible center suffices, as in Figure 4; center counts are included in exports.
Bins are left-closed/right-open, except that the last includes its upper edge.

The current windows group the SAME local derivative used in the potential
windows. They are distinct from earlier exploratory secant estimates based on
the two endpoints of a complete current window.

## Composition and weighting

Filters use the same recorded-element definitions and corrected template
memberships as the composition viewer. PGM means Pt, Pd, Rh, Ru, Ir or Os.
Pt/C is displayed separately from other PGM catalysts. Records without a
composition classification are omitted, not assigned to non-PGM. An element
feature records its presence, not its fraction.
The non-PGM filter requires recorded composition with none of the six PGMs.
Co-occurrence does not imply alloying.

The default current-normalization filter is geometric area. The optional
all-normalization-bases selection includes other reported normalization bases;
the composition restriction still applies. Those currents are not directly
comparable as geometric current density. Template membership can overlap; union selections
count each curve once. The sixteen non-Pt/C templates do not contain the
separate Pt/C reference families.

In each condition, group and window, default weights give each contributing
paper equal total weight and divide it equally among that paper's curves.
Weights are recalculated after filtering. The alternative gives each curve
equal weight. Quartiles are inverse weighted empirical-CDF quantiles; the
overview shows a median and interquartile interval, not a confidence interval.

The density view uses a weighted Gaussian kernel with the same bandwidth for
all displayed groups (default 20 mV/dec; adjustable). Density integrates to one
over the real line. A restricted display range does not renormalize it; the
observed weight outside the display is reported. Single-curve groups are shown
as a rug mark, not a density. The empirical-CDF option requires no bandwidth.
The distribution's x axis can be linear or logarithmic. This is a display
change only: it does not fit kernels in log-slope space or alter weights.
The y axis remains density per mV/dec. Non-positive slopes cannot be drawn
on a log axis but remain in the statistics and reported outside-display weight.

Different bins can contain different curves and papers. The resulting
distributions describe observed apparent slopes, not a fitted kinetic step or
an intrinsic material constant. Prepared points are restricted to
0.2-500 mA/cm2 and 0-2,000 mV, as in Figure 4. The site's potential bins extend
to 500 mV; its current-bin statistics use the full prepared potential range.
Counts refer to curves, not unique catalyst formulations.

## Data exports

- `local_slopes.csv`: every eligible local derivative with its support metrics.
- `curve_window_slopes.csv`: per-curve medians and contributing-center counts.
- `all_paper_weighted_summary.csv`: full prepared-cohort summaries for checking
  against Figure 4 (all conditions and normalization bases).
- The website exports the active curve-window records and selected native
  points with their DOI, material, composition and normalized statistical weight.
