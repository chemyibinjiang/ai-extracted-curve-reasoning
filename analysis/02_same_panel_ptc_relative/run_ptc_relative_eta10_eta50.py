from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.gridspec import GridSpec, GridSpecFromSubplotSpec


ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = Path(__file__).resolve().parent / "outputs"

LOCAL_AB_FILE = OUT_DIR / "source_AB_current_same_panel_eta10_eta50_rows.csv"
LOCAL_CD_FILE = OUT_DIR / "source_CD_current_strict_bvir_offset_rows.csv"
# This candidate package is drawn from the frozen June 17 source tables copied
# into this folder, so reruns do not silently follow later upstream analysis edits.
AB_FILE = LOCAL_AB_FILE
CD_FILE = LOCAL_CD_FILE
FULL_PAIR_FILE = OUT_DIR / "figure6_candidate_ptc_fit_pairs_high_quality_CD_EF.csv"

OUT_PNG = OUT_DIR / "main_text_figure6_A_to_G_20260619_panelF_bv_interval.png"
OUT_REPORT = OUT_DIR / "main_text_figure6_A_to_G_20260619_panelF_bv_interval_report.md"

GROUP_ORDER = ["Acidic non-PM", "Alkaline non-PM", "Acidic PM", "Alkaline PM"]
GROUP_SHORT = {
    "Acidic non-PM": "Acidic\nnon-PM",
    "Alkaline non-PM": "Alkaline\nnon-PM",
    "Acidic PM": "Acidic\nPM",
    "Alkaline PM": "Alkaline\nPM",
}
GROUP_COLORS = {
    "Acidic non-PM": "#4E79A7",
    "Alkaline non-PM": "#F28E2B",
    "Acidic PM": "#8E6AD8",
    "Alkaline PM": "#1B7F79",
}
BRANCH_COLORS = {
    "both_better": "#1B7F79",
    "remaining_alkaline_pm": "#C51B7D",
}
BRANCH_ORDER = ["both_better", "remaining_alkaline_pm"]
BRANCH_LABELS = {
    "both_better": "Both better",
    "remaining_alkaline_pm": "Remaining",
}
PANEL_G_RULES = [
    "Alloy/intermetallic/bimetallic",
    "Explicit carbon support",
    "Pt-containing",
    "Ir-containing",
    "Ru-containing",
    "Ru + carbon support",
    "Ru + alloy/bimetallic",
    "Phase-controlled Ru nanocages",
    "Oxide/hydroxide interface",
    "Other PM chalcogenide/phosphide",
]
RNG = np.random.default_rng(20260616)
POSTERIOR_DRAWS = 40000

plt.rcParams["font.family"] = "Arial"
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["mathtext.fontset"] = "custom"
plt.rcParams["mathtext.rm"] = "Arial"
plt.rcParams["mathtext.it"] = "Arial:italic"
plt.rcParams["mathtext.bf"] = "Arial:bold"
plt.rcParams["mathtext.default"] = "regular"
plt.rcParams["font.size"] = 12.0
plt.rcParams["axes.titlesize"] = 13.8
plt.rcParams["axes.titleweight"] = "bold"
plt.rcParams["axes.labelsize"] = 12.2
plt.rcParams["xtick.labelsize"] = 10.4
plt.rcParams["ytick.labelsize"] = 10.4
plt.rcParams["legend.fontsize"] = 9.4

DELTA_ETA10_LABEL = r"$\Delta\eta_{10}$"
DELTA_ETA50_LABEL = r"$\Delta\eta_{50}$"
ETA_INTERVAL_LABEL = r"$\Delta(\eta_{50}-\eta_{10})$"


def as_bool(series: pd.Series) -> pd.Series:
    if pd.api.types.is_bool_dtype(series):
        return series.fillna(False)
    return series.astype(str).str.lower().isin(["true", "1", "yes"])


def numeric(frame: pd.DataFrame, column: str) -> pd.Series:
    return pd.to_numeric(frame[column], errors="coerce")


def load_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    ab = pd.read_csv(AB_FILE, low_memory=False)
    cd = pd.read_csv(CD_FILE, low_memory=False)
    if FULL_PAIR_FILE.exists():
        pair_cols = [
            "case_rel_path",
            "figure_id",
            "panel_id",
            "curve_label",
            "fixed_neff2_cand_b_tafel_mV_dec",
            "fixed_neff2_ptc_b_tafel_mV_dec",
            "fixed_neff2_log10_b_tafel_ptc_over_candidate",
            "fixed_neff2_hc_intercept_advantage_mV",
        ]
        pair_info = pd.read_csv(FULL_PAIR_FILE, low_memory=False, usecols=lambda c: c in set(pair_cols))
        cd = cd.merge(pair_info, on=["case_rel_path", "figure_id", "panel_id", "curve_label"], how="left")
        cd["strict_cand_b_bv_mV_dec"] = numeric(cd, "fixed_neff2_cand_b_tafel_mV_dec")
        cd["strict_ptc_b_bv_mV_dec"] = numeric(cd, "fixed_neff2_ptc_b_tafel_mV_dec")
        cd["strict_delta_b_bv_mV_dec"] = cd["strict_cand_b_bv_mV_dec"] - cd["strict_ptc_b_bv_mV_dec"]
        cd["strict_delta_b_bv_interval_mV"] = cd["strict_delta_b_bv_mV_dec"] * np.log10(5.0)
        cd["strict_log10_b_bv_ptc_over_candidate"] = numeric(cd, "fixed_neff2_log10_b_tafel_ptc_over_candidate")
        cd["strict_hc_intercept_candidate_minus_ptc_mV"] = -numeric(cd, "fixed_neff2_hc_intercept_advantage_mV")
    for frame in (ab, cd):
        frame["both_better"] = as_bool(frame["both_better_global"])
        frame["alkaline_pm_branch"] = np.where(
            frame["figure6_group"].eq("Alkaline PM") & frame["both_better"],
            "both_better",
            np.where(frame["figure6_group"].eq("Alkaline PM"), "remaining_alkaline_pm", pd.NA),
        )
        frame["figure6_group"] = pd.Categorical(frame["figure6_group"], GROUP_ORDER, ordered=True)
    return ab.sort_values(["figure6_group", "case_rel_path", "figure_id", "panel_id", "curve_label"]), cd.sort_values(
        ["figure6_group", "case_rel_path", "figure_id", "panel_id", "curve_label"]
    )


