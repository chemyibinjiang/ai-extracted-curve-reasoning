"""Numerical and isolated-package tests for Figures 4, 5 and 6."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("NUMBA_NUM_THREADS", "1")
os.environ.setdefault("NUMBA_CACHE_DIR", str(ROOT / "build/test-numba-cache"))
for path in ("analysis/figure4", "analysis/figure5", "analysis/figure6", "analysis/figure6/vendor/vht"):
    sys.path.insert(0, str(ROOT / path))
import numpy as np
import kscn_model
import control_core
from numerics import kinetic_and_jacobian, optimize_scale
from local_slopes import curve_derivatives
from weights import pw
from axis_preparation import clean_series, current_to_ma, potential_reference_basis
from branch_preparation import select_current_sign_branch, transform_to_branch_eta
import pandas as pd


class CoreTests(unittest.TestCase):
    def test_coordinate_units_branch_and_duplicate_points(self):
        current, mode = current_to_ma(np.array([-1000., -2000.]), "uA cm-2", "current density")
        np.testing.assert_array_equal(current, [-1., -2.])
        self.assertEqual(mode, "uA_to_mA")
        self.assertEqual(potential_reference_basis("V", "E vs RHE", "RHE"), "rhe")
        eta, rule = transform_to_branch_eta("rhe", np.array([20., -10., -50., -100.]))
        np.testing.assert_array_equal(eta, [-20., 10., 50., 100.])
        self.assertEqual(rule, "minus_E_RHE_negative_branch")
        mask, sign, _ = select_current_sign_branch(np.array([.3, -.4, -2., -20.]), eta)
        np.testing.assert_array_equal(mask, [False, True, True, True])
        self.assertEqual(sign, -1.)
        j, eta = clean_series(np.array([.1, 1., 1., 2., 600., 4.]), np.array([1., 10., 14., 30., 40., -1.]))
        np.testing.assert_array_equal(j, [1., 2.])
        np.testing.assert_array_equal(eta, [12., 30.])

    def test_local_quadratic_derivative_and_support(self):
        x = np.linspace(-1., 1., 21)
        rows = curve_derivatives(10**x, 20 + 3*x + 5*x*x)
        eligible = [row for row in rows if row["status"] == "eligible"]
        self.assertEqual(len(eligible), 13)
        for row in eligible:
            self.assertAlmostEqual(row["slope_mV_dec"], 3 + 10*x[row["native_index"]], places=10)
        self.assertEqual(sum(row["status"] == "edge_support" for row in rows), 8)

    def test_paper_weights_are_not_curve_weights(self):
        rows = pd.DataFrame(dict(paper_key=["p1", "p1", "p1", "p2"], curve_uid=["a", "b", "c", "d"]))
        np.testing.assert_allclose(pw(rows), [1/6, 1/6, 1/6, 1/2])

    def test_curated_source_hashes_and_scope(self):
        records = json.loads((ROOT / "analysis/SOURCE_MANIFEST.json").read_text())["files"]
        paths = [record["path"] for record in records]
        self.assertEqual(len(paths), len(set(paths)))
        for record in records:
            path = (ROOT / record["path"]).resolve()
            self.assertTrue(path.is_relative_to(ROOT / "analysis"))
            self.assertIn(path.suffix, {".py", ".csv", ".json"})
            data = path.read_bytes()
            self.assertEqual(len(data), record["bytes"], record["path"])
            self.assertEqual(hashlib.sha256(data).hexdigest(), record["sha256"], record["path"])

    def test_kinetic_jacobian(self):
        parameters = np.array([-3., .4, .5, .5, -1., -.7, 0., .1])
        x = np.array([np.geomspace(.1, 10, 11), np.geomspace(.2, 20, 11)])
        _, jacobian = kinetic_and_jacobian(parameters, x)
        delta = 1e-5
        for i in range(len(parameters)):
            perturb = np.zeros_like(parameters)
            perturb[i] = delta
            plus, _ = kinetic_and_jacobian(parameters + perturb, x)
            minus, _ = kinetic_and_jacobian(parameters - perturb, x)
            np.testing.assert_allclose(jacobian[:, :, i], (plus - minus) / (2 * delta), rtol=2e-5, atol=2e-5)

    def test_rate_control_independent_solver_and_gauge(self):
        row = SimpleNamespace(log10_kH_over_kV=-3., log10_kT_over_kV=.4,
            kH_over_kV=1e-3, kT_over_kV=10**.4, DeltaG_eff_meV=60., alphaV=.5, alphaH=.5)
        for voltage in (10., 50., 150.):
            baseline = control_core.state(row, voltage)
            for perturb in (np.zeros(3), np.array([.2, -.1, .3])):
                np.testing.assert_allclose(control_core.state(row, voltage, perturb),
                    control_core.independent_state(row, voltage, perturb), rtol=1e-8, atol=1e-10)
            scaled = control_core.state(row, voltage, np.full(3, .2))
            np.testing.assert_allclose(scaled[[0, 3, 4, 5]], np.exp(.2) * baseline[[0, 3, 4, 5]], rtol=1e-10)
            np.testing.assert_allclose(scaled[1:3], baseline[1:3], atol=1e-12)
            self.assertAlmostEqual(control_core.rate_control(row, voltage).sum(), 1., places=6)
        equilibrium = control_core.state(row, 0.)
        rates = control_core.elementary_rates(row, 0., equilibrium[1])
        np.testing.assert_allclose(rates[::2], rates[1::2], rtol=1e-10, atol=1e-12)

    def test_scale_fit_preserves_point_support(self):
        x = np.geomspace(1, 20, 20)
        factor, lo, hi, boundary = optimize_scale(x, x / 1.5, lambda q: q, .5, 30.)
        self.assertAlmostEqual(factor, 1.5, places=7)
        self.assertGreaterEqual((x / factor).min(), .5)
        self.assertLessEqual((x / factor).max(), 30.)
        self.assertFalse(boundary)
        self.assertLessEqual(lo, 0.)
        self.assertGreaterEqual(hi, 0.)

    def test_kscn_scaling_and_forward_inverse(self):
        saved = json.loads((ROOT / "analysis/figure5/reference/KSCN_MODEL.json").read_text())
        parameters = np.array(saved["parameters"])
        voltage = np.linspace(10., 120., 20)
        original = kscn_model.state(voltage, parameters)
        scaled = kscn_model.state(voltage, kscn_model.scaled_parameters(parameters, saved["factor"], "finite_volmer"))
        np.testing.assert_allclose(scaled["current"], saved["factor"] * original["current"], rtol=1e-10)
        np.testing.assert_allclose(scaled["theta"], original["theta"], rtol=1e-10)
        np.testing.assert_allclose(kscn_model.inverse(original["current"], parameters), voltage, atol=1e-8)
        with self.assertRaises(ValueError):
            kscn_model.scaled_parameters(parameters, 0, "finite_volmer")


class IsolatedPackageTests(unittest.TestCase):
    def test_entry_points_without_external_files(self):
        # An explicit small allowlist, not a copy of the working repository.
        with tempfile.TemporaryDirectory(prefix="figure-analysis-check-") as directory:
            isolated = Path(directory).resolve()
            for relative in ("analysis/common", "analysis/figure4", "analysis/figure5", "analysis/figure6"):
                shutil.copytree(ROOT / relative, isolated / relative,
                                ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
            dataset = Path("data_literature/zenodo_extracted_curve_dataset_v1")
            (isolated / dataset).mkdir(parents=True)
            for name in ("curve_metadata.csv", "curve_points_long.csv", "source_publication_records.csv"):
                shutil.copy2(ROOT / dataset / name, isolated / dataset / name)
            (isolated / "scripts").mkdir()
            shutil.copy2(ROOT / "scripts/validate_figures.py", isolated / "scripts/validate_figures.py")
            env = os.environ.copy()
            env.pop("PYTHONPATH", None)
            env.pop("FIGURE6_OUTPUT", None)
            env["NUMBA_CACHE_DIR"] = str(isolated / "build/numba-cache")
            for script in ("analysis/figure4/run.py", "analysis/figure5/run.py", "analysis/figure6/run.py"):
                result = subprocess.run([sys.executable, script], cwd=isolated, env=env,
                    capture_output=True, text=True, timeout=180)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            f4 = json.loads((isolated / "build/figure4/CHECKS.json").read_text())
            self.assertEqual(f4["curves"], 3033)
            self.assertEqual(f4["original_points"], 80399)
            self.assertEqual(f4["local_derivative_centers"], 48478)
            self.assertEqual(f4["BVjR_passes"], 2351)
            preparation = json.loads((isolated / "build/figure4/PREPARATION_CHECKS.json").read_text())
            self.assertEqual(preparation["extracted_curves"], 4211)
            self.assertEqual(preparation["extracted_points"], 132314)
            self.assertEqual(sum(preparation["selection_counts"].values()), 4211)
            self.assertTrue(preparation["figure4_coordinates_and_selection_reproduced"])
            ledger = pd.read_csv(isolated / "build/figure4/COHORT_SELECTION.csv")
            self.assertEqual(ledger.included_figure4.sum(), 3033)
            self.assertEqual((~ledger.included_figure4).sum(), 1178)
            self.assertTrue(ledger.curve_uid.is_unique)
            f5 = json.loads((isolated / "build/figure5/RESULTS.json").read_text())
            self.assertEqual(f5["D"]["NiFeP_points"], 61)
            self.assertEqual(f5["D"]["KSCN_heldout_points"], 22)
            self.assertEqual(f5["C"]["selected_source"], "figure4_experiment")
            self.assertEqual(f5["C"]["n"], 40)
            self.assertIn("independently fitted", f5["C"]["theta_source"])
            self.assertLess(f5["C"]["VHT_best"]["RMSE_mV"], .67)
            f6 = json.loads((isolated / "build/figure6/REPLAY_CHECKS.json").read_text())
            self.assertEqual(f6["family_grid_rows"], 4591)
            self.assertEqual(f6["dominant_crossings"], 12)
            self.assertEqual(f6["acid_VHT_passes"], 48)
            self.assertEqual(f6["KOH_VHT_passes"], 174)
            self.assertFalse(f6["kinetic_parameters_refitted"])
            refit = subprocess.run([sys.executable, "analysis/figure4/run.py", "refit", "--workers", "4",
                "--output", "build/figure4-refit"], cwd=isolated, env=env, capture_output=True, text=True, timeout=600)
            self.assertEqual(refit.returncode, 0, refit.stdout + refit.stderr)
            checks = json.loads((isolated / "build/figure4-refit/REFIT_CHECKS.json").read_text())
            self.assertEqual(checks["model_fits"], 6066)
            self.assertTrue(checks["reference_objectives_reproduced"])
            for prefix, expected in [("bv", 806), ("bvir", 2351)]:
                self.assertEqual(checks["models"][prefix]["successful_fits"], 3033)
                self.assertEqual(checks["models"][prefix]["R2_ge_099"], expected)
                self.assertEqual(checks["models"][prefix]["pass_assignment_changes"], 0)


if __name__ == "__main__":
    unittest.main()
