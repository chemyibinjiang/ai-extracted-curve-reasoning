#!/usr/bin/env python3
"""Build the public Zenodo package for the extracted HER curve dataset.

The release intentionally includes extracted numeric curve records and safe
source identifiers (DOI, figure/panel IDs, catalyst/condition metadata), but
excludes original publication figures, source HTML, screenshots, captions, and
local proof/audit paths.
"""

from __future__ import annotations

import csv
import hashlib
import html
import json
import re
import shutil
import urllib.parse
import zipfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
CANONICAL = ROOT / "data" / "LSV_publication_database" / "02_canonical_tables"
SOURCE_ASSETS = ROOT / "data" / "LSV_publication_database" / "01_source_html_assets"
OUT_DIR = ROOT / "data_literature" / "zenodo_extracted_curve_dataset_v1"
ZIP_PATH = ROOT / "data_literature" / "zenodo_extracted_curve_dataset_v1.zip"
PUBLICATION_DATASET_BUCKET = "primary_main_HER"


META_DOI_PATTERNS = [
    re.compile(
        r"<meta[^>]+(?:name|property)=[\"']"
        r"(?:citation_doi|publication_doi|dc\.identifier|DC\.Identifier)"
        r"[\"'][^>]+content=[\"']([^\"']+)",
        re.I,
    ),
    re.compile(
        r"<meta[^>]+content=[\"']([^\"']+)[\"'][^>]+(?:name|property)=[\"']"
        r"(?:citation_doi|publication_doi|dc\.identifier|DC\.Identifier)[\"']",
        re.I,
    ),
    re.compile(r"\"doi\"\s*:\s*\"(10\.\d{4,9}/[^\"\\]+)\"", re.I),
    re.compile(
        r"saved from url=\([^)]*\)https?://[^\s\"<>]+/doi/(?:full/|abs/)?"
        r"(10\.\d{4,9}/[^\s\"<>]+)",
        re.I,
    ),
]
GENERIC_DOI_PATTERN = re.compile(r"10\.\d{4,9}/[-._;()/:A-Za-z0-9]+", re.I)


SAFE_CASE_COLUMNS = [
    "source_record_id",
    "source_doi",
    "source_doi_url",
    "paper_title",
    "included_in_quantitative_dataset",
    "figures",
    "processed_panels",
    "publication_panels",
    "extracted_curves",
    "publication_curves",
    "current_normalized_completed_curves",
]

SAFE_PANEL_COLUMNS = [
    "panel_uid",
    "source_record_id",
    "source_doi",
    "source_doi_url",
    "paper_title",
    "figure_id",
    "panel_id",
    "panel_label",
    "panel_type_anchoring",
    "panel_type_curve_extraction",
    "plot_area_box_cropped",
    "x_axis_label",
    "x_axis_units",
    "x_axis_type",
    "x_tick_labels",
    "y_axis_label",
    "y_axis_units",
    "y_axis_type",
    "y_tick_labels",
    "legend_entries",
    "raw_curve_count_current_response",
    "publication_included_panel",
    "analysis_bucket",
    "relevance_group",
    "reaction_type_publication",
    "final_HER_category",
    "curve_family_publication",
    "measurement_configuration_publication",
    "electrolyte_text_publication",
    "enrich_reaction_type_panel",
    "enrich_electrolyte_family_panel",
    "enrich_electrolyte_text_panel",
    "enrich_curve_family_panel",
    "enrich_measurement_configuration_panel",
    "panel_enrichment_manual_review_required",
]

SAFE_CURVE_COLUMNS = [
    "curve_uid",
    "panel_uid",
    "source_record_id",
    "source_doi",
    "source_doi_url",
    "paper_title",
    "figure_id",
    "panel_id",
    "curve_index",
    "curve_id",
    "catalyst_name",
    "condition_name",
    "curve_label_current_response",
    "condition_label_current_response",
    "publication_curve_label",
    "publication_condition_label",
    "stroke_color",
    "line_style",
    "marker_style",
    "visible_segment_status",
    "sampled_point_count",
    "publication_included_curve",
    "publication_analysis_bucket",
    "source_usable_for_normalization_publication",
    "enrich_reaction_type",
    "enrich_electrolyte_regime",
    "enrich_electrolyte_identity",
    "enrich_reference_scale",
    "enrich_ir_compensation_status",
    "enrich_measurement_configuration",
    "enrich_curve_family",
    "enrich_current_normalization_basis",
    "enrich_reported_material_name",
    "enrich_catalyst_role",
    "enrich_material_class",
    "enrich_active_elements",
    "enrich_support_material",
    "enrich_substrate_material",
    "enrich_structural_motif",
    "enrich_contains_pgm",
    "enrich_bimetallic_flag",
    "normalization_status_current",
    "source_usable_for_normalization_current",
    "normalized_point_count_current",
    "x_min_current",
    "x_max_current",
    "y_min_current",
    "y_max_current",
    "x_axis_label_current",
    "x_axis_units_current",
    "y_axis_label_current",
    "y_axis_units_current",
    "x_axis_type_current",
    "y_axis_type_current",
    "overlay_red_flagged_point_count_current",
    "overlay_red_manual_review_required_current",
]

