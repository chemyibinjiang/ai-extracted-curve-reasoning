"""Reproduce NiFeP comparisons and audit the layer-to-geometric conversion."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "nifep_examples", ROOT / "analysis/effective_bv/examples.py")
examples = importlib.util.module_from_spec(spec)
spec.loader.exec_module(examples)


class NiFePReproductionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folder = tempfile.TemporaryDirectory(prefix="nifep-reproduction-")
        cls.addClassCleanup(cls.folder.cleanup)
        cls.output = Path(cls.folder.name)
        cls.result = examples.layers(cls.output)
        cls.metrics = pd.read_csv(cls.output / "D_NIFEP_MODEL_COMPARISON.csv")
        cls.points = pd.read_csv(cls.output / "D_NIFEP_PREDICTIONS.csv")

    def test_same_observations_and_exclusions(self):
        original = examples.read("NiFeP_ORIGINAL_DATA.csv")
        excluded = examples.read("NiFeP_EXCLUDED_DATA.csv")
        keys = ["curve_uid", "native_index"]
        self.assertEqual(len(original), 63)
        self.assertEqual(len(excluded), 2)
        self.assertEqual(len(self.points), 61)
        self.assertEqual(set(map(tuple, original[keys].to_numpy())),
                         set(map(tuple, self.points[keys].to_numpy())) |
                         set(map(tuple, excluded[keys].to_numpy())))
        self.assertFalse(set(map(tuple, self.points[keys].to_numpy())) &
                         set(map(tuple, excluded[keys].to_numpy())))
        self.assertEqual(self.points.groupby("layers").size().to_dict(),
                         {12: 24, 18: 20, 24: 17})

    def test_metrics_from_predictions(self):
        self.assertEqual(len(self.metrics), 8)
        self.assertTrue(self.metrics.equivalent_converged.all())
        self.assertTrue(self.metrics.coefficient_sum.between(.001-1e-10, 2+1e-10).all())
        for row in self.metrics.itertuples():
            points = self.points if row.scope == "shared" else self.points[self.points.layers.eq(row.layers)]
            column = row.scope + ("_BV_eta_mV" if row.model == "BV" else "_eta_mV")
            errors = points[column] - points.eta_mV
            self.assertEqual(row.n, len(points))
            self.assertEqual(row.k, 3 if row.model == "BV" else 4)
            self.assertAlmostEqual(row.sse_mV2, float(errors @ errors), places=7)
            self.assertAlmostEqual(row.rmse_mV, float(np.sqrt(np.mean(errors**2))), places=9)
            self.assertAlmostEqual(row.r2, 1-float(errors @ errors)/
                                   float(((points.eta_mV-points.eta_mV.mean())**2).sum()), places=10)
        for _, group in self.metrics.groupby(["scope", "layers"], dropna=False):
            by_model = group.set_index("model")
            self.assertLess(by_model.loc["BV+jR", "sse_mV2"], by_model.loc["BV", "sse_mV2"])

    def test_geometric_current_parameters(self):
        independent = self.metrics[self.metrics.scope.eq("independent")]
        np.testing.assert_allclose(independent.j0_geometric_mA_cm2,
                                   independent.j0_per_layer_mA_cm2 * independent.layers)
        np.testing.assert_allclose(independent.Rapp_geometric_ohm_cm2,
                                   independent.R_per_layer_ohm_cm2 / independent.layers)
        for row in independent.itertuples():
            points = self.points[self.points.layers.eq(row.layers)]
            geometric = dict(log_j0=np.log(row.j0_geometric_mA_cm2),
                             fraction=row.alpha_c/row.coefficient_sum,
                             coefficient_sum=row.coefficient_sum, R=row.Rapp_geometric_ohm_cm2)
            column = "independent_BV_eta_mV" if row.model == "BV" else "independent_eta_mV"
            np.testing.assert_allclose(examples.bv.predict(points.j_mA_cm2.to_numpy(), geometric),
                                       points[column], rtol=1e-9, atol=1e-8)
        shared = self.metrics[self.metrics.scope.eq("shared")]
        self.assertTrue(shared[["layers", "j0_geometric_mA_cm2", "Rapp_geometric_ohm_cm2"]].isna().all().all())
        self.assertAlmostEqual(self.result["inverse_layer_slope"], 17.7716242233, places=5)

    def test_public_reference_outputs(self):
        reference = ROOT / "analysis/figure5/reference"
        expected = pd.read_csv(reference / "NIFEP_MODEL_COMPARISON.csv")
        self.assertEqual(self.metrics[["scope", "model"]].to_dict("records"),
                         expected[["scope", "model"]].to_dict("records"))
        columns = ["n", "k", "rmse_mV", "r2", "Rapp_geometric_ohm_cm2"]
        np.testing.assert_allclose(self.metrics[columns], expected[columns],
                                   rtol=1e-6, atol=1e-7, equal_nan=True)
        expected_points = pd.read_csv(reference / "NIFEP_POINT_PREDICTIONS.csv")
        self.assertEqual(self.points[["curve_uid", "native_index"]].to_dict("records"),
                         expected_points[["curve_uid", "native_index"]].to_dict("records"))
        columns = ["eta_mV", "j_mA_cm2", "shared_eta_mV", "independent_eta_mV",
                   "shared_BV_eta_mV", "independent_BV_eta_mV"]
        np.testing.assert_allclose(self.points[columns], expected_points[columns], rtol=1e-7, atol=1e-6)


if __name__ == "__main__":
    unittest.main()