def padded_limits(*series: pd.Series, include_zero: bool = True, pad: float = 0.06) -> tuple[float, float]:
    values = []
    for item in series:
        vals = pd.to_numeric(item, errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
        values.extend(vals.tolist())
    low = float(np.nanmin(values))
    high = float(np.nanmax(values))
    if include_zero:
        low = min(low, 0.0)
        high = max(high, 0.0)
    span = max(high - low, 1.0)
    return low - pad * span, high + pad * span


def posterior_draws_for_line(x_values: pd.Series, y_values: pd.Series, n_draws: int = POSTERIOR_DRAWS) -> pd.DataFrame:
    """Weak-prior Bayesian linear fit via normal-inverse-chi-square posterior."""
    x = pd.to_numeric(x_values, errors="coerce").to_numpy(float)
    y = pd.to_numeric(y_values, errors="coerce").to_numpy(float)
    ok = np.isfinite(x) & np.isfinite(y)
    x = x[ok]
    y = y[ok]
    if len(x) < 3:
        return pd.DataFrame(columns=["intercept", "slope", "sigma_mV"])
    design = np.c_[np.ones_like(x), x]
    xtx_inv = np.linalg.inv(design.T @ design)
    beta_hat = xtx_inv @ design.T @ y
    resid = y - design @ beta_hat
    rss = float(resid @ resid)
    df = max(len(y) - design.shape[1], 1)
    sigma2 = rss / RNG.chisquare(df, size=n_draws)
    z = RNG.normal(size=(n_draws, design.shape[1]))
    beta = beta_hat + (z @ np.linalg.cholesky(xtx_inv).T) * np.sqrt(sigma2)[:, None]
    return pd.DataFrame({"intercept": beta[:, 0], "slope": beta[:, 1], "sigma_mV": np.sqrt(sigma2)})


def compute_posteriors(ab: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    draws_parts = []
    summary_rows = []
    for group in GROUP_ORDER:
        sub = ab[ab["figure6_group"].eq(group)]
        draws = posterior_draws_for_line(sub["delta_eta10_mV"], sub["delta_eta50_mV"])
        draws["figure6_group"] = group
        draws_parts.append(draws)
        summary_rows.append(
            {
                "figure6_group": group,
                "n_rows": len(sub),
                "n_cases": sub["case_rel_path"].nunique(),
                "slope_median": draws["slope"].median(),
                "slope_q025": draws["slope"].quantile(0.025),
                "slope_q975": draws["slope"].quantile(0.975),
                "intercept_median_mV": draws["intercept"].median(),
                "intercept_q025_mV": draws["intercept"].quantile(0.025),
                "intercept_q975_mV": draws["intercept"].quantile(0.975),
                "sigma_median_mV": draws["sigma_mV"].median(),
            }
        )
    return pd.concat(draws_parts, ignore_index=True), pd.DataFrame(summary_rows)


def compute_alkaline_pm_branch_posteriors(ab: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    draws_parts = []
    summary_rows = []
    alk = ab[ab["figure6_group"].eq("Alkaline PM")].copy()
    for branch in BRANCH_ORDER:
        sub = alk[alk["alkaline_pm_branch"].eq(branch)]
        draws = posterior_draws_for_line(sub["delta_eta10_mV"], sub["delta_eta50_mV"])
        draws["alkaline_pm_branch"] = branch
        draws_parts.append(draws)
        summary_rows.append(
            {
                "group": branch,
                "ab_n_rows": len(sub),
                "ab_n_cases": sub["case_rel_path"].nunique(),
                "branch_slope_median": draws["slope"].median(),
                "branch_slope_q025": draws["slope"].quantile(0.025),
                "branch_slope_q975": draws["slope"].quantile(0.975),
                "branch_intercept_median_mV": draws["intercept"].median(),
                "branch_intercept_q025_mV": draws["intercept"].quantile(0.025),
                "branch_intercept_q975_mV": draws["intercept"].quantile(0.975),
            }
        )
    return pd.concat(draws_parts, ignore_index=True), pd.DataFrame(summary_rows)


def add_panel_label(fig: plt.Figure, axes: plt.Axes | list[plt.Axes], label: str, dx: float = 0.034, dy: float = 0.008) -> None:
    if isinstance(axes, plt.Axes):
        axes = [axes]
    left = min(ax.get_position().x0 for ax in axes)
    top = max(ax.get_position().y1 for ax in axes)
    fig.text(left - dx, top + dy, label, fontsize=25, fontweight="bold", ha="left", va="top")


def style_axes(ax: plt.Axes, grid: bool = True) -> None:
    if grid:
        ax.grid(alpha=0.22, linewidth=0.8)
    for spine in ax.spines.values():
        spine.set_linewidth(0.9)
        spine.set_color("#4B5563")


def legend(ax: plt.Axes, **kwargs) -> None:
    leg = ax.legend(frameon=True, facecolor="white", edgecolor="#D1D5DB", framealpha=0.94, fancybox=False, **kwargs)
    leg.get_frame().set_linewidth(0.7)


def panel_a(ax: plt.Axes, ab: pd.DataFrame) -> None:
    lim = padded_limits(ab["delta_eta10_mV"], ab["delta_eta50_mV"], include_zero=True, pad=0.05)
    ax.plot(lim, lim, color="#4B5563", linestyle=":", linewidth=1.4, zorder=1)
    ax.axhline(0, color="#111827", linewidth=0.9)
    ax.axvline(0, color="#111827", linewidth=0.9)
    for group in GROUP_ORDER:
        sub = ab[ab["figure6_group"].eq(group)]
        ax.scatter(
            sub["delta_eta10_mV"],
            sub["delta_eta50_mV"],
            s=35,
            color=GROUP_COLORS[group],
            alpha=0.72,
            edgecolor="white",
            linewidth=0.35,
            label=f"{group} (n={len(sub)})",
            zorder=3,
        )
    ax.set_xlim(lim)
    ax.set_ylim(lim)
    ax.set_title("Pt/C-relative catalyst distribution", pad=6)
    ax.set_xlabel(f"{DELTA_ETA10_LABEL} vs same-panel Pt/C (mV)")
    ax.set_ylabel(f"{DELTA_ETA50_LABEL} vs same-panel Pt/C (mV)")
    legend(ax, loc="upper left", fontsize=9.5)
    style_axes(ax)


def interval_panel(ax: plt.Axes, summary: pd.DataFrame, metric: str, title: str, reference: float, xlabel: str) -> None:
    y = np.arange(len(GROUP_ORDER))
    for idx, group in enumerate(GROUP_ORDER):
        row = summary[summary["figure6_group"].eq(group)].iloc[0]
        med = row[f"{metric}_median" if metric == "slope" else f"{metric}_median_mV"]
        q025 = row[f"{metric}_q025" if metric == "slope" else f"{metric}_q025_mV"]
        q975 = row[f"{metric}_q975" if metric == "slope" else f"{metric}_q975_mV"]
        ax.errorbar(
            med,
            idx,
            xerr=[[med - q025], [q975 - med]],
            marker="o",
            markersize=7,
            color=GROUP_COLORS[group],
            ecolor=GROUP_COLORS[group],
            elinewidth=2.0,
            capsize=3,
        )
    ax.axvline(reference, color="#4B5563", linestyle="--", linewidth=1.1)
    ax.set_yticks(y)
    ax.set_yticklabels([GROUP_SHORT[g].replace("\n", " ") for g in GROUP_ORDER])
    ax.invert_yaxis()
    ax.set_xlabel(xlabel)
    ax.set_title(title, pad=5)
    style_axes(ax)


def kde_density(values: pd.Series, grid: np.ndarray) -> np.ndarray:
    vals = pd.to_numeric(values, errors="coerce").dropna().to_numpy(float)
    if len(vals) < 2:
        return np.zeros_like(grid)
    std = float(np.std(vals, ddof=1))
    bandwidth = max(1.06 * std * len(vals) ** (-1 / 5), 1e-6)
    z = (grid[:, None] - vals[None, :]) / bandwidth
    return np.exp(-0.5 * z * z).sum(axis=1) / (len(vals) * bandwidth * np.sqrt(2 * np.pi))


def panel_b(fig: plt.Figure, spec, posterior_draws: pd.DataFrame) -> tuple[plt.Axes, plt.Axes]:
    gs = GridSpecFromSubplotSpec(2, 1, subplot_spec=spec, hspace=0.32)
    ax_slope = fig.add_subplot(gs[0])
    ax_intercept = fig.add_subplot(gs[1])
    slope_lim = padded_limits(posterior_draws["slope"], include_zero=False, pad=0.08)
    intercept_lim = padded_limits(posterior_draws["intercept"], include_zero=True, pad=0.08)
    slope_grid = np.linspace(slope_lim[0], slope_lim[1], 320)
    intercept_grid = np.linspace(intercept_lim[0], intercept_lim[1], 320)
    for group in GROUP_ORDER:
        sub = posterior_draws[posterior_draws["figure6_group"].eq(group)]
        color = GROUP_COLORS[group]
        slope_density = kde_density(sub["slope"], slope_grid)
        intercept_density = kde_density(sub["intercept"], intercept_grid)
        ax_slope.plot(slope_grid, slope_density, color=color, linewidth=1.8, label=GROUP_SHORT[group].replace("\n", " "))
        ax_slope.fill_between(slope_grid, 0, slope_density, color=color, alpha=0.06, linewidth=0)
        ax_intercept.plot(intercept_grid, intercept_density, color=color, linewidth=1.8)
        ax_intercept.fill_between(intercept_grid, 0, intercept_density, color=color, alpha=0.06, linewidth=0)
    ax_slope.axvline(1.0, color="#4B5563", linestyle="--", linewidth=0.9)
    ax_intercept.axvline(0.0, color="#4B5563", linestyle="--", linewidth=0.9)
    ax_slope.set_title("Bayesian fitted-line posteriors", pad=4)
    ax_slope.set_xlabel(r"Slope of $\Delta\eta_{50}$ vs $\Delta\eta_{10}$", labelpad=2)
    ax_intercept.set_xlabel("Intercept (mV)", labelpad=2)
    ax_slope.set_ylabel("Posterior density")
    ax_intercept.set_ylabel("Posterior density")
    legend(ax_slope, loc="upper right", fontsize=8.4)
    style_axes(ax_slope)
    style_axes(ax_intercept)
    return ax_slope, ax_intercept


def summarize_metric(frame: pd.DataFrame, group_col: str, metrics: list[str]) -> pd.DataFrame:
    rows = []
    groups = GROUP_ORDER if group_col == "figure6_group" else ["both_better", "remaining_alkaline_pm"]
    for group in groups:
        sub = frame[frame[group_col].eq(group)].copy()
        base = {"group": group, "n_rows": len(sub), "n_cases": sub["case_rel_path"].nunique()}
        for metric in metrics:
            vals = numeric(sub, metric)
            base[f"{metric}_mean"] = vals.mean()
            base[f"{metric}_median"] = vals.median()
            base[f"{metric}_q25"] = vals.quantile(0.25)
            base[f"{metric}_q75"] = vals.quantile(0.75)
            base[f"{metric}_sem"] = vals.std(ddof=1) / np.sqrt(vals.notna().sum()) if vals.notna().sum() > 1 else np.nan
        rows.append(base)
    return pd.DataFrame(rows)


def add_total_isolines(ax: plt.Axes, x_lim: tuple[float, float], y_lim: tuple[float, float]) -> None:
    x_grid = np.linspace(x_lim[0], x_lim[1], 300)
    for total, alpha in [(-100, 0.26), (-50, 0.34), (0, 0.55), (50, 0.34), (100, 0.26)]:
        y_grid = total - x_grid
        visible = (y_grid >= y_lim[0]) & (y_grid <= y_lim[1])
        if visible.any():
            ax.plot(x_grid[visible], y_grid[visible], color="#6B7280", linestyle="--", linewidth=0.75, alpha=alpha)
            idx = np.where(visible)[0][-1]
            ax.text(x_grid[idx], y_grid[idx], f"{total:+.0f}", color="#555555", fontsize=7.0, ha="right", va="bottom")


def panel_c(fig: plt.Figure, spec, cd: pd.DataFrame) -> tuple[plt.Axes, plt.Axes, plt.Axes, pd.DataFrame]:
    summary = summarize_metric(cd, "figure6_group", ["bv_gap_mV", "ir_gap_mV", "gap_widening_eta50_minus_eta10_mV"])
    gs_joint = GridSpecFromSubplotSpec(
        2,
        2,
        subplot_spec=spec,
        width_ratios=[4.4, 1.05],
        height_ratios=[1.0, 4.2],
        hspace=0.04,
        wspace=0.05,
    )
    ax_top = fig.add_subplot(gs_joint[0, 0])
    ax_main = fig.add_subplot(gs_joint[1, 0], sharex=ax_top)
    ax_right = fig.add_subplot(gs_joint[1, 1], sharey=ax_main)
    x_col = "bv_gap_mV"
    y_col = "ir_gap_mV"
    x_lim = padded_limits(cd[x_col], include_zero=True, pad=0.08)
    y_lim = padded_limits(cd[y_col], include_zero=True, pad=0.08)
    x_lim = (max(x_lim[0], -190), min(x_lim[1], 140))
    y_lim = (max(y_lim[0], -125), min(y_lim[1], 155))
    x_bins = np.linspace(x_lim[0], x_lim[1], 20)
    y_bins = np.linspace(y_lim[0], y_lim[1], 19)
    for group in GROUP_ORDER:
        sub = cd[cd["figure6_group"].eq(group)]
        color = GROUP_COLORS[group]
        ax_main.scatter(
            sub[x_col],
            sub[y_col],
            s=22,
            color=color,
            edgecolors="white",
            linewidths=0.25,
            alpha=0.66,
            label=f"{GROUP_SHORT[group].replace(chr(10), ' ')} (n={len(sub)})",
            zorder=3,
        )
        ax_top.hist(sub[x_col].dropna(), bins=x_bins, histtype="stepfilled", color=color, alpha=0.25, edgecolor=color, linewidth=0.9)
        ax_right.hist(
            sub[y_col].dropna(),
            bins=y_bins,
            histtype="stepfilled",
            orientation="horizontal",
            color=color,
            alpha=0.25,
            edgecolor=color,
            linewidth=0.9,
        )
    ax_main.axhline(0, color="#111827", linewidth=0.85)
    ax_main.axvline(0, color="#111827", linewidth=0.85)
    add_total_isolines(ax_main, x_lim, y_lim)
    ax_main.set_xlim(x_lim)
    ax_main.set_ylim(y_lim)
    ax_main.set_xlabel(f"Strict-BV contribution to {ETA_INTERVAL_LABEL} (mV)", labelpad=5)
    ax_main.set_ylabel(f"iR contribution to {ETA_INTERVAL_LABEL} (mV)", labelpad=5)
    ax_top.set_title("Strict-BV and empirical iR decomposition", pad=4)
    ax_top.set_ylabel("Count", labelpad=3)
    ax_right.set_xlabel("Count", labelpad=3)
    ax_top.tick_params(axis="x", labelbottom=False)
    ax_right.tick_params(axis="y", labelleft=False)
    legend(ax_main, loc="upper left", fontsize=7.8)
    style_axes(ax_main)
    style_axes(ax_top)
    style_axes(ax_right)
    return ax_main, ax_top, ax_right, summary


def strip_box(ax: plt.Axes, frame: pd.DataFrame, group_col: str, metric: str, groups: list[str], title: str, ylabel: str) -> None:
    ax.axhline(0, color="#111827", linewidth=0.85, zorder=1)
    for i, group in enumerate(groups):
        sub = frame[frame[group_col].eq(group)]
        vals = numeric(sub, metric).dropna().to_numpy()
        if len(vals) == 0:
            continue
        jitter = RNG.normal(0, 0.045, size=len(vals))
        color = GROUP_COLORS.get(group, BRANCH_COLORS.get(group, "#6B7280"))
        ax.scatter(np.full_like(vals, i, dtype=float) + jitter, vals, s=20, color=color, alpha=0.48, edgecolor="none", zorder=2)
        q25, med, q75 = np.quantile(vals, [0.25, 0.5, 0.75])
        ax.plot([i - 0.20, i + 0.20], [med, med], color="#111827", linewidth=2.0, zorder=4)
        ax.plot([i, i], [q25, q75], color="#111827", linewidth=1.5, zorder=4)
    ax.set_xticks(np.arange(len(groups)))
    if group_col == "figure6_group":
        ax.set_xticklabels([GROUP_SHORT[g] for g in groups], rotation=0)
    else:
        ax.set_xticklabels(["Both\nbetter", "Remaining"], rotation=0)
    ax.set_title(title, pad=4)
    ax.set_ylabel(ylabel)
    style_axes(ax)


def violin_strip(
    ax: plt.Axes,
    frame: pd.DataFrame,
    group_col: str,
    metric: str,
    groups: list[str],
    title: str,
    ylabel: str,
    ylim: tuple[float, float] | None = None,
    show_ylabel: bool = True,
) -> None:
    data = [numeric(frame[frame[group_col].eq(group)], metric).dropna().to_numpy(float) for group in groups]
    positions = np.arange(1, len(groups) + 1)
    nonempty = [vals for vals in data if len(vals) > 1]
    nonempty_positions = [pos for pos, vals in zip(positions, data) if len(vals) > 1]
    if nonempty:
        parts = ax.violinplot(nonempty, positions=nonempty_positions, widths=0.75, showextrema=False)
        for body, pos in zip(parts["bodies"], nonempty_positions):
            group = groups[int(pos) - 1]
            body.set_facecolor(GROUP_COLORS.get(group, BRANCH_COLORS.get(group, "#6B7280")))
            body.set_alpha(0.16)
            body.set_edgecolor("none")
    for pos, group, vals in zip(positions, groups, data):
        if len(vals) == 0:
            continue
        color = GROUP_COLORS.get(group, BRANCH_COLORS.get(group, "#6B7280"))
        jitter = RNG.normal(0, 0.055, size=len(vals))
        ax.scatter(np.full(len(vals), pos) + jitter, vals, s=13, color=color, alpha=0.58, edgecolor="white", linewidth=0.18, zorder=3)
        q25, med, q75 = np.quantile(vals, [0.25, 0.5, 0.75])
        ax.plot([pos - 0.25, pos + 0.25], [med, med], color="#111827", linewidth=1.6, zorder=5)
        ax.plot([pos, pos], [q25, q75], color="#111827", linewidth=1.05, zorder=5)
    ax.axhline(0, color="#111827", linewidth=0.75)
    ax.set_xticks(positions)
    if group_col == "figure6_group":
        labels = [GROUP_SHORT[group] for group in groups]
    else:
        labels = ["Both\nbetter" if group == "both_better" else "Remaining" for group in groups]
    ax.set_xticklabels(labels, fontsize=8.2)
    ax.set_title(title, pad=4, fontsize=10.3, fontweight="bold")
    ax.set_ylabel(ylabel if show_ylabel else "", fontsize=8.8, labelpad=3)
    if ylim is not None:
        ax.set_ylim(ylim)
    style_axes(ax)


def panel_d_or_f(fig: plt.Figure, spec, frame: pd.DataFrame, group_col: str, title: str) -> tuple[list[plt.Axes], pd.DataFrame]:
    groups = GROUP_ORDER if group_col == "figure6_group" else ["both_better", "remaining_alkaline_pm"]
    metrics = [
        ("strict_cand_b_bv_mV_dec", "Candidate BV-derived Tafel slope", r"mV dec$^{-1}$", (25, 210)),
        ("strict_delta_b_bv_mV_dec", r"Same-panel $b_{\mathrm{BV}}$ contrast", r"mV dec$^{-1}$", None),
        ("strict_hc_intercept_candidate_minus_ptc_mV", "High-current intercept contrast", "mV", None),
        ("ir_gap_mV", "Same-panel iR interval", "mV", None),
    ]
    gs = GridSpecFromSubplotSpec(2, 2, subplot_spec=spec, hspace=0.45, wspace=0.32)
    axes = [fig.add_subplot(gs[i, j]) for i in range(2) for j in range(2)]
    for ax, (metric, sub_title, ylabel, ylim) in zip(axes, metrics):
        violin_strip(ax, frame, group_col, metric, groups, sub_title, ylabel, ylim, show_ylabel=True)
    return axes, summarize_metric(frame, group_col, [m[0] for m in metrics])


def panel_branch_slope_posterior(ax: plt.Axes, branch_draws: pd.DataFrame) -> None:
    slope_lim = padded_limits(branch_draws["slope"], include_zero=False, pad=0.12)
    slope_grid = np.linspace(slope_lim[0], slope_lim[1], 320)
    for branch in BRANCH_ORDER:
        sub = branch_draws[branch_draws["alkaline_pm_branch"].eq(branch)]
        density = kde_density(sub["slope"], slope_grid)
        color = BRANCH_COLORS[branch]
        ax.plot(slope_grid, density, color=color, linewidth=1.8, label=BRANCH_LABELS[branch])
        ax.fill_between(slope_grid, 0, density, color=color, alpha=0.08, linewidth=0)
    ax.axvline(1.0, color="#4B5563", linestyle="--", linewidth=0.9)
    ax.set_title("Branch slope posterior", pad=4, fontsize=10.3, fontweight="bold")
    ax.set_xlabel(r"Slope of $\Delta\eta_{50}$ vs $\Delta\eta_{10}$", fontsize=8.8, labelpad=2)
    ax.set_ylabel("Posterior density", fontsize=8.8, labelpad=3)
    legend(ax, loc="upper right", fontsize=7.8)
    style_axes(ax)


def panel_f(
    fig: plt.Figure,
    spec,
    alk_cd: pd.DataFrame,
    branch_draws: pd.DataFrame,
    branch_summary: pd.DataFrame,
) -> tuple[list[plt.Axes], pd.DataFrame]:
    metrics = [
        ("branch_posterior", "Branch slope posterior", "Posterior density", None),
        ("ir_gap_mV", "Same-panel iR interval", "mV", None),
        ("strict_cand_b_bv_mV_dec", "Candidate BV-derived Tafel slope", r"mV dec$^{-1}$", (25, 210)),
        ("bv_gap_mV", "Exact strict-BV interval contribution", "mV", None),
    ]
    gs = GridSpecFromSubplotSpec(2, 2, subplot_spec=spec, hspace=0.50, wspace=0.32)
    axes = [fig.add_subplot(gs[i, j]) for i in range(2) for j in range(2)]
    panel_branch_slope_posterior(axes[0], branch_draws)
    violin_strip(
        axes[1],
        alk_cd,
        "alkaline_pm_branch",
        metrics[1][0],
        BRANCH_ORDER,
        metrics[1][1],
        metrics[1][2],
        metrics[1][3],
        show_ylabel=True,
    )
    violin_strip(
        axes[2],
        alk_cd,
        "alkaline_pm_branch",
        metrics[2][0],
        BRANCH_ORDER,
        metrics[2][1],
        metrics[2][2],
        metrics[2][3],
        show_ylabel=True,
    )
    violin_strip(
        axes[3],
        alk_cd,
        "alkaline_pm_branch",
        metrics[3][0],
        BRANCH_ORDER,
        metrics[3][1],
        metrics[3][2],
        metrics[3][3],
        show_ylabel=True,
    )
    descriptor_summary = summarize_metric(alk_cd, "alkaline_pm_branch", [metrics[1][0], metrics[2][0], metrics[3][0]])
    return axes, descriptor_summary.merge(branch_summary, on="group", how="outer")


def panel_e(ax: plt.Axes, ab: pd.DataFrame) -> pd.DataFrame:
    alk = ab[ab["figure6_group"].eq("Alkaline PM")].copy()
    lim = padded_limits(alk["delta_eta10_mV"], alk["delta_eta50_mV"], include_zero=True, pad=0.07)
    ax.plot(lim, lim, color="#4B5563", linestyle=":", linewidth=1.4, zorder=1)
    ax.axhline(0, color="#111827", linewidth=0.9)
    ax.axvline(0, color="#111827", linewidth=0.9)
    for branch in ["remaining_alkaline_pm", "both_better"]:
        sub = alk[alk["alkaline_pm_branch"].eq(branch)]
        label = "Both better" if branch == "both_better" else "Remaining"
        ax.scatter(
            sub["delta_eta10_mV"],
            sub["delta_eta50_mV"],
            s=42 if branch == "both_better" else 32,
            color=BRANCH_COLORS[branch],
            alpha=0.76 if branch == "both_better" else 0.48,
            edgecolor="white",
            linewidth=0.35,
            label=f"{label} (n={len(sub)})",
            zorder=3 if branch == "both_better" else 2,
        )
    ax.set_xlim(lim)
    ax.set_ylim(lim)
    ax.set_title("Alkaline PM branch map", pad=6)
    ax.set_xlabel(f"{DELTA_ETA10_LABEL} vs same-panel Pt/C (mV)", labelpad=5)
    ax.set_ylabel(f"{DELTA_ETA50_LABEL} vs same-panel Pt/C (mV)", labelpad=5)
    legend(ax, loc="upper left", fontsize=10)
    style_axes(ax)
    return (
        alk.groupby("alkaline_pm_branch")
        .agg(
            n_rows=("curve_label", "size"),
            n_cases=("case_rel_path", "nunique"),
            median_delta_eta10_mV=("delta_eta10_mV", "median"),
            median_delta_eta50_mV=("delta_eta50_mV", "median"),
            median_gap_mV=("gap_widening_eta50_minus_eta10_mV", "median"),
        )
        .reset_index()
    )


def explicit_carbon_mask(frame: pd.DataFrame) -> pd.Series:
    text_cols = [
        "curve_label",
        "enrich_reported_material_name",
        "support_material",
        "substrate_material",
        "paper_title",
        "audit_strict_subfamily",
        "manual_identity_family",
    ]
    text = frame[text_cols].fillna("").agg(" ".join, axis=1).str.lower()
    pattern = (
        r"carbon|\bcnt\b|graphene|graphitic|cqds?|\bcqds\b|carbon cloth|carbon foam|"
        r"carbon fiber|\bcnf\b|hcs|nhcs|n-doped c|bp-2000|vulcan|ketjen|xc-72|fullerene"
    )
    return text.str.contains(pattern, regex=True)


def metadata_rule_table(ab: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    alk = ab[ab["figure6_group"].eq("Alkaline PM")].copy()
    both = alk["alkaline_pm_branch"].eq("both_better")
    remaining = alk["alkaline_pm_branch"].eq("remaining_alkaline_pm")
    strict = alk["audit_strict_subfamily"].fillna("").str.lower()
    text = alk[
        [
            "curve_label",
            "enrich_reported_material_name",
            "support_material",
            "substrate_material",
            "paper_title",
            "manual_identity_family",
            "audit_strict_subfamily",
        ]
    ].fillna("").agg(" ".join, axis=1).str.lower()
    carbon = explicit_carbon_mask(alk)
    alloy = strict.str.contains("alloy|intermetallic|bimetallic|multimetal|high-entropy", regex=True)
    phase_ru = strict.str.contains("phase-controlled ru", regex=True)
    oxide = as_bool(alk["manual_has_oxide_hydroxide_interface"]) | strict.str.contains("oxide|hydroxide|oxyphilic", regex=True)
    pt = as_bool(alk["Pt_containing"])
    ir = as_bool(alk["Ir_containing"])
    ru = as_bool(alk["Ru_containing"])
    ru_chalc = ru & (
        strict.str.contains("chalcogenide|selenide|mos2|ws2", regex=True)
        | as_bool(alk["manual_has_chalcogenide"])
    )
    ru_mof = ru & text.str.contains("mof|framework|cpf|bdc|femof", regex=True)
    ru_without_strong = ru & ~(carbon | alloy | phase_ru)
    other_pm_chalc_phos = strict.eq("other pm chalcogenide/phosphide")

    rules = [
        ("Alloy/intermetallic/bimetallic", alloy, "audit_strict_subfamily contains alloy/intermetallic/bimetallic/multimetal/high-entropy"),
        ("Explicit carbon support", carbon, "label/support/substrate/title/subfamily contains carbon, CNT, graphene, CQD, CNF, carbon cloth/foam/fiber, N-doped C, HCS/NHCS, fullerene"),
        ("Pt-containing", pt, "Pt_containing is true"),
        ("Ir-containing", ir, "Ir_containing is true"),
        ("Ru-containing", ru, "Ru_containing is true"),
        ("Ru + carbon support", ru & carbon, "Ru_containing and explicit carbon support"),
        ("Ru + alloy/bimetallic", ru & alloy, "Ru_containing and alloy/intermetallic/bimetallic rule"),
        ("Phase-controlled Ru nanocages", ru & phase_ru, "Ru_containing and phase-controlled Ru nanocage subfamily"),
        ("Ru without carbon/alloy/phase", ru_without_strong, "Ru_containing but no explicit carbon, alloy/bimetallic, or phase-controlled Ru flag"),
        ("Oxide/hydroxide interface", oxide, "manual oxide/hydroxide interface or strict subfamily contains oxide/hydroxide/oxyphilic"),
        ("Other PM chalcogenide/phosphide", other_pm_chalc_phos, "audit_strict_subfamily equals other PM chalcogenide/phosphide"),
        ("Ru chalcogenide/MoS2", ru_chalc, "Ru_containing plus chalcogenide/selenide/MoS2/WS2 flag"),
        ("Ru MOF/framework", ru_mof, "Ru_containing plus MOF/framework/CPF/BDC/FeMOF text"),
    ]
    branch_total_both = int(both.sum())
    branch_total_remaining = int(remaining.sum())
    rows = []
    flags = pd.DataFrame({"case_rel_path": alk["case_rel_path"], "curve_label": alk["curve_label"], "both_better": both})
    for rule_name, mask, definition in rules:
        mask = mask.fillna(False)
        in_both = mask & both
        in_remaining = mask & remaining
        category_total = int(mask.sum())
        category_both = int(in_both.sum())
        rows.append(
            {
                "rule_category": rule_name,
                "exact_definition": definition,
                "plotted_in_panel_G": rule_name in PANEL_G_RULES,
                "both_better_feature_count": category_both,
                "both_better_total_rows": branch_total_both,
                "both_better_branch_fraction": category_both / branch_total_both if branch_total_both else np.nan,
                "remaining_feature_count": int(in_remaining.sum()),
                "remaining_total_rows": branch_total_remaining,
                "remaining_branch_fraction": int(in_remaining.sum()) / branch_total_remaining if branch_total_remaining else np.nan,
                "branch_fraction_delta_both_minus_remaining": (
                    category_both / branch_total_both - int(in_remaining.sum()) / branch_total_remaining
                    if branch_total_both and branch_total_remaining
                    else np.nan
                ),
                "category_total_rows": category_total,
                "category_both_better_rows": category_both,
                "category_both_better_rate": category_both / category_total if category_total else np.nan,
                "category_total_cases": alk.loc[mask, "case_rel_path"].nunique(),
            }
        )
        flags[rule_name] = mask.to_numpy()
    return pd.DataFrame(rows), flags


def panel_g(ax: plt.Axes, rule_summary: pd.DataFrame) -> None:
    rows = rule_summary[rule_summary["rule_category"].isin(PANEL_G_RULES)].copy()
    rows["plot_order"] = rows["rule_category"].map({name: idx for idx, name in enumerate(PANEL_G_RULES)})
    rows = rows.sort_values("plot_order").reset_index(drop=True)
    x = np.arange(len(rows))
    width = 0.36
    both_vals = rows["both_better_branch_fraction"].to_numpy(float)
    remaining_vals = rows["remaining_branch_fraction"].to_numpy(float)
    ax.bar(
        x - width / 2,
        both_vals,
        width=width,
        color=BRANCH_COLORS["both_better"],
        label="Both better",
    )
    ax.bar(
        x + width / 2,
        remaining_vals,
        width=width,
        color=BRANCH_COLORS["remaining_alkaline_pm"],
        label="Remaining alkaline PM",
    )
    max_val = float(np.nanmax([both_vals.max(initial=0), remaining_vals.max(initial=0)]))
    ax.set_ylim(0, min(1.0, max_val + 0.14))
    for i, r in rows.iterrows():
        ax.text(
            i - width / 2,
            r["both_better_branch_fraction"] + 0.018,
            f"{int(r['both_better_feature_count'])}/{int(r['both_better_total_rows'])}",
            va="bottom",
            ha="center",
            fontsize=10.0,
            color="#111827",
            rotation=0,
        )
        ax.text(
            i + width / 2,
            r["remaining_branch_fraction"] + 0.018,
            f"{int(r['remaining_feature_count'])}/{int(r['remaining_total_rows'])}",
            va="bottom",
            ha="center",
            fontsize=10.0,
            color="#111827",
            rotation=0,
        )
    short_labels = {
        "Alloy/intermetallic/bimetallic": "Alloy/\nintermetallic",
        "Explicit carbon support": "Carbon\nsupport",
        "Pt-containing": "Pt-\ncontaining",
        "Ir-containing": "Ir-\ncontaining",
        "Ru-containing": "Ru-\ncontaining",
        "Ru + carbon support": "Ru-carbon\nsupport",
        "Ru + alloy/bimetallic": "Ru-alloy/\nbimetallic",
        "Phase-controlled Ru nanocages": "Phase-controlled\nRu nanocages",
        "Oxide/hydroxide interface": "Oxide/\nhydroxide",
        "Other PM chalcogenide/phosphide": "Other PM\nchalc./phosphide",
    }
    ax.set_xticks(x)
    ax.set_xticklabels([short_labels.get(v, v) for v in rows["rule_category"]], fontsize=11.0)
    ax.set_ylabel("Fraction of branch rows", fontsize=12.2)
    ax.set_xlabel("")
    ax.set_title("Alkaline PM metadata enrichment", pad=6)
    legend(ax, loc="upper right", fontsize=11.0)
    style_axes(ax)


def panel_a_summary(ab: pd.DataFrame) -> pd.DataFrame:
    return (
        ab.groupby("figure6_group", observed=False)
        .agg(
            n_rows=("curve_label", "size"),
            n_cases=("case_rel_path", "nunique"),
            median_delta_eta10_mV=("delta_eta10_mV", "median"),
            median_delta_eta50_mV=("delta_eta50_mV", "median"),
            median_gap_mV=("gap_widening_eta50_minus_eta10_mV", "median"),
        )
        .reset_index()
    )


def write_outputs(
    ab: pd.DataFrame,
    cd: pd.DataFrame,
    post_summary: pd.DataFrame,
    c_summary: pd.DataFrame,
    d_summary: pd.DataFrame,
    e_summary: pd.DataFrame,
    f_summary: pd.DataFrame,
    g_summary: pd.DataFrame,
    g_flags: pd.DataFrame,
) -> None:
    panel_a_summary(ab).to_csv(OUT_DIR / "panel_A_four_group_scatter_summary.csv", index=False)
    post_summary.to_csv(OUT_DIR / "panel_B_four_group_posterior_summary.csv", index=False)
    c_summary.to_csv(OUT_DIR / "panel_C_four_group_interval_decomposition_summary.csv", index=False)
    d_summary.to_csv(OUT_DIR / "panel_D_four_group_descriptor_summary.csv", index=False)
    e_summary.to_csv(OUT_DIR / "panel_E_alkaline_pm_branch_map_summary.csv", index=False)
    f_summary.to_csv(OUT_DIR / "panel_F_alkaline_pm_branch_descriptor_summary.csv", index=False)
    g_summary.to_csv(OUT_DIR / "panel_G_alkaline_pm_rule_enrichment_summary.csv", index=False)
    g_flags.to_csv(OUT_DIR / "panel_G_alkaline_pm_rule_flags_by_row.csv", index=False)
    ab.to_csv(OUT_DIR / "source_AB_current_same_panel_eta10_eta50_rows.csv", index=False)
    cd.to_csv(OUT_DIR / "source_CD_current_strict_bvir_offset_rows.csv", index=False)

    ab_counts = ab["figure6_group"].value_counts().reindex(GROUP_ORDER).fillna(0).astype(int)
    cd_counts = cd["figure6_group"].value_counts().reindex(GROUP_ORDER).fillna(0).astype(int)
    alk_ab = ab[ab["figure6_group"].eq("Alkaline PM")]
    alk_cd = cd[cd["figure6_group"].eq("Alkaline PM")]
    both_ab = alk_ab[alk_ab["alkaline_pm_branch"].eq("both_better")]
    rem_ab = alk_ab[alk_ab["alkaline_pm_branch"].eq("remaining_alkaline_pm")]
    both_cd = alk_cd[alk_cd["alkaline_pm_branch"].eq("both_better")]
    rem_cd = alk_cd[alk_cd["alkaline_pm_branch"].eq("remaining_alkaline_pm")]

    messages = [
        ("A", "The four broad groups show that Pt/C-relative low-current and high-current behavior do not collapse to a single universal line."),
        ("B", "Bayesian slope/intercept summaries quantify the broad-group Δη₅₀ versus Δη₁₀ trends without drawing extra fitted lines over panel A."),
        ("C", "The group-level Δ(η₅₀−η₁₀) interval separates into strict-BV and empirical iR contributions; Eoffset cancels from this interval."),
        ("D", "Alkaline PM is distinct in interval-driving descriptors, especially in the Tafel-scale term and iR interval; baseline/intercept is secondary context."),
        ("E", "Within alkaline PM, both_better is the stricter branch defined by η₁₀ and η₅₀ both beating same-panel Pt/C."),
        ("F", "The alkaline PM both_better branch differs from the remaining alkaline PM rows in posterior trend, empirical iR interval, BV-derived Tafel scale, and exact strict-BV interval contribution."),
        ("G", "The both_better branch is enriched in rule-level catalyst motifs; these are associations, not causal proof."),
    ]
    message_text = "\n".join(f"- Panel {p}: {m}" for p, m in messages)

    rule_text = "\n".join(
        f"- {r.rule_category}: {r.exact_definition}"
        for r in g_summary.itertuples(index=False)
    )
    count_text = "\n".join(
        f"- {g}: AB n={int(ab_counts[g])}; CD n={int(cd_counts[g])}"
        for g in GROUP_ORDER
    )
    posterior_text = "\n".join(
        f"- {r.figure6_group}: slope={r.slope_median:.2f} [{r.slope_q025:.2f}, {r.slope_q975:.2f}], "
        f"intercept={r.intercept_median_mV:.1f} mV [{r.intercept_q025_mV:.1f}, {r.intercept_q975_mV:.1f}]"
        for r in post_summary.itertuples(index=False)
    )
    g_text = "\n".join(
        f"- {r.rule_category}: both_better {int(r.both_better_feature_count)}/{int(r.both_better_total_rows)} "
        f"({100*r.both_better_branch_fraction:.1f}%) vs remaining {int(r.remaining_feature_count)}/{int(r.remaining_total_rows)} "
        f"({100*r.remaining_branch_fraction:.1f}%)."
        for r in g_summary.itertuples(index=False)
    )

    def public_path(path: Path) -> str:
        try:
            return path.resolve().relative_to(ROOT.resolve()).as_posix()
        except ValueError:
            return path.name

    ab_file_public = public_path(AB_FILE)
    cd_file_public = public_path(CD_FILE)
    out_png_public = public_path(OUT_PNG)

    report = dedent(
        f"""
        # Main-Text Figure 6 Package, 2026-06-19 panel-F BV-interval package

        ## Inputs
        - AB same-panel Pt/C η10/η50 table: `{ab_file_public}`
        - CD strict-BV+iR+Eoffset decomposition table: `{cd_file_public}`
        - Output PNG: `{out_png_public}`

        ## Exact Counts
        - Panel A/B use AB rows: n={len(ab)}, cases={ab['case_rel_path'].nunique()}.
        - Panel C/D use CD rows: n={len(cd)}, cases={cd['case_rel_path'].nunique()}.
        - Panel E/G use alkaline PM AB rows: n={len(alk_ab)}, cases={alk_ab['case_rel_path'].nunique()}.
        - Panel F uses alkaline PM CD rows: n={len(alk_cd)}, cases={alk_cd['case_rel_path'].nunique()}.
        - Alkaline PM AB split: both_better n={len(both_ab)}, cases={both_ab['case_rel_path'].nunique()}; remaining_alkaline_pm n={len(rem_ab)}, cases={rem_ab['case_rel_path'].nunique()}.
        - Alkaline PM CD split: both_better n={len(both_cd)}, cases={both_cd['case_rel_path'].nunique()}; remaining_alkaline_pm n={len(rem_cd)}, cases={rem_cd['case_rel_path'].nunique()}.

        Broad group counts:
        {count_text}

        ## Exact both_better Definition
        `both_better` is defined only inside alkaline PM rows as: candidate Δη10 vs same-panel Pt/C < 0 and candidate Δη50 vs same-panel Pt/C < 0. In the current tables this is the `both_better_global == True` flag for rows with `figure6_group == Alkaline PM`. `remaining_alkaline_pm` is every other alkaline PM row.

        ## Panel Messages
        {message_text}

        ## Panel B Posterior Summary
        {posterior_text}

        ## Panel G Metadata Categories
        {rule_text}

        Panel G enrichment counts:
        {g_text}

        ## Readability Changes Versus The Old Figure 6
        - Panel A is now a clean four-group scatter without fitted lines; the line evidence is moved to panel B.
        - Panel B uses interval/dot posterior summaries instead of dense KDE curves.
        - Panel C replaces the old busy BV+iR scatter with a direct mean contribution decomposition by group.
        - Panel D separates interval-driving descriptors from secondary baseline/intercept context.
        - Panels E and F isolate the alkaline PM both_better branch after the broad-group panels establish the context.
        - Panel G uses rule-level metadata categories instead of singleton catalyst identities or raw elemental frequencies.
        - Metadata language is intentionally enrichment/association-based; no causal mechanism is claimed from these literature-derived features.

        ## Scientific Guardrails
        - Eoffset is not plotted as an interval contributor because it is current-independent and cancels from Δ(η50−η10).
        - The intercept/baseline descriptor is kept secondary because it does not drive the 10-to-50 mA interval by itself.
        - The strict-BV interval interpretation is tied mainly to the Tafel-scale term `(bBV,cand−bBV,Pt/C)log10(5)`.
        """
    ).strip()
    clean_messages = [
        ("A", "The four broad groups show the Pt/C-relative eta10/eta50 distribution."),
        ("B", "Bayesian fitted-line posterior densities quantify broad-group Delta eta50 versus Delta eta10 trends without crowding panel A."),
        ("C", "The joint scatter and marginal histograms show how Delta(eta50-eta10) separates into strict-BV and empirical iR contributions; Eoffset cancels from this interval."),
        ("D", "Four-group fitted descriptors are shown as scatter/violin distributions with median and IQR markers."),
        ("E", "Within alkaline PM, both_better is the stricter branch defined by eta10 and eta50 both beating same-panel Pt/C."),
        ("F", "The alkaline PM both_better branch is compared with the remaining alkaline PM rows using fitted descriptor distributions plus a branch-level slope posterior."),
        ("G", "The both_better branch is compared with remaining alkaline PM rows by rule-level catalyst metadata categories."),
    ]
    clean_message_text = "\n".join(f"- Panel {p}: {m}" for p, m in clean_messages)
    report = dedent(
        f"""
        # Main-Text Figure 6 Package, 2026-06-19 panel-F BV-interval package

        ## Inputs
        - AB same-panel Pt/C eta10/eta50 table: `{ab_file_public}`
        - CD strict-BV+iR+Eoffset decomposition table: `{cd_file_public}`
        - Panel D/F bBV descriptors use `fixed_neff2_cand_b_tafel_mV_dec` and same-panel contrasts recomputed from fixed-neff2 candidate and Pt/C values.
        - Output PNG: `{out_png_public}`

        ## Exact Counts
        - Panel A/B use AB rows: n={len(ab)}, cases={ab['case_rel_path'].nunique()}.
        - Panel C/D use CD rows: n={len(cd)}, cases={cd['case_rel_path'].nunique()}.
        - Panel E/G use alkaline PM AB rows: n={len(alk_ab)}, cases={alk_ab['case_rel_path'].nunique()}.
        - Panel F uses alkaline PM CD rows for fitted descriptors: n={len(alk_cd)}, cases={alk_cd['case_rel_path'].nunique()}, and alkaline PM AB rows for the branch slope posterior: n={len(alk_ab)}, cases={alk_ab['case_rel_path'].nunique()}.
        - Alkaline PM AB split: both_better n={len(both_ab)}, cases={both_ab['case_rel_path'].nunique()}; remaining_alkaline_pm n={len(rem_ab)}, cases={rem_ab['case_rel_path'].nunique()}.
        - Alkaline PM CD split: both_better n={len(both_cd)}, cases={both_cd['case_rel_path'].nunique()}; remaining_alkaline_pm n={len(rem_cd)}, cases={rem_cd['case_rel_path'].nunique()}.

        Broad group counts:
        {count_text}

        ## Exact both_better Definition
        `both_better` is defined only inside alkaline PM rows as: candidate Delta eta10 vs same-panel Pt/C < 0 and candidate Delta eta50 vs same-panel Pt/C < 0. In the current tables this is the `both_better_global == True` flag for rows with `figure6_group == Alkaline PM`. `remaining_alkaline_pm` is every other alkaline PM row.

        ## Panel Messages
        {clean_message_text}

        ## Panel B Posterior Summary
        {posterior_text}

        ## Panel G Metadata Categories
        {rule_text}

        Panel G enrichment counts:
        {g_text}

        ## Readability Changes Versus The Previous Draft
        - Panel D/F descriptor statistics now use the strict fixed-neff2 BV-derived Tafel scale rather than the legacy alpha05/free-a_app descriptor.
        - Panel B restores the old posterior-density/KDE style for slope and intercept.
        - Panel C restores the joint strict-BV versus empirical-iR contribution scatter with marginal histograms.
        - Panel D keeps scatter/violin descriptor distributions for broad groups; panel F replaces the secondary intercept subplot with an alkaline-PM branch slope posterior and uses exact strict-BV interval contribution as the fourth branch descriptor.
        - Panel letters were realigned to panel bounds and no longer clip at the top of the canvas.
        - The figure keeps the seven-panel A-G story while returning the older visual grammar for posterior and descriptor panels.

        ## Scientific Guardrails
        - Eoffset is not plotted as an interval contributor because it is current-independent and cancels from Delta(eta50-eta10).
        - The intercept/baseline descriptor is kept secondary because it does not drive the 10-to-50 mA interval by itself.
        - The strict-BV interval interpretation is tied mainly to the Tafel-scale term `(bBV,cand-bBV,Pt/C)log10(5)`.
        """
    ).strip()
    OUT_REPORT.write_text(report.replace("\n        ", "\n"), encoding="utf-8")


def main() -> None:
    ab, cd = load_data()
    posterior_draws, post_summary = compute_posteriors(ab)
    branch_draws, branch_summary = compute_alkaline_pm_branch_posteriors(ab)

    fig = plt.figure(figsize=(16.6, 16.8))
    gs = GridSpec(4, 2, figure=fig, height_ratios=[1.03, 1.37, 1.08, 1.00], hspace=0.24, wspace=0.16)

    ax_a = fig.add_subplot(gs[0, 0])
    panel_a(ax_a, ab)
    ax_b1, ax_b2 = panel_b(fig, gs[0, 1], posterior_draws)

    ax_c, ax_c_top, ax_c_right, c_summary = panel_c(fig, gs[1, 0], cd)
    d_axes, d_summary = panel_d_or_f(fig, gs[1, 1], cd, "figure6_group", "Four-group fitted descriptors")

    ax_e = fig.add_subplot(gs[2, 0])
    e_summary = panel_e(ax_e, ab)
    alk_cd = cd[cd["figure6_group"].eq("Alkaline PM")].copy()
    f_axes, f_summary = panel_f(fig, gs[2, 1], alk_cd, branch_draws, branch_summary)

    ax_g = fig.add_subplot(gs[3, :])
    g_summary, g_flags = metadata_rule_table(ab)
    panel_g(ax_g, g_summary)

    fig.subplots_adjust(left=0.082, right=0.988, top=0.965, bottom=0.060)
    add_panel_label(fig, ax_a, "A")
    add_panel_label(fig, [ax_b1, ax_b2], "B", dx=0.052, dy=0.018)
    add_panel_label(fig, [ax_c, ax_c_top, ax_c_right], "C")
    add_panel_label(fig, d_axes, "D")
    add_panel_label(fig, ax_e, "E")
    add_panel_label(fig, f_axes, "F")
    add_panel_label(fig, ax_g, "G")

    fig.savefig(OUT_PNG, dpi=450)
    plt.close(fig)

    write_outputs(ab, cd, post_summary, c_summary, d_summary, e_summary, f_summary, g_summary, g_flags)
    print(f"Wrote {OUT_PNG}")
    print(f"Wrote {OUT_REPORT}")
    print(f"AB rows: {len(ab)}; CD rows: {len(cd)}")


if __name__ == "__main__":
    main()
