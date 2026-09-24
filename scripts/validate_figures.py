"""Validate manuscript artwork and recompute Figure 6 summary statistics.

Uses the Python standard library. Does not run extraction, discovery, or fitting.
"""

import argparse
from collections import defaultdict
import csv
import hashlib
import itertools
import json
import math
from pathlib import Path
import statistics
import struct
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
RELEASE = Path("reproducibility/manifest.json")
TABLE_NAMES = (
    "COVERAGE_BARS", "PARAMETER_COORDINATES", "RATE_CONTROL_MEAN_SD",
    "MEAN_CONTROL_CROSSINGS", "CONTROL_CROSSINGS", "RATE_CONTROL_FAMILY_GRID",
)
FAMILIES = {"acid": {f"A{i}" for i in range(1, 5)},
            "KOH": {f"B{i}" for i in range(1, 6)}}
STEPS = ("V", "H", "T")
# The finalized Figure 1 contains two identical Inkscape mesh-rendering polyfills.
MESH_POLYFILL_SHA256 = "3e30e1359b419c41df1992d3a86174a8c744d4a4a64333d76856a197f413b6ad"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def close(actual, expected, message, tolerance=1e-9):
    require(math.isfinite(actual) and math.isfinite(expected)
            and math.isclose(actual, expected, rel_tol=tolerance, abs_tol=tolerance),
            f"{message}: {actual} != {expected}")


def boolean(value):
    require(value in ("True", "False"), f"Invalid Boolean: {value}")
    return value == "True"


def publication_family(condition, source):
    mapping = {(c, f if c == "acid" else f.replace("B", "K")): f
               for c, families in FAMILIES.items() for f in families}
    require((condition, source) in mapping, "Unknown source family")
    return mapping[(condition, source)]


def validate_assets(root):
    manifest = json.loads((root / RELEASE).read_text(encoding="utf-8"))
    require(manifest["schema_version"] == 1, "Unsupported manifest schema")
    expected = {f"figures/manuscript/Figure{i}.{ext}"
                for i in range(1, 7) for ext in ("svg", "png")}
    expected |= {f"analysis/figure6/expected/{name}.csv" for name in TABLE_NAMES}
    paths = [record["path"] for record in manifest["assets"]]
    require(len(paths) == len(set(paths)) and set(paths) == expected,
            "Figure manifest must contain exactly the 18 expected assets")
    for record in manifest["assets"]:
        path = root / record["path"]
        require(path.is_file(), f"Missing asset: {path}")
        raw = path.read_bytes()
        require(not raw.startswith(b"version https://git-lfs.github.com/spec/v1"),
                f"LFS pointer instead of asset: {path}; run git lfs pull for manuscript figures")
        require(len(raw) == record["bytes"], f"File size changed: {path}")
        require(hashlib.sha256(raw).hexdigest() == record["sha256"],
                f"SHA-256 mismatch: {path}")
        if record["kind"] == "png":
            require(raw[:8] == b"\x89PNG\r\n\x1a\n" and raw[12:16] == b"IHDR",
                    f"Invalid PNG: {path}")
            require(list(struct.unpack(">II", raw[16:24])) == record["dimensions"],
                    f"PNG dimensions changed: {path}")
        elif record["kind"] == "svg":
            svg = ET.fromstring(raw)
            require(svg.tag == "{http://www.w3.org/2000/svg}svg", f"Invalid SVG: {path}")
            viewbox = [float(x) for x in svg.attrib.get("viewBox", "").split()]
            require(len(viewbox) == 4 and min(viewbox[2:]) > 0, f"Invalid viewBox: {path}")
            for node in svg.iter():
                if node.tag.rsplit("}", 1)[-1] == "script":
                    checksum = hashlib.sha256("".join(node.itertext()).encode()).hexdigest()
                    require(path.name == "Figure1.svg" and checksum == MESH_POLYFILL_SHA256,
                            f"Unrecognized script in SVG: {path}")
                for key, value in node.attrib.items():
                    if key.rsplit("}", 1)[-1] == "href":
                        require(not value or value.startswith(("#", "data:")),
                                f"External SVG reference in {path.name}: {value[:80]}")
    return len(paths)


