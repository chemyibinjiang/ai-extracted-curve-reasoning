from __future__ import annotations

import json
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

import consistent_branch_eta_current_sign_bvir_offset_rerun_20260608 as fit_pipe
from publication_plot_style import apply_publication_style, save_publication_figure


OUT_DIR = Path(__file__).resolve().parent
DB_ROOT = OUT_DIR.parent.parent / "LSV_publication_database"
TABLE_DIR = DB_ROOT / "02_canonical_tables"

RUN_STEM = "consistent_branch_eta_current_sign_bvir_offset_20260608"
FIT_PATH = OUT_DIR / f"{RUN_STEM}_curve_fits.csv"
PASS_PATH = OUT_DIR / f"{RUN_STEM}_pass_matrix.csv"
CURVE_TABLE_PATH = TABLE_DIR / "curves.csv"
POINTS_PATH = TABLE_DIR / "normalized_curve_points.jsonl"

L1_PATH = OUT_DIR / "current_sign_l1_Dmetric_sensitivity_success_only_20260609_curve_rows.csv"
PANEL_VARIATION_PATH = OUT_DIR / "current_sign_l1_RE_panel_variation_against_trivial_explanations_20260609.csv"

OUT_STEM = "publication_overall_bv_ir_offset_figure_20260609"

R2 = r"R$^{2}$"
MA_CM2 = r"mA cm$^{-2}$"

MODEL_COLORS = {
    "BV": "#5B5B5B",
    "BV+iR": "#2F6DB3",
    "BV+offset": "#2C9C69",
    "BV+iR+offset": "#B24745",
    "sparse": "#B24745",
    "data": "#1F1F1F",
    "failed": "#A23E48",
}

MODE_ORDER = ["R_only", "E_only", "R_and_E"]
MODE_LABELS = {"R_only": "R only", "E_only": "E$_{offset}$ only", "R_and_E": "R + E$_{offset}$"}
MODE_COLORS = {"R_only": "#4C78A8", "E_only": "#F28E2B", "R_and_E": "#8E6BBE"}
GROUP_ORDER = ["PGM", "non-PGM"]
GROUP_LABELS = {"PGM": "PM", "non-PGM": "non-PM"}
GROUP_COLORS = {"PGM": "#F28E2B", "non-PGM": "#4C78A8"}

EXAMPLES = [
    {
        "slot": "R only",
        "curve_uid": "batch8/case1612/figure_4__panel_a/curve_gray",
        "title": "R only: 20% Pt/C (1)",
        "kind": "sparse",
    },
    {
        "slot": "E_offset only",
        "curve_uid": "batch3/case492/figure_5__panel_a/curve_1",
        "title": "E$_{offset}$ only: Pt$_1$Fe$_1$-TAC",
        "kind": "sparse",
    },
    {
        "slot": "R + E_offset",
        "curve_uid": "batch8/case1831/figure_5__panel_a/curve_2",
        "title": "R + E$_{offset}$: 20% Pt/C (2)",
        "kind": "sparse",
    },
    {
        "slot": "Still below threshold",
        "curve_uid": "batch0/case44/figure_4__panel_a/curve_2",
        "title": "Still <0.99: WO$_3$",
        "kind": "failure",
    },
]


def axes_bbox(axes: mpl.axes.Axes | list[mpl.axes.Axes]) -> mpl.transforms.Bbox:
    axes_list = axes if isinstance(axes, list) else [axes]
    return mpl.transforms.Bbox.union([ax.get_position() for ax in axes_list])


def add_row_header(
    fig: mpl.figure.Figure,
    axes: mpl.axes.Axes | list[mpl.axes.Axes],
    label: str,
    title: str,
    *,
    label_x: float | None = None,
    y_pad: float = 0.016,
) -> None:
    bbox = axes_bbox(axes)
    y = bbox.y1 + y_pad
    actual_label_x = max(0.02, bbox.x0 - 0.07) if label_x is None else label_x
    fig.text(actual_label_x, y, label, fontsize=13, fontweight="bold", ha="left", va="bottom")
    fig.text((bbox.x0 + bbox.x1) / 2, y, title, fontsize=10, fontweight="bold", ha="center", va="bottom")


