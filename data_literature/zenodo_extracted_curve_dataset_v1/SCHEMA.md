# Schema

## Common provenance fields

- `source_record_id`: internal publication-record identifier used during data
  construction, formatted as `batchX/caseY`.
- `source_doi`: DOI of the source publication.
- `source_doi_url`: DOI resolver URL.
- `paper_title`: source publication title.
- `figure_id`: normalized figure identifier from the source article.
- `panel_id`: normalized panel identifier within the figure.
- `panel_uid`: unique panel identifier used by this dataset.
- `curve_uid`: unique curve identifier used by this dataset.

## `source_publication_records.csv`

Publication-level metadata and aggregate counts. The table is intended for
auditing source coverage and duplicate DOI counts.

## `panel_metadata.csv`

Panel-level metadata, including panel IDs, axis labels and units, tick labels,
HER relevance labels, reaction/electrolyte context, and panel-level enrichment
metadata. The table excludes paths to source figures or extraction images.

## `curve_metadata.csv`

Curve-level metadata, including catalyst names, curve labels, condition labels,
line/marker descriptors, publication inclusion flags, normalized coordinate
ranges, axis labels and units, and curve-level enrichment metadata. The
`catalyst_name` field is a convenience field selected from curated publication
labels or enrichment/material labels when available.

## `curve_points_long.csv`

Normalized extracted curve points. One row is one sampled point:

- `x_value`, `y_value`: normalized scientific coordinates.
- `point_confidence`: point-level extraction confidence when available.
- `x_axis_label`, `x_axis_units`, `y_axis_label`, `y_axis_units`: native axis
  metadata for the normalized curve.

The table includes DOI and catalyst fields for standalone use, but
`curve_uid` is the primary key for joining back to `curve_metadata.csv`.

## `axis_fits.csv`

Sanitized axis-fit diagnostics for panels. It includes model choice, slope,
intercept, anchor counts, normalized RMSE, confidence, and manual-review flags.
Local paths and free-text fit justifications are not included.
