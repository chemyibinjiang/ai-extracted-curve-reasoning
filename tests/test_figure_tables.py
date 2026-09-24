"""Regression tests for the scientific checks, including deliberate corruption."""

from copy import deepcopy
from pathlib import Path
import sys
import unittest
import json
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from validate_figures import load_tables, validate_science


class FigureTableTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tables = load_tables(ROOT)

    def test_frozen_science(self):
        result = validate_science(self.tables)
        self.assertEqual(result["dominant_crossings"], 12)
        self.assertEqual(result["mean_crossings"], 2)

    def test_figure5_direct_kinetic_fit_artwork(self):
        root = ET.parse(ROOT / "figures/manuscript/Figure5.svg").getroot()
        row = next(node for node in root if node.get("id") == "row_C")
        text = " ".join(row.itertext())
        for label in ("NiMo: empirical fits", "VHT fit", "Predicted coverage", "No jR term", "Same LSV"):
            self.assertIn(label, text)
        ids = [node.get("id") for node in root.iter() if node.get("id")]
        self.assertEqual(len(ids), len(set(ids)))
        report = json.loads((ROOT / "reproducibility/figure5-nimo-validation.json").read_text())
        self.assertEqual(report["selected_source"], "figure4_experiment")
        self.assertEqual(report["n"], 40)
        for item in report["metrics"]:
            self.assertIn(f"{item['RMSE_mV']:.2f} mV", text)

    def test_population_sd_is_not_accepted(self):
        tables = deepcopy(self.tables)
        row = tables["RATE_CONTROL_MEAN_SD"][0]
        n = int(row["n_families"])
        row["X_V_sd"] = str(float(row["X_V_sd"]) * ((n - 1) / n) ** 0.5)
        with self.assertRaisesRegex(ValueError, "Sample SD mismatch"):
            validate_science(tables)

    def test_missing_a4_crossover_is_not_accepted(self):
        tables = deepcopy(self.tables)
        tables["CONTROL_CROSSINGS"] = [r for r in tables["CONTROL_CROSSINGS"] if r["family"] != "A4"]
        with self.assertRaisesRegex(ValueError, "Crossing count mismatch"):
            validate_science(tables)

    def test_coverage_denominator_cannot_be_total_cohort(self):
        tables = deepcopy(self.tables)
        tables["COVERAGE_BARS"][0]["denominator"] = "81"
        with self.assertRaisesRegex(ValueError, "Coverage denominator changed"):
            validate_science(tables)

    def test_extrapolated_mean_is_not_supported(self):
        tables = deepcopy(self.tables)
        tables["RATE_CONTROL_MEAN_SD"][0]["all_families_supported"] = "True"
        with self.assertRaisesRegex(ValueError, "Common-support mask changed"):
            validate_science(tables)

    def test_duplicate_family_is_not_accepted(self):
        tables = deepcopy(self.tables)
        first = tables["RATE_CONTROL_FAMILY_GRID"][0]
        duplicate = next(r for r in tables["RATE_CONTROL_FAMILY_GRID"]
                         if r["condition"] == first["condition"]
                         and r["eta_mV"] == first["eta_mV"] and r["family"] != first["family"])
        first["family"] = duplicate["family"]
        with self.assertRaisesRegex(ValueError, "Missing or duplicate family"):
            validate_science(tables)


if __name__ == "__main__":
    unittest.main()
