"""The complete search uses the same candidates and objectives as the figures."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import unittest
import zipfile
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'analysis/effective_bv'))
spec=importlib.util.spec_from_file_location('template_search',ROOT/'analysis/effective_bv/search.py')
search=importlib.util.module_from_spec(spec);spec.loader.exec_module(search)


class SearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.candidates=search.grid()

    def test_grid_and_selected_indices(self):
        self.assertEqual(len(self.candidates),276551)
        for condition in ('acid','KOH'):
            selected=pd.read_csv(ROOT/f'analysis/effective_bv/reference/{condition}/TEMPLATES.csv')
            for t in selected.itertuples():
                np.testing.assert_allclose(self.candidates.iloc[t.candidate_index],
                    [t.fraction,t.coefficient_sum,t.Q_mV],rtol=1e-12,atol=1e-12)

    def test_selected_profiles_agree_with_exact_inverse(self):
        for condition in ('acid','KOH'):
            _,ids,groups,n,j,y,limits=search.cohort(condition)
            selected=pd.read_csv(ROOT/f'analysis/effective_bv/reference/{condition}/TEMPLATES.csv')
            candidates=selected[['fraction','coefficient_sum','Q_mV']].to_numpy(float)
            loss,scale=search.profile_candidates(j,y,n,candidates)
            expected=pd.read_csv(ROOT/f'analysis/effective_bv/reference/{condition}/ASSIGNMENTS.csv').set_index('curve_uid')
            for i,uid in enumerate(ids):
                k=loss[:,i].argmin();t=selected.iloc[k];z=scale[k,i]
                pred=search.bv.predict(j[i,:n[i]],dict(log_j0=z,fraction=t.fraction,
                    coefficient_sum=t.coefficient_sum,R=t.Q_mV*np.exp(-z)))
                sse=np.sum((pred-y[i,:n[i]])**2)
                np.testing.assert_allclose(sse,loss[k,i],rtol=2e-6,atol=2e-6)
                self.assertEqual(bool(sse<=limits[i]),bool(expected.loc[uid,'adequate']))
                self.assertEqual(t.family,expected.loc[uid,'family'])

    def test_archived_files_are_recoverable(self):
        folder=ROOT/'exploration/archive'
        manifest=json.loads((folder/'MANIFEST.json').read_text())
        path=folder/manifest['archive']
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),manifest['sha256'])
        with zipfile.ZipFile(path) as z:
            self.assertIsNone(z.testzip())
            self.assertEqual(json.loads(z.read('ARCHIVE_MANIFEST.json'))['files'], manifest['files'])
            for item in manifest['files']:
                self.assertEqual(hashlib.sha256(z.read(item['path'])).hexdigest(),item['sha256'])
        self.assertFalse((ROOT/'analysis/common/strict_bv.py').exists())
        self.assertFalse((ROOT/'analysis/figure6/reference/KOH/TEMPLATES.csv').exists())
        self.assertFalse(any((ROOT/'figures/Figure_05_bvir').glob('*.py')))
        self.assertFalse(any((ROOT/'figures/Figure_06_ptc_relative').rglob('*.py')))


if __name__=='__main__':unittest.main()
