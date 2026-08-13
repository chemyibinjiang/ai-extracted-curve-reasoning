"""Reproduce the archived 2026-05-09 staged benchmark pixel metrics.

The archived v2 evaluator source was not included in the benchmark zips. This
script reconstructs its distance and coverage calculations from the preserved
anchors, extracted points, hidden curves, and curve assignments. It is a
read-only audit: no benchmark record is modified.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


HERE = Path(__file__).resolve().parent
BENCHMARK_ROOT = HERE.parent
CASE_SET = "focused_curve_extraction_set_v4_1_fixed"
DEFAULT_CASE_ROOT = BENCHMARK_ROOT / "benchmark_cases" / CASE_SET
DEFAULT_TRUTH_ROOT = BENCHMARK_ROOT / "peeragent_ground_truth" / CASE_SET
DEFAULT_ARCHIVED_EVAL_ROOT = HERE / "archived_staged_v2_evaluation"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def first_response(case_dir: Path, stage: str) -> Path:
    matches = sorted((case_dir / stage / "panel_runs").glob("*/response.json"))
    if len(matches) != 1:
        raise RuntimeError(
            f"Expected one {stage} response for {case_dir.name}, found {len(matches)}"
        )
    return matches[0]


def project_axis(values: pd.Series, fit: dict) -> np.ndarray:
    numeric = values.to_numpy(dtype=float)
    if fit["chosen_model"] == "log10":
        numeric = np.log10(numeric)
    parameters = fit["fit_parameters"]
    return parameters["slope"] * numeric + parameters["intercept"]


def reconstruct_axis_fit(anchor: dict, axis: str) -> dict:
    """Rebuild the archived least-squares axis fit from preserved tick anchors."""
    mapping = anchor["axis_mapping"][axis]
    chosen_model = mapping["chosen_model"]
    coordinate_key = "pixel_x" if axis == "x" else "pixel_y"
    points = [point for point in anchor["anchor_points"] if point["axis"] == axis]
    if len(points) < 2:
        raise RuntimeError(f"Need at least two {axis}-axis anchors, found {len(points)}")

    values = np.asarray([float(point["tick_value"]) for point in points], dtype=float)
    if chosen_model == "log10":
        if np.any(values <= 0):
            raise RuntimeError(f"Log10 {axis}-axis contains non-positive tick values")
        values = np.log10(values)
    pixels = np.asarray([float(point[coordinate_key]) for point in points], dtype=float)
    slope, intercept = np.polyfit(values, pixels, 1)
    return {
        "chosen_model": chosen_model,
        "fit_parameters": {"slope": float(slope), "intercept": float(intercept)},
    }


def load_axis_fit(anchor_path: Path, anchor: dict) -> dict:
    """Load the original temporary fit when available, otherwise reconstruct it."""
    fit_path = anchor_path.parent / "tmp" / "axis_fit_output.json"
    if fit_path.exists():
        return read_json(fit_path)
    return {
        "x": reconstruct_axis_fit(anchor, "x"),
        "y": reconstruct_axis_fit(anchor, "y"),
    }


def distances_to_polyline(points: np.ndarray, polyline: np.ndarray) -> np.ndarray:
    starts = polyline[:-1]
    ends = polyline[1:]
    segments = ends - starts
    squared_lengths = np.sum(segments * segments, axis=1)
    offsets = points[:, None, :] - starts[None, :, :]
    fractions = np.divide(
        np.sum(offsets * segments[None, :, :], axis=2),
        squared_lengths[None, :],
        out=np.zeros((len(points), len(starts))),
        where=squared_lengths[None, :] > 0,
    )
    fractions = np.clip(fractions, 0.0, 1.0)
    closest = starts[None, :, :] + fractions[:, :, None] * segments[None, :, :]
    return np.sqrt(np.sum((points[:, None, :] - closest) ** 2, axis=2)).min(axis=1)


def x_coverage(points: np.ndarray, truth: np.ndarray) -> float:
    shared_span = max(
        0.0,
        min(points[:, 0].max(), truth[:, 0].max())
        - max(points[:, 0].min(), truth[:, 0].min()),
    )
    truth_span = truth[:, 0].max() - truth[:, 0].min()
    return float(shared_span / truth_span) if truth_span > 0 else 1.0


def inferred_verdict(median_px: float, p95_px: float, coverage: float) -> str:
    if median_px > 2.0 or p95_px > 10.0 or coverage < 0.50:
        return "fail"
    if coverage < 0.75:
        return "warn"
    return "pass"


def reproduce(
    case_root: Path, truth_root: Path, archived_eval_root: Path
) -> tuple[pd.DataFrame, pd.DataFrame]:
    archived = pd.read_csv(
        archived_eval_root / "curve_answer_eval_pixel_distance_v2.csv"
    )
    truth_index = pd.read_csv(truth_root / "case_truth_index.csv").set_index("case_id")
    regenerated: list[dict] = []

    for case_id, archived_case in archived.groupby("case_id", sort=False):
        case_dir = case_root / case_id
        anchor_path = first_response(case_dir, "codex_panel_anchoring")
        extraction_path = first_response(case_dir, "codex_panel_curve_extraction")
        anchor = read_json(anchor_path)
        extraction = read_json(extraction_path)
        axis_fit = load_axis_fit(anchor_path, anchor)

        index_row = truth_index.loc[case_id]
        metadata = read_json(truth_root / index_row["metadata_file"])
        truth_table = pd.read_csv(truth_root / index_row["raw_data_file"])
        extracted_curves = {curve["curve_id"]: curve for curve in extraction["curves"]}
        crop_left, crop_top = anchor.get("crop_box_original", [0, 0, 0, 0])[:2]

        for archived_row in archived_case.itertuples(index=False):
            curve = extracted_curves[archived_row.curve_id]
            truth_rows = truth_table[
                truth_table[metadata["series_column"]].astype(str)
                == str(archived_row.matched_series)
            ]
            if truth_rows.empty:
                raise RuntimeError(
                    f"Missing truth series {archived_row.matched_series!r} for {case_id}"
                )

            truth_x = project_axis(truth_rows[metadata["x_column"]], axis_fit["x"])
            truth_y = project_axis(truth_rows[metadata["y_column"]], axis_fit["y"])
            if archived_row.axis_coord_kind == "original":
                truth_x = truth_x - crop_left
                truth_y = truth_y - crop_top
            truth_points = np.column_stack((truth_x, truth_y))
            extracted_points = np.asarray(
                [
                    [point["pixel_x"], point["pixel_y"]]
                    for point in curve["sampled_points"]
                ],
                dtype=float,
            )
            distances = distances_to_polyline(extracted_points, truth_points)
            coverage = x_coverage(extracted_points, truth_points)
            median_px = float(np.median(distances))
            p95_px = float(np.quantile(distances, 0.95))
            mean_px = float(np.mean(distances))
            regenerated.append(
                {
                    "case_id": case_id,
                    "curve_id": archived_row.curve_id,
                    "median_dist_px": median_px,
                    "p95_dist_px": p95_px,
                    "mean_dist_px": mean_px,
                    "x_coverage_px": coverage,
                    "verdict": inferred_verdict(median_px, p95_px, coverage),
                }
            )

    regenerated_frame = pd.DataFrame(regenerated)
    compared = archived.merge(
        regenerated_frame,
        on=["case_id", "curve_id"],
        how="outer",
        suffixes=("_archived", "_replayed"),
        validate="one_to_one",
    )
    return regenerated_frame, compared


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-root", type=Path, default=DEFAULT_CASE_ROOT)
    parser.add_argument("--truth-root", type=Path, default=DEFAULT_TRUTH_ROOT)
    parser.add_argument(
        "--archived-eval-root", type=Path, default=DEFAULT_ARCHIVED_EVAL_ROOT
    )
    parser.add_argument("--tolerance", type=float, default=1e-10)
    parser.add_argument("--write-regenerated", type=Path)
    args = parser.parse_args()

    regenerated, compared = reproduce(
        args.case_root.resolve(),
        args.truth_root.resolve(),
        args.archived_eval_root.resolve(),
    )
    metric_columns = ("median_dist_px", "p95_dist_px", "mean_dist_px", "x_coverage_px")
    maximum_differences = {}
    for column in metric_columns:
        difference = (
            compared[f"{column}_replayed"] - compared[f"{column}_archived"]
        ).abs()
        maximum_differences[column] = float(difference.max())

    verdict_match = bool(
        (compared["verdict_archived"] == compared["verdict_replayed"]).all()
    )
    passed = verdict_match and all(
        value <= args.tolerance for value in maximum_differences.values()
    )
    summary = {
        "curves_replayed": int(len(regenerated)),
        "maximum_absolute_differences": maximum_differences,
        "verdicts_match": verdict_match,
        "tolerance": args.tolerance,
        "audit_pass": passed,
        "archived_aggregate": {
            "median_per_curve_median_distance_px": float(
                compared["median_dist_px_archived"].median()
            ),
            "p90_per_curve_median_distance_px": float(
                compared["median_dist_px_archived"].quantile(0.90)
            ),
            "median_per_curve_p95_distance_px": float(
                compared["p95_dist_px_archived"].median()
            ),
            "median_x_coverage": float(compared["x_coverage_px_archived"].median()),
        },
    }
    print(json.dumps(summary, indent=2))
    if args.write_regenerated:
        args.write_regenerated.parent.mkdir(parents=True, exist_ok=True)
        regenerated.to_csv(args.write_regenerated, index=False)
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