SAFE_AXIS_COLUMNS = [
    "panel_uid",
    "source_record_id",
    "source_doi",
    "source_doi_url",
    "figure_id",
    "panel_id",
    "axis",
    "chosen_model",
    "usable_for_downstream",
    "confidence",
    "raw_anchor_count",
    "parsed_anchor_count",
    "normalized_rmse",
    "slope",
    "intercept",
    "manual_review_recommended",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: Iterable[dict[str, object]], columns: list[str]) -> int:
    count = 0
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: sanitize_value(row.get(column, "")) for column in columns})
            count += 1
    return count


def sanitize_value(value: object) -> object:
    if isinstance(value, str):
        return value.replace("\x00", "")
    return value


def read_file_head(path: Path, byte_count: int = 3_000_000) -> str:
    with path.open("rb") as handle:
        return handle.read(byte_count).decode("utf-8", errors="ignore")


def clean_doi(candidate: str) -> str | None:
    value = html.unescape(urllib.parse.unquote(candidate or "")).strip()
    value = value.replace("\\/", "/")
    value = re.sub(r"[\s\"'<>)#?,;]+$", "", value)
    value = value.removesuffix(".html").strip(".").lower()
    if not value.startswith("10."):
        return None
    if "(issn)" in value or "/doi/" in value:
        return None
    # Wiley issue DOIs are common in page metadata but are not paper DOIs.
    if re.search(r"10\.1002/[a-z]{3,6}\.v\d+", value):
        return None
    return value


def extract_case_dois() -> dict[str, str]:
    inventory_path = SOURCE_ASSETS / "manifest" / "source_html_assets_inventory.csv"
    if not inventory_path.exists():
        raise FileNotFoundError(
            f"Missing private DOI source inventory: {inventory_path}. "
            "The Zenodo package builder needs it only to derive DOI strings; "
            "no source HTML or figures are copied."
        )

    doi_by_case: dict[str, str] = {}
    for row in read_csv(inventory_path):
        candidates: list[str] = []
        html_files = [item.strip() for item in row.get("html_files", "").split(";") if item.strip()]
        for relpath in html_files:
            path = SOURCE_ASSETS / relpath
            if path.exists():
                text = read_file_head(path)
                for pattern in META_DOI_PATTERNS:
                    candidates.extend(pattern.findall(text))
                filename = path.name.replace("___", "/").replace("%2F", "/")
                candidates.extend(GENERIC_DOI_PATTERN.findall(filename))

        cleaned: list[str] = []
        for candidate in candidates:
            doi = clean_doi(candidate)
            if doi and doi not in cleaned:
                cleaned.append(doi)
        if cleaned:
            doi_by_case[row["case_rel_path"]] = cleaned[0]

    return doi_by_case


def add_source_fields(row: dict[str, str], doi_by_case: dict[str, str]) -> dict[str, str]:
    out = dict(row)
    source_record_id = row.get("case_rel_path", "")
    if not source_record_id and row.get("publication_batch") and row.get("case_id"):
        source_record_id = f"{row['publication_batch']}/{row['case_id']}"
    doi = doi_by_case.get(source_record_id, "")
    out["source_record_id"] = source_record_id
    out["source_doi"] = doi
    out["source_doi_url"] = f"https://doi.org/{doi}" if doi else ""
    return out


def first_nonempty(*values: str) -> str:
    for value in values:
        if value and str(value).strip():
            return str(value).strip()
    return ""


