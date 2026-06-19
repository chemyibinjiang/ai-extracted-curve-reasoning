from __future__ import annotations

import math
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
import numpy as np
import pandas as pd

import bv_ir_fitting_analysis as base
from publication_plot_style import apply_publication_style, save_publication_figure


OUT_DIR = Path(__file__).resolve().parent
DB_ROOT = OUT_DIR.parent.parent / "LSV_publication_database"
TABLE_DIR = DB_ROOT / "02_canonical_tables"

FIT_PATH = OUT_DIR / "bvir_shape_driver_curve_metrics.csv"
STRICT_FIT_PATH = OUT_DIR / "bv_ir_fit_results.csv"
RELAXED_FIT_PATH = OUT_DIR / "bv_ir_relaxed_fit_results.csv"
SHARE_PATH = OUT_DIR / "bv_ir_relaxed_unsaved_current_density_error_share_matrix.csv"
COUNT_PATH = OUT_DIR / "bv_ir_relaxed_unsaved_current_density_point_count_matrix.csv"
ROW_SUMMARY_PATH = OUT_DIR / "bv_ir_relaxed_unsaved_current_density_error_row_summary.csv"

R2_LABEL = "R\u00b2"
OHM_CM2 = "\u03a9 cm\u00b2"
MA_CM2 = "mA cm\u207b\u00b2"
UNIT_FONT = FontProperties(fname=r"C:\Windows\Fonts\segoeui.ttf")
CURRENT_LABELS = ["0-3", "3-5", "5-10", "10-30", "30-50", "50-100", "100-300", "300-500"]


def bool_series(series: pd.Series) -> pd.Series:
    return series.astype(str).str.lower().isin({"true", "1", "yes"})


def panel_label(ax: plt.Axes, label: str) -> None:
    ax.text(
        -0.13,
        1.07,
        label,
        transform=ax.transAxes,
        ha="left",
        va="top",
        fontsize=11,
        fontweight="bold",
    )


def set_current_density_xlabel(ax: plt.Axes, prefix: str, *, y: float, labelpad: float = 1.0) -> None:
    ax.set_xlabel(
        f"{prefix} ({MA_CM2})",
        labelpad=labelpad,
        fontproperties=UNIT_FONT,
        fontsize=mpl.rcParams["axes.labelsize"],
    )


def filter_text(jmax_cutoff: float | None) -> str:
    if jmax_cutoff is None:
        return ""
    return f"; |j| max \u2265 {jmax_cutoff:g}"


def short_label(text: object, max_chars: int = 26) -> str:
    label = str(text) if text is not None else ""
    label = " ".join(label.split())
    if len(label) <= max_chars:
        return label
    return label[: max_chars - 1].rstrip() + "\u2026"


def catalyst_display_label(text: object) -> str:
    label = str(text) if text is not None else ""
    label = " ".join(label.split())
    special = {
        "Co1N3P1C/CF2": r"$\mathbf{Co}_{\mathbf{1}}\mathbf{N}_{\mathbf{3}}\mathbf{P}_{\mathbf{1}}\mathbf{C}/\mathbf{CF}_{\mathbf{2}}$",
        "Solid sphere MoO2": r"Solid sphere $\mathbf{MoO}_{\mathbf{2}}$",
    }
    return special.get(label, short_label(label))


def subset_by_jmax(frame: pd.DataFrame, jmax_cutoff: float | None, column: str = "j_max_mA") -> pd.DataFrame:
    if jmax_cutoff is None:
        return frame.copy()
    return frame[pd.to_numeric(frame[column], errors="coerce") >= jmax_cutoff].copy()


