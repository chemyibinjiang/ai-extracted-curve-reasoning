const fs = require("fs");
const path = require("path");

const OUT_DIR = __dirname;
const ROOT = path.resolve(OUT_DIR, "..", "..", "..");
const STAGE_DIR = path.join(
  ROOT,
  "data",
  "LSV_publication_database",
  "05_stage_responses",
  "batch0",
  "case3",
  "figure_4__a",
);

const axisFit = JSON.parse(fs.readFileSync(path.join(STAGE_DIR, "axis_fit_output.json"), "utf8"));
const extraction = JSON.parse(fs.readFileSync(path.join(STAGE_DIR, "curve_extraction_response.json"), "utf8"));

const W = 1000;
const H = 440;
const M = { l: 112, r: 34, t: 16, b: 70 };
const plot = { x: M.l, y: M.t, w: W - M.l - M.r, h: H - M.t - M.b };
const C = {
  ink: "#101b2d",
  axis: "#8e9dad",
  grid: "#e3ebf3",
  teal: "#08756c",
  gray: "#74777a",
  red: "#f23b5c",
  purple: "#9a57bd",
  orange: "#f2b747",
  blue: "#2d73cc",
};

function esc(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function attrs(obj) {
  return Object.entries(obj)
    .filter(([, v]) => v !== undefined && v !== null)
    .map(([k, v]) => `${k}="${esc(v)}"`)
    .join(" ");
}

function text(x, y, content, size, fill = C.ink, weight = 700, extra = {}) {
  return `<text ${attrs({
    x,
    y,
    fill,
    "font-size": size,
    "font-weight": weight,
    "font-family": "Arial",
    ...extra,
  })}>${esc(content)}</text>`;
}

function line(x1, y1, x2, y2, stroke = C.axis, width = 2, extra = {}) {
  return `<line ${attrs({ x1, y1, x2, y2, stroke, "stroke-width": width, "stroke-linecap": "round", ...extra })}/>`;
}

function rect(x, y, width, height, fill = "none", stroke = C.axis, strokeWidth = 3) {
  return `<rect ${attrs({ x, y, width, height, fill, stroke, "stroke-width": strokeWidth })}/>`;
}

function circle(cx, cy, r, fill, stroke, width) {
  return `<circle ${attrs({ cx, cy, r, fill, stroke, "stroke-width": width })}/>`;
}

function polyline(points, color, width = 5) {
  return `<polyline ${attrs({
    points: points.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(" "),
    fill: "none",
    stroke: color,
    "stroke-width": width,
    "stroke-linecap": "round",
    "stroke-linejoin": "round",
  })}/>`;
}

function toDataPoint(pt) {
  const x = (pt.pixel_x - axisFit.x.fit_parameters.intercept) / axisFit.x.fit_parameters.slope;
  const y = (pt.pixel_y - axisFit.y.fit_parameters.intercept) / axisFit.y.fit_parameters.slope;
  return { x, y, confidence: pt.confidence };
}

function mapPoint(pt) {
  const xmin = -0.35;
  const xmax = 0.08;
  const ymin = -50;
  const ymax = 2;
  return [
    plot.x + ((pt.x - xmin) / (xmax - xmin)) * plot.w,
    plot.y + plot.h - ((pt.y - ymin) / (ymax - ymin)) * plot.h,
  ];
}

function buildSvg() {
  const colors = {
    "Pt/C": C.gray,
    "Ru-PtFeNiCuW/CNTs": C.red,
    "Ru-PtFeNiCu/CNTs": C.purple,
    "Ru-PtFeNiCu-CO/CNTs": C.orange,
    "PtFeNiCuW/CNTs": C.blue,
  };
  const parts = [
    `<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}">`,
    `<rect width="${W}" height="${H}" fill="#ffffff"/>`,
    rect(plot.x, plot.y, plot.w, plot.h, "#ffffff", C.axis, 3),
  ];

  for (let i = 1; i < 5; i++) {
    const gx = plot.x + (plot.w * i) / 5;
    const gy = plot.y + (plot.h * i) / 5;
    parts.push(line(gx, plot.y, gx, plot.y + plot.h, C.grid, 1.4));
    parts.push(line(plot.x, gy, plot.x + plot.w, gy, C.grid, 1.4));
  }

  const refY = mapPoint({ x: -0.35, y: -10 })[1];
  parts.push(line(plot.x, refY, plot.x + plot.w, refY, "#99a6b4", 2.1, { "stroke-dasharray": "14 13" }));

  for (const curve of extraction.curves) {
    const dataPoints = curve.sampled_points.map(toDataPoint).sort((a, b) => a.x - b.x);
    const mapped = dataPoints.map(mapPoint);
    const color = colors[curve.curve_label] || C.ink;
    parts.push(polyline(mapped, color, 4.2));
    for (const [cx, cy] of mapped) {
      parts.push(circle(cx, cy, 4.6, "#ffffff", color, 2.2));
    }
  }

  parts.push(text(plot.x + plot.w / 2, H - 18, "Potential (V vs. RHE)", 22, C.ink, 800, { "text-anchor": "middle" }));
  parts.push(text(42, plot.y + plot.h / 2, "Current density (mA cm_geo^-2)", 18, C.ink, 800, {
    transform: `rotate(-90 42 ${plot.y + plot.h / 2})`,
    "text-anchor": "middle",
  }));
  parts.push("</svg>");
  return parts.join("\n");
}

const svgPath = path.join(OUT_DIR, "rebuilt_curve_from_extracted_points_batch0_case3_fig4a.svg");
const htmlPath = path.join(OUT_DIR, "rebuilt_curve_from_extracted_points_batch0_case3_fig4a.html");
fs.writeFileSync(svgPath, buildSvg(), "utf8");
fs.writeFileSync(
  htmlPath,
  `<!doctype html><meta charset="utf-8"><style>body{margin:0;background:white}img{display:block;width:${W}px;height:${H}px}</style><img src="./${path.basename(svgPath)}">`,
  "utf8",
);
console.log(svgPath);
console.log(htmlPath);
