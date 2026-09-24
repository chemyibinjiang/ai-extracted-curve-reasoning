"""Replace only Figure 5C's plot viewports; retain the edited surrounding SVG.

Requires the numerical outputs of refit_nimo.py and Inkscape for PNG export.
The output directory must differ from figures/manuscript/.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SVG = "{http://www.w3.org/2000/svg}"
XLINK = "{http://www.w3.org/1999/xlink}href"


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def plots(data_directory, output):
    data = pd.read_csv(data_directory / "C_NIMO_FIT_POINTS.csv")
    lines = pd.read_csv(data_directory / "C_NIMO_FIT_LINES.csv")
    coverage = pd.read_csv(data_directory / "C_NIMO_PREDICTED_COVERAGE.csv")
    report = json.loads((data_directory / "C_NIMO_REPORT.json").read_text())
    assert report["selected_source"] == "figure4_experiment" and report["n"] == len(data) == 40
    metrics = {r["model"]: r["RMSE_mV"] for r in report["metrics"]}
    plt.rcParams.update({"font.family": "Arial", "font.weight": "bold", "font.size": 11.5,
        "axes.labelweight": "bold", "axes.titleweight": "bold", "axes.labelsize": 12,
        "axes.titlesize": 15.5, "axes.spines.top": False, "axes.spines.right": False,
        "axes.linewidth": .8, "xtick.major.size": 3, "ytick.major.size": 3,
        "svg.fonttype": "none", "svg.hashsalt": "Figure5_NiMo_direct_fit",
        "mathtext.fontset": "custom", "mathtext.rm": "Arial:bold",
        "mathtext.it": "Arial:bold:italic", "mathtext.bf": "Arial:bold"})
    colors = {"BV": "#1765ff", "BV+jR": "#ed2338", "VHT": "#009b72"}

    def fit_axis(ax, models):
        ax.plot(data.U_mV, data.J_mA_cm2, "o", ms=3., mfc="white", mec="black", mew=.7,
                label="Data", zorder=4)
        for name in models:
            ax.plot(lines[name + "_eta_mV"], lines.j_mA_cm2,
                "--" if name == "BV" else "-", lw=1.5, color=colors[name], label=name.replace("+", " + "))
        ax.set(xlabel=r"$|\eta|$ (mV)", ylabel=r"$|j|$ (mA cm$^{-2}$)",
               xlim=(60, 155), ylim=(0, 26), xticks=[75, 100, 125, 150], yticks=[0, 5, 10, 15, 20, 25])
        ax.legend(loc="upper left", frameon=False, handlelength=1.6, handletextpad=.5,
                  labelspacing=.25, borderpad=.1, fontsize=11)

    fig = plt.figure(figsize=(5.5, 3.))
    ax = fig.add_axes([.16, .23, .80, .65])
    fit_axis(ax, ["BV", "BV+jR"])
    ax.set_title("NiMo: empirical fits", pad=8)
    ax.text(.04, .52, f"Voltage RMSE\nBV: {metrics['BV']:.2f} mV\nBV + jR: {metrics['BV+jR']:.2f} mV",
            transform=ax.transAxes, va="top", fontsize=10.5)
    resistance = report["empirical_fits"]["BV+jR"]["r_mV_per_mA"]
    ax.text(.96, .09, rf"$R_{{\rm app}}={resistance:.2f}\ \Omega\ {{\rm cm}}^2$",
            ha="right", transform=ax.transAxes, fontsize=11, color=colors["BV+jR"])
    fig.savefig(output / "C_empirical.svg", transparent=True, metadata={"Date": None})
    plt.close(fig)

    fig = plt.figure(figsize=(5.96, 3.))
    ax = fig.add_axes([.105, .23, .355, .65])
    fit_axis(ax, ["VHT"])
    ax.set(yticks=[0, 10, 20])
    ax.set_title("VHT fit", pad=8)
    ax.text(.05, .57, f"RMSE\n{metrics['VHT']:.2f} mV", va="top", transform=ax.transAxes, fontsize=10.5)
    ax.text(.96, .08, "No jR term", ha="right", transform=ax.transAxes, fontsize=10.5)
    theta = fig.add_axes([.64, .23, .345, .65])
    theta.plot(coverage.eta_mV, coverage.theta, color=colors["VHT"], lw=1.5, label=r"Fit 1: $\theta_{\rm H}$")
    theta.plot(coverage.eta_mV, coverage.theta_mirror, color="#8049e0", lw=1.4, ls="--",
               label=r"Fit 2: $1-\theta_{\rm H}$")
    theta.set(xlabel=r"$|\eta|$ (mV)", ylabel=r"Coverage, $\theta_{\rm H}$",
              xlim=(60, 155), ylim=(0, 1), xticks=[75, 100, 125, 150], yticks=[0, .5, 1])
    theta.set_title("Predicted coverage", pad=8)
    theta.legend(loc="upper left", frameon=False, fontsize=10.5, handlelength=1.5,
                 handletextpad=.4, borderpad=.05, labelspacing=.3)
    theta.text(.5, .055, "Same LSV", ha="center", transform=theta.transAxes, fontsize=10.5)
    fig.savefig(output / "C_kinetics_coverage.svg", transparent=True, metadata={"Date": None})
    plt.close(fig)
    return report


def embedded(path, old, prefix):
    svg = ET.parse(path).getroot()
    ids = {node.get("id"): prefix + node.get("id") for node in svg.iter() if node.get("id")}
    for node in svg.iter():
        if node.get("id"):
            node.set("id", ids[node.get("id")])
        for key, value in list(node.attrib.items()):
            if key == XLINK and value.startswith("#"):
                node.set(key, "#" + ids[value[1:]])
            elif "url(#" in value:
                node.set(key, re.sub(r"url\(#([^)]*)\)", lambda m: f"url(#{ids[m[1]]})", value))
    for key in ("x", "y", "width", "height", "id"):
        svg.set(key, old.get(key))
    svg.set("preserveAspectRatio", "xMidYMid")
    svg.set("style", "overflow:visible")
    svg.tail = old.tail
    return svg


def replace_plots(baseline, data_directory, output, inkscape="inkscape"):
    output, baseline = Path(output).resolve(), Path(baseline).resolve()
    if output == baseline.parent or (REPO / "figures").resolve() in output.parents:
        raise ValueError("Generate a separate review export before publishing")
    output.mkdir(parents=True, exist_ok=True)
    report = plots(Path(data_directory), output)
    for _, (prefix, uri) in ET.iterparse(baseline, events=["start-ns"]):
        if not re.fullmatch(r"ns\d+", prefix):
            ET.register_namespace(prefix, uri)
    tree = ET.parse(baseline)
    root = tree.getroot()
    before = copy.deepcopy(root)
    row = next(node for node in root if node.get("id") == "row_C")
    replacements = {"svg667": "C_empirical.svg", "svg733": "C_kinetics_coverage.svg"}
    originals = {}
    for key, filename in replacements.items():
        old = next(node for node in row if node.get("id") == key)
        originals[key] = old
        position = list(row).index(old)
        row.remove(old)
        row.insert(position, embedded(output / filename, old, "nimo_" + key + "_"))
    description = root.find(SVG + "desc")
    old_description = description.text
    description.text = ("Figure 5: electrical compensation, bubble-associated CV/EIS trends, "
        "surface kinetics, and current rescaling. C independently fits the same 40 experimental "
        "NiMo points with BV, BV+jR and reversible resistance-free VHT. Voltage RMSE is "
        "2.403, 0.427 and 0.661 mV. Both coverages are calculated from fitted symmetry-related "
        "VHT parameters; they are not digitized or measured coverage. The model has no jR "
        "term or voltage offset. A nearly equivalent VH limit means a Tafel contribution "
        "is not uniquely established. A, B, D and the C concept schematic are unchanged. "
        "See Figure5_caption.md in the repository and Figure5_METHODS.md in the figure gallery for assumptions.")
    final = output / "Figure5.svg"
    tree.write(final, encoding="utf-8", xml_declaration=True)
    # Restore the two viewports and description: everything else must be identical.
    for key, original in originals.items():
        current = next(node for node in row if node.get("id") == key)
        position = list(row).index(current)
        row.remove(current)
        row.insert(position, original)
    description.text = old_description
    assert ET.tostring(root) == ET.tostring(before), "Unrelated artwork was changed"
    executable = shutil.which(inkscape)
    if not executable:
        raise RuntimeError("Inkscape is required; provide --inkscape")

    def export(source, destination, width):
        subprocess.run([executable, str(source), "--export-type=png", "--export-background=white",
            f"--export-width={width}", f"--export-filename={destination}"],
            check=True, capture_output=True, text=True)

    export(final, final.with_suffix(".png"), 3000)
    detail = ET.parse(final)
    detail.getroot().set("viewBox", "0 882 1800 392")
    detail.getroot().set("height", str(300 * 392 / 1800) + "mm")
    detail_path = output / "Figure5C.svg"
    detail.write(detail_path, encoding="utf-8", xml_declaration=True)
    export(detail_path, detail_path.with_suffix(".png"), 2400)
    # Rerender the baseline using the same renderer settings for a scoped pixel check.
    baseline_preview = output / "baseline.png"
    export(baseline, baseline_preview, 3000)
    from PIL import Image, ImageChops
    with Image.open(final.with_suffix(".png")) as image, Image.open(baseline_preview) as prior:
        assert image.size == prior.size
        changed = ImageChops.difference(image.convert("RGB"), prior.convert("RGB")).getbbox()
        if changed:
            assert changed[0] >= 370 * 3000 / 1800
            assert changed[1] >= 882 * 3000 / 1800 and changed[3] <= 1274 * 3000 / 1800
    result = dict(baseline_sha256=digest(baseline), svg_sha256=digest(final),
        png_sha256=digest(final.with_suffix(".png")), numerical_report_sha256=digest(Path(data_directory) / "C_NIMO_REPORT.json"),
        changed_pixel_bounds=changed, unchanged_A_B_D_and_C_schematic=True,
        source_doi=report["source_doi"], selected_source=report["selected_source"],
        n=report["n"], metrics=report["metrics"])
    (output / "ARTWORK_CHECKS.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, default=REPO / "figures/manuscript/Figure5.svg")
    parser.add_argument("--data", type=Path, default=REPO / "build/figure5-nimo")
    parser.add_argument("--output", type=Path, default=REPO / "build/figure5-updated")
    parser.add_argument("--inkscape", default="inkscape")
    args = parser.parse_args()
    print(json.dumps(replace_plots(args.baseline, args.data, args.output, args.inkscape), indent=2))


if __name__ == "__main__":
    main()