def load_point_records(uids: set[str]) -> dict[str, dict]:
    records: dict[str, dict] = {}
    with POINTS_PATH.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            record = json.loads(line)
            uid = record.get("curve_uid")
            if uid in uids:
                records[uid] = record
                if len(records) == len(uids):
                    break
    missing = sorted(uids - set(records))
    if missing:
        raise RuntimeError(f"Missing normalized point records: {missing}")
    return records


def bv_curve(j: np.ndarray, row: pd.Series) -> np.ndarray:
    j0 = float(row["bv_profile_j0_mA"])
    a = float(row["bv_profile_a_mV"])
    return a * np.arcsinh(j / max(j0, 1e-300))


def sparse_curve(j: np.ndarray, row: pd.Series) -> np.ndarray:
    j0 = float(row["Dmax_j0_mA"])
    a = float(row["Dmax_a_mV"])
    r = float(row["Dmax_R_ohm_cm2"])
    e = float(row["Dmax_E_offset_mV"])
    return e + a * np.arcsinh(j / max(j0, 1e-300)) + r * j


def bvir_offset_curve(j: np.ndarray, row: pd.Series) -> np.ndarray:
    j0 = float(row["bvir_offset_j0_mA"])
    a = float(row["bvir_offset_a_mV"])
    r = float(row["bvir_offset_r_mV_per_mA"])
    e = float(row["bvir_offset_e_offset_mV"])
    return e + a * np.arcsinh(j / max(j0, 1e-300)) + r * j


def read_fit_inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    pass_matrix = pd.read_csv(PASS_PATH)
    fit_rows = pd.read_csv(FIT_PATH).set_index("curve_uid", drop=False)
    curve_rows = pd.read_csv(CURVE_TABLE_PATH).set_index("curve_uid", drop=False)
    l1_rows = pd.read_csv(L1_PATH).set_index("curve_uid", drop=False)
    return pass_matrix, fit_rows, curve_rows, l1_rows


def plot_panel_a(ax: mpl.axes.Axes, pass_matrix: pd.DataFrame) -> pd.DataFrame:
    models = ["BV", "BV+iR", "BV+offset", "BV+iR+offset"]
    labels = ["BV", "BV + iR", "BV + E$_{offset}$", "BV + iR + E$_{offset}$"]
    colors = [MODEL_COLORS[m] for m in models]
    denom = len(pass_matrix)
    rows = []
    counts = [int(pass_matrix[m].sum()) for m in models]
    rates = [100.0 * c / denom for c in counts]
    y = np.arange(len(models))[::-1]
    ax.barh(y, rates, color=colors, height=0.62)
    ax.set_yticks(y, labels)
    ax.set_xlim(0, 100)
    ax.set_xlabel(f"Curves with {R2} ≥ 0.99 (%)")
    ax.tick_params(axis="y", length=0)
    for yi, rate, count, model in zip(y, rates, counts, models):
        ax.text(
            min(rate + 1.5, 91.5),
            yi,
            f"{count}/{denom} ({rate:.1f}%)",
            ha="left",
            va="center",
            fontsize=8,
            color="black",
        )
        rows.append({"model": model, "count": count, "denominator": denom, "percent": rate})
    ax.text(
        0.99,
        1.03,
        f"|j|max ≥ 20 {MA_CM2}; n = {denom}",
        transform=ax.transAxes,
        ha="right",
        va="bottom",
        fontsize=8,
        color="#333333",
    )
    return pd.DataFrame(rows)


