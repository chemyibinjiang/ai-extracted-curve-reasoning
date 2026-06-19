from __future__ import annotations

import base64
from io import BytesIO
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from PIL import Image, ImageDraw, ImageFont, JpegImagePlugin  # noqa: F401


BASE = Path(__file__).resolve().parent
OUT_STEM = BASE / "Figure_1_article_source_card"

TEXT = (18, 24, 33)
MUTED = (72, 85, 104)
BORDER = (90, 126, 173)
BLUE = (35, 99, 190)
ORANGE = (238, 92, 42)


def font(size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", size=size)


def text_size(draw: ImageDraw.ImageDraw, text: str, fnt: ImageFont.FreeTypeFont) -> tuple[int, int]:
    box = draw.textbbox((0, 0), text, font=fnt)
    return box[2] - box[0], box[3] - box[1]


def wrap_lines(draw: ImageDraw.ImageDraw, text: str, fnt: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = word if not current else f"{current} {word}"
        if text_size(draw, candidate, fnt)[0] <= max_width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def draw_wrapped(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, fnt: ImageFont.FreeTypeFont, fill, max_width: int, gap: int = 10):
    x, y = xy
    line_h = text_size(draw, "Ag", fnt)[1] + gap
    for idx, line in enumerate(wrap_lines(draw, text, fnt, max_width)):
        draw.text((x, y + idx * line_h), line, font=fnt, fill=fill)


def render_plot(width: int, height: int) -> Image.Image:
    plt.rcParams.update(
        {
            "font.family": "Arial",
            "font.weight": "bold",
            "axes.labelweight": "bold",
            "axes.titleweight": "bold",
            "mathtext.default": "regular",
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )
    x = np.linspace(1.22, 1.74, 300)
    co = 10 ** (-2.9 + 3.75 / (1 + np.exp(-24 * (x - 1.42))))
    pt = 10 ** (-3.15 + 3.45 / (1 + np.exp(-22 * (x - 1.50))))

    fig, ax = plt.subplots(figsize=(width / 300, height / 300), dpi=300)
    ax.plot(x, co, color=np.array(ORANGE) / 255, lw=2.2, label="Co-N-C")
    ax.plot(x, pt, color=np.array(BLUE) / 255, lw=2.2, label="Pt/C")
    ax.set_yscale("log")
    ax.set_xlim(1.2, 1.8)
    ax.set_ylim(1e-3, 1e1)
    ax.set_xlabel("E (V vs RHE)", fontsize=11, fontweight="bold", labelpad=4)
    ax.set_ylabel(r"j (mA cm$^{-2}$)", fontsize=11, fontweight="bold", labelpad=4)
    ax.tick_params(axis="both", labelsize=9, width=1.1, length=3.4, color="#555555")
    for tick in ax.get_xticklabels() + ax.get_yticklabels():
        tick.set_fontweight("bold")
        tick.set_color("#111827")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_linewidth(1.6)
        ax.spines[side].set_color("#555555")
    ax.legend(frameon=False, fontsize=9.5, loc="center right", bbox_to_anchor=(0.98, 0.38))
    fig.tight_layout(pad=0.35)
    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=300, facecolor="white")
    plt.close(fig)
    buf.seek(0)
    return Image.open(buf).convert("RGB").resize((width, height), Image.Resampling.LANCZOS)


def save_all(img: Image.Image):
    png = OUT_STEM.with_suffix(".png")
    tif = OUT_STEM.with_suffix(".tif")
    pdf = OUT_STEM.with_suffix(".pdf")
    svg = OUT_STEM.with_suffix(".svg")
    img.save(png, dpi=(600, 600))
    img.save(tif, dpi=(600, 600), compression="tiff_lzw")
    img.save(pdf, resolution=600)
    buf = BytesIO()
    img.save(buf, format="PNG")
    encoded = base64.b64encode(buf.getvalue()).decode("ascii")
    svg.write_text(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{img.width}" height="{img.height}" viewBox="0 0 {img.width} {img.height}">'
        f'<image width="{img.width}" height="{img.height}" href="data:image/png;base64,{encoded}"/></svg>\n',
        encoding="utf-8",
    )
    for path in (png, tif, pdf, svg):
        print(f"Wrote {path.name}")


def main():
    w, h = 980, 1180
    img = Image.new("RGB", (w, h), "white")
    draw = ImageDraw.Draw(img)

    margin = 45
    draw.rounded_rectangle((margin, margin, w - margin, h - margin), radius=40, fill=(252, 253, 255), outline=BORDER, width=6)

    # Header badge and title.
    badge = (margin + 45, margin + 42, margin + 125, margin + 122)
    draw.ellipse(badge, fill=BLUE)
    tw, th = text_size(draw, "1", font(44))
    draw.text((badge[0] + (badge[2] - badge[0] - tw) / 2, badge[1] + (badge[3] - badge[1] - th) / 2 - 4), "1", font=font(44), fill="white")
    draw_wrapped(
        draw,
        (margin + 165, margin + 41),
        "Article HTML / caption + figure panel",
        font(39),
        BLUE,
        w - margin * 2 - 215,
        gap=4,
    )

    caption = "Figure 2. LSV curves of Co-N-C and Pt/C in 0.1 M KHCO3. Scan rate: 5 mV s-1."
    draw_wrapped(draw, (margin + 72, margin + 205), caption, font(34), TEXT, w - margin * 2 - 144, gap=11)

    plot = render_plot(620, 455)
    plot_x = (w - plot.width) // 2 + 22
    plot_y = margin + 515
    draw.rounded_rectangle((plot_x - 18, plot_y - 18, plot_x + plot.width + 18, plot_y + plot.height + 18), radius=8, fill="white", outline=(170, 178, 190), width=4)
    img.paste(plot, (plot_x, plot_y))

    save_all(img)


if __name__ == "__main__":
    main()
