"""Invariants of the observed-only Figure 7 shape model."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import unittest
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
PACKAGE=ROOT/'analysis/figure7'
spec=importlib.util.spec_from_file_location('figure7_partial_model',PACKAGE/'lib/partial_model.py')
model=importlib.util.module_from_spec(spec)
spec.loader.exec_module(model)
annotation_spec=importlib.util.spec_from_file_location('figure7_metadata',PACKAGE/'lib/metadata.py')
annotation=importlib.util.module_from_spec(annotation_spec)
annotation_spec.loader.exec_module(annotation)
sys.path.insert(0, str(PACKAGE/'lib'))
growth_spec=importlib.util.spec_from_file_location('figure7_observed_growth',PACKAGE/'lib/20_observed_growth.py')
growth=importlib.util.module_from_spec(growth_spec)
growth_spec.loader.exec_module(growth)
sys.path.pop(0)


class Figure7Tests(unittest.TestCase):
    def test_observed_current_does_not_extrapolate_or_bridge_large_gaps(self):
        x=np.array([20.,30.,60.,80.]); y=np.array([0.,1.,2.,3.])
        self.assertEqual(growth.value_at(x,y,25),.5)
        self.assertEqual(growth.value_at(x,y,70),2.5)
        self.assertEqual(growth.value_at(x,y,60),2.)
        for eta in [10,45,90]:
            self.assertTrue(np.isnan(growth.value_at(x,y,eta)))

    def test_observed_summary_gives_each_paper_equal_weight(self):
        base=dict(condition='alkaline',group='no_PGM',metric='log10_j',low_mV=50,high_mV=50)
        rows=pd.DataFrame([dict(base,paper_key='a',value=0.),
                           dict(base,paper_key='b',value=2.)])
        repeated=pd.concat([rows.iloc[:1]]*9+[rows.iloc[1:]],ignore_index=True)
        first=growth.summarize(rows).iloc[0]
        second=growth.summarize(repeated).iloc[0]
        self.assertEqual(first['mean'],1.)
        self.assertEqual(second['papers'],2)
        for field in ['mean','lower95','upper95']:
            self.assertEqual(first[field],second[field])

    def test_source_checked_composition_correction(self):
        raw=pd.read_csv(PACKAGE/'inputs/MEMBER_COMPATIBILITY.csv')
        corrected=annotation.corrected_metadata(raw)
        uid='batch1/case74/figure_1__c/curve_5'
        mask=raw.curve_uid.eq(uid)
        self.assertEqual(set(raw.loc[mask,'template']),{'T11','T12','T15'})
        self.assertTrue(raw.loc[mask,'active_elements'].isna().all())
        self.assertTrue(corrected.loc[mask,'composition_known'].all())
        self.assertEqual(set(corrected.loc[mask,'active_elements']),{'["Sc", "Co"]'})
        pd.testing.assert_frame_equal(raw.loc[~mask],corrected.loc[~mask])
        for column in ['current_scale_beta','empirical_R2','candidate_index']:
            pd.testing.assert_series_equal(raw[column],corrected[column])
        unique=corrected.drop_duplicates('curve_uid')
        elements=unique.active_elements.map(json.loads)
        self.assertTrue(elements.map(bool).all())
        pgm=elements.map(lambda x:bool(set(x)&{'Pt','Pd','Rh','Ru','Ir','Os'}))
        self.assertEqual((int(pgm.sum()),int((~pgm).sum())),(695,648))

    @classmethod
    def setUpClass(cls):
        cls.fit=dict(np.load(PACKAGE/'reference/MODEL.npz'))
        rng=np.random.default_rng(421)
        cls.y=1+(model.B@cls.fit['mu'])[None,:]+rng.normal(size=(8,3))@(model.B@cls.fit['load']).T
        cls.y[0,8:]=np.nan
        cls.y[1,:12]=np.nan

    def test_frozen_input_integrity(self):
        for row in json.loads((PACKAGE/'input_manifest.json').read_text()):
            self.assertEqual(hashlib.sha256((PACKAGE/row['path']).read_bytes()).hexdigest(),row['sha256'],row['path'])

    def test_arbitrary_current_amplitude_leaves_shape_unchanged(self):
        base=model.infer(self.fit,self.y)
        offsets=np.arange(len(self.y))[:,None]*2-4
        shifted=model.infer(self.fit,self.y+offsets)
        np.testing.assert_allclose(base['score'],shifted['score'],atol=1e-9)
        np.testing.assert_allclose(shifted['intercept']-base['intercept'],offsets[:,0],atol=1e-9)

    def test_missing_data_are_not_zero_filled_in_moments(self):
        actual=model.moments(self.y)
        for i,row in enumerate(self.y):
            good=np.isfinite(row); b=model.B[good]; y=row[good]
            center=np.eye(len(y))-np.ones((len(y),len(y)))/len(y)
            np.testing.assert_allclose(actual['g'][i],b.T@center@b,atol=1e-10)
            np.testing.assert_allclose(actual['h'][i],b.T@center@y,atol=1e-10)

    def test_fewer_observations_increase_conditional_variance(self):
        full=np.nan_to_num(self.y[-1:]).copy()
        partial=full.copy();partial[:,8:]=np.nan
        a=model.infer(self.fit,full)['covariance'][0]
        b=model.infer(self.fit,partial)['covariance'][0]
        self.assertGreater(np.linalg.eigvalsh(a).min(),0)
        self.assertGreaterEqual(np.linalg.eigvalsh(b-a).min(),-1e-10)

    def test_independent_dense_conditional_solution(self):
        result=model.infer(self.fit,self.y)
        scales=np.linalg.norm(self.fit['load'],axis=0)
        for i,row in enumerate(self.y):
            good=np.isfinite(row); b=model.B[good]; y=row[good]
            center=np.eye(len(y))-np.ones((len(y),len(y)))/len(y)
            design=center@b@self.fit['load']
            cov=np.linalg.inv(np.eye(3)+design.T@design/self.fit['sigma2'])
            z=cov@design.T@(center@(y-b@self.fit['mu']))/self.fit['sigma2']
            np.testing.assert_allclose(result['score'][i],scales*z,atol=1e-10)

    def test_single_cell_is_rejected(self):
        row=np.full((1,len(model.GRID)),np.nan);row[0,0]=1
        with self.assertRaises(ValueError):model.infer(self.fit,row)


if __name__=='__main__':unittest.main()
