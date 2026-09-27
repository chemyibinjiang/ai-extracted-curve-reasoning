import sys
from pathlib import Path
import unittest
import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parent))
import model


class NernstTests(unittest.TestCase):
    def test_exact_effective_bv_boundary(self):
        j=np.geomspace(.001,1000,150)
        row=dict(log_jL=np.log(.8),R=.17)
        p=np.array([row['log_jL'],1.,np.log(2.),row['R']])
        np.testing.assert_allclose(model.predict(j,row),model.bv.evaluate(j,p,True)[0],rtol=1e-11,atol=1e-9)

    def test_recovers_known_parameters(self):
        j=np.geomspace(.02,120,70)
        truth=dict(log_jL=np.log(.37),R=.42)
        fit=model.fit(j,model.predict(j,truth))
        self.assertAlmostEqual(fit['jL'],.37,places=6)
        self.assertAlmostEqual(fit['R'],.42,places=7)
        self.assertLess(fit['rmse'],1e-6)

    def test_template_profile_and_independent_fit_agree(self):
        j=np.geomspace(.1,90,50)
        truth=dict(log_jL=np.log(.7),R=.6)
        y=model.predict(j,truth)
        loss,z=model.profile(j,y,.7*.6)
        self.assertLess(loss,1e-12)
        self.assertAlmostEqual(np.exp(z),.7,places=7)

    def test_R_zero_is_nested(self):
        j=np.geomspace(.01,100,30)
        y=model.predict(j,dict(log_jL=np.log(.5),R=0.))
        self.assertLessEqual(model.fit(j,y,True)['sse'],model.fit(j,y,False)['sse']+1e-9)

    def test_invalid_current(self):
        with self.assertRaises(ValueError):
            model.fit(np.array([0.,1.,2.]),np.array([1.,2.,3.]))


if __name__=='__main__':
    unittest.main()