def plot_pass_statistics(ax: plt.Axes, fit: pd.DataFrame, jmax_cutoff: float | None) -> None:
    strict = fit[bool_series(fit["model_comparison_ok"])].copy()
    strict = subset_by_jmax(strict, jmax_cutoff)
    n = len(strict)
    bv_pass = int((strict["bv_r2"] >= 0.99).sum())
    bvir_pass = int((strict["bvir_r2"] >= 0.99).sum())
    rescued = int(((strict["bv_r2"] < 0.99) & (strict["bvir_r2"] >= 0.99)).sum())

    pass_counts = np.array([bv_pass, bvir_pass], dtype=float)
    fail_counts = n - pass_counts
    pass_pct = pass_counts / n * 100.0
    fail_pct = fail_counts / n * 100.0

    x = np.arange(2)
    colors = ["#4C78A8", "#F58518"]
    ax.bar(x, fail_pct, color="#D9D9D9", width=0.58, edgecolor="white", linewidth=0.7)
    ax.bar(x, pass_pct, bottom=fail_pct, color=colors, width=0.58, edgecolor="white", linewidth=0.7)

    for idx, (pct, count) in enumerate(zip(pass_pct, pass_counts.astype(int))):
        ax.text(idx, fail_pct[idx] + pct / 2, f"{pct:.1f}%\n({count})", ha="center", va="center", color="white", fontweight="bold")
    for idx, count in enumerate(fail_counts.astype(int)):
        ax.text(idx, fail_pct[idx] / 2, f"{count}", ha="center", va="center", color="#555555")

    ax.annotate(
        f"+{rescued} rescued",
        xy=(1, 100.0),
        xytext=(0.5, 108.5),
        ha="center",
        va="bottom",
        arrowprops={"arrowstyle": "-|>", "color": "#333333", "lw": 0.9, "shrinkA": 4, "shrinkB": 3},
        fontsize=8.5,
    )
    ax.set_ylim(0, 116)
    ax.set_xticks(x)
    ax.set_xticklabels(["BV", "BV+iR"])
    ax.set_ylabel(f"Curves with {R2_LABEL} \u2265 0.99 (%)")
    ax.set_title(f"High-quality fit rate (n = {n}{filter_text(jmax_cutoff)})", pad=7, fontweight="bold")
    ax.grid(False)
    ax.text(
        0.5,
        -0.15,
        "gray = below threshold",
        transform=ax.transAxes,
        ha="center",
        va="center",
        color="#666666",
        fontsize=7.5,
        clip_on=False,
    )
    panel_label(ax, "A")


def load_j_eta(curve_uid: str, curves: pd.DataFrame, records: dict[str, dict[str, object]]) -> tuple[np.ndarray, np.ndarray]:
    curve = curves.loc[curves["curve_uid"] == curve_uid].iloc[0]
    record = records[curve_uid]
    points = record.get("native_points") or []
    x = np.asarray([point.get("x", np.nan) for point in points], dtype=float)
    y = np.asarray([point.get("y", np.nan) for point in points], dtype=float)
    axes = base.resolve_axes(curve, x, y)
    eta_mv, _ = base.potential_to_eta_mv(
        np.asarray(axes["potential_values"], dtype=float),
        str(axes["potential_units"]),
        str(axes["potential_label"]),
    )
    current_ma, _ = base.current_to_ma(
        np.asarray(axes["current_values"], dtype=float),
        str(axes["current_units"]),
        str(axes["current_label"]),
    )
    return base.clean_series(np.abs(current_ma), eta_mv)


def choose_examples(fit: pd.DataFrame, rows: pd.DataFrame) -> list[tuple[str, str]]:
    rescued = fit[
        (fit["r2_outcome_class"] == "rescued_by_iR")
        & (fit["bvir_r2"] >= 0.995)
        & (fit["fit_point_count"] >= 15)
        & (fit["j_max_mA"].between(30, 300))
    ].copy()
    rescued = rescued.sort_values(["rmse_reduction_mV", "delta_aic_bv_minus_bvir"], ascending=False)

    unsaved = rows.merge(fit, on="curve_uid", how="left", suffixes=("", "_fit"))
    unsaved = unsaved[
        (unsaved["accepted_fit_source"] == "strict")
        & (unsaved["n_points"] >= 25)
        & (unsaved["bvir_r2"].between(0.80, 0.93))
        & (unsaved["low_current_0_10_share"] > 0.8)
        & (unsaved["j_max_mA"] >= 40)
    ].copy()
    unsaved = unsaved.sort_values(["bvir_rmse_mV", "low_current_0_10_share"], ascending=[False, False])

    return [
        ("Rescued", str(rescued.iloc[0]["curve_uid"])),
        ("Still", str(unsaved.iloc[0]["curve_uid"])),
    ]


