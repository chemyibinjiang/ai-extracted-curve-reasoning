const fs = require("fs");
const path = require("path");

let lucide = {};
try {
  lucide = require("lucide");
} catch {
  lucide = {};
}

const OUT_DIR = __dirname;
const ROOT = path.resolve(OUT_DIR, "..", "..", "..");
const W = 1800;
const H = 2520;

const C = {
  ink: "#102033",
  muted: "#526173",
  border: "#cbd6e2",
  grid: "#e8eef5",
  blue: "#0b3a78",
  green: "#118240",
  red: "#c4202b",
  purple: "#5a2a8a",
  orange: "#b76b00",
  teal: "#08756c",
  paleBlue: "#f1f7ff",
  paleGreen: "#f0fbf3",
  paleRed: "#fff4f4",
  palePurple: "#f8f3ff",
  paleOrange: "#fff8ec",
  paleTeal: "#eefcfa",
  white: "#ffffff",
};

const CASE = {
  uid: "batch0/case3/figure_4__a",
  sourceCollection: "LSV-63-2026-4-5",
  title:
    "Octahedral Nanocrystals of Ru-Doped PtFeNiCuW/CNTs High-Entropy Alloy: High Performance Toward pH-Universal Hydrogen Evolution Reaction",
  doi: "10.1002/adma.202400433",
  panel: "Figure 4a",
  panelType: "HER polarization curve",
  electrolyte: "1.0 M KOH",
};

const STAGE_DIR = path.join(
  ROOT,
  "data",
  "LSV_publication_database",
  "05_stage_responses",
  "batch0",
  "case3",
  "figure_4__a",
);

const SOURCE_ROOT = path.join(
  ROOT,
  "data",
  "LSV_publication_database",
  "01_source_html_assets",
  "batch0",
  "case3",
);

function findFile(root, fileName) {
  const stack = [root];
  while (stack.length) {
    const dir = stack.pop();
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      const full = path.join(dir, entry.name);
      if (entry.isDirectory()) stack.push(full);
      else if (entry.name === fileName) return full;
    }
  }
  throw new Error(`Could not find ${fileName} under ${root}`);
}

