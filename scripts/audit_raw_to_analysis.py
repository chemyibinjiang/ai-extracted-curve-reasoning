"""Trace the published coordinate ZIP through preparation to analysis inputs.

This audits extracted numerical coordinates, not the digitization of source
images. Model refits and template-match checks are separate run.py stages.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import tempfile
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data_literature/zenodo_extracted_curve_dataset_v1"
ARCHIVE = DATA.with_suffix(".zip")
CSV_NAMES = {"axis_fits.csv", "curve_metadata.csv", "curve_points_long.csv",
             "DATA_DICTIONARY.csv", "panel_metadata.csv", "source_publication_records.csv"}
NAMES = CSV_NAMES | {"dataset_summary.json", "LICENSE_NOTE.md", "README.md",
                     "SCHEMA.md", "SHA256SUMS.txt"}


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def check_archive(archive=ARCHIVE, folder=DATA):
    """Require identical ZIP/folder releases, including documentation and hashes."""
    with ZipFile(archive) as zipped:
        names = zipped.namelist()
        if len(names) != len(NAMES) or set(names) != NAMES:
            raise ValueError("Unexpected or duplicate dataset ZIP entries")
        if zipped.testzip() is not None:
            raise ValueError("Dataset ZIP CRC failure")
        contents = {name: zipped.read(name) for name in names}
    for name, raw in contents.items():
        if raw != (folder / name).read_bytes():
            raise ValueError(f"ZIP/folder mismatch: {name}")
    hashes = {}
    for line in contents["SHA256SUMS.txt"].decode("utf-8-sig").splitlines():
        expected, name = line.split("  ", 1)
        if name in hashes or name not in NAMES - {"SHA256SUMS.txt"}:
            raise ValueError(f"Unexpected checksum entry: {name}")
        if digest(contents[name]) != expected:
            raise ValueError(f"ZIP checksum mismatch: {name}")
        hashes[name] = expected
    if set(hashes) != NAMES - {"SHA256SUMS.txt"}:
        raise ValueError("Incomplete ZIP checksums")
    return contents


def audit(output):
    import numpy as np
    import pandas as pd

    sys.path.insert(0, str(ROOT / "analysis/figure4"))
    import prepare as preparation
    from validate_dataset import validate

    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    contents = check_archive()
    report = {"archive_sha256": digest(ARCHIVE.read_bytes()), "archive_files": len(contents),
              "coordinate_table_sha256": {name: digest(contents[name]) for name in sorted(CSV_NAMES)},
              "zip_matches_folder": True}
    # Known basenames only; no paths from an archive are used for extraction.
    build = ROOT / "build"
    build.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="raw-audit-", dir=build) as directory:
        folder = Path(directory)
        for name, raw in contents.items():
            (folder / name).write_bytes(raw)
        report["raw_dataset"] = validate(folder)
        previous = preparation.DATASET
        try:
            preparation.DATASET = folder
            report["preparation"] = preparation.prepare(output / "preparation")
        finally:
            preparation.DATASET = previous
        # Record durable archive-member provenance instead of temporary paths.
        for item in report["preparation"]["sources"]:
            item["path"] = "data_literature/zenodo_extracted_curve_dataset_v1.zip!" + Path(item["path"]).name
        (output / "preparation/PREPARATION_CHECKS.json").write_text(
            json.dumps(report["preparation"], indent=2) + "\n", encoding="utf-8")

    read = preparation.read
    points = read(output / "preparation/PREPARED_POINTS.csv")
    keys = ["curve_uid", "native_index"]
    expected = read(ROOT / "analysis/figure7/inputs/POINTS.csv").sort_values(keys).reset_index(drop=True)
    pd.testing.assert_frame_equal(points, expected, check_dtype=False, rtol=1e-12, atol=1e-10)
    groups = {uid: part.sort_values("native_index") for uid, part in points.groupby("curve_uid")}
    report["figure7_prepared_points"] = len(points)
    report["ptc_native_inputs"] = {}
    for condition in ("acidic", "alkaline"):
        table = read(ROOT / f"analysis/figure6/inputs/{condition}/cohort_all_points.csv")
        for uid, part in table.groupby("curve_uid"):
            actual = part.sort_values("fit_point_index")[["j_mA_cm2", "eta_mV"]].to_numpy()
            expected = groups[uid][["j", "eta_mV"]].to_numpy()
            np.testing.assert_allclose(actual, expected, rtol=1e-12, atol=1e-10, err_msg=uid)
        report["ptc_native_inputs"][condition] = dict(curves=int(table.curve_uid.nunique()), points=len(table))

    native_count = 0
    with np.load(ROOT / "analysis/figure7/inputs/NATIVE_CURVES.npz", allow_pickle=False) as native:
        assert len(set(native["curve_uid"])) == len(native["curve_uid"])
        for i, uid in enumerate(native["curve_uid"]):
            part = groups[uid]
            part = part[part.eta_mV.between(0, 300)]
            n = int(native["n"][i])
            assert n == len(part), uid
            actual = np.column_stack([native["J"][i, :n], native["Y"][i, :n]])
            np.testing.assert_allclose(actual, part[["j", "eta_mV"]].to_numpy(),
                                       rtol=1e-12, atol=1e-10, err_msg=uid)
            np.testing.assert_allclose(native["tss"][i], np.sum((part.eta_mV - part.eta_mV.mean())**2),
                                       rtol=1e-12, atol=1e-10, err_msg=uid)
            native_count += n
        report["template_native_inputs"] = dict(curves=len(native["curve_uid"]), points=native_count)

    canonical = read(ROOT / "analysis/figure7/inputs/canonical_curves.csv").set_index("curve_uid").sort_index()
    archived_metadata_rows = len(canonical)
    canonical = canonical.loc[sorted(groups)]
    raw_metadata = read(DATA / "curve_metadata.csv").set_index("curve_uid")
    expected = raw_metadata.loc[canonical.index, canonical.columns]
    pd.testing.assert_frame_equal(canonical, expected, check_dtype=False)
    report["composition_metadata"] = dict(analysis_curves=len(canonical), fields=len(canonical.columns),
                                         archived_rows_not_used=archived_metadata_rows-len(canonical))
    report["status"] = "pass"
    report["scope"] = ("Every released extracted curve is processed in the preparation ledger. "
                       "All retained native Pt/C and Figure 7 inputs match that preparation. "
                       "Digitization from source images and new template-library discovery are not rerun here.")
    (output / "RAW_TO_ANALYSIS_AUDIT.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "build/raw-to-analysis")
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to(ROOT / "build"):
        parser.error("Keep audit outputs inside build/")
    print(json.dumps(audit(output), indent=2))