def load_tables(root):
    tables = {}
    for name in TABLE_NAMES:
        with (root / "analysis/figure6/expected" / f"{name}.csv").open(
                encoding="utf-8-sig", newline="") as stream:
            tables[name] = list(csv.DictReader(stream))
    return tables


def dominant_crossings(rows, condition, family, mean=False):
    support = "all_families_supported" if mean else "inside_fitted_support"
    suffix = "_mean" if mean else ""
    rows = sorted((r for r in rows if boolean(r[support])), key=lambda r: float(r["eta_mV"]))
    found = []
    for first, second in zip(rows, rows[1:]):
        x0, x1 = float(first["eta_mV"]), float(second["eta_mV"])
        close(x1 - x0, 0.5, "Rate-control grid must be contiguous")
        # Order T/V first to use the same pair notation as the published table.
        for a, b in itertools.combinations(("T", "V", "H"), 2):
            a0, a1 = (float(row[f"X_{a}{suffix}"]) for row in (first, second))
            b0, b1 = (float(row[f"X_{b}{suffix}"]) for row in (first, second))
            d0, d1 = a0 - b0, a1 - b1
            if d0 * d1 > 0 or d0 == d1:
                continue
            fraction = d0 / (d0 - d1)
            x = x0 + fraction * (x1 - x0)
            y = a0 + fraction * (a1 - a0)
            others = [float(first[f"X_{s}{suffix}"]) + fraction *
                      (float(second[f"X_{s}{suffix}"]) - float(first[f"X_{s}{suffix}"]))
                      for s in STEPS if s not in (a, b)]
            if y >= max(others) - 1e-10:
                item = (condition, family, f"X_{a}=X_{b}", x, y)
                if item not in found:
                    found.append(item)
    return found


def compare_crossings(saved, calculated):
    actual = []
    for row in saved:
        require(boolean(row["within_fitted_support"])
                and boolean(row["dominant_control_crossing"]), "Unsupported crossing")
        actual.append((row["condition"], row["family"], row["pair"],
                       float(row["eta_mV"]), float(row["control"])))
    require(len(actual) == len(calculated), "Crossing count mismatch")
    for observed, expected in zip(sorted(actual), sorted(calculated)):
        require(observed[:3] == expected[:3], "Crossing identity mismatch")
        close(observed[3], expected[3], "Crossing potential mismatch", 1e-8)
        close(observed[4], expected[4], "Crossing control mismatch", 1e-8)