def plot_fit_example(ax: plt.Axes, row: pd.Series, j: np.ndarray, eta: np.ndarray, label: str) -> None:
    order = np.argsort(j)
    j = j[order]
    eta = eta[order]
    grid = np.geomspace(max(float(np.nanmin(j)), 0.2), float(np.nanmax(j)), 220)

    bv_pred = base.bv_inverse(grid, math.log(float(row["bv_j0_mA"])), float(row["bv_a_mv"]))
    bvir_pred = base.bv_ir_inverse(
        grid,
        math.log(float(row["bvir_j0_mA"])),
        float(row["bvir_a_mv"]),
        float(row["bvir_r_mV_per_mA"]),
    )

    ax.scatter(j, eta, s=12, color="#222222", alpha=0.72, linewidths=0, label="data")
    ax.plot(grid, bv_pred, color="#4C78A8", lw=1.15, label="BV")
    ax.plot(grid, bvir_pred, color="#F58518", lw=1.35, label="BV+iR")
    ax.set_xscale("log")
    ax.set_title(
        f"{label}: {catalyst_display_label(row['curve_label'])}\n"
        f"BV {R2_LABEL}={row['bv_r2']:.3f}, BV+iR {R2_LABEL}={row['bvir_r2']:.3f}",
        fontsize=7.8,
        fontweight="bold",
        pad=4,
    )
    set_current_density_xlabel(ax, "|j|", y=-0.15, labelpad=1)
    ax.grid(color="#E6E6E6", linewidth=0.6)
    ax.tick_params(axis="both", labelsize=7)


def plot_examples(fig: plt.Figure, gs, fit: pd.DataFrame) -> list[dict[str, object]]:
    curves = pd.read_csv(TABLE_DIR / "curves.csv", dtype=str)
    records = base.read_normalized_records()
    rows = pd.read_csv(ROW_SUMMARY_PATH)
    examples = choose_examples(fit, rows)
    example_records = []

    inner = gs.subgridspec(1, 2, wspace=0.18)
    axes = [fig.add_subplot(inner[0, 0]), fig.add_subplot(inner[0, 1])]
    fit_by_uid = fit.set_index("curve_uid")
    for ax, (label, curve_uid) in zip(axes, examples):
        row = fit_by_uid.loc[curve_uid]
        j, eta = load_j_eta(curve_uid, curves, records)
        plot_fit_example(ax, row, j, eta, label)
        example_records.append(
            {
                "example_type": label,
                "curve_uid": curve_uid,
                "curve_label": row["curve_label"],
                "electrolyte_regime": row["electrolyte_regime"],
                "bv_r2": row["bv_r2"],
                "bvir_r2": row["bvir_r2"],
                "bvir_R_ohm_cm2": row["bvir_r_mV_per_mA"],
                "bvir_rmse_mV": row["bvir_rmse_mV"],
            }
        )

    axes[0].set_ylabel("Overpotential, \u03b7 (mV)")
    axes[1].set_ylabel("")
    axes[1].set_yticklabels([])
    handles, labels = axes[0].get_legend_handles_labels()
    axes[0].legend(handles, labels, frameon=False, loc="upper left", fontsize=7, handlelength=1.4)
    axes[0].text(
        -0.18,
        1.17,
        "B",
        transform=axes[0].transAxes,
        ha="left",
        va="top",
        fontsize=11,
        fontweight="bold",
    )
    return example_records


def electrolyte_group(value: object) -> str:
    text = str(value).lower()
    if text == "acidic":
        return "Acidic"
    if text == "alkaline":
        return "Alkaline"
    if text in {"neutral", "buffered"}:
        return "Neutral/\nbuffer"
    if text == "saline_or_seawater":
        return "Saline/\nseawater"
    return "Unclear"


