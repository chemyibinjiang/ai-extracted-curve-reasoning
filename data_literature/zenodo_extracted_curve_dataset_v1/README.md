# Extracted HER Polarization Curve Dataset

This Zenodo-ready package contains the primary hydrogen evolution reaction
(HER) polarization-curve dataset used in the manuscript "Multi-Agent AI Converts
Published Figures into Auditable Curve Evidence for Claim Validation and
Scientific Analysis".

The package is designed to publish the extracted numeric curve evidence while
excluding copyrighted source figures. Each curve can be traced back to its
source article and panel using DOI, figure ID, panel ID, and curve/catalyst
metadata. The release is limited to the final `primary_main_HER` publication
dataset. Original publication figures, screenshots, article HTML, and original
figure captions are intentionally not included.

## Files

- `source_publication_records.csv`: one row per denominator publication record,
  including DOI, DOI URL, title, inclusion flag, and aggregate record counts.
  The primary HER curve rows are represented by a subset of these records; see
  `dataset_summary.json`.
- `panel_metadata.csv`: one row per processed source panel, including DOI,
  figure/panel identifiers, axis labels, tick labels, reaction/electrolyte
  metadata, and publication-inclusion flags.
- `curve_metadata.csv`: one row per extracted curve, including DOI, panel
  identifier, curve identifier, catalyst/condition metadata, normalization
  status, axis metadata, and quality-control flags.
- `curve_points_long.csv`: one row per normalized extracted point. Join to
  `curve_metadata.csv` with `curve_uid`.
- `axis_fits.csv`: sanitized axis-fit records for the extracted panels.
- `SCHEMA.md`: field-level description of the release tables.
- `dataset_summary.json`: counts and build metadata.
- `SHA256SUMS.txt`: checksums for files in this package.

## Source Attribution

The fields `source_doi` and `source_doi_url` identify the original publication.
The fields `figure_id`, `panel_id`, `curve_id`, `catalyst_name`, and
`condition_name` identify the figure-panel curve within that publication.

## Exclusions

This release does not include original publication figures, source HTML,
screenshots, publisher asset folders, original figure captions, internal
validation records, or claim-validation cards. Users who need to inspect the
original figures should access the cited publications through their publishers.

## Suggested Zenodo Record

Suggested title: `Extracted HER polarization curves from electrocatalysis
literature`.

Suggested description: `A numeric dataset of AI-extracted primary hydrogen
evolution reaction polarization curves with DOI-, figure-, panel-, catalyst-,
and condition-level provenance. Original source figures and article HTML are
not included.`
