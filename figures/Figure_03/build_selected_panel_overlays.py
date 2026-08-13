from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageDraw, ImageFont


BASE = Path(__file__).resolve().parent
REPO = BASE.parent.parent
OVERLAY_DIR = BASE / "anchored_overlays_labeled_offset_axes"


def locate_benchmark_dir() -> Path:
    candidates = (
        REPO / "benchmark_data" / "benchmark_curve_extraction" / "benchmark_cases" / "focused_curve_extraction_set_v4_1_fixed",
        REPO / "data" / "benchmark_curve_extraction" / "benchmark_cases" / "focused_curve_extraction_set_v4_1_fixed",
    )
    for path in candidates:
        if path.exists():
            return path
    raise FileNotFoundError("Could not locate the focused benchmark case directory")


BENCHMARK_DIR = locate_benchmark_dir()

GREEN = (22, 190, 125)
DARK_GREEN = (0, 108, 78)
X_BLUE = (42, 126, 215)
Y_MAGENTA = (218, 47, 145)
X_GRID = (126, 181, 240, 112)
Y_GRID = (235, 145, 202, 112)
TEXT = (18, 24, 33)
WHITE = (255, 255, 255)

SELECTED_CASES = [
    ("a_lsv_04", "a_lsv_04_anchored_points.png"),
    ("b_kinetic_time_course_10", "b_kinetic_time_course_10_anchored_points.png"),
    ("c_uv_vis_02", "c_uv_vis_02_anchored_points.png"),
    ("d_raman_02", "d_raman_02_anchored_points.png"),
    ("e_xrd_10", "e_xrd_10_anchored_points.png"),
    ("f_gc_trace_03", "f_gc_trace_03_anchored_points.png"),
]


def font(size: int, bold: bool = True) -> ImageFont.FreeTypeFont:
    name = "arialbd.ttf" if bold else "arial.ttf"
    path = Path("C:/Windows/Fonts") / name
    return ImageFont.truetype(str(path), size=size)


def case_dir(case_id: str) -> Path:
    for child in BENCHMARK_DIR.iterdir():
        if child.is_dir() and child.name.lower() == case_id.lower():
            return child
    raise FileNotFoundError(f"Benchmark case not found: {case_id}")


def response_paths(case_id: str) -> tuple[Path, Path, Path]:
    folder = case_dir(case_id)
    normalized = case_id.lower()
    run_name = f"figure_{normalized}__panel_{normalized}"
    anchoring = folder / "codex_panel_anchoring" / "panel_runs" / run_name / "response.json"
    curve = folder / "codex_panel_curve_extraction" / "panel_runs" / run_name / "response.json"
    panel_crop = folder / "codex_panel_anchoring" / "panel_runs" / run_name / "panel_crop.png"
    return anchoring, curve, panel_crop


def dashed_line(
    draw: ImageDraw.ImageDraw,
    start: tuple[float, float],
    end: tuple[float, float],
    fill: tuple[int, int, int, int],
    width: int = 2,
    dash: int = 22,
    gap: int = 18,
) -> None:
    x0, y0 = start
    x1, y1 = end
    dx = x1 - x0
    dy = y1 - y0
    length = (dx * dx + dy * dy) ** 0.5
    if length == 0:
        return
    ux = dx / length
    uy = dy / length
    distance = 0.0
    while distance < length:
        next_distance = min(distance + dash, length)
        sx = x0 + ux * distance
        sy = y0 + uy * distance
        ex = x0 + ux * next_distance
        ey = y0 + uy * next_distance
        draw.line((sx, sy, ex, ey), fill=fill, width=width)
        distance += dash + gap


def text_size(draw: ImageDraw.ImageDraw, label: str, fnt: ImageFont.FreeTypeFont) -> tuple[int, int]:
    box = draw.textbbox((0, 0), label, font=fnt)
    return box[2] - box[0], box[3] - box[1]


