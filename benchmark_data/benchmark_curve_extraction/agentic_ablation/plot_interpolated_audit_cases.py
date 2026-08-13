#!/usr/bin/env python3
"""Plot selected interpolation-audit cases against hidden answer curves."""

from __future__ import annotations

import argparse
import importlib.util
import statistics
import sys
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
from matplotlib.lines import Line2D


HERE = Path(__file__).resolve().parent
DEFAULT_TRUTH_SOURCE = HERE.parent / "peeragent_ground_truth" / "focused_curve_extraction_set_v4_1_fixed"


def import_local(name: str, filename: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not import {filename}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


BENCHMARK = import_local("curve_benchmark_plot", "run_benchmark.py")
INTERPOLATION = import_local(
    "curve_interpolation_audit", "audit_interpolated_curve_errors.py"
)


AXIS_LABELS = {
    "LSV": ("Potential", "Response"),
    "kinetic_time_course": ("Time", "Response"),
    "UV_Vis": ("Wavelength", "Absorbance"),
    "Raman": ("Raman shift", "Intensity"),
    "XRD": ("2theta", "Intensity"),
    "GC_trace": ("Retention time", "Signal"),
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--truth-source", type=Path, default=DEFAULT_TRUTH_SOURCE)
    parser.add_argument("--monolithic-root", type=Path, required=True)
    parser.add_argument("--staged-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--case", action="append", required=True)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    truth_root = args.truth_source.resolve()
    truth_index = BENCHMARK.truth_index_by_case(truth_root)
    roots = {
        "Single agent": ("monolithic", args.monolithic_root.resolve()),
        "Staged workflow": ("staged", args.staged_root.resolve()),
    }
    colors = ["#111111", "#2878B5", "#D93A32", "#2B9B4B", "#7A4DB3"]
    styles = ["-", "--", "-.", ":", "-"]
    plt.rcParams.update(
        {"font.family": "Arial", "font.size": 10, "axes.linewidth": 1.1}
    )
    figure, axes = plt.subplots(
        len(args.case), 2, figsize=(11.5, 3.35 * len(args.case)), constrained_layout=True
    )
    if len(args.case) == 1:
        axes = [axes]

    for row_index, case_id in enumerate(args.case):
        family, truth_curves = BENCHMARK.load_truth_case(
            truth_root, truth_index, case_id
        )
        all_truth_points = [
            point for curve in truth_curves for point in curve["points"]
        ]
        x_values = [point[0] for point in all_truth_points]
        y_values = [point[1] for point in all_truth_points]
        bounds = (min(x_values), max(x_values), min(y_values), max(y_values))
        case_y_span = bounds[3] - bounds[2]
        color_by_truth = {
            index: colors[index % len(colors)] for index in range(len(truth_curves))
        }

        for column_index, (title, (condition, condition_root)) in enumerate(
            roots.items()
        ):
            axis = axes[row_index][column_index]
            anchor, response = BENCHMARK.load_condition_record(
                condition, condition_root / case_id
            )
            predicted, _, _ = BENCHMARK.scientific_curves(anchor, response)
            pair_results = [
                [
                    BENCHMARK.pair_metrics(predicted_curve, truth_curve, bounds)
                    for truth_curve in truth_curves
                ]
                for predicted_curve in predicted
            ]
            assignment = BENCHMARK.best_assignment(
                [
                    [metrics["assignment_cost"] for metrics in row]
                    for row in pair_results
                ]
            )
            interpolation_rmse = []
            coverage = []

            for truth_curve_index, truth_curve in enumerate(truth_curves):
                points = truth_curve["points"]
                axis.plot(
                    [point[0] for point in points],
                    [point[1] for point in points],
                    color=color_by_truth[truth_curve_index],
                    linestyle=styles[truth_curve_index % len(styles)],
                    linewidth=2.2,
                    alpha=0.8,
                    label=truth_curve["series"],
                )

            for predicted_index, truth_curve_index in assignment:
                predicted_curve = predicted[predicted_index]
                truth_curve = truth_curves[truth_curve_index]
                metrics = INTERPOLATION.interpolated_metrics(
                    predicted_curve["points"],
                    truth_curve["points"],
                    case_y_span,
                    1001,
                )
                interpolation_rmse.append(float(metrics["rmse_yspan"]))
                coverage.append(float(metrics["shared_x_coverage"]))
                points = predicted_curve["points"]
                axis.scatter(
                    [point[0] for point in points],
                    [point[1] for point in points],
                    s=17,
                    facecolors="white",
                    edgecolors=color_by_truth[truth_curve_index],
                    linewidths=1.0,
                    zorder=5,
                )

            axis.set_title(
                f"{case_id}: {title}\n"
                f"median RMSE={statistics.median(interpolation_rmse):.4f}; "
                f"minimum coverage={min(coverage):.3f}",
                fontweight="bold",
                fontsize=11,
            )
            x_span = bounds[1] - bounds[0]
            y_span = bounds[3] - bounds[2]
            axis.set_xlim(bounds[0] - 0.02 * x_span, bounds[1] + 0.02 * x_span)
            axis.set_ylim(bounds[2] - 0.05 * y_span, bounds[3] + 0.08 * y_span)
            axis.grid(color="#D9E1E8", linewidth=0.7, alpha=0.7)
            x_label, y_label = AXIS_LABELS.get(family, ("x", "y"))
            axis.set_xlabel(x_label, fontweight="bold")
            if column_index == 0:
                axis.set_ylabel(y_label, fontweight="bold")
            if column_index == 1:
                handles = [
                    Line2D(
                        [0],
                        [0],
                        color=color_by_truth[index],
                        linestyle=styles[index % len(styles)],
                        linewidth=2.2,
                        label=curve["series"],
                    )
                    for index, curve in enumerate(truth_curves)
                ]
                handles.append(
                    Line2D(
                        [0],
                        [0],
                        marker="o",
                        markerfacecolor="white",
                        color="#333333",
                        linewidth=0,
                        label="returned points",
                    )
                )
                axis.legend(handles=handles, fontsize=8, framealpha=0.9)

    figure.suptitle(
        "Largest shared-domain interpolation differences",
        fontsize=16,
        fontweight="bold",
    )
    args.output.resolve().parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(args.output.resolve(), dpi=220, bbox_inches="tight", facecolor="white")
    print(args.output.resolve())


if __name__ == "__main__":
    main()
