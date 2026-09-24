"""Independent physical checks and a self-contained direct NiMo refit."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

import numpy as np
import pandas as pd
from scipy.optimize import brentq

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "analysis/figure5"))
import nimo_vht as model


class NiMoKineticsTests(unittest.TestCase):
    def test_detailed_balance_and_independent_steady_state(self):
        for p in ([-2., .5, -1.2, .3], [1., -.3, 1.5, -.2]):
            h, t, K, scale = 10.**np.array(p)
            voltage = np.array([0., 20., 70., 150.])
            calculated = model.forward(voltage, p)
            for i, eta in enumerate(voltage):
                u = eta / model.THERMAL

                def rates(theta):
                    vacancy = 1-theta
                    return np.array([vacancy*np.exp(u/2), theta*np.exp(-u/2)/K,
                        h*theta*np.exp(u/2), h*K*vacancy*np.exp(-u/2),
                        t*theta**2, t*K*K*vacancy**2])

                def balance(theta):
                    v, h_rate, t_rate = rates(theta).reshape(3, 2) @ np.array([1., -1.])
                    return v-h_rate-2*t_rate

                theta = brentq(balance, 0., 1., xtol=1e-14)
                self.assertAlmostEqual(calculated["theta"][i], theta, places=11)
                rates_at_root = rates(theta)
                current = scale * (rates_at_root[0]-rates_at_root[1]+rates_at_root[2]-rates_at_root[3])
                np.testing.assert_allclose(calculated["current"][i], current, atol=1e-10, rtol=1e-10)
                if eta == 0:
                    self.assertAlmostEqual(theta, K/(1+K), places=12)
                    np.testing.assert_allclose(rates_at_root[::2], rates_at_root[1::2], rtol=1e-11)

    def test_symmetry_and_inverse(self):
        for p in (np.array([-2., .5, -1.2, .3]), np.array([-5., -5.2778, -1.4107, 4.8497])):
            eta = np.linspace(5, 200, 35)
            original = model.forward(eta, p)
            mirrored = model.forward(eta, model.mirror(p))
            np.testing.assert_allclose(original["theta"] + mirrored["theta"], 1., atol=1e-11)
            np.testing.assert_allclose(original["current"], mirrored["current"], rtol=1e-9, atol=1e-9)
            np.testing.assert_allclose(model.inverse(original["current"], p), eta, atol=1e-7)
            np.testing.assert_allclose(model.mirror(model.mirror(p)), p, atol=1e-12)
        with self.assertRaises(ValueError):
            model.inverse(np.array([-1.]), p)
        with self.assertRaises(ValueError):
            model.inverse(np.array([np.nan]), p)

    def test_isolated_fit_and_diagnostics(self):
        with tempfile.TemporaryDirectory(prefix="nimo-vht-check-") as temporary:
            root = Path(temporary)
            for relative in ("analysis/common/strict_bv.py", "analysis/figure5/nimo_vht.py",
                "analysis/figure5/refit_nimo.py", "analysis/figure5/inputs/C_PRIMARY_DATA.csv",
                "analysis/figure6/vendor/vht/independent_model.py"):
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(ROOT / relative, target)
            env = os.environ.copy()
            env.pop("PYTHONPATH", None)
            env["NUMBA_CACHE_DIR"] = str(root / "numba-cache")
            result = subprocess.run([sys.executable, "analysis/figure5/refit_nimo.py", "--starts", "32", "--no-plot"],
                cwd=root, env=env, capture_output=True, text=True, timeout=180)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            out = root / "build/figure5-nimo"
            report = json.loads((out / "C_NIMO_REPORT.json").read_text())
            self.assertEqual(report["n"], 40)
            self.assertEqual(report["selected_source"], "figure4_experiment")
            self.assertIn("no resistance or offset", report["VHT_convention"])
            errors = {r["model"]: r["RMSE_mV"] for r in report["metrics"]}
            np.testing.assert_allclose([errors[n] for n in ["BV", "BV+jR", "VHT"]],
                                       [2.402925, .427313, .660728], atol=2e-4, rtol=0)
            self.assertLess(report["maximum_relative_balance_error"], 1e-7)
            self.assertLess(report["diagnostics"]["wider_bounds"]["max_prediction_change_mV"], .002)
            self.assertLess(report["diagnostics"]["VH_limit"]["RMSE_mV"], .68)
            cv = pd.read_csv(out / "C_NIMO_CROSS_VALIDATION.csv")
            self.assertEqual(len(cv), 120)
            self.assertFalse(cv.duplicated(["model", "index"]).any())
            self.assertTrue(cv["index"].mod(5).eq(cv.fold).all())
            for name, group in cv.groupby("model"):
                self.assertEqual(set(group["index"]), set(range(40)))
                rmse = np.sqrt(np.mean((group.predicted_eta_mV-group.observed_eta_mV)**2))
                self.assertLess(rmse, 2.6 if name == "BV" else .8)
            coverage = pd.read_csv(out / "C_NIMO_PREDICTED_COVERAGE.csv")
            np.testing.assert_allclose(coverage.theta + coverage.theta_mirror, 1, atol=1e-10)
            self.assertTrue(coverage.theta.between(0, 1).all())
            self.assertTrue(coverage.eta_mV.between(*report["voltage_range_mV"]).all())
            windows = pd.read_csv(out / "C_NIMO_WINDOW_CHECKS.csv")
            self.assertEqual(len(windows), 9)
            for _, rows in windows.groupby(["requested_j_min", "requested_j_max"]):
                self.assertEqual(rows.n.nunique(), 1)
                self.assertTrue((rows.actual_j_min >= rows.requested_j_min).all())
                self.assertTrue((rows.actual_j_max <= rows.requested_j_max).all())


if __name__ == "__main__":
    unittest.main()
