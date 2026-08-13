#!/usr/bin/env python3
"""Audit returned curves against hidden answers on their shared x-domain.

This audit complements the full-extent symmetric-distance evaluator. It keeps
x-coverage as a separate quantity while measuring vertical disagreement only
where both the returned and answer curves exist. This prevents a flat omitted
tail from dominating the shape error.
"""

from __future__ import annotations

import argparse
import bisect
import csv
import importlib.util
import json
import math
import statistics
import sys
from pathlib import Path
from typing import Any, Iterable, Sequence


HERE = Path(__file__).resolve().parent
DEFAULT_CONFIG = HERE / "benchmark_config.json"
DEFAULT_CASE_SOURCE = HERE.parent / "benchmark_cases" / "focused_curve_extraction_set_v4_1_fixed"
DEFAULT_TRUTH_SOURCE = HERE.parent / "peeragent_ground_truth" / "focused_curve_extraction_set_v4_1_fixed"


def load_benchmark_module() -> Any:
    path = HERE / "run_benchmark.py"
    spec = importlib.util.spec_from_file_location("curve_benchmark", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not import benchmark evaluator from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


BENCHMARK = load_benchmark_module()


def percentile(values: Sequence[float], probability: float) -> float:
    finite = sorted(value for value in values if math.isfinite(value))
    if not finite:
        return math.nan
    if len(finite) == 1:
        return finite[0]
    position = probability * (len(finite) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return finite[lower]
    weight = position - lower
    return finite[lower] * (1.0 - weight) + finite[upper] * weight


def collapse_x(points: Iterable[tuple[float, float]]) -> list[tuple[float, float]]:
    grouped: dict[float, list[float]] = {}
    for x_value, y_value in points:
        if math.isfinite(x_value) and math.isfinite(y_value):
            grouped.setdefault(float(x_value), []).append(float(y_value))
    return sorted(
        (x_value, statistics.median(y_values))
        for x_value, y_values in grouped.items()
    )


def interpolate(points: Sequence[tuple[float, float]], x_value: float) -> float:
    if not points:
        raise ValueError("Cannot interpolate an empty curve.")
    xs = [point[0] for point in points]
    index = bisect.bisect_left(xs, x_value)
    if index <= 0:
        return points[0][1]
    if index >= len(points):
        return points[-1][1]
    x_left, y_left = points[index - 1]
    x_right, y_right = points[index]
    if x_right == x_left:
        return statistics.fmean((y_left, y_right))
    fraction = (x_value - x_left) / (x_right - x_left)
    return y_left + fraction * (y_right - y_left)


def interpolated_metrics(
    predicted_points: Sequence[tuple[float, float]],
    truth_points: Sequence[tuple[float, float]],
    case_y_span: float,
    grid_points: int,
) -> dict[str, float | int]:
    predicted = collapse_x(predicted_points)
    truth = collapse_x(truth_points)
    if len(predicted) < 2 or len(truth) < 2:
        raise ValueError("At least two distinct x coordinates are required per curve.")

    truth_x_min, truth_x_max = truth[0][0], truth[-1][0]
    predicted_x_min, predicted_x_max = predicted[0][0], predicted[-1][0]
    shared_x_min = max(truth_x_min, predicted_x_min)
    shared_x_max = min(truth_x_max, predicted_x_max)
    if shared_x_max <= shared_x_min:
        raise ValueError("Returned and answer curves have no shared x-domain.")

    truth_x_span = max(truth_x_max - truth_x_min, 1e-12)
    shared_coverage = (shared_x_max - shared_x_min) / truth_x_span
    sample_count = max(3, int(grid_points))
    step = (shared_x_max - shared_x_min) / (sample_count - 1)
    residuals = []
    absolute_residuals = []
    denominator = max(abs(case_y_span), 1e-12)
    for index in range(sample_count):
        x_value = shared_x_min + step * index
        residual = (
            interpolate(predicted, x_value) - interpolate(truth, x_value)
        ) / denominator
        residuals.append(residual)
        absolute_residuals.append(abs(residual))

    return {
        "shared_x_min": shared_x_min,
        "shared_x_max": shared_x_max,
        "shared_x_coverage": shared_coverage,
        "interpolation_grid_points": sample_count,
        "signed_bias_yspan": statistics.fmean(residuals),
        "mae_yspan": statistics.fmean(absolute_residuals),
        "rmse_yspan": math.sqrt(statistics.fmean(value * value for value in residuals)),
        "median_abs_yspan": statistics.median(absolute_residuals),
        "p95_abs_yspan": percentile(absolute_residuals, 0.95),
        "max_abs_yspan": max(absolute_residuals),
    }


def returned_point_metrics(
    predicted_points: Sequence[tuple[float, float]],
    truth_points: Sequence[tuple[float, float]],
    case_y_span: float,
) -> dict[str, float | int]:
    """Measure returned-point residuals without inventing segments between them."""
    predicted = collapse_x(predicted_points)
    truth = collapse_x(truth_points)
    if len(predicted) < 1 or len(truth) < 2:
        raise ValueError("Returned-point comparison requires points and a truth curve.")

    truth_x_min, truth_x_max = truth[0][0], truth[-1][0]
    in_domain = [
        (x_value, y_value)
        for x_value, y_value in predicted
        if truth_x_min <= x_value <= truth_x_max
    ]
    if not in_domain:
        raise ValueError("No returned points lie inside the answer x-domain.")

    denominator = max(abs(case_y_span), 1e-12)
    residuals = [
        (y_value - interpolate(truth, x_value)) / denominator
        for x_value, y_value in in_domain
    ]
    absolute_residuals = [abs(value) for value in residuals]
    return {
        "returned_points_in_truth_domain": len(in_domain),
        "returned_points_in_truth_domain_fraction": len(in_domain) / len(predicted),
        "returned_point_signed_bias_yspan": statistics.fmean(residuals),
        "returned_point_mae_yspan": statistics.fmean(absolute_residuals),
        "returned_point_rmse_yspan": math.sqrt(
            statistics.fmean(value * value for value in residuals)
        ),
        "returned_point_p95_abs_yspan": percentile(absolute_residuals, 0.95),
        "returned_point_max_abs_yspan": max(absolute_residuals),
    }


def returned_point_orthogonal_metrics(
    predicted_points: Sequence[tuple[float, float]],
    truth_points: Sequence[tuple[float, float]],
    bounds: tuple[float, float, float, float],
) -> dict[str, float]:
    """Measure one-way 2D distance from returned points to the answer polyline."""
    predicted_scaled = BENCHMARK.scaled_points(predicted_points, bounds)
    truth_scaled = BENCHMARK.scaled_points(truth_points, bounds)
    distances = BENCHMARK.distances_to_polyline(predicted_scaled, truth_scaled)
    finite = [value for value in distances if math.isfinite(value)]
    if not finite:
        raise ValueError("No finite returned-point distances were available.")
    return {
        "returned_point_orthogonal_median": statistics.median(finite),
        "returned_point_orthogonal_mean": statistics.fmean(finite),
        "returned_point_orthogonal_p95": percentile(finite, 0.95),
        "returned_point_orthogonal_max": max(finite),
    }


def write_csv(path: Path, rows: Sequence[dict[str, Any]], columns: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(columns), extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def condition_rows(
    condition: str,
    condition_root: Path,
    truth_root: Path,
    truth_index: dict[str, dict[str, str]],
    case_ids: Sequence[str],
    config: dict[str, Any],
    grid_points: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    curve_rows: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for case_id in case_ids:
        try:
            family, truth_curves = BENCHMARK.load_truth_case(
                truth_root, truth_index, case_id
            )
            anchor_response, curve_response = BENCHMARK.load_condition_record(
                condition, condition_root / case_id
            )
            predicted_curves, _, _ = BENCHMARK.scientific_curves(
                anchor_response, curve_response
            )
            display_models = BENCHMARK.truth_display_models(
                config.get("truth_display_axis_models", {}), case_id
            )
            for curve in predicted_curves:
                curve["points"] = BENCHMARK.display_points(
                    curve["points"], *display_models
                )
            for curve in truth_curves:
                curve["points"] = BENCHMARK.display_points(
                    curve["points"], *display_models
                )

            all_truth_points = [
                point for curve in truth_curves for point in curve["points"]
            ]
            y_values = [point[1] for point in all_truth_points]
            x_values = [point[0] for point in all_truth_points]
            bounds = (min(x_values), max(x_values), min(y_values), max(y_values))
            case_y_span = bounds[3] - bounds[2]
            pair_results = [
                [
                    BENCHMARK.pair_metrics(predicted, truth, bounds)
                    for truth in truth_curves
                ]
                for predicted in predicted_curves
            ]
            assignment = BENCHMARK.best_assignment(
                [
                    [metrics["assignment_cost"] for metrics in row]
                    for row in pair_results
                ]
            )
            for predicted_index, truth_index_value in assignment:
                predicted = predicted_curves[predicted_index]
                truth = truth_curves[truth_index_value]
                metrics = interpolated_metrics(
                    predicted["points"], truth["points"], case_y_span, grid_points
                )
                point_metrics = returned_point_metrics(
                    predicted["points"], truth["points"], case_y_span
                )
                orthogonal_metrics = returned_point_orthogonal_metrics(
                    predicted["points"], truth["points"], bounds
                )
                curve_rows.append(
                    {
                        "condition": condition,
                        "case_id": case_id,
                        "family": family,
                        "predicted_curve_id": predicted.get("curve_id", ""),
                        "predicted_label": predicted.get("curve_label", ""),
                        "truth_label": truth.get("series", ""),
                        "identity_exact": (
                            BENCHMARK.normalize_label(str(predicted.get("curve_label", "")))
                            == BENCHMARK.normalize_label(str(truth.get("series", "")))
                        ),
                        "n_predicted_points": len(predicted["points"]),
                        "n_truth_points": len(truth["points"]),
                        **metrics,
                        **point_metrics,
                        **orthogonal_metrics,
                    }
                )
        except Exception as exc:  # noqa: BLE001
            errors.append(
                {
                    "condition": condition,
                    "case_id": case_id,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
    return curve_rows, errors


def summarize_cases(curve_rows: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    keys = sorted({(row["condition"], row["case_id"]) for row in curve_rows})
    rows = []
    for condition, case_id in keys:
        subset = [
            row
            for row in curve_rows
            if row["condition"] == condition and row["case_id"] == case_id
        ]
        rmse_values = [float(row["rmse_yspan"]) for row in subset]
        point_rmse_values = [
            float(row["returned_point_rmse_yspan"]) for row in subset
        ]
        orthogonal_p95_values = [
            float(row["returned_point_orthogonal_p95"]) for row in subset
        ]
        coverage_values = [float(row["shared_x_coverage"]) for row in subset]
        rows.append(
            {
                "condition": condition,
                "case_id": case_id,
                "family": subset[0]["family"],
                "matched_curves": len(subset),
                "median_curve_rmse_yspan": statistics.median(rmse_values),
                "mean_curve_rmse_yspan": statistics.fmean(rmse_values),
                "max_curve_rmse_yspan": max(rmse_values),
                "median_returned_point_rmse_yspan": statistics.median(
                    point_rmse_values
                ),
                "max_returned_point_rmse_yspan": max(point_rmse_values),
                "median_returned_point_orthogonal_p95": statistics.median(
                    orthogonal_p95_values
                ),
                "max_returned_point_orthogonal_p95": max(orthogonal_p95_values),
                "median_shared_x_coverage": statistics.median(coverage_values),
                "minimum_shared_x_coverage": min(coverage_values),
            }
        )
    return rows


def paired_rows(case_rows: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    indexed = {
        (str(row["condition"]), str(row["case_id"])): row for row in case_rows
    }
    case_ids = sorted(
        {case_id for condition, case_id in indexed if condition == "monolithic"}
        & {case_id for condition, case_id in indexed if condition == "staged"}
    )
    rows = []
    for case_id in case_ids:
        monolithic = indexed[("monolithic", case_id)]
        staged = indexed[("staged", case_id)]
        mono_rmse = float(monolithic["median_curve_rmse_yspan"])
        staged_rmse = float(staged["median_curve_rmse_yspan"])
        mono_point_rmse = float(monolithic["median_returned_point_rmse_yspan"])
        staged_point_rmse = float(staged["median_returned_point_rmse_yspan"])
        mono_orthogonal_p95 = float(
            monolithic["median_returned_point_orthogonal_p95"]
        )
        staged_orthogonal_p95 = float(
            staged["median_returned_point_orthogonal_p95"]
        )
        rows.append(
            {
                "case_id": case_id,
                "family": monolithic["family"],
                "monolithic_median_curve_rmse_yspan": mono_rmse,
                "staged_median_curve_rmse_yspan": staged_rmse,
                "staged_minus_monolithic_rmse_yspan": staged_rmse - mono_rmse,
                "monolithic_median_returned_point_rmse_yspan": mono_point_rmse,
                "staged_median_returned_point_rmse_yspan": staged_point_rmse,
                "staged_minus_monolithic_returned_point_rmse_yspan": (
                    staged_point_rmse - mono_point_rmse
                ),
                "monolithic_median_returned_point_orthogonal_p95": (
                    mono_orthogonal_p95
                ),
                "staged_median_returned_point_orthogonal_p95": (
                    staged_orthogonal_p95
                ),
                "staged_minus_monolithic_returned_point_orthogonal_p95": (
                    staged_orthogonal_p95 - mono_orthogonal_p95
                ),
                "monolithic_minimum_shared_x_coverage": monolithic[
                    "minimum_shared_x_coverage"
                ],
                "staged_minimum_shared_x_coverage": staged[
                    "minimum_shared_x_coverage"
                ],
            }
        )
    return rows


def markdown_summary(
    case_rows: Sequence[dict[str, Any]],
    paired: Sequence[dict[str, Any]],
    errors: Sequence[dict[str, Any]],
) -> str:
    lines = [
        "# Shared-Domain Interpolation Audit",
        "",
        "Vertical errors are computed after interpolation on the x-domain shared",
        "by each returned curve and its assigned hidden answer. Errors are",
        "normalized by the complete answer-panel y-span. Coverage is reported",
        "separately and does not enter the interpolation error.",
        "",
        "## Condition Summary",
        "",
        "| condition | cases | median case RMSE | median minimum coverage |",
        "| --- | ---: | ---: | ---: |",
    ]
    for condition in ("monolithic", "staged"):
        subset = [row for row in case_rows if row["condition"] == condition]
        lines.append(
            f"| {condition} | {len(subset)} | "
            f"{statistics.median(float(row['median_curve_rmse_yspan']) for row in subset):.6f} | "
            f"{statistics.median(float(row['minimum_shared_x_coverage']) for row in subset):.3f} |"
        )

    differences = [
        float(row["staged_minus_monolithic_rmse_yspan"]) for row in paired
    ]
    lines.extend(
        [
            "",
            "## Practical Difference Counts",
            "",
            "A positive difference favors the monolithic single-agent result; a",
            "negative difference favors the staged workflow. Thresholds are fractions",
            "of the complete answer-panel y-span.",
            "",
            "| absolute RMSE difference | staged better | monolithic better |",
            "| ---: | ---: | ---: |",
        ]
    )
    for threshold in (0.005, 0.01, 0.02, 0.05):
        staged_better = sum(value < -threshold for value in differences)
        monolithic_better = sum(value > threshold for value in differences)
        lines.append(
            f"| > {threshold:.3f} | {staged_better} | {monolithic_better} |"
        )
    lines.extend(
        [
            "",
            f"Paired median staged-minus-monolithic RMSE difference: "
            f"{statistics.median(differences):.6f}.",
            f"Staged lower in {sum(value < 0 for value in differences)} cases; "
            f"monolithic lower in {sum(value > 0 for value in differences)} cases.",
        ]
    )

    lines.extend(
        [
            "",
            "## Returned-Point 2D Check",
            "",
            "For sharp XRD, GC, and Raman peaks, same-x vertical residuals can",
            "overstate small horizontal displacements. The following comparison uses",
            "the p95 normalized 2D distance from returned points to the answer",
            "polyline; x-coverage remains a separate requirement.",
            "",
            "| case | family | monolithic p95 | staged p95 | staged-minus-monolithic |",
            "| --- | --- | ---: | ---: | ---: |",
        ]
    )
    for row in sorted(
        paired,
        key=lambda item: abs(
            float(item["staged_minus_monolithic_returned_point_orthogonal_p95"])
        ),
        reverse=True,
    )[:10]:
        lines.append(
            f"| {row['case_id']} | {row['family']} | "
            f"{float(row['monolithic_median_returned_point_orthogonal_p95']):.6f} | "
            f"{float(row['staged_median_returned_point_orthogonal_p95']):.6f} | "
            f"{float(row['staged_minus_monolithic_returned_point_orthogonal_p95']):.6f} |"
        )

    lines.extend(
        [
            "",
            "## Largest Staged Advantages",
            "",
            "| case | family | monolithic RMSE | staged RMSE | staged-minus-monolithic |",
            "| --- | --- | ---: | ---: | ---: |",
        ]
    )
    for row in sorted(
        paired, key=lambda item: float(item["staged_minus_monolithic_rmse_yspan"])
    )[:10]:
        lines.append(
            f"| {row['case_id']} | {row['family']} | "
            f"{float(row['monolithic_median_curve_rmse_yspan']):.6f} | "
            f"{float(row['staged_median_curve_rmse_yspan']):.6f} | "
            f"{float(row['staged_minus_monolithic_rmse_yspan']):.6f} |"
        )

    lines.extend(
        [
            "",
            "## Largest Monolithic Advantages",
            "",
            "| case | family | monolithic RMSE | staged RMSE | staged-minus-monolithic |",
            "| --- | --- | ---: | ---: | ---: |",
        ]
    )
    for row in sorted(
        paired,
        key=lambda item: float(item["staged_minus_monolithic_rmse_yspan"]),
        reverse=True,
    )[:10]:
        lines.append(
            f"| {row['case_id']} | {row['family']} | "
            f"{float(row['monolithic_median_curve_rmse_yspan']):.6f} | "
            f"{float(row['staged_median_curve_rmse_yspan']):.6f} | "
            f"{float(row['staged_minus_monolithic_rmse_yspan']):.6f} |"
        )

    lines.extend(["", "## Errors", ""])
    if not errors:
        lines.append("None.")
    else:
        for error in errors:
            lines.append(
                f"- `{error['condition']}` / `{error['case_id']}`: {error['error']}"
            )
    lines.append("")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--case-source", type=Path, default=DEFAULT_CASE_SOURCE)
    parser.add_argument("--truth-source", type=Path, default=DEFAULT_TRUTH_SOURCE)
    parser.add_argument("--monolithic-root", type=Path, required=True)
    parser.add_argument("--staged-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--grid-points", type=int, default=1001)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    config = BENCHMARK.load_config(args.config.resolve())
    case_ids = BENCHMARK.selected_case_ids(args.case_source.resolve(), [])
    truth_root = args.truth_source.resolve()
    truth_index = BENCHMARK.truth_index_by_case(truth_root)
    curve_rows: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for condition, condition_root in (
        ("monolithic", args.monolithic_root.resolve()),
        ("staged", args.staged_root.resolve()),
    ):
        rows, condition_errors = condition_rows(
            condition,
            condition_root,
            truth_root,
            truth_index,
            case_ids,
            config,
            args.grid_points,
        )
        curve_rows.extend(rows)
        errors.extend(condition_errors)

    case_rows = summarize_cases(curve_rows)
    paired = paired_rows(case_rows)
    output_dir = args.output_dir.resolve()
    write_csv(
        output_dir / "interpolated_curve_metrics.csv",
        curve_rows,
        [
            "condition",
            "case_id",
            "family",
            "predicted_curve_id",
            "predicted_label",
            "truth_label",
            "identity_exact",
            "n_predicted_points",
            "n_truth_points",
            "shared_x_min",
            "shared_x_max",
            "shared_x_coverage",
            "interpolation_grid_points",
            "signed_bias_yspan",
            "mae_yspan",
            "rmse_yspan",
            "median_abs_yspan",
            "p95_abs_yspan",
            "max_abs_yspan",
            "returned_points_in_truth_domain",
            "returned_points_in_truth_domain_fraction",
            "returned_point_signed_bias_yspan",
            "returned_point_mae_yspan",
            "returned_point_rmse_yspan",
            "returned_point_p95_abs_yspan",
            "returned_point_max_abs_yspan",
            "returned_point_orthogonal_median",
            "returned_point_orthogonal_mean",
            "returned_point_orthogonal_p95",
            "returned_point_orthogonal_max",
        ],
    )
    write_csv(
        output_dir / "interpolated_case_metrics.csv",
        case_rows,
        [
            "condition",
            "case_id",
            "family",
            "matched_curves",
            "median_curve_rmse_yspan",
            "mean_curve_rmse_yspan",
            "max_curve_rmse_yspan",
            "median_returned_point_rmse_yspan",
            "max_returned_point_rmse_yspan",
            "median_returned_point_orthogonal_p95",
            "max_returned_point_orthogonal_p95",
            "median_shared_x_coverage",
            "minimum_shared_x_coverage",
        ],
    )
    write_csv(
        output_dir / "paired_interpolated_case_differences.csv",
        paired,
        [
            "case_id",
            "family",
            "monolithic_median_curve_rmse_yspan",
            "staged_median_curve_rmse_yspan",
            "staged_minus_monolithic_rmse_yspan",
            "monolithic_median_returned_point_rmse_yspan",
            "staged_median_returned_point_rmse_yspan",
            "staged_minus_monolithic_returned_point_rmse_yspan",
            "monolithic_median_returned_point_orthogonal_p95",
            "staged_median_returned_point_orthogonal_p95",
            "staged_minus_monolithic_returned_point_orthogonal_p95",
            "monolithic_minimum_shared_x_coverage",
            "staged_minimum_shared_x_coverage",
        ],
    )
    (output_dir / "interpolation_audit_errors.json").write_text(
        json.dumps(errors, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (output_dir / "interpolation_audit_summary.md").write_text(
        markdown_summary(case_rows, paired, errors), encoding="utf-8"
    )
    print(f"Interpolation audit written to {output_dir}")


if __name__ == "__main__":
    main()
