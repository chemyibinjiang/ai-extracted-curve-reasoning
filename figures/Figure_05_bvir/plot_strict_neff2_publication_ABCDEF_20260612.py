from __future__ import annotations

import json
from pathlib import Path
import sys

OUT_DIR = Path(__file__).resolve().parent


def resolve_database_root(start: Path) -> Path:
    for root in (start.parent.parent, *start.parents):
        for candidate in (root / "LSV_publication_database", root / "data" / "LSV_publication_database"):
            if (candidate / "02_canonical_tables").exists():
                return candidate
    return start.parent.parent / "LSV_publication_database"


PACKAGE_ROOT = next((root for root in [OUT_DIR, *OUT_DIR.parents] if (root / "data" / "LSV_publication_database").exists()), OUT_DIR.parent.parent)
ANALYSIS_HELPER_DIR = OUT_DIR
if str(ANALYSIS_HELPER_DIR) not in sys.path:
    sys.path.insert(0, str(ANALYSIS_HELPER_DIR))

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import consistent_branch_eta_current_sign_bvir_offset_rerun_20260608 as fit_pipe
import strict_neff2_bvir_offset_whole_dataset_20260611 as strict_fit
from publication_plot_style import apply_publication_style, save_publication_figure


DB_ROOT = resolve_database_root(OUT_DIR)
TABLE_DIR = DB_ROOT / "02_canonical_tables"
RUN_STEM = "strict_neff2_bvir_offset_whole_dataset_20260611"
OUT_STEM = "strict_neff2_publication_ABCDEF_20260612"
RUN_INPUT_DIR = OUT_DIR
if not (RUN_INPUT_DIR / f"{RUN_STEM}_pass_matrix_dedup.csv").exists() and ANALYSIS_HELPER_DIR.exists():
    RUN_INPUT_DIR = ANALYSIS_HELPER_DIR

CURVE_TABLE_PATH = TABLE_DIR / "curves.csv"
POINTS_PATH = TABLE_DIR / "normalized_curve_points.jsonl"

R2 = "R\u00b2"
MA_CM2 = r"mA cm$^{-2}$"

MODEL_ORDER = ["BV", "BV+iR", "BV+offset", "BV+iR+offset"]
MODEL_LABELS = ["BV", "BV + iR", "BV + E$_{off}$", "BV + iR + E$_{off}$"]
MODEL_COLORS = {
    "BV": "#777777",
    "BV+iR": "#2F6DB3",
    "BV+offset": "#2C9C69",
    "BV+iR+offset": "#B24745",
    "data": "#1F1F1F",
}
EXAMPLE_MODEL_STYLES = {
    "bv": ("BV", "BV", 1.15, 0.55),
    "bvir": ("BV+iR", "BV+iR", 1.7, 0.96),
    "bv_offset": ("BV+offset", "BV+E$_{off}$", 1.7, 0.96),
    "bvir_offset": ("BV+iR+offset", "BV+iR+E$_{off}$", 1.7, 0.96),
}

GROUPS = ["PM", "Non-PM"]
GROUP_COLORS = {"PM": "#F28E2B", "Non-PM": "#4C78A8"}

EXAMPLES = [
    {
        "slot": "iR-enabled",
        "curve_uid": "batch8/case1831/figure_5__panel_a/curve_2",
        "title": "iR-enabled\n20 wt% Pt/C",
        "models": ["bv", "bvir"],
    },
    {
        "slot": "offset-enabled",
        "curve_uid": "batch8/case1632/figure_4__a/curve_2",
        "title": "Offset-enabled\nRu$_2$Ge$_3$/RuGe",
        "models": ["bv", "bv_offset"],
    },
    {
        "slot": "iR + offset-enabled",
        "curve_uid": "batch0/case29/figure_3__panel_a/curve_5",
        "title": "iR + offset-enabled\nMnWO$_4$/FeCoNi-D",
        "models": ["bv", "bvir_offset"],
    },
    {
        "slot": "not captured",
        "curve_uid": "batch0/case44/figure_4__panel_a/curve_2",
        "title": "Not captured\nWO$_3$",
        "models": ["bvir_offset"],
    },
]


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


def normalize_pm(value: object) -> str:
    text = str(value).strip().lower()
    if text in {"true", "1", "yes", "pgm", "pm"}:
        return "PM"
    if text in {"false", "0", "no", "non-pgm", "non-pm"}:
        return "Non-PM"
    return "unknown"