def build_release() -> dict[str, object]:
    doi_by_case = extract_case_dois()

    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    OUT_DIR.mkdir(parents=True)

    cases = [add_source_fields(row, doi_by_case) for row in read_csv(CANONICAL / "cases.csv")]
    panels = [
        add_source_fields(row, doi_by_case)
        for row in read_csv(CANONICAL / "panels.csv")
        if row.get("analysis_bucket") == PUBLICATION_DATASET_BUCKET
    ]
    release_panel_uids = {row["panel_uid"] for row in panels}
    curves = []
    curve_metadata_by_uid: dict[str, dict[str, str]] = {}
    for row in read_csv(CANONICAL / "curves.csv"):
        if row.get("publication_analysis_bucket") != PUBLICATION_DATASET_BUCKET:
            continue
        out = add_source_fields(row, doi_by_case)
        out["catalyst_name"] = first_nonempty(
            out.get("publication_curve_label", ""),
            out.get("enrich_reported_material_name", ""),
            out.get("curve_label_current_response", ""),
            out.get("catalyst_context_current_response", ""),
        )
        out["condition_name"] = first_nonempty(
            out.get("publication_condition_label", ""),
            out.get("condition_label_current_response", ""),
            out.get("enrich_electrolyte_identity", ""),
            out.get("enrich_electrolyte_regime", ""),
        )
        curves.append(out)
        curve_metadata_by_uid[out["curve_uid"]] = out

    axes = [
        add_source_fields(row, doi_by_case)
        for row in read_csv(CANONICAL / "axis_fits.csv")
        if row.get("panel_uid") in release_panel_uids
    ]

    write_csv(OUT_DIR / "source_publication_records.csv", cases, SAFE_CASE_COLUMNS)
    write_csv(OUT_DIR / "panel_metadata.csv", panels, SAFE_PANEL_COLUMNS)
    write_csv(OUT_DIR / "curve_metadata.csv", curves, SAFE_CURVE_COLUMNS)
    write_csv(OUT_DIR / "axis_fits.csv", axes, SAFE_AXIS_COLUMNS)

    point_columns = [
        "curve_uid",
        "panel_uid",
        "source_record_id",
        "source_doi",
        "source_doi_url",
        "figure_id",
        "panel_id",
        "curve_id",
        "catalyst_name",
        "condition_name",
        "point_index",
        "x_value",
        "y_value",
        "point_confidence",
        "x_axis_label",
        "x_axis_units",
        "y_axis_label",
        "y_axis_units",
        "x_axis_type",
        "y_axis_type",
    ]
    point_count = 0
    missing_curve_metadata = 0
    with (OUT_DIR / "curve_points_long.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=point_columns)
        writer.writeheader()
        with (CANONICAL / "normalized_curve_points.jsonl").open(encoding="utf-8") as source:
            for line in source:
                record = json.loads(line)
                if record.get("curve_uid", "") not in curve_metadata_by_uid:
                    continue
                meta = curve_metadata_by_uid.get(record.get("curve_uid", ""))
                if not meta:
                    missing_curve_metadata += 1
                    meta = add_source_fields(record, doi_by_case)
                    meta["catalyst_name"] = first_nonempty(
                        record.get("curve_label", ""), record.get("catalyst_context", "")
                    )
                    meta["condition_name"] = record.get("condition_label", "")
                for idx, point in enumerate(record.get("native_points") or []):
                    point_row = {
                            "curve_uid": record.get("curve_uid", ""),
                            "panel_uid": record.get("panel_uid", ""),
                            "source_record_id": meta.get("source_record_id", ""),
                            "source_doi": meta.get("source_doi", ""),
                            "source_doi_url": meta.get("source_doi_url", ""),
                            "figure_id": record.get("figure_id", ""),
                            "panel_id": record.get("panel_id", ""),
                            "curve_id": record.get("curve_id", ""),
                            "catalyst_name": meta.get("catalyst_name", ""),
                            "condition_name": meta.get("condition_name", ""),
                            "point_index": idx,
                            "x_value": point.get("x", ""),
                            "y_value": point.get("y", ""),
                            "point_confidence": point.get("confidence", ""),
                            "x_axis_label": record.get("x_axis_label", ""),
                            "x_axis_units": record.get("x_axis_units", ""),
                            "y_axis_label": record.get("y_axis_label", ""),
                            "y_axis_units": record.get("y_axis_units", ""),
                            "x_axis_type": record.get("x_axis_type", ""),
                            "y_axis_type": record.get("y_axis_type", ""),
                    }
                    writer.writerow({key: sanitize_value(value) for key, value in point_row.items()})
                    point_count += 1

    write_documentation()

    summary = make_summary(cases, panels, curves, axes, doi_by_case, point_count, missing_curve_metadata)
    with (OUT_DIR / "dataset_summary.json").open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2, ensure_ascii=False)
        handle.write("\n")

    write_checksums()
    write_zip()
    return summary


