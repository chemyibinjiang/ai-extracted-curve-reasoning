from __future__ import annotations

import base64
import csv
from io import BytesIO
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib import patches
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from PIL import Image, ImageDraw, ImageFont, JpegImagePlugin  # noqa: F401

from build_selected_panel_overlays import build_selected_overlays


BASE = Path(__file__).resolve().parent
OVERLAY_DIR = BASE / "anchored_overlays_labeled_offset_axes"
OUT_BASE = BASE / "Figure_3_synthetic_benchmark"
REPO_ROOT = BASE.parents[1]

PAGE_W = 6000
MARGIN = 130
GAP = 70

TEXT = (18, 24, 33)
MUTED = (75, 87, 106)
BORDER = (202, 214, 226)
GRID = (222, 230, 239)
GREEN = (22, 190, 125)
BLUE = (45, 117, 188)
MAGENTA = (218, 47, 145)
BLACK = (18, 24, 33)


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    name = "arialbd.ttf"
    path = Path("C:/Windows/Fonts") / name
    return ImageFont.truetype(str(path), size=size)


def text_size(draw: ImageDraw.ImageDraw, text: str, fnt: ImageFont.FreeTypeFont) -> tuple[int, int]:
    box = draw.textbbox((0, 0), text, font=fnt)
    return box[2] - box[0], box[3] - box[1]


def rounded(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], radius: int, fill, outline=None, width: int = 1):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def mpl_color(rgb: tuple[int, int, int]) -> tuple[float, float, float]:
    return tuple(channel / 255 for channel in rgb)


