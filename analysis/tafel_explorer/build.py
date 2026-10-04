"""Build a static Tafel explorer from the published prepared observations."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "analysis/figure4"))
sys.path.insert(0, str(ROOT / "analysis/figure7/lib"))
from local_slopes import curve_derivatives
from metadata import corrected_metadata
from weights import pw, quant

PGM = {"Pt", "Pd", "Rh", "Ru", "Ir", "Os"}
WINDOWS = {
    "eta": [0, 25, 50, 100, 150, 200, 300, 400, 500],
    "current": [0.2, 1, 5, 10, 20, 40, 80, 160, 320, 500],
}
INPUTS = [
    "analysis/figure4/inputs/POINTS.csv", "analysis/figure4/inputs/CURVES.csv",
    "analysis/figure7/inputs/canonical_curves.csv", "analysis/figure7/inputs/CATALYST_AUDIT.csv",
    "analysis/figure7/inputs/MEMBER_COMPATIBILITY.csv", "analysis/figure7/inputs/METADATA_CORRECTIONS.json",
    "analysis/figure4/local_slopes.py", "analysis/figure4/weights.py",
]


def window_index(value, edges):
    """Left-closed bins, including the last endpoint in the last bin."""
    if not np.isfinite(value) or value < edges[0] or value > edges[-1]:
        return None
    return min(int(np.searchsorted(edges, value, side="right") - 1), len(edges) - 2)


def load_metadata():
    curves = pd.read_csv(ROOT / INPUTS[1])
    cols = ["curve_uid", "enrich_active_elements", "enrich_current_normalization_basis",
            "enrich_reported_material_name", "enrich_electrolyte_identity", "enrich_ir_compensation_status"]
    canonical = corrected_metadata(pd.read_csv(ROOT / INPUTS[2], usecols=cols, low_memory=False))
    audit = pd.read_csv(ROOT / INPUTS[3])
    assert curves.curve_uid.is_unique and len(curves) == 3033
    merged = curves.merge(canonical, on="curve_uid", validate="one_to_one").merge(audit, on="curve_uid", validate="one_to_one")
    assert len(merged) == len(curves)
    pairs = pd.read_csv(ROOT / INPUTS[4])
    memberships = pairs.groupby("curve_uid").template.agg(lambda x: sorted(set(x)))
    merged["templates"] = merged.curve_uid.map(memberships).map(lambda x: x if isinstance(x, list) else [])
    return merged


def summarize_curve(rows):
    result = {}
    for axis, edges in WINDOWS.items():
        bins = [[] for _ in edges[:-1]]
        for row in rows:
            wi = window_index(row["eta_mV" if axis == "eta" else "j"], edges)
            if wi is not None:
                bins[wi].append(row["slope_mV_dec"])
        result[axis] = [[float(np.median(v)), len(v)] if v else None for v in bins]
    return result


def build(output, plotly_js=None):
    output.mkdir(parents=True, exist_ok=True)
    metadata = load_metadata().set_index("curve_uid")
    points = pd.read_csv(ROOT / INPUTS[0], float_precision="round_trip")
    assert len(points) == 80399 and points.curve_uid.nunique() == 3033
    records, local, windows, status_counts = [], [], [], {}
    for uid, g in points.groupby("curve_uid", sort=True):
        g = g.sort_values("native_index")
        row = metadata.loc[uid]
        elements = json.loads(row.enrich_active_elements) if pd.notna(row.enrich_active_elements) else []
        elements = sorted(set(elements)) if isinstance(elements, list) else []
        ptc = bool(row.is_ptc)
        pgm = bool(PGM.intersection(elements))
        group = "PtC" if ptc else "PGM" if pgm else "nonPGM" if elements else "unknown"
        derivatives = curve_derivatives(g.j.to_numpy(), g.eta_mV.to_numpy())
        for item in derivatives:
            status_counts[item["status"]] = status_counts.get(item["status"], 0) + 1
        eligible = [r for r in derivatives if r["status"] == "eligible"]
        summary = summarize_curve(eligible)
        material = row.enrich_reported_material_name if pd.notna(row.enrich_reported_material_name) else row.curve_label
        record = dict(id=uid, paper=row.paper_key, material=str(material), elements=elements,
                      condition=str(row.regime_class), group=group, pgm=pgm, templates=row.templates,
                      basis=str(row.enrich_current_normalization_basis) if pd.notna(row.enrich_current_normalization_basis) else "unclear",
                      electrolyte=str(row.enrich_electrolyte_identity) if pd.notna(row.enrich_electrolyte_identity) else "",
                      compensation=str(row.enrich_ir_compensation_status) if pd.notna(row.enrich_ir_compensation_status) else "",
                      points=g[["j", "eta_mV"]].to_numpy().tolist(), windows=summary)
        records.append(record)
        local.extend(dict(curve_uid=uid, paper_key=row.paper_key, **r) for r in eligible)
        for axis, values in summary.items():
            for wi, value in enumerate(values):
                if value:
                    windows.append(dict(curve_uid=uid, paper_key=row.paper_key, axis=axis, window_index=wi,
                                        lower=WINDOWS[axis][wi], upper=WINDOWS[axis][wi+1],
                                        slope_mV_dec=value[0], derivative_centers=value[1]))
    w = pd.DataFrame(windows)
    table = []
    for (axis, wi), g in w.groupby(["axis", "window_index"]):
        q = quant(g.slope_mV_dec, pw(g), [.05, .25, .5, .75, .95])
        table.append(dict(axis=axis, window_index=int(wi), lower=WINDOWS[axis][wi], upper=WINDOWS[axis][wi+1],
                          curves=len(g), papers=g.paper_key.nunique(), derivative_centers=int(g.derivative_centers.sum()),
                          **dict(zip(["p05", "p25", "median", "p75", "p95"], q))))
    preferred = ["Pt", "Ru", "Ir", "Pd", "Rh", "Os", "Fe", "Co", "Ni", "Mo", "W", "Cu", "Mn", "Cr", "V", "Ti"]
    elements = {e for r in records for e in r["elements"]}
    data = dict(records=records, windows=WINDOWS, pgmElements=sorted(PGM),
                elements=[e for e in preferred if e in elements] + sorted(elements-set(preferred)),
                rich=["T01", "T02", "T04", "T11", "T15", "T16"],
                sourceCurves=len(records), sourcePapers=points.paper_key.nunique(), sourcePoints=len(points))
    pd.DataFrame(local).to_csv(output / "local_slopes.csv", index=False)
    w.to_csv(output / "curve_window_slopes.csv", index=False)
    pd.DataFrame(table).to_csv(output / "all_paper_weighted_summary.csv", index=False)
    (output / "data.js").write_text("window.TAFEL_DATA=" + json.dumps(data, separators=(",", ":"), ensure_ascii=True, allow_nan=False) + ";\n", encoding="utf-8")
    for name in ["index.html", "app.js", "style.css"]:
        shutil.copy2(HERE / "web" / name, output / name)
    if plotly_js:
        shutil.copy2(plotly_js, output / "plotly.min.js")
    else:
        from plotly.offline import get_plotlyjs
        (output / "plotly.min.js").write_text(get_plotlyjs(), encoding="utf-8")
    shutil.copy2(HERE / "README.md", output / "METHODS.md")
    protocol = dict(source_curves=len(records), source_papers=int(points.paper_key.nunique()),
                    source_points=len(points), eligible_derivative_centers=len(local),
                    curves_with_derivatives=len({r["curve_uid"] for r in local}),
                    derivative_status_counts=status_counts, windows=WINDOWS,
                    source_sha256={p: hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in INPUTS},
                    builder_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                    plotly_sha256=hashlib.sha256((output / "plotly.min.js").read_bytes()).hexdigest(),
                    statistic="Median eligible native local derivative per curve and bin; equal papers by default within each selected group and bin.",
                    derivative="d|eta| / d log10|j|; 9-point tricube-weighted quadratic, unchanged Figure 4 algorithm.",
                    membership="All prepared curves or union of existing template memberships; no new template fitting.",
                    density="Weighted Gaussian KDE with one common user-selected bandwidth in mV/dec; integrates to one over the real line; not a confidence interval.")
    (output / "provenance.json").write_text(json.dumps(protocol, indent=2), encoding="utf-8")
    print(json.dumps({k:v for k,v in protocol.items() if k not in {"source_sha256"}}, indent=2))
    return records, pd.DataFrame(table)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "build/tafel-explorer")
    parser.add_argument("--plotly-js", type=Path, help="Existing Plotly bundle, as an alternative to the Python plotly package")
    args = parser.parse_args()
    build(args.output.resolve(), args.plotly_js)