def plot_r_violin(ax: plt.Axes, fit: pd.DataFrame, jmax_cutoff: float | None) -> None:
    groups = ["Acidic", "Alkaline", "Neutral/\nbuffer", "Saline/\nseawater"]
    colors = ["#4C78A8", "#54A24B", "#B279A2", "#72B7B2"]
    frame = fit.copy()
    frame["electrolyte_group"] = frame["electrolyte_regime"].map(electrolyte_group)
    frame["R_eff"] = pd.to_numeric(frame["bvir_r_mV_per_mA"], errors="coerce").clip(lower=0)
    offset = 0.01
    data = [np.log10(frame.loc[frame["electrolyte_group"] == group, "R_eff"].dropna().to_numpy() + offset) for group in groups]

    parts = ax.violinplot(data, positions=np.arange(len(groups)), widths=0.78, showmeans=False, showmedians=False, showextrema=False)
    for body, color in zip(parts["bodies"], colors):
        body.set_facecolor(color)
        body.set_edgecolor("#333333")
        body.set_alpha(0.72)
        body.set_linewidth(0.55)

    rng = np.random.default_rng(17)
    for idx, (group, color) in enumerate(zip(groups, colors)):
        values = data[idx]
        if values.size == 0:
            continue
        draw = values if values.size <= 220 else rng.choice(values, size=220, replace=False)
        jitter = rng.normal(0, 0.055, size=draw.size)
        ax.scatter(np.full(draw.size, idx) + jitter, draw, s=4.5, color=color, edgecolors="none", alpha=0.26, rasterized=True)
        median = np.nanmedian(values)
        ax.plot([idx - 0.27, idx + 0.27], [median, median], color="#111111", lw=1.0)
        ax.text(idx, 2.13, f"n={values.size}", ha="center", va="bottom", fontsize=7.2, color="black")

    tick_r = np.array([0, 0.1, 1, 10, 100], dtype=float)
    ax.set_yticks(np.log10(tick_r + offset))
    ax.set_yticklabels(["0", "0.1", "1", "10", "100"])
    ax.set_ylim(-2.18, 2.35)
    ax.set_xticks(np.arange(len(groups)))
    ax.set_xticklabels(groups)
    ax.set_ylabel(f"Effective R ({OHM_CM2}, log scale)")
    ax.set_title(f"Fitted effective R by electrolyte{filter_text(jmax_cutoff)}", pad=7, fontweight="bold")
    ax.grid(False)
    panel_label(ax, "C")


def accepted_jmax_by_curve() -> pd.Series:
    relaxed = pd.read_csv(RELAXED_FIT_PATH, low_memory=False)
    strict_ok = bool_series(relaxed.get("strict_fit_ok", pd.Series(False, index=relaxed.index)))
    strict_jmax = pd.to_numeric(relaxed.get("j_max_mA"), errors="coerce")
    relaxed_jmax = pd.to_numeric(relaxed.get("relaxed_j_max_mA_like"), errors="coerce")
    accepted_jmax = strict_jmax.where(strict_ok, relaxed_jmax)
    return pd.Series(accepted_jmax.to_numpy(float), index=relaxed["curve_uid"].astype(str))


def plot_error_heatmap(ax: plt.Axes, fig: plt.Figure, jmax_cutoff: float | None) -> None:
    share = pd.read_csv(SHARE_PATH, index_col=0).reindex(columns=CURRENT_LABELS)
    counts = pd.read_csv(COUNT_PATH, index_col=0).reindex(columns=CURRENT_LABELS).fillna(0)
    rows = pd.read_csv(ROW_SUMMARY_PATH, index_col=0).reindex(index=share.index)
    if jmax_cutoff is not None:
        jmax = accepted_jmax_by_curve()
        keep = share.index.to_series().map(jmax).astype(float) >= jmax_cutoff
        share = share.loc[keep]
        counts = counts.loc[keep]
        rows = rows.loc[keep]
    no_data = counts.to_numpy(float) <= 0
    values = np.ma.masked_where(no_data, share.to_numpy(float) * 100.0)

    cmap = mpl.colormaps["YlOrRd"].copy()
    cmap.set_bad("#D7D7D7")
    image = ax.imshow(values, aspect="auto", cmap=cmap, vmin=0, vmax=100, interpolation="nearest", rasterized=True)
    ax.set_xticks(np.arange(len(CURRENT_LABELS)))
    ax.set_xticklabels(CURRENT_LABELS, rotation=35, ha="right")
    ax.set_yticks([])
    set_current_density_xlabel(ax, "|j| window", y=-0.19, labelpad=2)
    ax.set_ylabel("Curves sorted by dominant error")
    ax.set_title(
        f"Remaining BV+iR error distribution\n(n = {len(share)}{filter_text(jmax_cutoff)})",
        pad=4,
        fontweight="bold",
    )
    ax.set_xticks(np.arange(-0.5, len(CURRENT_LABELS), 1), minor=True)
    ax.grid(which="minor", axis="x", color="white", linewidth=0.7)
    ax.tick_params(which="minor", bottom=False)
    for spine in ax.spines.values():
        spine.set_visible(False)

    labels = rows["dominant_error_window"].astype(str).to_numpy()
    for idx in range(1, len(labels)):
        if labels[idx] != labels[idx - 1]:
            ax.axhline(idx - 0.5, color="#555555", linewidth=0.35, alpha=0.55)

    cbar = fig.colorbar(image, ax=ax, fraction=0.046, pad=0.018)
    cbar.set_label("SSE share (%)")
    cbar.ax.tick_params(labelsize=7)
    cbar.ax.text(0.5, -0.06, "gray = no data", transform=cbar.ax.transAxes, ha="center", va="top", fontsize=7, color="#555555")
    panel_label(ax, "D")


