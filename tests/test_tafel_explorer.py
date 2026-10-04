"""Observed-slope explorer regression and metadata checks."""
import importlib.util
from pathlib import Path
import unittest

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("tafel_explorer", ROOT / "analysis/tafel_explorer/build.py")
explorer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(explorer)


class TafelExplorerTests(unittest.TestCase):
    def test_window_boundaries(self):
        edges = [0, 25, 50, 100]
        for value, expected in [(-1, None), (0, 0), (24.99, 0), (25, 1), (50, 2), (100, 2), (101, None)]:
            self.assertEqual(explorer.window_index(value, edges), expected)

    def test_negative_slopes_and_curve_medians(self):
        rows = [dict(eta_mV=60, j=6, slope_mV_dec=v) for v in [-100, 10, 40]]
        summary = explorer.summarize_curve(rows)
        self.assertEqual(summary["eta"][2], [10., 3])
        self.assertEqual(summary["current"][2], [10., 3])
        negative = explorer.summarize_curve([rows[0]])
        self.assertEqual(negative["eta"][2], [-100., 1])

    def test_metadata_matches_template_catalog(self):
        m = explorer.load_metadata()
        matched = m[m.templates.map(bool)]
        self.assertEqual(len(m), 3033)
        self.assertEqual(len(matched), 1343)
        corrected = m.set_index("curve_uid").loc["batch1/case74/figure_1__c/curve_5"]
        self.assertEqual(set(explorer.json.loads(corrected.enrich_active_elements)), {"Co", "Sc"})
        self.assertEqual(corrected.templates, ["T11", "T12", "T15"])
        elements = matched.enrich_active_elements.map(explorer.json.loads)
        self.assertEqual(elements.map(lambda x: bool(set(x) & explorer.PGM)).sum(), 695)
        self.assertFalse(matched.is_ptc.any())

    def test_reproduces_figure4_potential_windows(self):
        points = pd.read_csv(ROOT / explorer.INPUTS[0], float_precision="round_trip")
        rows = []
        for uid, g in points.groupby("curve_uid"):
            g = g.sort_values("native_index")
            eligible = [r for r in explorer.curve_derivatives(g.j.to_numpy(), g.eta_mV.to_numpy()) if r["status"] == "eligible"]
            summary = explorer.summarize_curve(eligible)
            for wi, value in enumerate(summary["eta"]):
                if value:
                    rows.append(dict(curve_uid=uid, paper_key=g.paper_key.iloc[0], window=wi, slope=value[0]))
        frame = pd.DataFrame(rows)
        expected_counts = [291, 740, 1398, 1435, 1317, 1262, 775, 410]
        expected_medians = [40.18903042744924,64.74172094814476,109.27546945454023,158.58812415015817,
                            184.1912930315615,198.61206724486038,236.0731089132335,302.6470404880887]
        for wi, g in frame.groupby("window"):
            self.assertEqual(len(g), expected_counts[wi])
            np.testing.assert_allclose(explorer.quant(g.slope, explorer.pw(g), [.5])[0], expected_medians[wi], rtol=1e-10)


if __name__ == "__main__":
    unittest.main()