def plot_sparse_example(
    ax: mpl.axes.Axes,
    example: dict,
    fit_rows: pd.DataFrame,
    curve_rows: pd.DataFrame,
    l1_rows: pd.DataFrame,
    records: dict[str, dict],
) -> dict:
    uid = example["curve_uid"]
    fit_row = fit_rows.loc[uid]
    l1_row = l1_rows.loc[uid]
    prepared = fit_pipe.prepare_curve(curve_rows.loc[uid], records[uid])
    j = np.asarray(prepared["j"], dtype=float)
    eta = np.asarray(prepared["y"], dtype=float)
    order = np.argsort(j)
    j = j[order]
    eta = eta[order]
    j_grid = np.linspace(float(np.nanmin(j)), float(np.nanmax(j)), 360)
    y_bv = bv_curve(j_grid, fit_row)
    y_sparse = sparse_curve(j_grid, l1_row)
    mode = str(l1_row["Dmax_mode"])
    r_val = float(l1_row["Dmax_R_ohm_cm2"])
    d_val = float(l1_row["Dmax_Dmax_mV"])
    e_val = float(l1_row["Dmax_E_offset_mV"])
    sparse_label = f"{MODE_LABELS.get(mode, mode)} ({R2}={float(l1_row['Dmax_r2']):.4f})"

    ax.scatter(j, eta, s=13, color=MODEL_COLORS["data"], alpha=0.82, linewidth=0, label="Data", zorder=3)
    ax.plot(
        j_grid,
        y_bv,
        color="#8A8A8A",
        alpha=0.58,
        linewidth=1.15,
        label=f"BV ({R2}={float(fit_row['bv_profile_r2']):.4f})",
    )
    ax.plot(j_grid, y_sparse, color=MODEL_COLORS["sparse"], linewidth=1.55, label=sparse_label)
    ax.set_title(example["title"], loc="center", fontweight="bold", pad=2.5)
    ax.set_xlabel(f"|j| ({MA_CM2})")
    ax.set_ylabel("η (mV)")
    ax.legend(frameon=False, fontsize=6.2, loc="best", handlelength=1.25)
    if mode == "R_only":
        correction_text = f"R={r_val:.3g} Ω cm²"
    elif mode == "E_only":
        correction_text = f"E$_{{offset}}$={e_val:.0f} mV"
    else:
        correction_text = f"R={r_val:.3g} Ω cm²; E$_{{offset}}$={e_val:.0f} mV"
    ax.text(
        0.03,
        0.04,
        correction_text,
        transform=ax.transAxes,
        ha="left",
        va="bottom",
        fontsize=6.7,
        color="#333333",
        bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.72, "pad": 1.2},
    )
    return {
        "slot": example["slot"],
        "curve_uid": uid,
        "curve_label": fit_row["curve_label"],
        "paper_title": fit_row["paper_title"],
        "mode": mode,
        "BV_R2": float(fit_row["bv_profile_r2"]),
        "sparse_R2": float(l1_row["Dmax_r2"]),
        "selected_R_ohm_cm2": r_val,
        "selected_Dmax_mV": d_val,
        "selected_E_offset_mV": e_val,
        "j_max_mA_cm2": float(l1_row["j_max_mA"]),
        "fit_point_count": int(l1_row["fit_point_count"]),
    }


def plot_failure_example(
    ax: mpl.axes.Axes,
    example: dict,
    fit_rows: pd.DataFrame,
    curve_rows: pd.DataFrame,
    records: dict[str, dict],
) -> dict:
    uid = example["curve_uid"]
    row = fit_rows.loc[uid]
    prepared = fit_pipe.prepare_curve(curve_rows.loc[uid], records[uid])
    j = np.asarray(prepared["j"], dtype=float)
    eta = np.asarray(prepared["y"], dtype=float)
    order = np.argsort(j)
    j = j[order]
    eta = eta[order]
    j_grid = np.linspace(float(np.nanmin(j)), float(np.nanmax(j)), 360)

    ax.scatter(
        j,
        eta,
        s=13,
        color=MODEL_COLORS["data"],
        alpha=0.82,
        linewidth=0,
        label="Data",
        zorder=3,
    )
    ax.plot(
        j_grid,
        bvir_offset_curve(j_grid, row),
        color=MODEL_COLORS["failed"],
        linewidth=1.55,
        label=f"BV+iR+E$_{{offset}}$ ({R2}={float(row['bvir_offset_r2']):.4f})",
    )
    ax.set_title(example["title"], loc="center", fontweight="bold", pad=2.5)
    ax.set_xlabel(f"|j| ({MA_CM2})")
    ax.set_ylabel("η (mV)")
    ax.legend(frameon=False, fontsize=6.2, loc="best", handlelength=1.25)
    return {
        "slot": example["slot"],
        "curve_uid": uid,
        "curve_label": row["curve_label"],
        "paper_title": row["paper_title"],
        "mode": "failed_after_full",
        "BV_iR_E_offset_R2": float(row["bvir_offset_r2"]),
        "BV_iR_E_offset_RMSE_mV": float(row["bvir_offset_rmse_mV"]),
        "j_max_mA_cm2": float(row["j_max_mA"]),
        "fit_point_count": int(row["fit_point_count"]),
        "selected_current_sign": float(row["selected_current_sign"]),
        "selected_current_sign_rule": row["selected_current_sign_rule"],
    }


