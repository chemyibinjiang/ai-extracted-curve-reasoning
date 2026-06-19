from __future__ import annotations

from pathlib import Path

import matplotlib as mpl


PUBLICATION_DPI = 300
R2_LABEL = "R²"


def apply_publication_style() -> None:
    """Apply the shared plotting defaults for manuscript-ready figures."""
    mpl.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Arial", "DejaVu Sans"],
            "mathtext.fontset": "custom",
            "mathtext.rm": "Arial",
            "mathtext.it": "Arial:italic",
            "mathtext.bf": "Arial:bold",
            "mathtext.default": "regular",
            "font.size": 9,
            "axes.titlesize": 10,
            "axes.titleweight": "bold",
            "axes.labelsize": 9,
            "xtick.labelsize": 8,
            "ytick.labelsize": 8,
            "legend.fontsize": 8,
            "figure.titlesize": 12,
            "axes.linewidth": 0.8,
            "lines.linewidth": 1.4,
            "lines.markersize": 4,
            "patch.linewidth": 0.6,
            "xtick.direction": "out",
            "ytick.direction": "out",
            "xtick.major.width": 0.8,
            "ytick.major.width": 0.8,
            "xtick.major.size": 3.0,
            "ytick.major.size": 3.0,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "figure.dpi": 150,
            "savefig.dpi": PUBLICATION_DPI,
            "savefig.bbox": "tight",
            "savefig.pad_inches": 0.04,
            "savefig.facecolor": "white",
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "svg.fonttype": "none",
        }
    )


def save_publication_figure(
    fig,
    path: str | Path,
    *,
    dpi: int = PUBLICATION_DPI,
    pdf: bool = True,
    svg: bool = True,
) -> None:
    """Save a high-resolution PNG plus editable-font PDF/SVG companions."""
    out_path = Path(path)
    fig.savefig(out_path, dpi=dpi, bbox_inches="tight", facecolor="white")
    if pdf:
        fig.savefig(out_path.with_suffix(".pdf"), bbox_inches="tight", facecolor="white")
    if svg:
        fig.savefig(out_path.with_suffix(".svg"), bbox_inches="tight", facecolor="white")
