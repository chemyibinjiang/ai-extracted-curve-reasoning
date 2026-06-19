from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import FancyBboxPatch


BASE = Path(__file__).resolve().parent
OUT = BASE / "Figure_1_lsv_source_plot.png"

BLUE = "#2567d5"
ORANGE = "#f04e1a"
TEXT = "#111827"
AXIS = "#4b5563"
BORDER = "#a8b2c0"


def main():
    plt.rcParams.update(
        {
            "font.family": "Arial",
            "font.weight": "bold",
            "axes.labelweight": "bold",
            "mathtext.default": "regular",
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )

    x = np.linspace(1.22, 1.74, 600)
    co_nc = 10 ** (-2.95 + 3.72 / (1 + np.exp(-25.5 * (x - 1.415))))
    pt_c = 10 ** (-3.25 + 3.25 / (1 + np.exp(-23.0 * (x - 1.505))))

    fig = plt.figure(figsize=(6.2, 4.8), dpi=300, facecolor="white")

    # Rounded outer frame, matching the manuscript schematic style.
    frame = FancyBboxPatch(
        (0.035, 0.045),
        0.93,
        0.90,
        boxstyle="round,pad=0.012,rounding_size=0.010",
        transform=fig.transFigure,
        linewidth=1.9,
        edgecolor=BORDER,
        facecolor="white",
        zorder=0,
    )
    fig.add_artist(frame)

    ax = fig.add_axes([0.30, 0.30, 0.52, 0.50], zorder=2)
    ax.plot(x, co_nc, color=ORANGE, lw=4.0, solid_capstyle="round")
    ax.plot(x, pt_c, color=BLUE, lw=4.0, solid_capstyle="round")

    ax.set_yscale("log")
    ax.set_xlim(1.20, 1.78)
    ax.set_ylim(1e-3, 1e1)
    ax.set_xticks([1.25, 1.50, 1.75])
    ax.set_xticklabels(["1.25", "1.50", "1.75"])
    ax.set_yticks([1e-3, 1e-1, 1e1])
    ax.set_yticklabels([r"$10^{-3}$", r"$10^{-1}$", r"$10^{1}$"])

    ax.set_xlabel("E (V vs RHE)", fontsize=22, color=TEXT, labelpad=10)
    ax.set_ylabel(r"j (mA cm$^{-2}$)", fontsize=22, color=TEXT, labelpad=12)
    ax.tick_params(axis="both", which="major", labelsize=17, width=2.2, length=7, color=AXIS, pad=7)
    ax.tick_params(axis="both", which="minor", length=0)

    for tick in ax.get_xticklabels() + ax.get_yticklabels():
        tick.set_fontweight("bold")
        tick.set_color(TEXT)

    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_linewidth(2.5)
        ax.spines[side].set_color(AXIS)

    ax.grid(False)

    # Inset legend, drawn manually so it stays clean at small size.
    ax.plot([1.335, 1.455], [8.5e-2, 8.5e-2], color=ORANGE, lw=4.0, solid_capstyle="butt", clip_on=False)
    ax.text(1.475, 7.1e-2, "Co-N-C", fontsize=17, fontweight="bold", color=TEXT, va="center")
    ax.plot([1.335, 1.455], [2.4e-2, 2.4e-2], color=BLUE, lw=4.0, solid_capstyle="butt", clip_on=False)
    ax.text(1.475, 2.0e-2, "Pt/C", fontsize=17, fontweight="bold", color=TEXT, va="center")

    fig.savefig(OUT, dpi=600, facecolor="white")
    plt.close(fig)
    print(f"Wrote {OUT.name}")


if __name__ == "__main__":
    main()