def strict_model_curve(j: np.ndarray, row: pd.Series, prefix: str) -> np.ndarray:
    if prefix == "bv":
        params = np.asarray([row["bv_log_j0"], row["bv_alpha"]], dtype=float)
        return strict_fit.predict_variant(j, params, include_ir=False, include_offset=False)
    if prefix == "bvir":
        params = np.asarray([row["bvir_log_j0"], row["bvir_alpha"], row["bvir_r_mV_per_mA"]], dtype=float)
        return strict_fit.predict_variant(j, params, include_ir=True, include_offset=False)
    if prefix == "bv_offset":
        params = np.asarray([row["bv_offset_log_j0"], row["bv_offset_alpha"], row["bv_offset_e_offset_mV"]], dtype=float)
        return strict_fit.predict_variant(j, params, include_ir=False, include_offset=True)
    if prefix == "bvir_offset":
        params = np.asarray(
            [
                row["bvir_offset_log_j0"],
                row["bvir_offset_alpha"],
                row["bvir_offset_r_mV_per_mA"],
                row["bvir_offset_e_offset_mV"],
            ],
            dtype=float,
        )
        return strict_fit.predict_variant(j, params, include_ir=True, include_offset=True)
    raise ValueError(prefix)


def build_descriptors(fit_rows: pd.DataFrame, pass_matrix: pd.DataFrame) -> pd.DataFrame:
    flags = pass_matrix[["curve_uid", "BV", "BV+iR+offset"]].copy()
    descriptors = fit_rows.reset_index(drop=True).merge(flags, on="curve_uid", how="inner")
    descriptors = descriptors[(~descriptors["BV"].astype(bool)) & descriptors["BV+iR+offset"].astype(bool)].copy()
    descriptors["pm_group"] = descriptors["pgm_class"].map(normalize_pm)
    descriptors = descriptors[descriptors["pm_group"].isin(GROUPS)].copy()
    descriptors["strict_bv_tafel_mV_dec"] = pd.to_numeric(descriptors["bvir_offset_b_tafel_mV_dec"], errors="coerce")
    log_j0 = pd.to_numeric(descriptors["bvir_offset_log_j0"], errors="coerce")
    e_offset = pd.to_numeric(descriptors["bvir_offset_e_offset_mV"], errors="coerce")
    descriptors["strict_bv_log10_intercept_mV"] = e_offset - descriptors["strict_bv_tafel_mV_dec"] * log_j0 / np.log(10.0)
    descriptors["R_eff"] = pd.to_numeric(descriptors["bvir_offset_r_mV_per_mA"], errors="coerce")
    descriptors["E_offset"] = e_offset
    descriptors["j_max"] = pd.to_numeric(descriptors["j_max_mA"], errors="coerce")
    descriptors["D_R_mV"] = descriptors["R_eff"] * descriptors["j_max"]
    return descriptors


