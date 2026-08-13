#!/usr/bin/env python3
"""Build the SI figure for the staged-versus-single-agent benchmark audit."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import matplotlib.image as mpimg
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import tifffile
from matplotlib.lines import Line2D


HERE = Path(__file__).resolve().parent
BENCHMARK_ROOT = HERE.parent
CASE_SET = "focused_curve_extraction_set_v4_1_fixed"
TRUTH_ROOT = BENCHMARK_ROOT / "peeragent_ground_truth" / CASE_SET
STAGED_ROOT = BENCHMARK_ROOT / "benchmark_cases" / CASE_SET
RUN_ROOT = HERE / "runs" / "archived_staged_vs_single_agent_rescore_20260811"
MONOLITHIC_ROOT = (
    HERE / "runs" / "full_single_agent_20260811" / "monolithic" / "replicate_01"
)
EVALUATION_ROOT = RUN_ROOT / "evaluation" / "replicate_01"
OUTPUT_ROOT = HERE / "si_assets"

COLORS = ["#111111", "#2878B5", "#D93A32", "#2B9B4B", "#7A4DB3"]
STYLES = ["-", "--", "-.", ":", "-"]
FAMILY_COLORS = {
    "LSV": "#2F73B8",
    "kinetic_time_course": "#2E8B57",
    "UV_Vis": "#D99E1B",
    "Raman": "#7750B7",
    "XRD": "#D65321",
    "GC_trace": "#2A918C",
}
FAMILY_LABELS = {
    "LSV": "LSV",
    "kinetic_time_course": "Kinetic time course",
    "UV_Vis": "UV-Vis",
    "Raman": "Raman",
    "XRD": "XRD",
    "GC_trace": "GC trace",
}
AXIS_LABELS = {
    "LSV": ("Potential", "Response"),
    "kinetic_time_course": ("Time", "Response"),
    "UV_Vis": ("Wavelength (nm)", "Absorbance"),
    "Raman": ("Raman shift (cm$^{-1}$)", "Intensity"),
    "XRD": (r"2$\theta$ (degree)", "Intensity"),
    "GC_trace": ("Retention time", "Signal"),
}


def import_local(name: str, filename: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not import {filename}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


BENCHMARK = import_local("curve_benchmark_si", "run_benchmark.py")


def case_display(case_id: str) -> str:
    family, suffix = case_id.rsplit("_", 1)
    replacements = {
        "a_lsv": "A_LSV",
        "b_kinetic_time_course": "B_Kinetic_time_course",
        "c_uv_vis": "C_UV_Vis",
        "d_raman": "D_Raman",
        "e_xrd": "E_XRD",
        "f_gc_trace": "F_GC_trace",
    }
    return f"{replacements.get(family, family)}_{suffix}"


def truth_and_prediction(case_id: str, condition: str) -> tuple[str, list, list, list]:
    truth_index = BENCHMARK.truth_index_by_case(TRUTH_ROOT)
    family, truth_curves = BENCHMARK.load_truth_case(TRUTH_ROOT, truth_index, case_id)
    condition_root = MONOLITHIC_ROOT if condition == "monolithic" else STAGED_ROOT
    anchor, response = BENCHMARK.load_condition_record(
        condition, condition_root / case_id
    )
    predicted, _, _ = BENCHMARK.scientific_curves(anchor, response)
    all_truth_points = [point for curve in truth_curves for point in curve["points"]]
    x_values = [point[0] for point in all_truth_points]
    y_values = [point[1] for point in all_truth_points]
    bounds = (min(x_values), max(x_values), min(y_values), max(y_values))
    pair_results = [
        [
            BENCHMARK.pair_metrics(predicted_curve, truth_curve, bounds)
            for truth_curve in truth_curves
        ]
        for predicted_curve in predicted
    ]
    assignment = BENCHMARK.best_assignment(
        [[metrics["assignment_cost"] for metrics in row] for row in pair_results]
    )
    return family, truth_curves, predicted, assignment


def plot_curve_case(
    axis: plt.Axes,
    case_id: str,
    condition: str,
    show_ylabel: bool,
    show_legend: bool,
    only_series: str | None = None,
    legend_loc: str = "best",
) -> None:
    family, truth_curves, predicted, assignment = truth_and_prediction(
        case_id, condition
    )
    truth_indices = [
        index
        for index, curve in enumerate(truth_curves)
        if only_series is None or curve["series"] == only_series
    ]
    if not truth_indices:
        raise ValueError(f"Series {only_series!r} was not found for {case_id}")
    all_truth_points = [
        point for index in truth_indices for point in truth_curves[index]["points"]
    ]
    x_values = [point[0] for point in all_truth_points]
    y_values = [point[1] for point in all_truth_points]
    bounds = (min(x_values), max(x_values), min(y_values), max(y_values))
    y_span = bounds[3] - bounds[2]
    for truth_index in truth_indices:
        truth_curve = truth_curves[truth_index]
        points = truth_curve["points"]
        axis.plot(
            [point[0] for point in points],
            [point[1] for point in points],
            color=COLORS[truth_index % len(COLORS)],
            linestyle=STYLES[truth_index % len(STYLES)],
            linewidth=1.9,
            alpha=0.82,
        )
    for predicted_index, truth_index in assignment:
        if truth_index not in truth_indices:
            continue
        predicted_curve = predicted[predicted_index]
        truth_curve = truth_curves[truth_index]
        points = predicted_curve["points"]
        axis.scatter(
            [point[0] for point in points],
            [point[1] for point in points],
            s=17,
            facecolors="white",
            edgecolors=(
                "#2C7FB8"
                if only_series is not None
                else COLORS[truth_index % len(COLORS)]
            ),
            linewidths=0.9,
            zorder=5,
        )

    title = "Single agent" if condition == "monolithic" else "Staged workflow"
    axis.set_title(title, fontsize=10.0, fontweight="bold", pad=4)
    x_span = bounds[1] - bounds[0]
    axis.set_xlim(bounds[0] - 0.02 * x_span, bounds[1] + 0.02 * x_span)
    axis.set_ylim(bounds[2] - 0.05 * y_span, bounds[3] + 0.08 * y_span)
    axis.grid(color="#D9E1E8", linewidth=0.6, alpha=0.65)
    x_label, y_label = AXIS_LABELS[family]
    axis.set_xlabel(x_label, fontweight="bold", labelpad=2)
    if show_ylabel:
        axis.set_ylabel(y_label, fontweight="bold", labelpad=2)
    if show_legend:
        handles = [
            Line2D(
                [0],
                [0],
                color=COLORS[index % len(COLORS)],
                linestyle=STYLES[index % len(STYLES)],
                linewidth=1.9,
                label=("raw spectrum" if curve["series"] == "data" else curve["series"]),
            )
            for index, curve in enumerate(truth_curves)
            if index in truth_indices
        ]
        handles.append(
            Line2D(
                [0],
                [0],
                marker="o",
                markerfacecolor="white",
                markeredgecolor=("#2C7FB8" if only_series is not None else "#333333"),
                color="none",
                label=(
                    "returned raw points"
                    if only_series is not None
                    else "returned points"
                ),
            )
        )
        legend = axis.legend(
            handles=handles,
            fontsize=7.8,
            framealpha=1.0,
            facecolor="white",
            loc=legend_loc,
        )
        legend.set_zorder(20)


def axis_fit_from_anchor(anchor: dict, axis: str) -> tuple[float, float]:
    coordinate = "pixel_x" if axis == "x" else "pixel_y"
    points = [point for point in anchor["anchor_points"] if point["axis"] == axis]
    values = np.asarray([float(point["tick_value"]) for point in points])
    pixels = np.asarray([float(point[coordinate]) for point in points])
    slope, intercept = np.polyfit(values, pixels, 1)
    return float(slope), float(intercept)


def marker_overlay_data(condition: str) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    case_id = "a_lsv_06"
    truth_index = pd.read_csv(TRUTH_ROOT / "case_truth_index.csv").set_index("case_id")
    index_row = truth_index.loc[case_id]
    metadata = json.loads(
        (TRUTH_ROOT / index_row["metadata_file"]).read_text(encoding="utf-8")
    )
    truth_table = pd.read_csv(TRUTH_ROOT / index_row["raw_data_file"])
    truth_rows = truth_table[truth_table[metadata["series_column"]] == "M-1"]

    if condition == "staged":
        case_dir = STAGED_ROOT / case_id
        anchor_path = next(
            (case_dir / "codex_panel_anchoring" / "panel_runs").glob("*/response.json")
        )
        response_path = next(
            (case_dir / "codex_panel_curve_extraction" / "panel_runs").glob(
                "*/response.json"
            )
        )
        anchor = json.loads(anchor_path.read_text(encoding="utf-8"))
        response = json.loads(response_path.read_text(encoding="utf-8"))
        crop_offset = np.asarray(anchor["crop_box_original"][:2], dtype=float)
        x_slope, x_intercept = axis_fit_from_anchor(anchor, "x")
        y_slope, y_intercept = axis_fit_from_anchor(anchor, "y")
    else:
        run_dir = MONOLITHIC_ROOT / case_id / "monolithic_anchor_extract"
        response = json.loads((run_dir / "response.json").read_text(encoding="utf-8"))
        fit = json.loads(
            (run_dir / "tmp" / "axis_fit_output.json").read_text(encoding="utf-8")
        )
        x_slope = float(fit["x"]["fit_parameters"]["slope"])
        x_intercept = float(fit["x"]["fit_parameters"]["intercept"])
        y_slope = float(fit["y"]["fit_parameters"]["slope"])
        y_intercept = float(fit["y"]["fit_parameters"]["intercept"])
        crop_offset = np.asarray(response.get("crop_box_original", [0, 0])[:2])

    centers = np.column_stack(
        (
            x_slope * truth_rows[metadata["x_column"]].to_numpy() + x_intercept,
            y_slope * truth_rows[metadata["y_column"]].to_numpy() + y_intercept,
        )
    )
    curve = next(curve for curve in response["curves"] if curve["curve_label"] == "M-1")
    returned = np.asarray(
        [[point["pixel_x"], point["pixel_y"]] for point in curve["sampled_points"]],
        dtype=float,
    )
    returned += crop_offset
    image = mpimg.imread(STAGED_ROOT / case_id / f"{case_id}.png")
    return image, centers, returned


def plot_marker_zoom(axis: plt.Axes, condition: str) -> None:
    image, centers, returned = marker_overlay_data(condition)
    axis.imshow(image)
    axis.scatter(
        returned[:, 0],
        returned[:, 1],
        s=27,
        facecolors="none",
        edgecolors="#D81B60",
        linewidths=1.35,
        label="returned points",
        zorder=5,
    )
    axis.scatter(
        centers[:, 0],
        centers[:, 1],
        s=43,
        marker="+",
        color="#00A6A6",
        linewidths=1.7,
        label="marker centers",
        zorder=6,
    )
    axis.set_xlim(145, 460)
    axis.set_ylim(770, 610)
    axis.set_aspect("auto")
    axis.set_xticks([])
    axis.set_yticks([])
    title = "Single agent" if condition == "monolithic" else "Staged workflow"
    axis.set_title(title, fontsize=10.0, fontweight="bold", pad=4)
    for spine in axis.spines.values():
        spine.set_linewidth(0.9)


def plot_aggregate(axis: plt.Axes) -> None:
    case_metrics = pd.read_csv(EVALUATION_ROOT / "case_metrics.csv")
    pivot = case_metrics.pivot(index="case_id", columns="condition")
    stats = json.loads((EVALUATION_ROOT / "paired_statistics.json").read_text())
    for family, color in FAMILY_COLORS.items():
        case_ids = [
            case_id
            for case_id in pivot.index
            if pivot.loc[case_id, ("family", "monolithic")] == family
        ]
        axis.scatter(
            pivot.loc[case_ids, ("case_median_symmetric_scaled_distance", "staged")],
            pivot.loc[
                case_ids,
                ("case_median_symmetric_scaled_distance", "monolithic"),
            ],
            s=28,
            color=color,
            alpha=0.84,
            edgecolor="white",
            linewidth=0.45,
            label=FAMILY_LABELS[family],
        )
    limits = (8e-5, 0.5)
    axis.plot(limits, limits, color="#444444", linestyle="--", linewidth=1.1)
    axis.set_xscale("log")
    axis.set_yscale("log")
    axis.set_xlim(limits)
    axis.set_ylim(limits)
    axis.set_xlabel("Staged median scaled distance", fontweight="bold")
    axis.set_ylabel("Single-agent median scaled distance", fontweight="bold")
    axis.grid(which="both", color="#D9E1E8", linewidth=0.5, alpha=0.55)
    axis.legend(ncol=2, fontsize=6.8, frameon=False, loc="upper left")
    mono_median = float(
        case_metrics.loc[
            case_metrics["condition"] == "monolithic",
            "case_median_symmetric_scaled_distance",
        ].median()
    )
    staged_median = float(
        case_metrics.loc[
            case_metrics["condition"] == "staged",
            "case_median_symmetric_scaled_distance",
        ].median()
    )
    axis.text(
        0.97,
        0.04,
        "No detectable paired shift\n"
        f"single agent median = {mono_median:.5f}\n"
        f"staged median = {staged_median:.5f}\n"
        f"exact sign test p = {stats['exact_sign_test_two_sided_p']:.3f}",
        transform=axis.transAxes,
        ha="right",
        va="bottom",
        fontsize=7.5,
        bbox={"boxstyle": "round,pad=0.35", "facecolor": "white", "alpha": 0.9},
    )
    target = "c_uv_vis_05"
    x = float(pivot.loc[target, ("case_median_symmetric_scaled_distance", "staged")])
    y = float(
        pivot.loc[target, ("case_median_symmetric_scaled_distance", "monolithic")]
    )
    axis.annotate(
        case_display(target),
        xy=(x, y),
        xytext=(1.7e-3, 0.18),
        arrowprops={"arrowstyle": "->", "color": "#333333", "lw": 0.9},
        fontsize=7.2,
        fontweight="bold",
    )


def add_row_label(figure: plt.Figure, axis: plt.Axes, label: str, title: str) -> None:
    box = axis.get_position()
    figure.text(
        box.x0 - 0.025,
        box.y1 + 0.028,
        label,
        fontsize=13,
        fontweight="bold",
        va="bottom",
    )
    figure.text(
        box.x0,
        box.y1 + 0.028,
        title,
        fontsize=11.0,
        fontweight="bold",
        va="bottom",
    )


def main() -> None:
    plt.rcParams.update(
        {
            "font.family": "Times New Roman",
            "font.size": 9.2,
            "axes.linewidth": 0.9,
            "xtick.major.width": 0.8,
            "ytick.major.width": 0.8,
        }
    )
    figure = plt.figure(figsize=(7.35, 6.15), constrained_layout=False)
    grid = figure.add_gridspec(
        3,
        2,
        height_ratios=[1.08, 1.08, 0.75],
        hspace=0.78,
        wspace=0.23,
        left=0.10,
        right=0.985,
        top=0.94,
        bottom=0.065,
    )
    uv_axes = [figure.add_subplot(grid[0, 0]), figure.add_subplot(grid[0, 1])]
    plot_curve_case(uv_axes[0], "c_uv_vis_05", "monolithic", True, False)
    plot_curve_case(uv_axes[1], "c_uv_vis_05", "staged", False, True)

    raman_axes = [figure.add_subplot(grid[1, 0]), figure.add_subplot(grid[1, 1])]
    plot_curve_case(raman_axes[0], "d_raman_05", "monolithic", True, False)
    plot_curve_case(
        raman_axes[1],
        "d_raman_05",
        "staged",
        False,
        True,
        legend_loc="lower right",
    )

    marker_axes = [figure.add_subplot(grid[2, 0]), figure.add_subplot(grid[2, 1])]
    plot_marker_zoom(marker_axes[0], "monolithic")
    plot_marker_zoom(marker_axes[1], "staged")
    marker_axes[1].legend(
        loc="lower right", fontsize=7.8, framealpha=0.88, borderpad=0.4
    )

    add_row_label(
        figure,
        uv_axes[0],
        "A",
        f"{case_display('c_uv_vis_05')}: severe final-record error",
    )
    add_row_label(
        figure,
        raman_axes[0],
        "B",
        f"{case_display('d_raman_05')}: shape distortion versus truncated span",
    )
    add_row_label(
        figure,
        marker_axes[0],
        "C",
        f"{case_display('a_lsv_06')}: marker-center sampling audit (M-1 zoom)",
    )

    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    png = OUTPUT_ROOT / "Figure_S11_staged_vs_single_agent_ablation.png"
    tif = OUTPUT_ROOT / "Figure_S11_staged_vs_single_agent_ablation.tif"
    figure.savefig(png, dpi=300, facecolor="white")
    plt.close(figure)
    rendered = mpimg.imread(png)[..., :3]
    rendered_u8 = np.rint(rendered * 255).astype(np.uint8)
    tifffile.imwrite(
        tif,
        rendered_u8,
        resolution=(300, 300),
        resolutionunit="INCH",
        compression="deflate",
    )
    print(png)
    print(tif)


if __name__ == "__main__":
    main()