def label_box(
    draw: ImageDraw.ImageDraw,
    center: tuple[float, float],
    label: str,
    color: tuple[int, int, int],
    image_size: tuple[int, int],
    axis: str,
) -> None:
    fnt = font(24, True)
    tw, th = text_size(draw, label, fnt)
    pad_x = 9
    pad_y = 5
    w = tw + 2 * pad_x
    h = th + 2 * pad_y
    cx, cy = center
    if axis == "x":
        x0 = int(round(cx - w / 2))
        y0 = int(round(cy))
    else:
        x0 = int(round(cx - w))
        y0 = int(round(cy - h / 2))
    x0 = max(4, min(image_size[0] - w - 4, x0))
    y0 = max(4, min(image_size[1] - h - 4, y0))
    box = (x0, y0, x0 + w, y0 + h)
    draw.rounded_rectangle(box, radius=6, fill=WHITE, outline=color, width=1)
    draw.text((x0 + pad_x, y0 + pad_y - 1), label, font=fnt, fill=color)


def anchor_xy(anchor: dict, crop_box: list[float]) -> tuple[float, float]:
    x = float(anchor["pixel_x"])
    y = float(anchor["pixel_y"])
    if anchor.get("coordinate_system") == "original_figure":
        x -= float(crop_box[0])
        y -= float(crop_box[1])
    return x, y


def point_xy(point: dict, coordinate_system: str, crop_box: list[float]) -> tuple[float, float]:
    x = float(point["pixel_x"])
    y = float(point["pixel_y"])
    if coordinate_system == "original_figure":
        x -= float(crop_box[0])
        y -= float(crop_box[1])
    return x, y


def draw_points(
    draw: ImageDraw.ImageDraw,
    curves: Iterable[dict],
    crop_box: list[float],
) -> None:
    for curve in curves:
        coordinate_system = curve.get("point_coordinate_system", "cropped_panel")
        for point in curve.get("sampled_points", []):
            x, y = point_xy(point, coordinate_system, crop_box)
            r = 5
            draw.ellipse((x - r, y - r, x + r, y + r), fill=GREEN, outline=DARK_GREEN, width=1)


def build_overlay(case_id: str, output_name: str) -> Path:
    anchoring_path, curve_path, panel_crop_path = response_paths(case_id)
    anchoring = json.loads(anchoring_path.read_text(encoding="utf-8"))
    curve_response = json.loads(curve_path.read_text(encoding="utf-8"))

    crop_box = anchoring.get("crop_box_original", [0, 0, 0, 0])
    plot_box = anchoring["plot_area_box_cropped"]
    left, top, right, bottom = [float(v) for v in plot_box]

    base = Image.open(panel_crop_path).convert("RGBA")
    grid_layer = Image.new("RGBA", base.size, (255, 255, 255, 0))
    label_layer = Image.new("RGBA", base.size, (255, 255, 255, 0))
    grid_draw = ImageDraw.Draw(grid_layer)
    label_draw = ImageDraw.Draw(label_layer)

    for anchor in anchoring.get("anchor_points", []):
        axis = anchor.get("axis")
        tick_value = str(anchor.get("tick_value", ""))
        if not tick_value:
            continue
        x, y = anchor_xy(anchor, crop_box)
        if axis == "x" and left - 20 <= x <= right + 20:
            dashed_line(grid_draw, (x, top), (x, bottom), X_GRID, width=2)
            grid_draw.ellipse((x - 5, bottom - 5, x + 5, bottom + 5), fill=(*X_BLUE, 220))
            label_box(label_draw, (x, bottom + 20), tick_value, X_BLUE, base.size, "x")
        elif axis == "y" and top - 20 <= y <= bottom + 20:
            dashed_line(grid_draw, (left, y), (right, y), Y_GRID, width=2)
            grid_draw.ellipse((left - 5, y - 5, left + 5, y + 5), fill=(*Y_MAGENTA, 220))
            label_box(label_draw, (left - 10, y), tick_value, Y_MAGENTA, base.size, "y")

    combined = Image.alpha_composite(base, grid_layer)
    combined = Image.alpha_composite(combined, label_layer)
    point_draw = ImageDraw.Draw(combined)
    draw_points(point_draw, curve_response.get("curves", []), crop_box)

    output = OVERLAY_DIR / output_name
    OVERLAY_DIR.mkdir(parents=True, exist_ok=True)
    combined.convert("RGB").save(output, dpi=(300, 300))
    return output


def build_selected_overlays() -> list[Path]:
    return [build_overlay(case_id, output_name) for case_id, output_name in SELECTED_CASES]


def main() -> None:
    for path in build_selected_overlays():
        print(f"Wrote {path.name}")


if __name__ == "__main__":
    main()
