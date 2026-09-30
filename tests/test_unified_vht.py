"""The publication and model comparisons must use the same pooled fits."""
import hashlib
import json
from pathlib import Path
import sys
import unittest
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'analysis/effective_bv'))
import families
import kinetic_comparison
from types import SimpleNamespace
PUBLISHED=ROOT/'analysis/effective_bv/published'

class UnifiedVHTTests(unittest.TestCase):
    def test_objective_is_pooled_not_minimax(self):
        a={'pooled_rmse':1.,'worst_rmse':1.5}
        b={'pooled_rmse':1.1,'worst_rmse':1.2}
        self.assertIs(min([a,b],key=families.selection_key),a)

    def test_checked_files_and_fixed_alpha(self):
        manifest=json.loads((PUBLISHED/'MANIFEST.json').read_text())
        for r in manifest['files']:
            p=PUBLISHED/r['path']
            self.assertEqual(p.stat().st_size,r['bytes'])
            self.assertEqual(hashlib.sha256(p.read_bytes()).hexdigest(),r['sha256'])
        p=pd.read_csv(PUBLISHED/'KINETIC_PARAMETERS.csv')
        self.assertEqual(len(p),32)
        np.testing.assert_array_equal(p[['alphaV','alphaH']].to_numpy(),.5*np.ones((32,2)))
        for (condition,model),g in p.groupby(['condition','model']):
            if model in ['DeltaG_only','DeltaG_T']:self.assertEqual(g.log10_kH_over_kV.nunique(),1)
            if model in ['DeltaG_only','DeltaG_H']:self.assertEqual(g.log10_kT_over_kV.nunique(),1)

    def test_errors_and_raw_curve_counts(self):
        predictions=pd.read_csv(PUBLISHED/'TEMPLATE_RECONSTRUCTION.csv')
        predictions['error_squared']=(predictions.empirical_eta_mV-predictions.vht_eta_mV)**2
        pooled=predictions.groupby(['condition','model']).error_squared.mean()**.5
        worst=(predictions.groupby(['condition','model','family']).error_squared.mean()**.5).groupby(level=[0,1]).max()
        summary=pd.read_csv(PUBLISHED/'KINETIC_SUMMARY.csv').set_index(['condition','model'])
        np.testing.assert_allclose(summary.pooled_rmse_mV.sort_index(),pooled,atol=1e-9)
        np.testing.assert_allclose(summary.worst_rmse_mV.sort_index(),worst,atol=1e-9)
        replay=pd.read_csv(PUBLISHED/'RAW_VHT_REPLAY.csv')
        for key,expected in [(('acid','DeltaG_only'),(59,48)),(('KOH','DeltaG_T'),(188,165))]:
            r=replay[(replay.condition==key[0])&(replay.model==key[1])]
            self.assertEqual((len(r),int(r.R2.ge(.99).sum())),expected)

    def test_exact_duality_uses_absolute_current(self):
        p=pd.read_csv(PUBLISHED/'KINETIC_PARAMETERS.csv')
        for _,r in p[p.model=='independent_H_T_G'].iterrows():
            row=SimpleNamespace(**r.to_dict())
            dual=SimpleNamespace(**kinetic_comparison.dual(r.to_dict()))
            for eta in [10.,50.,100.,150.,190.]:
                state=families.state(row,eta);other=families.state(dual,eta)
                np.testing.assert_allclose(row.current_scale*state[0],dual.current_scale*other[0],rtol=1e-10)
                self.assertAlmostEqual(state[1]+other[1],1.,places=11)
                np.testing.assert_allclose(families.rate_control(row,eta)[[1,0,2]],families.rate_control(dual,eta),atol=2e-8)

if __name__=='__main__':unittest.main()
