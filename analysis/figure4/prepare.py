"""Rebuild the Figure 4 cohort from all released extracted curve coordinates."""
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from branch_preparation import prepare_curve

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DATASET = ROOT / "data_literature/zenodo_extracted_curve_dataset_v1"


def read(path):
    return pd.read_csv(path, float_precision="round_trip", low_memory=False)


def prepare(output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    metadata = read(DATASET / "curve_metadata.csv")
    points = read(DATASET / "curve_points_long.csv")
    sources = read(DATASET / "source_publication_records.csv")
    assert metadata.curve_uid.is_unique and sources.source_record_id.is_unique
    assert not points.duplicated(["curve_uid", "point_index"]).any()
    assert set(metadata.curve_uid) == set(points.curve_uid)
    assert len(metadata) == 4211 and len(points) == 132314
    assert metadata.publication_included_curve.eq("yes").all()
    assert metadata.publication_analysis_bucket.eq("primary_main_HER").all()
    assert metadata.normalization_status_current.eq("completed").all()

    # The publication-record table retains canonical source order. Keep the first
    # included source record for each DOI, not whichever has the best fit.
    sources = sources[sources.included_in_quantitative_dataset.eq("yes")].copy()
    sources["paper_key"] = sources.source_doi.fillna(sources.source_record_id).str.strip().str.lower()
    first = sources.drop_duplicates("paper_key").set_index("paper_key").source_record_id
    sources["retained_source_record_id"] = sources.paper_key.map(first)
    source_map = sources.set_index("source_record_id")
    groups = {uid: group.sort_values("point_index") for uid, group in points.groupby("curve_uid")}
    ledger, selected = [], []
    for _, curve in metadata.iterrows():
        group = groups[curve.curve_uid]
        assert len(group) == curve.normalized_point_count_current
        record = {"native_points": group[["x_value", "y_value"]].rename(
            columns={"x_value": "x", "y_value": "y"}).to_dict("records")}
        result = prepare_curve(curve, record)
        row, j, eta = result["row"], result["j"], result["y"]
        source = source_map.loc[curve.source_record_id]
        row.update(source_record_id=curve.source_record_id, paper_key=source.paper_key,
                   source_doi=curve.source_doi, retained_source_record_id=source.retained_source_record_id)
        row["current_reaches_20_mA_cm2"] = bool(len(j) and j.max() >= 20)
        row["retained_source_record"] = curve.source_record_id == source.retained_source_record_id
        gates = [
            (row["linear_axes"], "nonlinear_axes"),
            (row["current_density_basis"], "unsupported_current_density_axes"),
            (row["reference_axis_ready"], "unsupported_potential_reference"),
            (row["fit_range_ok"], "insufficient_points_or_range"),
            (row["current_reaches_20_mA_cm2"], "current_below_20_mA_cm2"),
            (row["retained_source_record"], "duplicate_publication_record"),
        ]
        row["selection_reason"] = next((reason for passes, reason in gates if not passes), "included")
        row["included_figure4"] = row["selection_reason"] == "included"
        ledger.append(row)
        if row["included_figure4"]:
            selected.append(pd.DataFrame(dict(curve_uid=curve.curve_uid, paper_key=row["paper_key"],
                native_index=np.arange(len(j)), j=j, eta_mV=eta)))

    ledger = pd.DataFrame(ledger)
    columns = ["curve_uid", "source_record_id", "source_doi", "paper_key", "figure_id", "panel_id",
        "curve_label", "condition_label", "native_point_count", "fit_point_count", "axis_orientation",
        "linear_axes", "current_density_basis", "reference_basis", "reference_axis_ready",
        "potential_unit_mode", "current_unit_mode", "eta_rule", "selected_current_sign",
        "selected_current_sign_rule", "selected_current_sign_raw_point_count", "j_min_mA", "j_max_mA",
        "y_min_mV", "y_max_mV", "fit_range_ok", "canonical_fit_eligible", "current_reaches_20_mA_cm2",
        "retained_source_record", "retained_source_record_id", "included_figure4", "selection_reason"]
    ledger[columns].to_csv(output / "COHORT_SELECTION.csv", index=False)
    rebuilt = pd.concat(selected, ignore_index=True)
    keys = ["curve_uid", "native_index"]
    rebuilt = rebuilt.sort_values(keys).reset_index(drop=True)
    rebuilt.to_csv(output / "PREPARED_POINTS.csv", index=False)
    cohort = ledger[ledger.included_figure4]
    cohort[read(HERE / "inputs/CURVES.csv").columns].to_csv(output / "PREPARED_CURVES.csv", index=False)
    report = dict(extracted_curves=len(metadata), extracted_points=len(points),
        fitting_curves=len(cohort), fitting_papers=int(cohort.paper_key.nunique()), fitting_points=len(rebuilt),
        selection_counts={key: int(value) for key, value in ledger.selection_reason.value_counts().items()},
        sources=[dict(path=path.relative_to(ROOT).as_posix(), sha256=hashlib.sha256(path.read_bytes()).hexdigest())
            for path in [DATASET / name for name in ("curve_metadata.csv", "curve_points_long.csv", "source_publication_records.csv")]])
    (output / "PREPARATION_CHECKS.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    expected = read(HERE / "inputs/POINTS.csv").sort_values(keys).reset_index(drop=True)
    pd.testing.assert_frame_equal(rebuilt, expected, check_dtype=False, check_exact=False, rtol=1e-12, atol=1e-10)
    expected_curves = read(HERE / "inputs/CURVES.csv").sort_values("curve_uid").reset_index(drop=True)
    actual_curves = cohort[expected_curves.columns].sort_values("curve_uid").reset_index(drop=True)
    labels = ["curve_label", "condition_label"]
    label_differences = []
    for column in labels:
        different = actual_curves[column].fillna("").ne(expected_curves[column].fillna(""))
        for index in np.flatnonzero(different):
            label_differences.append(dict(curve_uid=actual_curves.at[index, "curve_uid"], field=column,
                extracted_label=actual_curves.at[index, column], fit_table_label=expected_curves.at[index, column]))
    pd.DataFrame(label_differences, columns=["curve_uid", "field", "extracted_label", "fit_table_label"]).to_csv(
        output / "LABEL_DIFFERENCES.csv", index=False)
    pd.testing.assert_frame_equal(actual_curves.drop(columns=labels), expected_curves.drop(columns=labels),
        check_dtype=False, check_exact=False, rtol=1e-12, atol=1e-10)
    reference_ledger = HERE / "reference/COHORT_SELECTION.csv"
    if reference_ledger.exists():
        pd.testing.assert_frame_equal(read(output / "COHORT_SELECTION.csv"), read(reference_ledger),
            check_dtype=False, check_exact=False, rtol=1e-12, atol=1e-10)
    report["label_difference_records"] = len(label_differences)
    report["figure4_coordinates_and_selection_reproduced"] = True
    (output / "PREPARATION_CHECKS.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report
