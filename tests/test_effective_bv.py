"""Checks for the variable-coefficient analysis used in the manuscript revision."""
import json
import os
from pathlib import Path
import sys
import unittest
os.environ.setdefault("NUMBA_NUM_THREADS", "1")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "analysis/common"))
import numpy as np
import effective_bv as bv


class EffectiveBVTests(unittest.TestCase):
    def test_inverse_roundtrip(self):
        for a in (.01,.2,.5,.8,.99,1.):
            for u in np.geomspace(1e-10,1e12,55):
                v = bv.inverse(u,a)
                actual = np.expm1(a*v)-np.expm1((a-1)*v)
                np.testing.assert_allclose(actual,u,rtol=3e-11,atol=1e-13)

    def test_zero_anodic_endpoint(self):
        for u in np.geomspace(1e-10,1e12,40):
            self.assertAlmostEqual(bv.inverse(u,1.),np.log1p(u),places=10)

    def test_analytic_jacobian(self):
        j = np.geomspace(.2,100,35)
        for s in (.001,.3,1.7,2.):
            p = np.array([-1.2,.73,np.log(s),.45])
            _, jac = bv.evaluate(j,p,True)
            for k in range(len(p)):
                delta = np.zeros(4)
                delta[k] = 1e-5
                numeric = (bv.evaluate(j,p+delta,True)[0]-bv.evaluate(j,p-delta,True)[0])/2e-5
                np.testing.assert_allclose(jac[:,k],numeric,rtol=1e-5,atol=1e-5)

    def test_current_scaling_preserves_shape(self):
        j = np.geomspace(.2,100,25)
        row = dict(log_j0=-2.,fraction=.73,coefficient_sum=1.15,R=.55)
        scaled = dict(row,log_j0=row["log_j0"]+np.log(7),R=row["R"]/7)
        np.testing.assert_allclose(bv.predict(j,row),bv.predict(7*j,scaled),atol=1e-11)

    def test_fit_and_nesting(self):
        j = np.geomspace(.01,100,45)
        row = dict(log_j0=-1.,fraction=.6,coefficient_sum=1.3,R=.6)
        y = bv.predict(j,row)
        fits = bv.fit_pair(j,y)
        self.assertLess(fits["BV+jR"]["rmse"],1e-5)
        self.assertLessEqual(fits["BV+jR"]["sse"],fits["BV"]["sse"])
        self.assertEqual(fits["BV"]["k"],3)
        self.assertEqual(fits["BV+jR"]["k"],4)
        self.assertAlmostEqual(fits["BV+jR"]["coefficient_sum"],1.3,places=4)

    def test_invalid_data_rejected(self):
        for j,y in [([0,1,2],[1,2,3]),([1,2],[1,2]),([1,2,3],[1,np.nan,3])]:
            with self.assertRaises(ValueError):
                bv.fit(j,y)

    def test_reference_manifest(self):
        import hashlib
        folder = ROOT / "analysis/effective_bv/reference"
        manifest = json.loads((folder / "MANIFEST.json").read_text())
        for base,key in [(ROOT,"inputs"),(folder,"seeds")]:
            for name,digest in manifest[key].items():
                self.assertEqual(hashlib.sha256((base/name).read_bytes()).hexdigest(),digest,name)


if __name__ == "__main__":
    unittest.main()