def make_figure(jmax_cutoff: float | None, suffix: str) -> None:
    fit = pd.read_csv(FIT_PATH, low_memory=False)
    strict_fit = pd.read_csv(STRICT_FIT_PATH, low_memory=False)
    fit_filtered = subset_by_jmax(fit, jmax_cutoff)

    apply_publication_style()
    mpl.rcParams.update(
        {
            "font.size": 8.5,
            "axes.titlesize": 9.2,
            "axes.labelsize": 8.4,
            "xtick.labelsize": 7.5,
            "ytick.labelsize": 7.5,
            "legend.fontsize": 7.2,
        }
    )

    fig = plt.figure(figsize=(7.4, 6.9), constrained_layout=True)
    gs = fig.add_gridspec(2, 2, width_ratios=[1.0, 1.15], height_ratios=[0.9, 1.15], wspace=0.16, hspace=0.18)

    ax_a = fig.add_subplot(gs[0, 0])
    plot_pass_statistics(ax_a, strict_fit, jmax_cutoff)
    examples = plot_examples(fig, gs[0, 1], fit_filtered)

    ax_c = fig.add_subplot(gs[1, 0])
    plot_r_violin(ax_c, fit_filtered, jmax_cutoff)

    ax_d = fig.add_subplot(gs[1, 1])
    plot_error_heatmap(ax_d, fig, jmax_cutoff)

    out_path = OUT_DIR / f"publication_bvir_four_panel_summary{suffix}.png"
    save_publication_figure(fig, out_path, dpi=450)
    plt.close(fig)

    pd.DataFrame(examples).to_csv(OUT_DIR / f"publication_bvir_four_panel_examples{suffix}.csv", index=False)
    print(out_path)
    print(out_path.with_suffix(".pdf"))
    print(out_path.with_suffix(".svg"))
    print(OUT_DIR / f"publication_bvir_four_panel_examples{suffix}.csv")


def make_figure_cd_jmax20() -> None:
    fit = pd.read_csv(FIT_PATH, low_memory=False)
    strict_fit = pd.read_csv(STRICT_FIT_PATH, low_memory=False)
    jmax_cutoff = 20.0

    apply_publication_style()
    mpl.rcParams.update(
        {
            "font.size": 8.5,
            "axes.titlesize": 9.2,
            "axes.labelsize": 8.4,
            "xtick.labelsize": 7.5,
            "ytick.labelsize": 7.5,
            "legend.fontsize": 7.2,
        }
    )

    fig = plt.figure(figsize=(7.4, 6.9), constrained_layout=True)
    gs = fig.add_gridspec(2, 2, width_ratios=[1.0, 1.15], height_ratios=[0.9, 1.15], wspace=0.16, hspace=0.18)

    ax_a = fig.add_subplot(gs[0, 0])
    plot_pass_statistics(ax_a, strict_fit, None)
    examples = plot_examples(fig, gs[0, 1], fit)

    ax_c = fig.add_subplot(gs[1, 0])
    plot_r_violin(ax_c, subset_by_jmax(fit, jmax_cutoff), jmax_cutoff)

    ax_d = fig.add_subplot(gs[1, 1])
    plot_error_heatmap(ax_d, fig, jmax_cutoff)

    suffix = "_cd_jmax20"
    out_path = OUT_DIR / f"publication_bvir_four_panel_summary{suffix}.png"
    save_publication_figure(fig, out_path, dpi=450)
    plt.close(fig)

    pd.DataFrame(examples).to_csv(OUT_DIR / f"publication_bvir_four_panel_examples{suffix}.csv", index=False)
    print(out_path)
    print(out_path.with_suffix(".pdf"))
    print(out_path.with_suffix(".svg"))
    print(OUT_DIR / f"publication_bvir_four_panel_examples{suffix}.csv")


def main() -> None:
    for jmax_cutoff, suffix in [(None, ""), (10.0, "_jmax10"), (20.0, "_jmax20")]:
        make_figure(jmax_cutoff, suffix)
    make_figure_cd_jmax20()


if __name__ == "__main__":
    main()
