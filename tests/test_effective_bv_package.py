"""Run the current refit pipeline in an isolated, coordinate-only package."""
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

ROOT = Path(__file__).resolve().parents[1]


class EffectivePackageTests(unittest.TestCase):
    def test_all_stages_without_exploration_or_external_files(self):
        with tempfile.TemporaryDirectory(prefix="effective-bv-package-") as directory:
            root = Path(directory)
            for relative in ("analysis/common", "analysis/figure4", "analysis/figure5",
                             "analysis/figure6", "analysis/effective_bv"):
                shutil.copytree(ROOT/relative, root/relative,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.nbc", "*.nbi"))
            env = os.environ.copy()
            env.pop("PYTHONPATH", None)
            env.pop("FIGURE6_OUTPUT", None)
            env["NUMBA_CACHE_DIR"] = str(root/"build/numba-cache")
            result = subprocess.run([sys.executable,"analysis/effective_bv/run.py","all",
                "--workers","6","--starts","2"], cwd=root, env=env,
                capture_output=True, text=True, encoding="utf-8", timeout=600)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            output = root/"build/effective-bv-20260927"
            fits = pd.read_csv(output/"figure4/FITS.csv")
            self.assertEqual(len(fits),6066)
            self.assertTrue(fits.equivalent_converged.all())
            counts = fits.groupby("model").r2.apply(lambda r: int(r.ge(.99).sum())).to_dict()
            self.assertEqual(counts,{"BV":1588,"BV+jR":2361})
            examples = json.loads((output/"figure5/RESULTS.json").read_text())
            metrics = {r["model"]:r for r in examples["C"]["metrics"]}
            self.assertEqual(metrics["BV"]["free_parameters"],3)
            self.assertEqual(metrics["BV+jR"]["free_parameters"],4)
            self.assertLess(metrics["BV"]["RMSE_mV"],2.10)
            self.assertLess(metrics["BV+jR"]["RMSE_mV"],.43)
            self.assertLess(metrics["VHT"]["RMSE_mV"],.67)
            self.assertGreater(examples["B"]["trend_r2"],.97)
            cohort = json.loads((output/"figure6/EMPIRICAL_SUMMARY.json").read_text())
            self.assertEqual([(r["nonlinear"],r["families"],r["covered"]) for r in cohort],
                             [(73,4,59),(234,4,188)])
            kinetic = pd.read_csv(output/"figure6/KINETIC_SUMMARY.csv").set_index(["condition","model"])
            self.assertTrue(kinetic.loc[("acid","DeltaG_only"),"feasible"])
            self.assertTrue(kinetic.loc[("KOH","DeltaG_T"),"feasible"])
            self.assertFalse(kinetic.loc[("KOH","DeltaG_only"),"feasible"])
            controls = pd.read_csv(output/"figure6/RATE_CONTROL.csv")
            np.testing.assert_allclose(controls[["X_V","X_H","X_T"]].sum(axis=1),1,atol=2e-5)
            self.assertTrue((output/"index.html").is_file())
            self.assertEqual(len(list((output/"assets").glob("*.png"))),5)


if __name__ == "__main__":
    unittest.main()
