from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[1]
OUT_STEM = BASE / "Figure_1_curve_family_examples"
BENCHMARK_ROOT = (
    ROOT
    / "data"
    / "benchmark_curve_extraction"
    / "peeragent_ground_truth"
    / "focused_curve_extraction_set_v4_1_fixed"
)

TEXT = "#111827"
AXIS = "#374151"
COLORS = ["#111827", "#2567d5", "#e53935", "#2f9b75", "#7d52d2", "#e0a21f"]
LINESTYLES = ["-", "--", "-.", ":", "-", "--"]
MARKERS = ["o", "s", "^", "D", "v", "P"]


CASES = [
    {
        "rel": "a_LSV/a_LSV_04",
        "title": "LSV / polarization curve",
        "xlabel": "E (V vs. RHE)",
        "ylabel": "j (mA cm⁻²)",
        "legend": False,
    },
    {
        "rel": "b_kinetic_time_course/b_kinetic_time_course_10",
        "title": "Kinetic time course",
        "xlabel": "Time (min)",
        "ylabel": "Response (a.u.)",
        "legend": False,
        "markers": True,
    },
    {
        "rel": "c_UV_Vis/c_UV_Vis_02",
        "title": "UV-Vis spectrum",
        "xlabel": "Wavelength (nm)",
        "ylabel": "Absorbance (a.u.)",
        "legend": False,
    },
    {
        "rel": "d_Raman/d_Raman_02",
        "title": "Raman spectrum",
        "xlabel": "Raman shift (cm⁻¹)",
        "ylabel": "Intensity (a.u.)",
        "legend": False,
    },
    {
        "rel": "e_XRD/e_XRD_10",
        "title": "XRD pattern",
        "xlabel": r"2$\theta$ (degree)",
        "ylabel": "Intensity (a.u.)",
        "legend": False,
    },
    {
        "rel": "f_GC_trace/f_GC_trace_06",
        "title": "GC trace",
        "xlabel": "Time (min)",
        "ylabel": "Signal (a.u.)",
        "legend": False,
    },
]


def clean_label(label: str) -> str:
    return label.replace("�", "u")


def load_case(rel: str) -> tuple[dict, dict[str, tuple[np.ndarray, np.ndarray]]]:
    stem = BENCHMARK_ROOT / rel
    metadata_path = stem.with_name(stem.name + "_metadata.json")
    raw_path = stem.with_name(stem.name + "_raw.csv")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    x_col = metadata["x_column"]
    y_col = metadata["y_column"]
    series_col = metadata.get("series_column", "series")

    grouped: dict[str, list[tuple[float, float]]] = defaultdict(list)
    with raw_path.open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            series = row.get(series_col) or metadata["curve_family"]
            grouped[clean_label(series)].append((float(row[x_col]), float(row[y_col])))

    arrays: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    for series, pairs in grouped.items():
        pairs = sorted(pairs, key=lambda item: item[0])
        x = np.array([p[0] for p in pairs], dtype=float)
        y = np.array([p[1] for p in pairs], dtype=float)
        arrays[series] = (x, y)
    return metadata, arrays


def style_axis(ax, title: str, xlabel: str, ylabel: str) -> None:
    ax.set_title(title, fontsize=16.5, fontweight="bold", color=TEXT, loc="left", pad=9)
    ax.set_xlabel(xlabel, fontsize=13.0, fontweight="bold", fontfamily=["Arial", "DejaVu Sans"], color=TEXT, labelpad=5)
    ax.set_ylabel(ylabel, fontsize=13.0, fontweight="bold", fontfamily=["Arial", "DejaVu Sans"], color=TEXT, labelpad=5)
    ax.grid(False)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    for side in ["left", "bottom"]:
        ax.spines[side].set_linewidth(1.05)
        ax.spines[side].set_color(AXIS)
    ax.tick_params(axis="both", which="both", length=0, labelbottom=False, labelleft=False)
    ax.set_facecolor("white")


def apply_limits(ax, all_x: list[np.ndarray], all_y: list[np.ndarray], ypad_frac: float = 0.10) -> None:
    x_min = min(float(np.nanmin(x)) for x in all_x)
    x_max = max(float(np.nanmax(x)) for x in all_x)
    y_min = min(float(np.nanmin(y)) for y in all_y)
    y_max = max(float(np.nanmax(y)) for y in all_y)
    x_pad = 0.045 * (x_max - x_min if x_max > x_min else 1.0)
    y_pad = ypad_frac * (y_max - y_min if y_max > y_min else 1.0)
    ax.set_xlim(x_min - x_pad, x_max + x_pad)
    ax.set_ylim(y_min - y_pad, y_max + y_pad)


def plot_case(ax, spec: dict) -> None:
    _, series_arrays = load_case(spec["rel"])
    all_x: list[np.ndarray] = []
    all_y: list[np.ndarray] = []

    for idx, (label, (x, y)) in enumerate(series_arrays.items()):
        color = COLORS[idx % len(COLORS)]
        linestyle = LINESTYLES[idx % len(LINESTYLES)]
        marker = MARKERS[idx % len(MARKERS)] if spec.get("markers") else None
        markevery = max(1, len(x) // 12)
        ax.plot(
            x,
            y,
            color=color,
            lw=1.55,
            ls=linestyle,
            marker=marker,
            markersize=3.1 if marker else 0,
            markerfacecolor="white" if marker else color,
            markeredgewidth=0.85,
            markevery=markevery,
            label=label,
            solid_capstyle="round",
        )
        all_x.append(x)
        all_y.append(y)

    apply_limits(ax, all_x, all_y, ypad_frac=0.13 if "Raman" in spec["title"] or "XRD" in spec["title"] else 0.10)
    style_axis(ax, spec["title"], spec["xlabel"], spec["ylabel"])
    if spec.get("legend"):
        ax.legend(frameon=False, fontsize=7.5, loc="best", handlelength=1.8)


def main() -> None:
    if not BENCHMARK_ROOT.exists():
        raise FileNotFoundError(f"Benchmark root not found: {BENCHMARK_ROOT}")

    plt.rcParams.update(
        {
            "font.family": "Arial",
            "axes.titleweight": "bold",
            "mathtext.fontset": "custom",
            "mathtext.rm": "Arial",
            "mathtext.it": "Arial:italic",
            "mathtext.bf": "Arial:bold",
            "mathtext.default": "regular",
            "svg.fonttype": "none",
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )

    fig, axes = plt.subplots(2, 3, figsize=(10.2, 5.95), dpi=300)
    fig.patch.set_facecolor("white")

    for ax, spec in zip(axes.flat, CASES):
        plot_case(ax, spec)

    fig.subplots_adjust(left=0.080, right=0.985, bottom=0.120, top=0.915, wspace=0.38, hspace=0.58)

    for suffix, kwargs in {
        ".png": {"dpi": 600},
        ".tif": {"dpi": 600, "pil_kwargs": {"compression": "tiff_lzw"}},
        ".pdf": {},
        ".svg": {},
    }.items():
        fig.savefig(OUT_STEM.with_suffix(suffix), bbox_inches="tight", facecolor="white", **kwargs)

    plt.close(fig)
    for suffix in (".png", ".tif", ".pdf", ".svg"):
        print(f"Wrote {OUT_STEM.with_suffix(suffix).name}")


if __name__ == "__main__":
    main()