def make_summary(
    cases: list[dict[str, str]],
    panels: list[dict[str, str]],
    curves: list[dict[str, str]],
    axes: list[dict[str, str]],
    doi_by_case: dict[str, str],
    point_count: int,
    missing_curve_metadata: int,
) -> dict[str, object]:
    normalized_curves = [
        row for row in curves if row.get("normalization_status_current") == "completed"
    ]
    included_curves = [row for row in curves if row.get("publication_included_curve") == "yes"]
    included_panels = [row for row in panels if row.get("publication_included_panel") == "yes"]
    status_counts = Counter(row.get("normalization_status_current", "") for row in curves)
    reaction_counts = Counter(row.get("enrich_reaction_type", "") for row in curves)
    curve_source_records = {row.get("source_record_id", "") for row in curves if row.get("source_record_id")}
    curve_source_dois = {row.get("source_doi", "") for row in curves if row.get("source_doi")}
    return {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "source_canonical_tables": str(CANONICAL.relative_to(ROOT)).replace("\\", "/"),
        "records": {
            "source_publication_records": len(cases),
            "unique_source_dois": len(set(doi for doi in doi_by_case.values() if doi)),
            "publication_dataset_bucket": PUBLICATION_DATASET_BUCKET,
            "source_records_with_released_curves": len(curve_source_records),
            "unique_source_dois_with_released_curves": len(curve_source_dois),
            "publication_included_panels": len(included_panels),
            "panel_metadata_rows": len(panels),
            "publication_included_curves": len(included_curves),
            "curve_metadata_rows": len(curves),
            "normalized_completed_curves": len(normalized_curves),
            "normalized_curve_points": point_count,
            "axis_fit_rows": len(axes),
        },
        "doi_mapping": {
            "cases_with_doi": sum(1 for row in cases if row.get("source_doi")),
            "cases_without_doi": sum(1 for row in cases if not row.get("source_doi")),
        },
        "normalization_status_counts": dict(status_counts),
        "curve_reaction_type_counts": dict(reaction_counts),
        "missing_curve_metadata_records_in_points_jsonl": missing_curve_metadata,
        "excluded_from_release": [
            "original publication figures and screenshots",
            "source HTML and publisher asset folders",
            "figure captions from the original articles",
            "internal validation records and paper-level inconsistency cards",
            "local filesystem paths to extraction artifacts",
        ],
    }


def write_documentation() -> None:
    (OUT_DIR / "README.md").write_text(
        """# Extracted HER Polarization Curve Dataset

This Zenodo-ready package contains the primary hydrogen evolution reaction
(HER) polarization-curve dataset used in the manuscript "From Figure Pixels to
Quantitative Evidence: AI-Extracted Curves for Scientific Reasoning".

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
""",
        encoding="utf-8",
    )

    (OUT_DIR / "SCHEMA.md").write_text(
        """# Schema

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
""",
        encoding="utf-8",
    )

    rows = [
        ("source_publication_records.csv", "source_doi", "DOI of the source publication."),
        ("source_publication_records.csv", "source_doi_url", "DOI resolver URL."),
        ("panel_metadata.csv", "figure_id", "Normalized figure identifier."),
        ("panel_metadata.csv", "panel_id", "Normalized panel identifier."),
        ("curve_metadata.csv", "curve_uid", "Primary key for one extracted curve."),
        ("curve_metadata.csv", "catalyst_name", "Convenience catalyst/material name for the curve."),
        ("curve_metadata.csv", "condition_name", "Convenience experimental condition label."),
        ("curve_points_long.csv", "x_value", "Normalized x coordinate in native axis units."),
        ("curve_points_long.csv", "y_value", "Normalized y coordinate in native axis units."),
        ("curve_points_long.csv", "point_confidence", "Point-level extraction confidence, when available."),
        ("axis_fits.csv", "normalized_rmse", "Axis-fit RMSE normalized by the relevant plot-axis span."),
    ]
    write_csv(
        OUT_DIR / "DATA_DICTIONARY.csv",
        ({"table": table, "field": field, "description": description} for table, field, description in rows),
        ["table", "field", "description"],
    )

    (OUT_DIR / "LICENSE_NOTE.md").write_text(
        """# License and Source-Figure Note

This package is intended as a release of extracted numeric curve data and
machine-readable provenance metadata generated for the associated manuscript.
It does not include original publication figures, article HTML, screenshots,
or original figure captions.

The original publications remain under the licenses and copyright terms of
their respective publishers and authors. The DOI fields are included only for
source attribution and traceability.
""",
        encoding="utf-8",
    )


def write_checksums() -> None:
    lines: list[str] = []
    for path in sorted(OUT_DIR.iterdir()):
        if path.name == "SHA256SUMS.txt" or not path.is_file():
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        lines.append(f"{digest}  {path.name}")
    (OUT_DIR / "SHA256SUMS.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_zip() -> None:
    if ZIP_PATH.exists():
        ZIP_PATH.unlink()
    with zipfile.ZipFile(ZIP_PATH, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(OUT_DIR.iterdir()):
            if path.is_file():
                archive.write(path, arcname=f"{OUT_DIR.name}/{path.name}")


def main() -> None:
    summary = build_release()
    print(json.dumps(summary["records"], indent=2))
    print(f"Wrote {OUT_DIR}")
    print(f"Wrote {ZIP_PATH}")


if __name__ == "__main__":
    main()