def plot_panel_b(
    gs_cell,
    fig: mpl.figure.Figure,
    fit_rows: pd.DataFrame,
    curve_rows: pd.DataFrame,
    l1_rows: pd.DataFrame,
    records: dict[str, dict],
) -> tuple[list[dict], list[mpl.axes.Axes]]:
    sub = gs_cell.subgridspec(2, 2, hspace=0.60, wspace=0.35)
    axes = [fig.add_subplot(sub[i, j]) for i in range(2) for j in range(2)]
    example_rows: list[dict] = []
    for ax, example in zip(axes, EXAMPLES):
        if example["kind"] == "failure":
            example_rows.append(plot_failure_example(ax, example, fit_rows, curve_rows, records))
        else:
            example_rows.append(plot_sparse_example(ax, example, fit_rows, curve_rows, l1_rows, records))
    for ax in axes[:2]:
        ax.set_xlabel("")
    for ax in (axes[1], axes[3]):
        ax.set_ylabel("")
    return example_rows, axes


def clean_l1_for_panel_c(l1_rows: pd.DataFrame) -> pd.DataFrame:
    df = l1_rows.reset_index(drop=True).copy()
    df = df[df["Dmax_mode"].isin(MODE_ORDER) & df["pgm_class"].isin(GROUP_ORDER)].copy()
    for col in ["Dmax_R_ohm_cm2", "Dmax_Dmax_mV", "Dmax_E_offset_mV"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["pgm_class"] = pd.Categorical(df["pgm_class"], GROUP_ORDER, ordered=True)
    return df


def summarize_panel_c(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for group in GROUP_ORDER:
        sub = df[df["pgm_class"].eq(group)].copy()
        r_nonzero = sub.loc[sub["Dmax_R_ohm_cm2"] > 1e-12, "Dmax_R_ohm_cm2"]
        d_nonzero = sub.loc[sub["Dmax_R_ohm_cm2"] > 1e-12, "Dmax_Dmax_mV"]
        e_nonzero = sub.loc[sub["Dmax_E_offset_mV"] != 0, "Dmax_E_offset_mV"]
        row = {
            "pgm_class": group,
            "n_total": int(len(sub)),
            "R_nonzero_n": int(len(r_nonzero)),
            "R_nonzero_percent": float((sub["Dmax_R_ohm_cm2"] > 1e-12).mean() * 100.0),
            "R_nonzero_median_ohm_cm2": float(r_nonzero.median()),
            "D_nonzero_median_mV": float(d_nonzero.median()),
            "E_nonzero_n": int(len(e_nonzero)),
            "E_nonzero_percent": float((sub["Dmax_E_offset_mV"] != 0).mean() * 100.0),
            "E_nonzero_signed_median_mV": float(e_nonzero.median()),
            "E_positive_percent_total": float((sub["Dmax_E_offset_mV"] > 0).mean() * 100.0),
            "E_negative_percent_total": float((sub["Dmax_E_offset_mV"] < 0).mean() * 100.0),
        }
        for mode in MODE_ORDER:
            row[f"{mode}_n"] = int(sub["Dmax_mode"].eq(mode).sum())
            row[f"{mode}_percent"] = float(sub["Dmax_mode"].eq(mode).mean() * 100.0)
        rows.append(row)
    return pd.DataFrame(rows)


def jitter(center: float, n: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return center + rng.uniform(-0.14, 0.14, n)


def draw_nonzero_strip(
    ax: mpl.axes.Axes,
    df: pd.DataFrame,
    *,
    value_col: str,
    ylabel: str,
    title: str,
    ylim: tuple[float, float],
    subset: str,
    log_y: bool = False,
    zero_line: bool = False,
) -> None:
    for i, group in enumerate(GROUP_ORDER):
        sub = df[df["pgm_class"].eq(group)].copy()
        if subset == "R":
            sub = sub[sub["Dmax_R_ohm_cm2"] > 1e-12]
        elif subset == "E":
            sub = sub[sub["Dmax_E_offset_mV"] != 0]
        values = sub[value_col].dropna().to_numpy(float)
        draw = values
        if len(draw) > 420:
            draw = np.random.default_rng(20260609 + i).choice(draw, size=420, replace=False)
        ax.scatter(
            jitter(float(i), len(draw), 20260609 + i),
            draw,
            s=10,
            color=GROUP_COLORS[group],
            alpha=0.34,
            linewidth=0,
            rasterized=True,
        )
        q25, med, q75 = np.quantile(values, [0.25, 0.50, 0.75])
        ax.plot([i - 0.19, i + 0.19], [med, med], color="black", linewidth=1.35, solid_capstyle="butt")
        ax.plot([i, i], [q25, q75], color="black", linewidth=1.0, solid_capstyle="butt")
    if log_y:
        ax.set_yscale("log")
        ax.set_yticks([0.01, 0.1, 1, 10])
        ax.set_yticklabels(["0.01", "0.1", "1", "10"])
    if zero_line:
        ax.axhline(0, color="#333333", linewidth=0.8, zorder=0)
    ax.set_xlim(-0.55, 1.55)
    ax.set_ylim(*ylim)
    xtick_labels = []
    for group in GROUP_ORDER:
        sub = df[df["pgm_class"].eq(group)].copy()
        if subset == "R":
            sub = sub[sub["Dmax_R_ohm_cm2"] > 1e-12]
        elif subset == "E":
            sub = sub[sub["Dmax_E_offset_mV"] != 0]
        xtick_labels.append(f"{GROUP_LABELS[group]}\n(n={len(sub)})")
    ax.set_xticks(np.arange(2), xtick_labels)
    ax.set_ylabel(ylabel)
    ax.set_title(title, loc="center", fontweight="bold", pad=2.5)


def plot_panel_c(gs_cell, fig: mpl.figure.Figure, l1_rows: pd.DataFrame) -> tuple[pd.DataFrame, list[mpl.axes.Axes]]:
    df = clean_l1_for_panel_c(l1_rows)
    summary = summarize_panel_c(df)
    sub = gs_cell.subgridspec(1, 3, wspace=0.40)
    axes = [fig.add_subplot(sub[0, i]) for i in range(3)]

    ax = axes[0]
    x = np.arange(2)
    bottom = np.zeros(2)
    for mode in MODE_ORDER:
        vals = np.array([float(summary.loc[summary["pgm_class"].eq(group), f"{mode}_percent"].iloc[0]) for group in GROUP_ORDER])
        ax.bar(
            x,
            vals,
            bottom=bottom,
            color=MODE_COLORS[mode],
            edgecolor="white",
            linewidth=0.6,
            label=MODE_LABELS[mode],
        )
        for xi, bi, vi, group in zip(x, bottom, vals, GROUP_ORDER):
            count = int(summary.loc[summary["pgm_class"].eq(group), f"{mode}_n"].iloc[0])
            if vi >= 10:
                label = f"{count}\n{vi:.0f}%" if vi >= 18 else f"{count} ({vi:.0f}%)"
                ax.text(xi, bi + vi / 2, label, ha="center", va="center", fontsize=7, color="black")
        bottom += vals
    ax.set_xticks(x, ["PM\n(n=705)", "non-PM\n(n=577)"])
    ax.set_ylim(0, 100)
    ax.set_ylabel("Rescued curves (%)")
    ax.set_title("Correction frequency", loc="center", fontweight="bold", pad=2.5)
    ax.legend(
        frameon=False,
        loc="upper left",
        bbox_to_anchor=(0.00, -0.23),
        ncol=3,
        handlelength=1.0,
        borderaxespad=0.0,
        columnspacing=0.85,
        handletextpad=0.45,
    )

    draw_nonzero_strip(
        axes[1],
        df,
        value_col="Dmax_R_ohm_cm2",
        ylabel="Selected R when R > 0 (Ω cm²)",
        title="Nonzero R magnitude",
        ylim=(0.004, 12),
        subset="R",
        log_y=True,
    )
    draw_nonzero_strip(
        axes[2],
        df,
        value_col="Dmax_E_offset_mV",
        ylabel="Selected E$_{offset}$ when nonzero (mV)",
        title="Nonzero E$_{offset}$",
        ylim=(-55, 55),
        subset="E",
        zero_line=True,
    )
    return summary, axes


def plot_panel_d(gs_cell, fig: mpl.figure.Figure, l1_rows: pd.DataFrame) -> tuple[pd.DataFrame, list[mpl.axes.Axes]]:
    l1 = clean_l1_for_panel_c(l1_rows)
    summary_row = pd.read_csv(OUT_DIR / "current_sign_l1_RE_trivial_explanation_checks_summary_20260609.csv").iloc[0]

    yes = l1[l1["ir_compensation_status_clean"].eq("yes")]
    yes_r_n = int((yes["Dmax_R_ohm_cm2"] > 1e-12).sum())
    yes_d10_n = int((yes["Dmax_Dmax_mV"] >= 10.0).sum())
    yes_n = int(len(yes))
    yes_pct = 100.0 * yes_r_n / yes_n if yes_n else np.nan
    yes_d10_pct = 100.0 * yes_d10_n / yes_n if yes_n else np.nan

    bars = pd.DataFrame(
        [
            {
                "metric": "Same-panel\n$D_R$ range >25 mV",
                "count": int(round(float(summary_row["D_range_gt25mV_pct"]) * int(summary_row["panels_ge2"]) / 100.0)),
                "denominator": int(summary_row["panels_ge2"]),
                "percent": float(summary_row["D_range_gt25mV_pct"]),
            },
            {
                "metric": "Reported iR comp.\nSelected R > 0",
                "count": yes_r_n,
                "denominator": yes_n,
                "percent": yes_pct,
            },
            {
                "metric": "Reported iR comp.\n$D_R$ ≥10 mV",
                "count": yes_d10_n,
                "denominator": yes_n,
                "percent": yes_d10_pct,
            },
        ]
    )

    ax1 = fig.add_subplot(gs_cell)

    colors = ["#7E9FCA", "#74A99A", "#C9798D"]
    x = np.arange(len(bars))
    ax1.bar(x, bars["percent"], color=colors, width=0.62)
    ax1.set_ylim(0, 70)
    ax1.set_xticks(x, bars["metric"])
    ax1.set_ylabel("Fraction (%)")
    ax1.set_title("R-term controls", loc="center", fontweight="bold", pad=2.5)
    for xi, row in bars.iterrows():
        ax1.text(
            xi,
            float(row["percent"]) + 2.0,
            f"{int(row['count'])}/{int(row['denominator'])}\n{float(row['percent']):.1f}%",
            ha="center",
            va="bottom",
            fontsize=7,
            color="black",
        )

    stats_df = bars.copy()
    return stats_df, [ax1]


def plot_panel_e(gs_cell, fig: mpl.figure.Figure) -> tuple[pd.DataFrame, list[mpl.axes.Axes]]:
    summary_row = pd.read_csv(OUT_DIR / "current_sign_l1_RE_trivial_explanation_checks_summary_20260609.csv").iloc[0]
    n_panels = int(summary_row["panels_ge2"])

    bars = pd.DataFrame(
        [
            {
                "metric": "Same-panel\nE range >10 mV",
                "count": int(round(float(summary_row["E_range_gt10mV_pct"]) * n_panels / 100.0)),
                "denominator": n_panels,
                "percent": float(summary_row["E_range_gt10mV_pct"]),
            },
            {
                "metric": "Same-panel\n0 and nonzero E",
                "count": int(round(float(summary_row["E_zero_and_nonzero_pct"]) * n_panels / 100.0)),
                "denominator": n_panels,
                "percent": float(summary_row["E_zero_and_nonzero_pct"]),
            },
            {
                "metric": "Same-panel\nE >0 and E <0",
                "count": int(round(float(summary_row["E_pos_and_neg_pct"]) * n_panels / 100.0)),
                "denominator": n_panels,
                "percent": float(summary_row["E_pos_and_neg_pct"]),
            },
        ]
    )

    ax1 = fig.add_subplot(gs_cell)

    colors = ["#8E6BBE", "#F28E2B", "#7E9FCA"]
    x = np.arange(len(bars))
    ax1.bar(x, bars["percent"], color=colors, width=0.62)
    ax1.set_ylim(0, 70)
    ax1.set_xticks(x, bars["metric"])
    ax1.set_ylabel("Fraction (%)")
    ax1.set_title("Offset controls", loc="center", fontweight="bold", pad=2.5)
    for xi, row in bars.iterrows():
        ax1.text(
            xi,
            float(row["percent"]) + 2.0,
            f"{int(row['count'])}/{int(row['denominator'])}\n{float(row['percent']):.1f}%",
            ha="center",
            va="bottom",
            fontsize=7,
            color="black",
        )

    stats_df = bars.copy()
    return stats_df, [ax1]


def main() -> None:
    apply_publication_style()
    mpl.rcParams.update(
        {
            "axes.grid": False,
            "font.size": 8.2,
            "axes.titlesize": 9.2,
            "axes.labelsize": 8.2,
            "xtick.labelsize": 7.2,
            "ytick.labelsize": 7.2,
            "legend.fontsize": 6.8,
        }
    )

    pass_matrix, fit_rows, curve_rows, l1_rows = read_fit_inputs()
    records = load_point_records({ex["curve_uid"] for ex in EXAMPLES})

    fig = plt.figure(figsize=(8.6, 12.2))
    outer = fig.add_gridspec(4, 1, height_ratios=[1.02, 3.25, 1.95, 2.45], hspace=0.68)

    ax_a = fig.add_subplot(outer[0, 0])
    pass_summary = plot_panel_a(ax_a, pass_matrix)
    example_rows, axes_b = plot_panel_b(outer[1, 0], fig, fit_rows, curve_rows, l1_rows, records)
    diagnostics = outer[2, 0].subgridspec(1, 2, wspace=0.42)
    panel_c_summary, axes_c = plot_panel_d(diagnostics[0, 0], fig, l1_rows)
    panel_d_summary, axes_d = plot_panel_e(diagnostics[0, 1], fig)
    panel_e_summary, axes_e = plot_panel_c(outer[3, 0], fig, l1_rows)

    add_row_header(fig, ax_a, "A", "Model success rates", y_pad=0.010)
    add_row_header(fig, axes_b, "B", "Representative rescued and unsaved curves", y_pad=0.022)
    add_row_header(fig, axes_c, "C", r"R-term diagnostics: $D_R=R_{\mathrm{eff}}|j|_{\max}$", y_pad=0.030)
    add_row_header(fig, axes_d, "D", r"Offset diagnostics: $E_{\mathrm{offset}}$", y_pad=0.030)
    add_row_header(fig, axes_e, "E", "Sparse correction statistics among BV-failed rescued curves", y_pad=0.030)

    pass_summary.to_csv(OUT_DIR / f"{OUT_STEM}_panel_A_summary.csv", index=False)
    pd.DataFrame(example_rows).to_csv(OUT_DIR / f"{OUT_STEM}_panel_B_examples.csv", index=False)
    panel_c_summary.to_csv(OUT_DIR / f"{OUT_STEM}_panel_C_summary.csv", index=False)
    panel_d_summary.to_csv(OUT_DIR / f"{OUT_STEM}_panel_D_summary.csv", index=False)
    panel_e_summary.to_csv(OUT_DIR / f"{OUT_STEM}_panel_E_summary.csv", index=False)

    save_publication_figure(fig, OUT_DIR / f"{OUT_STEM}.png")
    plt.close(fig)
    print(f"saved {OUT_STEM}.png/.pdf/.svg")


if __name__ == "__main__":
    main()