def paste_fit(canvas: Image.Image, src: Image.Image, box: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    x0, y0, x1, y1 = box
    max_w = x1 - x0
    max_h = y1 - y0
    scale = min(max_w / src.width, max_h / src.height)
    new_w = int(src.width * scale)
    new_h = int(src.height * scale)
    img = src.resize((new_w, new_h), Image.Resampling.LANCZOS)
    px = x0 + (max_w - new_w) // 2
    py = y0 + (max_h - new_h) // 2
    canvas.paste(img, (px, py))
    return px, py, px + new_w, py + new_h


def render_matplotlib(fig: Figure) -> Image.Image:
    canvas = FigureCanvasAgg(fig)
    canvas.draw()
    w, h = canvas.get_width_height()
    rgba = np.frombuffer(canvas.buffer_rgba(), dtype=np.uint8).reshape((h, w, 4))
    plt.close(fig)
    return Image.fromarray(rgba, "RGBA").convert("RGB")


def load_v2_curve_metrics() -> tuple[np.ndarray, np.ndarray]:
    candidates = (
        REPO_ROOT
        / "benchmark_data"
        / "benchmark_curve_extraction"
        / "agentic_ablation"
        / "archived_staged_v2_evaluation"
        / "curve_answer_eval_pixel_distance_v2.csv",
        REPO_ROOT
        / "data"
        / "benchmark_curve_extraction"
        / "peeragent_ground_truth"
        / "focused_curve_extraction_set_v4_1_fixed"
        / "_private_eval"
        / "curve_answer_eval_pixel_distance_v2.csv",
    )
    for path in candidates:
        if not path.exists():
            continue
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
        median_distances = np.asarray(
            [float(row["median_dist_px"]) for row in rows], dtype=float
        )
        p95_distances = np.asarray(
            [float(row["p95_dist_px"]) for row in rows], dtype=float
        )
        return median_distances, p95_distances
    raise FileNotFoundError("Could not locate archived staged v2 curve metrics")


def make_b_chart(width: int, height: int) -> Image.Image:
    families = ["LSV", "Kinetic", "UV-Vis", "Raman", "XRD", "GC"]
    curves = [31, 28, 25, 23, 15, 15]
    colors = [BLUE, (47, 141, 88), (222, 162, 31), (126, 82, 210), (234, 88, 19), (49, 155, 151)]

    img = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(img)

    card_y = 62
    card_h = 270
    gap = 28
    card_w = (width - 2 * 78 - 2 * gap) // 3
    cards = [
        ("Panels", "60", "6 families x 10"),
        ("Curves", "137", "extracted total"),
        ("Identity match", "137/137", "correct legend identity"),
    ]
    for idx, (label, value, note) in enumerate(cards):
        x = 78 + idx * (card_w + gap)
        fill = (238, 250, 245) if idx == 2 else (247, 249, 252)
        outline = (138, 210, 181) if idx == 2 else BORDER
        rounded(draw, (x, card_y, x + card_w, card_y + card_h), 12, fill, outline, 3)
        accent = (47, 141, 88) if idx == 2 else BLUE
        draw.rectangle((x, card_y, x + 16, card_y + card_h), fill=accent)
        draw.text((x + 48, card_y + 38), label, font=font(52, True), fill=MUTED)
        draw.text((x + 48, card_y + 105), value, font=font(90, True), fill=TEXT)
        draw.text((x + 48, card_y + 214), note, font=font(40, True), fill=MUTED)

    bar_x0 = 110
    bar_x1 = width - 110
    bar_y0 = 505
    bar_h = 165
    total = sum(curves)
    draw.text((bar_x0, 420), "Extracted curves by family", font=font(68, True), fill=TEXT)
    draw.text((bar_x1 - 420, 432), "total n = 137", font=font(56, True), fill=MUTED)

    x = bar_x0
    centers = []
    for family, value, color in zip(families, curves, colors):
        w = int(round((bar_x1 - bar_x0) * value / total))
        if family == families[-1]:
            w = bar_x1 - x
        rounded(draw, (x, bar_y0, x + w, bar_y0 + bar_h), 6, color, None)
        label = f"{family} {value}"
        segment_font = font(48, True)
        tw, th = text_size(draw, label, segment_font)
        draw.text((x + (w - tw) // 2, bar_y0 + (bar_h - th) // 2 - 3), label, font=segment_font, fill="white")
        centers.append((x + w // 2, color, family))
        x += w

    axis_y = bar_y0 + bar_h + 48
    draw.line((bar_x0, axis_y, bar_x1, axis_y), fill=GRID, width=3)
    for center, color, family in centers:
        draw.ellipse((center - 10, axis_y - 10, center + 10, axis_y + 10), fill=color)
        family_font = font(48, True)
        tw, _ = text_size(draw, family, family_font)
        draw.text((center - tw // 2, axis_y + 22), family, font=family_font, fill=MUTED)

    id_y = 870
    rounded(draw, (110, id_y, width - 110, id_y + 220), 12, (238, 250, 245), (138, 210, 181), 3)
    draw.text((158, id_y + 34), "Agent curve-legend identity routing", font=font(68, True), fill=(47, 141, 88))
    draw.text(
        (158, id_y + 125),
        "All extracted curves were mapped to the corresponding legend identity.",
        font=font(54, True),
        fill=TEXT,
    )
    return img


def make_c_chart(width: int, height: int) -> Image.Image:
    median_distances, p95_distances = load_v2_curve_metrics()
    counts, edges = np.histogram(median_distances, bins=np.linspace(0, 2.0, 15))
    median_value = float(np.median(median_distances))
    p90_value = float(np.quantile(median_distances, 0.90))
    median_p95_value = float(np.median(p95_distances))

    img = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(img)

    chart_x0 = 150
    chart_x1 = width - 130
    chart_top = 120
    axis_y = 640
    max_h = 430

    draw.text((chart_x0, 40), "Distance distribution", font=font(64, True), fill=TEXT)
    draw.text((chart_x1 - 650, 46), "lower is better", font=font(58, True), fill=MUTED)

    def xmap(value: float) -> int:
        return int(chart_x0 + (value / 2.0) * (chart_x1 - chart_x0))

    for tick in [0, 0.5, 1.0, 1.5, 2.0]:
        x = xmap(tick)
        draw.line((x, chart_top, x, axis_y), fill=GRID, width=4)
        tick_label = f"{tick:g}"
        tick_font = font(48, True)
        tw, _ = text_size(draw, tick_label, tick_font)
        draw.text((x - tw // 2, axis_y + 28), tick_label, font=tick_font, fill=MUTED)

    draw.line((chart_x0, axis_y, chart_x1, axis_y), fill=TEXT, width=4)
    draw.line((chart_x0, chart_top, chart_x0, axis_y), fill=TEXT, width=4)

    max_count = max(counts)
    bar_fill = (113, 161, 212)
    for left, right, count in zip(edges[:-1], edges[1:], counts):
        x0 = xmap(float(left)) + 5
        x1 = xmap(float(right)) - 5
        bar_h = int((count / max_count) * max_h) if count else 0
        if bar_h > 0:
            rounded(draw, (x0, axis_y - bar_h, x1, axis_y), 3, bar_fill, None)

    median_x = xmap(median_value)
    p90_x = xmap(p90_value)
    draw.line((median_x, chart_top - 5, median_x, axis_y), fill=(18, 67, 126), width=10)
    draw.line((p90_x, chart_top - 5, p90_x, axis_y), fill=(230, 82, 18), width=10)
    draw.text((median_x + 28, chart_top + 55), f"median {median_value:.2f} px", font=font(62, True), fill=(18, 67, 126))
    draw.text((p90_x + 28, chart_top + 180), f"p90 {p90_value:.2f} px", font=font(62, True), fill=(230, 82, 18))

    x_label = "Per-curve median point-to-answer distance (pixels)"
    x_label_font = font(50, True)
    tw, _ = text_size(draw, x_label, x_label_font)
    draw.text(((width - tw) // 2, axis_y + 106), x_label, font=x_label_font, fill=MUTED)

    metrics = [
        ("Curves", str(len(median_distances))),
        ("Median", f"{median_value:.2f} px"),
        ("Median p95", f"{median_p95_value:.2f} px"),
    ]
    chip_gap = 24
    chip_x0 = 112
    chip_y0 = 905
    chip_h = 185
    chip_w = (width - 2 * chip_x0 - 2 * chip_gap) // 3
    for idx, (label, value) in enumerate(metrics):
        x = chip_x0 + idx * (chip_w + chip_gap)
        fill = (247, 249, 252)
        outline = BORDER
        accent = BLUE
        if idx == 1:
            fill = (239, 246, 253)
            accent = (18, 67, 126)
        elif idx == 2:
            fill = (255, 246, 239)
            accent = (230, 82, 18)
        rounded(draw, (x, chip_y0, x + chip_w, chip_y0 + chip_h), 12, fill, outline, 3)
        draw.rectangle((x, chip_y0, x + 14, chip_y0 + chip_h), fill=accent)
        draw.text((x + 42, chip_y0 + 28), label, font=font(42, True), fill=MUTED)
        draw.text((x + 42, chip_y0 + 92), value, font=font(58, True), fill=TEXT)

    return img


def make_panel_a(width: int) -> Image.Image:
    examples = [
        ("a_lsv_04_anchored_points.png", "LSV", "LSV / polarization curve", BLUE),
        ("b_kinetic_time_course_10_anchored_points.png", "Kinetic", "Kinetic time course", (47, 141, 88)),
        ("c_uv_vis_02_anchored_points.png", "UV-Vis", "UV-Vis spectrum", (222, 162, 31)),
        ("d_raman_02_anchored_points.png", "Raman", "Raman spectrum", (126, 82, 210)),
        ("e_xrd_10_anchored_points.png", "XRD", "XRD pattern", (234, 88, 19)),
        ("f_gc_trace_03_anchored_points.png", "GC trace", "Co-eluting GC trace", (49, 155, 151)),
    ]
    tile_w = (width - 2 * MARGIN - GAP) // 2
    tile_header = 165
    tile_pad = 30
    max_image_h = 1900
    tile_h = tile_header + max_image_h + 36
    title_h = 180
    row_gap = 72
    out_h = title_h + 3 * tile_h + 2 * row_gap
    out = Image.new("RGB", (width, out_h), "white")
    draw = ImageDraw.Draw(out)

    draw.text((MARGIN, 22), "A", font=font(98, True), fill=TEXT)
    draw.text((MARGIN + 118, 42), "Different types of curves", font=font(86, True), fill=TEXT)

    pill_font = font(70, True)
    title_font = font(66, True)
    for idx, (filename, short, long, color) in enumerate(examples):
        row = idx // 2
        col = idx % 2
        x = MARGIN + col * (tile_w + GAP)
        y = title_h + row * (tile_h + row_gap)
        rounded(draw, (x, y, x + tile_w, y + tile_h), 12, "white", BORDER, 2)

        label_w = text_size(draw, short, pill_font)[0] + 74
        rounded(draw, (x + 24, y + 26, x + 24 + label_w, y + 126), 8, color, None)
        draw.text((x + 61, y + 37), short, font=pill_font, fill="white")
        draw.text((x + 24 + label_w + 40, y + 43), long, font=title_font, fill=TEXT)

        src = Image.open(OVERLAY_DIR / filename).convert("RGB")
        paste_fit(
            out,
            src,
            (x + tile_pad, y + tile_header, x + tile_w - tile_pad, y + tile_h - 20),
        )
    return out


def draw_header(draw: ImageDraw.ImageDraw) -> None:
    draw.text((MARGIN, 68), "Synthetic benchmark and extraction performance", font=font(76, True), fill=TEXT)
    draw.text(
        (MARGIN, 164),
        "Extracted points are overlaid on original curve strokes; recognized tick values are offset from the original axes, and curve identities are mapped to legends.",
        font=font(38),
        fill=MUTED,
    )
    y = 300
    draw.ellipse((MARGIN, y - 13, MARGIN + 26, y + 13), fill=GREEN, outline=(0, 115, 80), width=2)
    draw.text((MARGIN + 44, y - 23), "extracted sampled points", font=font(32), fill=TEXT)
    x = MARGIN + 690
    draw.line((x, y, x + 160, y), fill=BLUE, width=6)
    draw.text((x + 190, y - 23), "x tick values/grid", font=font(32), fill=BLUE)
    x += 760
    draw.line((x, y, x + 160, y), fill=MAGENTA, width=6)
    draw.text((x + 190, y - 23), "y tick values/grid", font=font(32), fill=MAGENTA)
    x += 820
    draw.line((x, y, x + 160, y), fill=BLACK, width=6)
    draw.text((x + 190, y - 23), "original curve stroke", font=font(32), fill=TEXT)


def main() -> None:
    build_selected_overlays()
    panel_a = make_panel_a(PAGE_W)
    full_card_w = PAGE_W - 2 * MARGIN
    bottom_card_w = (full_card_w - GAP) // 2
    b_chart = make_b_chart(bottom_card_w - 70, 1180)
    c_chart = make_c_chart(bottom_card_w - 70, 1180)

    header_h = 25
    panel_a_y = header_h
    b_y = panel_a_y + panel_a.height + 85
    b_title_h = 180
    bottom_card_h = 1300
    page_h = b_y + b_title_h + bottom_card_h + 95

    page = Image.new("RGB", (PAGE_W, page_h), "white")
    draw = ImageDraw.Draw(page)
    page.paste(panel_a, (0, panel_a_y))

    b_x = MARGIN
    b_w = bottom_card_w
    b_card_y = b_y + b_title_h
    draw.text((b_x, b_y), "B", font=font(108, True), fill=TEXT)
    draw.text((b_x + 132, b_y + 20), "Benchmark composition", font=font(78, True), fill=TEXT)
    rounded(draw, (b_x, b_card_y, b_x + b_w, b_card_y + bottom_card_h), 12, "white", BORDER, 2)
    paste_fit(page, b_chart, (b_x + 32, b_card_y + 36, b_x + b_w - 32, b_card_y + bottom_card_h - 34))

    c_x = MARGIN + bottom_card_w + GAP
    c_w = bottom_card_w
    c_card_y = b_card_y
    draw.text((c_x, b_y), "C", font=font(108, True), fill=TEXT)
    draw.text((c_x + 132, b_y + 20), "Point-level agreement", font=font(78, True), fill=TEXT)
    rounded(draw, (c_x, c_card_y, c_x + c_w, c_card_y + bottom_card_h), 12, "white", BORDER, 2)
    paste_fit(page, c_chart, (c_x + 32, c_card_y + 36, c_x + c_w - 32, c_card_y + bottom_card_h - 34))

    png = OUT_BASE.with_suffix(".png")
    tif = OUT_BASE.with_suffix(".tif")
    pdf = OUT_BASE.with_suffix(".pdf")
    svg = OUT_BASE.with_suffix(".svg")
    page.save(png, dpi=(300, 300))
    page.save(tif, dpi=(300, 300), compression="tiff_lzw")
    page.save(pdf, resolution=300.0)
    png_b64 = base64.b64encode(png.read_bytes()).decode("ascii")
    svg.write_text(
        f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{page.width}" height="{page.height}" viewBox="0 0 {page.width} {page.height}">
  <image width="{page.width}" height="{page.height}" href="data:image/png;base64,{png_b64}"/>
</svg>
""",
        encoding="utf-8",
    )
    for path in (png, tif, pdf, svg):
        print(f"Wrote {path.name}")


if __name__ == "__main__":
    main()