def same_panel_diagnostics(descriptors: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    panel_rows = []
    for panel_uid, sub in descriptors.groupby("panel_uid", dropna=False):
        if len(sub) < 2:
            continue
        d_values = sub["D_R_mV"].dropna()
        e_values = sub["E_offset"].dropna()
        if len(d_values) < 2 or len(e_values) < 2:
            continue
        panel_rows.append(
            {
                "panel_uid": panel_uid,
                "n_curves": len(sub),
                "D_range_mV": float(d_values.max() - d_values.min()),
                "E_range_mV": float(e_values.max() - e_values.min()),
                "E_zero_and_nonzero": bool((e_values.abs() <= 5.0).any() and (e_values.abs() > 5.0).any()),
                "E_pos_and_neg": bool((e_values > 5.0).any() and (e_values < -5.0).any()),
            }
        )
    panels = pd.DataFrame(panel_rows)

    ir_yes = descriptors[descriptors["ir_compensation_status"].astype(str).str.lower().eq("yes")].copy()
    c_rows = [
        {
            "metric": "Panel $\\Delta D_R$ >25 mV",
            "count": int((panels["D_range_mV"] > 25.0).sum()),
            "denominator": int(len(panels)),
            "percent": float(100.0 * (panels["D_range_mV"] > 25.0).mean()),
        },
        {
            "metric": "Panel $\\Delta D_R$ >50 mV",
            "count": int((panels["D_range_mV"] > 50.0).sum()),
            "denominator": int(len(panels)),
            "percent": float(100.0 * (panels["D_range_mV"] > 50.0).mean()),
        },
        {
            "metric": "Reported iR: $D_R$ >=10 mV",
            "count": int((ir_yes["D_R_mV"] >= 10.0).sum()),
            "denominator": int(len(ir_yes)),
            "percent": float(100.0 * (ir_yes["D_R_mV"] >= 10.0).mean()) if len(ir_yes) else np.nan,
        },
    ]
    d_rows = [
        {
            "metric": "Panel $\\Delta E_{off}$ >10 mV",
            "count": int((panels["E_range_mV"] > 10.0).sum()),
            "denominator": int(len(panels)),
            "percent": float(100.0 * (panels["E_range_mV"] > 10.0).mean()),
        },
        {
            "metric": "Mixed zero/nonzero $E_{off}$",
            "count": int(panels["E_zero_and_nonzero"].sum()),
            "denominator": int(len(panels)),
            "percent": float(100.0 * panels["E_zero_and_nonzero"].mean()),
        },
        {
            "metric": "Opposite-sign $E_{off}$",
            "count": int(panels["E_pos_and_neg"].sum()),
            "denominator": int(len(panels)),
            "percent": float(100.0 * panels["E_pos_and_neg"].mean()),
        },
    ]
    return panels, pd.DataFrame(c_rows), pd.DataFrame(d_rows)


def panel_a(ax: mpl.axes.Axes, pass_matrix: pd.DataFrame) -> pd.DataFrame:
    denom = len(pass_matrix)
    counts = [int(pass_matrix[model].astype(bool).sum()) for model in MODEL_ORDER]
    rates = [100.0 * count / denom for count in counts]
    y = np.arange(len(MODEL_ORDER))[::-1]
    ax.barh(y, rates, color=[MODEL_COLORS[model] for model in MODEL_ORDER], height=0.62)
    ax.set_yticks(y, MODEL_LABELS)
    ax.set_xlim(0, 100)
    ax.set_xlabel(f"Curves with {R2} \u2265 0.99 (%)")
    ax.set_title("Strict BV model success", fontweight="bold", pad=4)
    ax.tick_params(axis="y", length=0)
    for yi, rate, count in zip(y, rates, counts):
        ax.text(min(rate + 1.3, 91.5), yi, f"{count}/{denom} ({rate:.1f}%)", ha="left", va="center", fontsize=7.0)
    ax.text(
        0.99,
        1.03,
        f"|j|$_{{max}}$ \u2265 20 {MA_CM2}; n = {denom}",
        transform=ax.transAxes,
        ha="right",
        va="bottom",
        fontsize=7.0,
        color="#333333",
    )
    ax.grid(False)
    return pd.DataFrame({"model": MODEL_ORDER, "count": counts, "denominator": denom, "percent": rates})


def plot_example(ax: mpl.axes.Axes, example: dict, fit_rows: pd.DataFrame, curve_rows: pd.DataFrame, records: dict[str, dict]) -> dict:
    uid = example["curve_uid"]
    row = fit_rows.loc[uid]
    prepared = fit_pipe.prepare_curve(curve_rows.loc[uid], records[uid])
    j = np.asarray(prepared["j"], dtype=float)
    eta = np.asarray(prepared["y"], dtype=float)
    order = np.argsort(j)
    j = j[order]
    eta = eta[order]
    j_grid = np.linspace(float(np.nanmin(j)), float(np.nanmax(j)), 360)

    ax.scatter(eta, j, s=12, color=MODEL_COLORS["data"], alpha=0.78, linewidth=0, zorder=5)
    annotation_rows = []
    for prefix in example["models"]:
        key, label, lw, alpha = EXAMPLE_MODEL_STYLES[prefix]
        y_model = strict_model_curve(j_grid, row, prefix)
        ax.plot(y_model, j_grid, color=MODEL_COLORS[key], linewidth=lw, alpha=alpha)
        annotation_rows.append((key, label, float(row[f"{prefix}_r2"]), lw, alpha))

    ax.set_title(example["title"], fontweight="bold", fontsize=7.8, pad=2.0)
    ax.set_xlabel("\u03b7 (mV)")
    ax.set_ylabel(f"|j| ({MA_CM2})")
    ax.grid(False)
    ax.xaxis.set_major_locator(mpl.ticker.MaxNLocator(4))
    ax.yaxis.set_major_locator(mpl.ticker.MaxNLocator(4))
    ax.set_ylim(bottom=max(0, np.nanmin(j) - 0.05 * (np.nanmax(j) - np.nanmin(j))))
    for idx, (key, label, r2, lw, alpha) in enumerate(annotation_rows):
        y_label = 0.94 - 0.09 * idx
        ax.plot(
            [0.04, 0.095],
            [y_label, y_label],
            transform=ax.transAxes,
            color=MODEL_COLORS[key],
            linewidth=lw,
            alpha=alpha,
            solid_capstyle="round",
            clip_on=False,
        )
        ax.text(
            0.105,
            y_label,
            f"{label} {R2}={r2:.3f}",
            transform=ax.transAxes,
            ha="left",
            va="center",
            fontsize=6.0,
            color="#222222",
            bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.82, "pad": 1.0},
        )
    return {
        "slot": example["slot"],
        "curve_uid": uid,
        "curve_label": row.get("curve_label"),
        "paper_title": row.get("paper_title"),
        "BV_R2": float(row["bv_r2"]),
        "BV_iR_R2": float(row["bvir_r2"]),
        "BV_Eoffset_R2": float(row["bv_offset_r2"]),
        "BV_iR_Eoffset_R2": float(row["bvir_offset_r2"]),
        "R_ohm_cm2": float(row["bvir_offset_r_mV_per_mA"]),
        "E_offset_mV": float(row["bvir_offset_e_offset_mV"]),
        "alpha": float(row["bvir_offset_alpha"]),
        "j_max_mA_cm2": float(row["j_max_mA"]),
    }