const ASSETS = {
  sourceFigure: findFile(SOURCE_ROOT, "adma202400433-fig-0004-m.png"),
  panelCrop: path.join(STAGE_DIR, "panel_crop.png"),
  panelAnnotated: path.join(STAGE_DIR, "panel_annotated.png"),
  curveDiagnostic: path.join(STAGE_DIR, "curve_overlap_diagnostic.png"),
  contactSheet: path.join(STAGE_DIR, "curve_views_contact_sheet.png"),
  axisFit: path.join(STAGE_DIR, "axis_fit_output.json"),
  extraction: path.join(STAGE_DIR, "curve_extraction_response.json"),
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

function line(x1, y1, x2, y2, stroke = C.ink, width = 3, extra = {}) {
  return `<line ${attrs({ x1, y1, x2, y2, stroke, "stroke-width": width, "stroke-linecap": "round", ...extra })}/>`;
}

function rect(x, y, w, h, fill = C.white, stroke = C.border, width = 2, rx = 12, extra = {}) {
  return `<rect ${attrs({ x, y, width: w, height: h, rx, fill, stroke, "stroke-width": width, ...extra })}/>`;
}

function circle(cx, cy, r, fill = C.white, stroke = C.border, width = 2) {
  return `<circle ${attrs({ cx, cy, r, fill, stroke, "stroke-width": width })}/>`;
}

function text(x, y, content, size = 24, fill = C.ink, weight = 500, extra = {}) {
  return `<text ${attrs({
    x,
    y,
    fill,
    "font-size": size,
    "font-weight": weight,
    "font-family": "Arial, Helvetica, sans-serif",
    ...extra,
  })}>${esc(content)}</text>`;
}

function tspans(x, y, lines, size = 22, fill = C.ink, weight = 500, lineHeight = 1.18, extra = {}) {
  const body = lines
    .map((lineText, i) => `<tspan ${attrs({ x, dy: i === 0 ? 0 : size * lineHeight })}>${esc(lineText)}</tspan>`)
    .join("");
  return `<text ${attrs({
    x,
    y,
    fill,
    "font-size": size,
    "font-weight": weight,
    "font-family": "Arial, Helvetica, sans-serif",
    ...extra,
  })}>${body}</text>`;
}

function wrapWords(content, maxChars) {
  const words = String(content).split(/\s+/);
  const lines = [];
  let current = "";
  for (const word of words) {
    if (!current) current = word;
    else if ((current + " " + word).length <= maxChars) current += " " + word;
    else {
      lines.push(current);
      current = word;
    }
  }
  if (current) lines.push(current);
  return lines;
}

function icon(name, x, y, size = 34, color = C.ink, strokeWidth = 2.3) {
  const data = lucide[name];
  if (!data) return "";
  const scale = size / 24;
  const nodes = data
    .map(([nodeName, nodeAttrs]) => {
      const a = { ...nodeAttrs };
      if (!a.fill) a.fill = "none";
      if (!a.stroke) a.stroke = "currentColor";
      a["stroke-width"] = a["stroke-width"] || strokeWidth;
      a["stroke-linecap"] = a["stroke-linecap"] || "round";
      a["stroke-linejoin"] = a["stroke-linejoin"] || "round";
      return `<${nodeName} ${attrs(a)}/>`;
    })
    .join("");
  return `<g transform="translate(${x} ${y}) scale(${scale})" color="${color}">${nodes}</g>`;
}

function arrow(x1, y1, x2, y2, color = C.blue, width = 5) {
  const dx = x2 - x1;
  const dy = y2 - y1;
  const len = Math.sqrt(dx * dx + dy * dy) || 1;
  const ux = dx / len;
  const uy = dy / len;
  const px = -uy;
  const py = ux;
  const tip = `${x2},${y2}`;
  const left = `${x2 - ux * 24 + px * 10},${y2 - uy * 24 + py * 10}`;
  const right = `${x2 - ux * 24 - px * 10},${y2 - uy * 24 - py * 10}`;
  return `${line(x1, y1, x2, y2, color, width)}<polygon points="${tip} ${left} ${right}" fill="${color}"/>`;
}

function panelLabel(letter, x, y, color) {
  return `${rect(x, y, 50, 50, color, "none", 0, 9)}${text(x + 16, y + 35, letter, 30, C.white, 800)}`;
}

function card(x, y, w, h, color, title, letter, subtitle = "") {
  return [
    rect(x, y, w, h, C.white, color, 3, 13),
    panelLabel(letter, x + 18, y + 18, color),
    text(x + 80, y + 51, title, 26, color, 800),
    subtitle ? text(x + 80, y + 83, subtitle, 18, C.muted, 500) : "",
  ].join("");
}

function dataUri(file) {
  const ext = path.extname(file).toLowerCase();
  const mime = ext === ".jpg" || ext === ".jpeg" ? "image/jpeg" : "image/png";
  return `data:${mime};base64,${fs.readFileSync(file).toString("base64")}`;
}

let clipCounter = 0;
function imageBox(file, x, y, w, h, options = {}) {
  const id = `clip_${clipCounter++}`;
  const pad = options.pad ?? 0;
  const stroke = options.stroke ?? C.border;
  const bg = options.bg ?? C.white;
  const rx = options.rx ?? 8;
  const href = dataUri(file);
  const title = options.title ? text(x + 14, y + 28, options.title, 17, C.ink, 800) : "";
  return [
    rect(x, y, w, h, bg, stroke, 2, rx),
    `<clipPath id="${id}">${rect(x + pad, y + pad, w - 2 * pad, h - 2 * pad, "none", "none", 0, rx)}</clipPath>`,
    `<image ${attrs({
      href,
      x: x + pad,
      y: y + pad + (options.title ? 32 : 0),
      width: w - 2 * pad,
      height: h - 2 * pad - (options.title ? 36 : 0),
      preserveAspectRatio: options.preserveAspectRatio || "xMidYMid meet",
      "clip-path": `url(#${id})`,
      opacity: options.opacity,
    })}/>`,
    title,
  ].join("");
}

function readJson(file) {
  return JSON.parse(fs.readFileSync(file, "utf8"));
}

function toDataPoints(curve, axisFit) {
  const xSlope = axisFit.x.fit_parameters.slope;
  const xInt = axisFit.x.fit_parameters.intercept;
  const ySlope = axisFit.y.fit_parameters.slope;
  const yInt = axisFit.y.fit_parameters.intercept;
  return curve.sampled_points.map((pt) => ({
    x: (pt.pixel_x - xInt) / xSlope,
    y: (pt.pixel_y - yInt) / ySlope,
    c: pt.confidence,
  }));
}

function mapPlot(points, x, y, w, h, xmin, xmax, ymin, ymax) {
  return points
    .map((pt) => {
      const sx = x + ((pt.x - xmin) / (xmax - xmin)) * w;
      const sy = y + h - ((pt.y - ymin) / (ymax - ymin)) * h;
      return [sx, sy];
    })
    .filter(([sx, sy]) => Number.isFinite(sx) && Number.isFinite(sy));
}

function polyline(points, color, width = 3, dash = "", opacity = 1) {
  return `<polyline ${attrs({
    points: points.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(" "),
    fill: "none",
    stroke: color,
    "stroke-width": width,
    "stroke-linecap": "round",
    "stroke-linejoin": "round",
    "stroke-dasharray": dash || undefined,
    opacity,
  })}/>`;
}

function etaAt(points, yTarget = -10) {
  const ordered = [...points].sort((a, b) => a.y - b.y);
  for (let i = 1; i < ordered.length; i++) {
    const a = ordered[i - 1];
    const b = ordered[i];
    if ((a.y - yTarget) * (b.y - yTarget) <= 0 && a.y !== b.y) {
      const t = (yTarget - a.y) / (b.y - a.y);
      return a.x + t * (b.x - a.x);
    }
  }
  return null;
}

function rebuiltPlot(x, y, w, h) {
  const axisFit = readJson(ASSETS.axisFit);
  const extraction = readJson(ASSETS.extraction);
  const colors = {
    "Pt/C": "#757575",
    "Ru-PtFeNiCuW/CNTs": "#ef3b5d",
    "Ru-PtFeNiCu/CNTs": "#9b59b6",
    "Ru-PtFeNiCu-CO/CNTs": "#f2b94b",
    "PtFeNiCuW/CNTs": "#2f73c6",
  };
  const all = extraction.curves.map((curve) => ({
    label: curve.curve_label,
    points: toDataPoints(curve, axisFit).sort((a, b) => a.x - b.x),
    count: curve.sampled_points.length,
  }));
  const xmin = -0.35;
  const xmax = 0.08;
  const ymin = -50;
  const ymax = 2;
  const parts = [
    rect(x, y, w, h, C.white, "#8a98a8", 2, 0),
    text(x + 12, y + 26, "rebuilt from extracted points", 17, C.teal, 700),
  ];
  for (let i = 1; i < 5; i++) {
    parts.push(line(x + (w * i) / 5, y, x + (w * i) / 5, y + h, C.grid, 1));
    parts.push(line(x, y + (h * i) / 5, x + w, y + (h * i) / 5, C.grid, 1));
  }
  parts.push(line(x, y + h - ((-10 - ymin) / (ymax - ymin)) * h, x + w, y + h - ((-10 - ymin) / (ymax - ymin)) * h, "#8d99a6", 1.5, { "stroke-dasharray": "8 8" }));
  for (const curve of all) {
    const mapped = mapPlot(curve.points, x, y, w, h, xmin, xmax, ymin, ymax);
    parts.push(polyline(mapped, colors[curve.label] || C.ink, 4));
    for (const [px, py] of mapped) parts.push(circle(px, py, 3.2, C.white, colors[curve.label] || C.ink, 1.5));
  }
  parts.push(text(x + w / 2, y + h + 30, "Potential (V vs. RHE)", 17, C.ink, 700, { "text-anchor": "middle" }));
  parts.push(text(x - 32, y + h / 2, "Current density (mA cm_geo^-2)", 16, C.ink, 700, { transform: `rotate(-90 ${x - 32} ${y + h / 2})`, "text-anchor": "middle" }));
  return { svg: parts.join(""), curves: all, etaRed: etaAt(all.find((c) => c.label === "Ru-PtFeNiCuW/CNTs").points) };
}

function spineStep(n, y, color, labelLines) {
  return [
    circle(88, y, 28, color, C.white, 5),
    text(88, y + 10, String(n), 31, C.white, 800, { "text-anchor": "middle" }),
    tspans(88, y + 56, labelLines, 19, color, 800, 1.08, { "text-anchor": "middle" }),
  ].join("");
}

function bulletText(x, y, lines, color = C.ink) {
  const parts = [];
  lines.forEach((lineText, i) => {
    const yy = y + i * 28;
    parts.push(circle(x, yy - 7, 4, color, color, 0));
    parts.push(text(x + 15, yy, lineText, 19, C.ink, 500));
  });
  return parts.join("");
}

function sourcePanel() {
  const x = 190;
  const y = 72;
  const w = 1590;
  const h = 660;
  return [
    card(x, y, w, h, C.blue, "Original publication figure + caption", "A", "source-ingestion agent records article-linked provenance"),
    imageBox(ASSETS.sourceFigure, x + 45, y + 125, 1015, 430, { stroke: "#d7dee8", rx: 8 }),
    rect(x + 45, y + 572, 1015, 34, "#f7fbff", "#d7dee8", 1.2, 6),
    text(x + 65, y + 595, `${CASE.panel}: ${CASE.panelType}; ${CASE.electrolyte}`, 18, C.muted, 700),
    icon("Bot", x + 1090, y + 44, 40, C.blue),
    text(x + 1148, y + 72, "Source-ingestion agent", 24, C.blue, 800),
    rect(x + 1100, y + 125, 420, 140, "#fbfdff", "#d7dee8", 2, 9),
    text(x + 1124, y + 158, "Source", 20, C.ink, 800),
    text(x + 1124, y + 190, CASE.doi, 22, C.blue, 800),
    text(x + 1124, y + 224, `${CASE.sourceCollection} / case3`, 18, C.muted, 600),
    rect(x + 1100, y + 290, 420, 215, "#fbfdff", "#d7dee8", 2, 9),
    text(x + 1124, y + 323, "Caption route", 20, C.ink, 800),
    tspans(x + 1124, y + 356, wrapWords("Figure 4 reports HER performance in 1.0 M KOH electrolyte; panel a contains HER polarization curves normalized by geometric area.", 38), 19, C.ink, 500, 1.18),
    rect(x + 1100, y + 530, 420, 90, "#f5f8fc", "#d7dee8", 2, 9),
    text(x + 1124, y + 562, "Selected panel", 19, C.ink, 800),
    text(x + 1124, y + 596, CASE.uid, 18, C.muted, 600),
  ].join("");
}

function selectionPanel() {
  const x = 190;
  const y = 760;
  const w = 1590;
  const h = 350;
  return [
    card(x, y, w, h, C.green, "Orchestrator agent - panel selection", "B", "the full source figure is retained while panel a is queued"),
    imageBox(ASSETS.sourceFigure, x + 45, y + 105, 520, 205, { stroke: "#dfe7ef", rx: 8, opacity: 0.72 }),
    rect(x + 47, y + 107, 160, 92, "none", "#20b26b", 5, 6),
    text(x + 54, y + 330, "source figure thumbnail", 17, C.muted, 600),
    arrow(x + 590, y + 205, x + 680, y + 205, C.green, 5),
    imageBox(ASSETS.panelCrop, x + 710, y + 92, 440, 250, { stroke: "#dfe7ef", rx: 8 }),
    rect(x + 1200, y + 92, 455, 250, "#fbfffc", "#d8eadf", 2, 10),
    text(x + 1224, y + 130, "HER panel queued", 24, C.green, 800),
    rect(x + 1224, y + 154, 88, 30, "#eef7f1", "#d8eadf", 1, 5),
    text(x + 1236, y + 176, "HER LSV", 16, C.green, 800),
    rect(x + 1324, y + 154, 124, 30, "#f3f6fb", "#d8eadf", 1, 5),
    text(x + 1335, y + 176, "figure_4 / a", 16, C.muted, 700),
    tspans(x + 1224, y + 218, wrapWords("The selected view keeps the original article figure path before axis anchoring and curve extraction.", 40), 18, C.ink, 500, 1.2),
    rect(x + 1224, y + 280, 280, 30, "#f6f8fb", "#e1e7ee", 1, 5),
    text(x + 1237, y + 301, "next_stage: axis_anchoring", 16, C.muted, 700),
  ].join("");
}

function anchoringPanel() {
  const x = 190;
  const y = 1132;
  const w = 760;
  const h = 380;
  const fit = readJson(ASSETS.axisFit);
  return [
    card(x, y, w, h, C.purple, "Anchoring agent - axis crop & anchoring", "C", "tick anchors are fitted before point coordinates are converted"),
    imageBox(ASSETS.panelAnnotated, x + 45, y + 105, 415, 250, { stroke: "#dfe7ef", rx: 8 }),
    rect(x + 495, y + 116, 205, 235, "#fbf9ff", "#eadff4", 2, 9),
    text(x + 518, y + 148, "x axis", 20, C.purple, 800),
    text(x + 518, y + 176, "Potential / V vs. RHE", 17, C.ink, 500),
    text(x + 518, y + 204, "6 ticks, linear", 17, C.ink, 500),
    text(x + 518, y + 246, "y axis", 20, C.purple, 800),
    text(x + 518, y + 274, "Current density", 17, C.ink, 500),
    text(x + 518, y + 302, "6 ticks, linear", 17, C.ink, 500),
    text(x + 518, y + 337, `x RMSE ${fit.x.candidate_fits[0].normalized_rmse.toFixed(4)}`, 16, C.muted, 700),
    text(x + 518, y + 363, `y RMSE ${fit.y.candidate_fits[0].normalized_rmse.toFixed(4)}`, 16, C.muted, 700),
  ].join("");
}

function extractionPanel() {
  const x = 970;
  const y = 1132;
  const w = 810;
  const h = 380;
  const extraction = readJson(ASSETS.extraction);
  return [
    card(x, y, w, h, C.red, "Curve-extraction agent - extraction & QC", "D", "actual extracted points and crowded-region flags"),
    imageBox(ASSETS.curveDiagnostic, x + 45, y + 105, 405, 250, { stroke: "#dfe7ef", rx: 8 }),
    rect(x + 485, y + 116, 265, 235, "#fffafa", "#f0d2d2", 2, 9),
    text(x + 508, y + 148, "QC flags", 20, C.red, 800),
    rect(x + 508, y + 168, 158, 28, "#fff0f0", "#f0d2d2", 1, 5),
    text(x + 521, y + 188, "low contrast", 15, C.red, 700),
    rect(x + 508, y + 204, 166, 28, "#fff8e8", "#efd9aa", 1, 5),
    text(x + 521, y + 224, "crowded tails", 15, C.orange, 700),
    tspans(x + 508, y + 264, wrapWords(extraction.overlap_recovery_reason, 31).slice(0, 5), 17, C.ink, 500, 1.16),
  ].join("");
}

function datasetPanel() {
  const x = 190;
  const y = 1532;
  const w = 1590;
  const h = 390;
  const rebuilt = rebuiltPlot(x + 50, y + 115, 540, 250);
  const pointCount = rebuilt.curves.reduce((sum, curve) => sum + curve.count, 0);
  const eta = Math.abs(rebuilt.etaRed * 1000).toFixed(1);
  return [
    card(x, y, w, h, C.orange, "Normalization / dataset agent - rebuild curve dataset", "E", "pixel points are converted into article-linked curve records"),
    rebuilt.svg,
    rect(x + 650, y + 126, 270, 230, "#fffdf8", "#eadfc6", 2, 10),
    icon("Database", x + 678, y + 152, 74, C.blue),
    text(x + 780, y + 166, "5 curves", 23, C.ink, 800),
    text(x + 780, y + 204, `${pointCount} points`, 23, C.ink, 800),
    text(x + 780, y + 250, `Ru-PtFeNiCuW/`, 17, C.red, 800),
    text(x + 780, y + 274, `CNTs`, 17, C.red, 800),
    text(x + 780, y + 308, `eta10 = ${eta} mV`, 20, C.ink, 800),
    text(x + 780, y + 335, "at -10 mA cm^-2", 14, C.muted, 600),
    rect(x + 980, y + 105, 535, 250, "#fffdf8", "#eadfc6", 2, 10),
    text(x + 1010, y + 142, "Machine-readable curve record", 23, C.ink, 800),
    bulletText(x + 1014, y + 178, [
      "source DOI, figure, panel, and curve label",
      "axis model, tick anchors, and unit metadata",
      "converted curve points with confidence traces",
      "QC note retained for downstream review",
    ], C.orange),
    rect(x + 1010, y + 315, 325, 36, "#f7f2e8", "#eadfc6", 1, 6),
    text(x + 1024, y + 339, `${CASE.doi} / ${CASE.panel}`, 16, C.muted, 700),
  ].join("");
}

function supportPanel() {
  const x = 190;
  const y = 1945;
  const w = 1590;
  const h = 320;
  return [
    card(x, y, w, h, C.teal, "Reasoning / metric-checking agent - claim validation pass-through", "F", "curve-derived metrics are checked against source text claims"),
    rect(x + 70, y + 125, 180, 120, "#f5fffd", "#cce8e4", 2, 10),
    text(x + 160, y + 165, "Metric", 20, C.ink, 800, { "text-anchor": "middle" }),
    text(x + 160, y + 194, "support", 20, C.ink, 800, { "text-anchor": "middle" }),
    circle(x + 160, y + 232, 27, C.green, C.white, 4),
    icon("Check", x + 143, y + 215, 34, C.white, 3.2),
    rect(x + 315, y + 125, 490, 120, "#fbfdff", "#d7dee8", 2, 10),
    text(x + 340, y + 161, "Text claim", 20, C.ink, 800),
    text(x + 340, y + 205, "Ru-PtFeNiCuW/CNTs: eta10 = 16 mV in 1.0 M KOH", 20, C.ink, 500),
    arrow(x + 835, y + 185, x + 900, y + 185, C.ink, 3),
    rect(x + 890, y + 125, 365, 120, "#f5fffd", "#cce8e4", 2, 10),
    text(x + 915, y + 161, "Curve-derived metric", 20, C.teal, 800),
    text(x + 915, y + 198, "Interpolated eta10 = 16.2 mV;", 18, C.ink, 500),
    text(x + 915, y + 226, "within tolerance", 18, C.ink, 500),
    arrow(x + 1280, y + 185, x + 1330, y + 185, C.teal, 5),
    rect(x + 1355, y + 135, 195, 56, "#ecfff1", "#84d79a", 2, 8),
    text(x + 1452, y + 171, "SUPPORTED", 22, C.green, 800, { "text-anchor": "middle" }),
    rect(x + 1370, y + 207, 165, 40, "#f6f8fb", "#d7dee8", 1, 7),
    text(x + 1452, y + 233, "eta10 interpolation", 15, C.muted, 700, { "text-anchor": "middle" }),
    text(x + 300, y + 285, "Linked record: source -> panel -> curve -> metric", 19, C.ink, 600),
    text(x + 780, y + 285, "The same article-linked curve record becomes evidence for claim checking.", 19, C.ink, 500),
  ].join("");
}

function footerBadge(x, iconName, title, body) {
  return [
    icon(iconName, x, 2324, 44, C.blue),
    text(x + 66, 2338, title, 20, C.ink, 800),
    tspans(x + 66, 2366, wrapWords(body, 29), 15, C.muted, 600, 1.1),
  ].join("");
}

function buildSvg() {
  const parts = [];
  parts.push(`<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}">`);
  parts.push(rect(0, 0, W, H, "#ffffff", "none", 0, 0));
  parts.push(text(W / 2, 48, "Source-grounded multi-agent workflow for reconstructing article-linked curve evidence", 33, C.ink, 800, { "text-anchor": "middle" }));
  parts.push(text(88, 76, "Multi-agent", 18, C.ink, 800, { "text-anchor": "middle" }));
  parts.push(text(88, 100, "pipeline", 18, C.ink, 800, { "text-anchor": "middle" }));
  parts.push(icon("UsersRound", 61, 112, 56, C.ink));
  parts.push(line(88, 188, 88, 2155, "#1d3958", 5));
  parts.push(spineStep(1, 220, C.blue, ["Source", "article", "package"]));
  parts.push(spineStep(2, 835, C.green, ["Panel", "selection"]));
  parts.push(spineStep(3, 1210, C.purple, ["Axis", "anchoring"]));
  parts.push(spineStep(4, 1400, C.red, ["Curve", "extraction", "& QC"]));
  parts.push(spineStep(5, 1675, C.orange, ["Rebuilt", "curve", "dataset"]));
  parts.push(spineStep(6, 2085, C.teal, ["Metric", "support", "check"]));
  parts.push(arrow(88, 300, 88, 770, "#1d3958", 5));
  parts.push(arrow(88, 900, 88, 1160, "#1d3958", 5));
  parts.push(arrow(88, 1260, 88, 1365, "#1d3958", 5));
  parts.push(arrow(88, 1460, 88, 1640, "#1d3958", 5));
  parts.push(arrow(88, 1740, 88, 2040, "#1d3958", 5));
  parts.push(sourcePanel());
  parts.push(selectionPanel());
  parts.push(anchoringPanel());
  parts.push(extractionPanel());
  parts.push(datasetPanel());
  parts.push(supportPanel());
  parts.push(rect(160, 2295, 1645, 125, "#fbfdff", "#d7dee8", 2, 10));
  parts.push(footerBadge(205, "Link", "Source grounding", "Every record is traceable to the original article."));
  parts.push(footerBadge(530, "ShieldCheck", "Transparency", "Axes, ticks, crops and uncertainty are explicit."));
  parts.push(footerBadge(860, "ClipboardCheck", "Reproducibility", "Machine-readable records enable reanalysis."));
  parts.push(footerBadge(1195, "SearchCheck", "Quality control", "Crowded regions are flagged; uncertainty retained."));
  parts.push(footerBadge(1515, "Workflow", "Specialized agents", "Each agent performs a focused, verifiable task."));
  parts.push("</svg>");
  return parts.join("\n");
}

const svg = buildSvg();
const svgPath = path.join(OUT_DIR, "Figure_3_source_grounded_workflow_candidate.svg");
const htmlPath = path.join(OUT_DIR, "Figure_3_source_grounded_workflow_candidate.html");

fs.writeFileSync(svgPath, svg, "utf8");
fs.writeFileSync(
  htmlPath,
  `<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>Figure 3 workflow candidate</title>
  <style>
    body { margin: 0; background: #f4f6f8; }
    .page { width: ${W}px; margin: 0 auto; background: white; }
    img { display: block; width: ${W}px; height: ${H}px; }
  </style>
</head>
<body>
  <div class="page"><img src="./${path.basename(svgPath)}" alt="Figure 3 source-grounded workflow candidate"></div>
</body>
</html>
`,
  "utf8",
);

console.log(`Wrote ${svgPath}`);
console.log(`Wrote ${htmlPath}`);
console.log(`Concrete example: ${CASE.uid} (${CASE.doi})`);
