from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.ticker import NullLocator


BASE = Path(__file__).resolve().parent
OUT = BASE / "Figure_1_lsv_source_plot_compact.png"


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

    x = np.linspace(1.24, 1.76, 500)
    co_nc = 10 ** (-2.95 + 3.72 / (1 + np.exp(-27.0 * (x - 1.405))))
    pt_c = 10 ** (-3.25 + 3.25 / (1 + np.exp(-24.0 * (x - 1.485))))

    fig, ax = plt.subplots(figsize=(3.15, 2.35), dpi=220, facecolor="white")
    ax.plot(x, co_nc, color="#f05a28", lw=1.7, label="Co-N-C")
    ax.plot(x, pt_c, color="#2f66b3", lw=1.7, label="Pt/C")

    ax.set_yscale("log")
    ax.set_xlim(1.2, 1.8)
    ax.set_ylim(1e-3, 1e1)
    ax.set_xticks([1.2, 1.4, 1.6, 1.8])
    ax.set_yticks([1e-3, 1e-2, 1e-1, 1e0, 1e1])

    ax.yaxis.set_minor_locator(NullLocator())
    ax.set_xlabel("E (V vs RHE)", fontsize=9.5, fontweight="bold", color="black", labelpad=3)
    ax.set_ylabel(r"$j$ (mA cm$^{-2}$)", fontsize=9.5, fontweight="bold", color="black", labelpad=3)
    ax.tick_params(axis="both", which="major", labelsize=8, width=0.8, length=3.0, color="black", labelcolor="black", pad=2)
    for tick_label in ax.get_xticklabels() + ax.get_yticklabels():
        tick_label.set_fontweight("bold")
        tick_label.set_color("black")

    for side in ("left", "bottom", "right", "top"):
        ax.spines[side].set_visible(True)
        ax.spines[side].set_color("black")
        ax.spines[side].set_linewidth(0.85)

    leg = ax.legend(
        frameon=False,
        fontsize=7.2,
        loc="center right",
        bbox_to_anchor=(0.94, 0.43),
        handlelength=1.5,
        handletextpad=0.5,
    )
    for line in leg.get_lines():
        line.set_linewidth(1.8)

    fig.tight_layout(pad=0.28)
    fig.savefig(OUT, dpi=220, facecolor="white")
    plt.close(fig)
    print(f"Wrote {OUT.name}")


if __name__ == "__main__":
    main()