def panel_b(gs_cell, fig: mpl.figure.Figure, fit_rows: pd.DataFrame, curve_rows: pd.DataFrame, records: dict[str, dict]) -> tuple[list[dict], list[mpl.axes.Axes]]:
    sub = gs_cell.subgridspec(2, 2, hspace=0.72, wspace=0.25)
    axes = [fig.add_subplot(sub[i, j]) for i in range(2) for j in range(2)]
    rows = [plot_example(ax, example, fit_rows, curve_rows, records) for ax, example in zip(axes, EXAMPLES)]
    for ax in [axes[1], axes[3]]:
        ax.set_ylabel("")
    return rows, axes


def diagnostic_bar_panel(ax: mpl.axes.Axes, rows: pd.DataFrame, title: str, color: str, note: str | None = None) -> None:
    y = np.arange(len(rows))[::-1]
    ax.barh(y, rows["percent"], color=color, height=0.58, alpha=0.92)
    ax.set_yticks(y, rows["metric"])
    ax.set_xlim(0, 105)
    ax.set_xlabel("Fraction (%)")
    ax.set_title(title, fontweight="bold", pad=4)
    ax.tick_params(axis="y", length=0)
    ax.grid(False)
    for yi, (_, row) in zip(y, rows.iterrows()):
        percent = float(row["percent"])
        inside = percent >= 55
        xpos = percent - 2.0 if inside else percent + 1.2
        ax.text(
            xpos,
            yi,
            f"{int(row['count'])}/{int(row['denominator'])} ({percent:.1f}%)",
            ha="right" if inside else "left",
            va="center",
            fontsize=6.6,
            color="white" if inside else "#222222",
        )
    if note:
        ax.text(0.99, 0.03, note, transform=ax.transAxes, ha="right", va="bottom", fontsize=6.3, color="#555555")


def descriptor_panel(ax: mpl.axes.Axes, descriptors: pd.DataFrame, column: str, bins: np.ndarray, xlabel: str, title: str, *, clip: tuple[float, float], legend: bool = False) -> None:
    for group in GROUPS:
        values = descriptors.loc[descriptors["pm_group"].eq(group), column].dropna().to_numpy(float)
        raw_n = len(values)
        values = values[(values >= clip[0]) & (values <= clip[1])]
        ax.hist(values, bins=bins, density=True, histtype="step", linewidth=1.35, color=GROUP_COLORS[group], label=f"{group} (n={raw_n})")
        med = np.nanmedian(values) if values.size else np.nan
        if np.isfinite(med):
            ax.axvline(med, color=GROUP_COLORS[group], linewidth=1.0, linestyle="--", alpha=0.78)
    ax.set_xlabel(xlabel)
    ax.set_ylabel("Density")
    ax.set_title(title, fontweight="bold", pad=4)
    if legend:
        ax.legend(frameon=False, fontsize=6.7, loc="upper right")
    ax.grid(False)