def validate_science(tables):
    coverage = tables["COVERAGE_BARS"]
    require(len(coverage) == 20, "Expected 20 template coverage bars")
    for condition, (denominator, budget, covered) in {
            "acid": (73, 4, 59), "KOH": (234, 5, 195)}.items():
        rows = sorted((r for r in coverage if r["condition"] == condition), key=lambda r: int(r["K"]))
        require([int(r["K"]) for r in rows] == list(range(1, 11)), "Incomplete coverage budgets")
        for row in rows:
            require(int(row["denominator"]) == denominator, "Coverage denominator changed")
            percentage = float(row["coverage_percent"])
            require(0 <= percentage <= 100, "Invalid coverage percentage")
            count = percentage * denominator / 100
            close(count, round(count), "Nonintegral coverage count")
        require([int(r["K"]) for r in rows if boolean(r["selected"])] == [budget],
                "Selected coverage budget changed")
        require(next(int(r["K"]) for r in rows if float(r["coverage_percent"]) >= 80) == budget,
                "Selected budget is not the first attaining 80 percent")
        close(float(rows[budget - 1]["coverage_percent"]), 100 * covered / denominator,
              "Selected coverage changed")

    parameters = tables["PARAMETER_COORDINATES"]
    require(len(parameters) == 9, "Expected nine representative parameter coordinates")
    identities = {(r["condition"], r["family"]) for r in parameters}
    expected_identities = {(c, f) for c, families in FAMILIES.items() for f in families}
    require(identities == expected_identities, "Parameter family identities changed")
    for row in parameters:
        require(publication_family(row["condition"], row["source_family"]) == row["family"],
                "Publication/source family mapping changed")
        ratio, reference = float(row["kT_over_kV"]), float(row["acid_reference_kT_over_kV"])
        require(ratio > 0 and reference > 0, "Invalid rate ratio")
        close(reference, 2.2595462971415303, "Acid reference changed")
        close(float(row["log10_relative_TV"]), math.log10(ratio / reference), "Rate transform changed")
        if row["condition"] == "acid":
            close(ratio, reference, "Shared acid rate-ratio constraint changed")

    grid = tables["RATE_CONTROL_FAMILY_GRID"]
    means = tables["RATE_CONTROL_MEAN_SD"]
    require(len(grid) == 4591 and len(means) == 998, "Unexpected rate-control grid sizes")
    by_point, by_family, by_condition = defaultdict(list), defaultdict(list), defaultdict(list)
    for source in grid:
        row = dict(source, family=publication_family(source["condition"], source["family"]))
        condition, family, eta = row["condition"], row["family"], float(row["eta_mV"])
        require((condition, family) in expected_identities, "Unknown family in rate-control grid")
        require(1 <= eta <= {"acid": 200, "KOH": 300}[condition], "Grid exceeds analysis window")
        supported = float(row["fitted_support_min_mV"]) <= eta <= float(row["fitted_support_max_mV"])
        require(boolean(row["inside_fitted_support"]) == supported, "Family support mask changed")
        close(sum(float(row[f"X_{s}"]) for s in STEPS), 1.0, "Control sum", 1e-5)
        by_point[(condition, eta)].append(row)
        by_family[(condition, family)].append(row)
    seen = set()
    for row in means:
        condition, eta = row["condition"], float(row["eta_mV"])
        key = (condition, eta)
        require(key not in seen, "Duplicate mean-grid point")
        seen.add(key)
        families = by_point[key]
        n = len(FAMILIES[condition])
        require(len(families) == n and {r["family"] for r in families} == FAMILIES[condition],
                "Missing or duplicate family at grid point")
        require(int(row["n_families"]) == n, "Wrong family denominator")
        inside = sum(boolean(r["inside_fitted_support"]) for r in families)
        require(int(row["n_families_supported"]) == inside, "Support count changed")
        require(boolean(row["all_families_supported"]) == (inside == n), "Common-support mask changed")
        for step in STEPS:
            values = [float(r[f"X_{step}"]) for r in families]
            close(float(row[f"X_{step}_mean"]), statistics.mean(values), "Family mean mismatch")
            close(float(row[f"X_{step}_sd"]), statistics.stdev(values), "Sample SD mismatch")
        by_condition[condition].append(row)
    require(seen == set(by_point), "Mean grid does not cover all family grid points")
    crossings = []
    for (condition, family), rows in by_family.items():
        crossings.extend(dominant_crossings(rows, condition, family))
    mean_crossings = []
    for condition, rows in by_condition.items():
        mean_crossings.extend(dominant_crossings(rows, condition, "mean", mean=True))
    compare_crossings(tables["MEAN_CONTROL_CROSSINGS"], mean_crossings)
    compare_crossings(tables["CONTROL_CROSSINGS"], crossings + mean_crossings)
    return dict(parameter_coordinates=len(parameters), family_grid_rows=len(grid),
                mean_sd_rows=len(means), dominant_crossings=len(crossings + mean_crossings),
                mean_crossings=len(mean_crossings))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    root = args.root.resolve()
    report = dict(validated_assets=validate_assets(root), **validate_science(load_tables(root)))
    report["scope"] = "Frozen artwork integrity and numeric summary audit; no refitting"
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
