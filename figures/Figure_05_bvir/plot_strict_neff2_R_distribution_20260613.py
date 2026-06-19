from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from publication_plot_style import apply_publication_style, save_publication_figure


HERE = Path(__file__).resolve().parent
IN_CSV = HERE / "strict_neff2_publication_ABCDEF_20260612_panel_EF_descriptors.csv"
OUT_STEM = HERE / "strict_neff2_R_distribution_20260613"

GROUPS = ["PM", "Non-PM"]
COLORS = {"PM": "#F28E2B", "Non-PM": "#4C78A8"}


def summarize(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for group, sub in df.groupby("pm_group"):
        if group not in GROUPS:
            continue
        for field, label in [
            ("R_eff", "R_eff_ohm_cm2"),
            ("D_R_mV", "D_R_mV"),
        ]:
            s = pd.to_numeric(sub[field], errors="coerce").dropna()
            rows.append(
                {
                    "group": group,
                    "metric": label,
                    "n": int(len(s)),
                    "n_nonzero": int((s.abs() > 1e-9).sum()),
                    "median": float(s.median()),
                    "p75": float(s.quantile(0.75)),
                    "p90": float(s.quantile(0.90)),
                    "p95": float(s.quantile(0.95)),
                    "p99": float(s.quantile(0.99)),
                    "max": float(s.max()),
                }
            )
    return pd.DataFrame(rows)


def draw_hist(ax, df: pd.DataFrame, field: str, bins: np.ndarray, xlabel: str, title: str, xlim: tuple[float, float]) -> None:
    for group in GROUPS:
        sub = df[df["pm_group"].eq(group)]
        values = pd.to_numeric(sub[field], errors="coerce").dropna().to_numpy()
        ax.hist(
            values,
            bins=bins,
            density=True,
            histtype="step",
            linewidth=1.8,
            color=COLORS[group],
            label=f"{group} (n={len(values)})",
        )
        med = np.median(values)
        p90 = np.quantile(values, 0.90)
        ax.axvline(med, color=COLORS[group], linestyle="-", linewidth=1.0, alpha=0.9)
        ax.axvline(p90, color=COLORS[group], linestyle="--", linewidth=1.0, alpha=0.8)
    ax.set_xlim(*xlim)
    ax.set_xlabel(xlabel)
    ax.set_ylabel("Density")
    ax.set_title(title, fontweight="bold", pad=4)
    ax.legend(frameon=False, loc="upper right")


def main() -> None:
    apply_publication_style()
    df = pd.read_csv(IN_CSV)
    df = df[df["pm_group"].isin(GROUPS)].copy()
    df["R_eff"] = pd.to_numeric(df["R_eff"], errors="coerce")
    df["D_R_mV"] = pd.to_numeric(df["D_R_mV"], errors="coerce")

    stats = summarize(df)
    stats.to_csv(OUT_STEM.with_name(OUT_STEM.name + "_summary.csv"), index=False)

    fig, axes = plt.subplots(1, 2, figsize=(7.0, 2.55), constrained_layout=True)
    draw_hist(
        axes[0],
        df,
        "R_eff",
        np.linspace(0, 5.0, 46),
        r"$R_{\mathrm{eff}}$ ($\Omega$ cm$^2$)",
        r"Fitted current-dependent term",
        (0, 5.0),
    )
    draw_hist(
        axes[1],
        df,
        "D_R_mV",
        np.linspace(0, 400.0, 49),
        r"$D_R = R_{\mathrm{eff}} |j|_{\max}$ (mV)",
        r"Maximum fitted iR-like loss",
        (0, 400.0),
    )
    for ax in axes:
        ax.text(
            0.02,
            0.96,
            "solid: median; dashed: P90",
            transform=ax.transAxes,
            ha="left",
            va="top",
            fontsize=7,
            color="#444444",
        )
    save_publication_figure(fig, OUT_STEM.with_suffix(".png"))
    plt.close(fig)
    print(OUT_STEM.with_suffix(".png"))
    print(OUT_STEM.with_name(OUT_STEM.name + "_summary.csv"))


if __name__ == "__main__":
    main()