def add_panel_label(fig: mpl.figure.Figure, axes, label: str, y_pad: float = 0.012) -> None:
    axes_list = axes if isinstance(axes, list) else [axes]
    bbox = mpl.transforms.Bbox.union([ax.get_position() for ax in axes_list])
    fig.text(max(0.015, bbox.x0 - 0.06), bbox.y1 + y_pad, label, fontsize=13, fontweight="bold", ha="left", va="bottom")


def main() -> None:
    apply_publication_style()
    mpl.rcParams.update(
        {
            "axes.grid": False,
            "font.size": 8.0,
            "axes.titlesize": 8.6,
            "axes.labelsize": 7.7,
            "xtick.labelsize": 6.7,
            "ytick.labelsize": 6.7,
            "legend.fontsize": 6.4,
        }
    )

    pass_matrix = pd.read_csv(RUN_INPUT_DIR / f"{RUN_STEM}_pass_matrix_dedup.csv")
    fit_rows = pd.read_csv(RUN_INPUT_DIR / f"{RUN_STEM}_curve_fits.csv", low_memory=False).set_index("curve_uid", drop=False)
    curve_rows = pd.read_csv(CURVE_TABLE_PATH, low_memory=False).set_index("curve_uid", drop=False)
    records = load_point_records({example["curve_uid"] for example in EXAMPLES})
    descriptors = build_descriptors(fit_rows, pass_matrix)
    panel_diag, c_rows, d_rows = same_panel_diagnostics(descriptors)

    fig = plt.figure(figsize=(7.65, 10.85))
    outer = fig.add_gridspec(4, 2, height_ratios=[0.64, 2.38, 0.95, 1.0], hspace=0.68, wspace=0.48)
    ax_a = fig.add_subplot(outer[0, :])
    example_rows, axes_b = panel_b(outer[1, :], fig, fit_rows, curve_rows, records)
    ax_c = fig.add_subplot(outer[2, 0])
    ax_d = fig.add_subplot(outer[2, 1])
    ax_e = fig.add_subplot(outer[3, 0])
    ax_f = fig.add_subplot(outer[3, 1])

    panel_a_rows = panel_a(ax_a, pass_matrix)
    diagnostic_bar_panel(ax_c, c_rows, "iR-term diagnostics", MODEL_COLORS["BV+iR"])
    diagnostic_bar_panel(ax_d, d_rows, "Offset-term diagnostics", MODEL_COLORS["BV+offset"])
    descriptor_panel(
        ax_e,
        descriptors,
        "strict_bv_tafel_mV_dec",
        np.linspace(25, 250, 46),
        "$b_{BV}$ (mV dec$^{-1}$)",
        "High-current BV slope",
        clip=(25, 250),
        legend=True,
    )
    descriptor_panel(
        ax_f,
        descriptors,
        "strict_bv_log10_intercept_mV",
        np.linspace(-250, 250, 51),
        "$B_{BV}$ (mV)",
        "High-current BV intercept",
        clip=(-250, 250),
    )
    ax_f.axvline(0, color="#333333", linewidth=0.8)

    add_panel_label(fig, ax_a, "A")
    add_panel_label(fig, axes_b, "B", y_pad=0.014)
    add_panel_label(fig, ax_c, "C")
    add_panel_label(fig, ax_d, "D")
    add_panel_label(fig, ax_e, "E")
    add_panel_label(fig, ax_f, "F")

    out = OUT_DIR / f"{OUT_STEM}.png"
    save_publication_figure(fig, out)
    plt.close(fig)

    panel_a_rows.to_csv(OUT_DIR / f"{OUT_STEM}_panel_A_summary.csv", index=False)
    pd.DataFrame(example_rows).to_csv(OUT_DIR / f"{OUT_STEM}_panel_B_examples.csv", index=False)
    c_rows.to_csv(OUT_DIR / f"{OUT_STEM}_panel_C_iR_diagnostics.csv", index=False)
    d_rows.to_csv(OUT_DIR / f"{OUT_STEM}_panel_D_Eoffset_diagnostics.csv", index=False)
    descriptors.to_csv(OUT_DIR / f"{OUT_STEM}_panel_EF_descriptors.csv", index=False)
    panel_diag.to_csv(OUT_DIR / f"{OUT_STEM}_same_panel_diagnostics.csv", index=False)
    print(f"saved {out.name}/.pdf/.svg")
    print(f"examples: {OUT_STEM}_panel_B_examples.csv")


if __name__ == "__main__":
    main()
