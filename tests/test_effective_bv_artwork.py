"""Check current artwork against numerical inputs and preserved composition."""
import importlib.util
import json
from pathlib import Path
import re
import sys
import unittest
import zipfile

from lxml import etree as E
import numpy as np
from scipy.optimize import brentq

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'analysis/effective_bv'))
import artwork


class ArtworkTests(unittest.TestCase):
    def test_preserved_composition(self):
        with zipfile.ZipFile(ROOT/'analysis/effective_bv/artwork_templates.zip') as archive:
            for i in [4,5,6]:
                before=E.fromstring(archive.read(f'Figure{i}.svg'))
                after=E.parse(str(ROOT/f'figures/manuscript/Figure{i}.svg')).getroot()
                artwork.protected_checks(before,after,i)
            before=E.fromstring(archive.read('Figure1.svg'))
            after=E.parse(str(ROOT/'figures/manuscript/Figure1.svg')).getroot()
            self.assertEqual(E.tostring(artwork.byid(before,'svg1')),
                             E.tostring(artwork.byid(after,'svg1')))

    def test_current_numbers_and_families(self):
        for i,labels in [(4,['52.4%','77.8%','1,588 curves','2,361 curves','Median = 77.6']),
                         (5,['BV: 2.10 mV','BV + jR: 0.43 mV','0.66 mV']),
                         (6,['188/234','59/73','(n=79)','B4'])]:
            root=E.parse(str(ROOT/f'figures/manuscript/Figure{i}.svg'))
            text=' '.join(''.join(t.itertext()) for t in root.iter(artwork.S+'text'))
            for label in labels:
                self.assertIn(label,text)
            if i==6:
                self.assertNotIn('B5',text)
                axes=[n for n in root.iter() if n.get('id','').startswith('axes-family-control-')]
                self.assertEqual(len(axes),8)

    def test_svg_references_resolve(self):
        for i in range(1,8):
            root=E.parse(str(ROOT/f'figures/manuscript/Figure{i}.svg'))
            ids={n.get('id') for n in root.iter() if n.get('id')}
            for n in root.iter():
                for k,v in n.attrib.items():
                    refs=re.findall(r'url\(#([^)]*)\)',v)
                    if k==artwork.X and v.startswith('#'):
                        refs.append(v[1:])
                    for ref in refs:
                        self.assertIn(ref,ids,(i,ref))

    def test_numeric_audit_matches_figure_manifest(self):
        report=json.loads((ROOT/'reproducibility/artwork-effective-bv-20260930.json').read_text())
        self.assertEqual(report['figures']['4']['BV']['accepted'],1588)
        self.assertEqual(report['figures']['4']['BV+jR']['accepted'],2361)
        self.assertEqual(report['figures']['6']['members'],{'acid':59,'KOH':188})
        self.assertEqual(report['figures']['1']['members'],{'B1':37,'B2':79,'B3':25,'B4':47})
        # Figures 1 and 3 were revised after this dated kinetic-artwork audit.
        for name,digest in report['outputs'].items():
            if name.startswith(('Figure1.','Figure3.')):
                continue
            self.assertEqual(artwork.sha(ROOT/'figures/manuscript'/name),digest)
        manifest=json.loads((ROOT/'reproducibility/manifest.json').read_text())
        for item in manifest['assets']:
            self.assertEqual(artwork.sha(ROOT/item['path']),item['sha256'])

    def test_figure1_matches_figure7_population(self):
        root=E.parse(str(ROOT/'figures/manuscript/Figure1.svg')).getroot()
        scores=artwork.read(ROOT/'analysis/figure7/reference/SCORES.csv').set_index('curve_uid')
        self.assertEqual(len(scores),2360)
        for panel in ['D-observations','D-population-pca']:
            nodes=[n for n in artwork.byid(root,panel).iter() if n.get('data-curve-uid')]
            self.assertEqual(len(nodes),len(scores))
            self.assertEqual({n.get('data-curve-uid') for n in nodes},set(scores.index))
            for node in nodes:
                row=scores.loc[node.get('data-curve-uid')]
                self.assertEqual(node.get('data-group'),row.group)
                if panel=='D-population-pca':
                    # Invert the published panel's affine axis mapping.
                    self.assertAlmostEqual((float(node.get('cx'))-728)/430*1.82-1.2,row.PC1)
                    self.assertAlmostEqual(.6-(float(node.get('cy'))-206)/253*1.09,row.PC2)

    def test_figure1_templates_use_20mV_reference(self):
        root=E.parse(str(ROOT/'figures/manuscript/Figure1.svg')).getroot()
        table=artwork.read(ROOT/'analysis/figure7/inputs/TEMPLATES.csv').set_index('template')
        nodes=[n for n in artwork.byid(root,'D-templates').iter() if n.get('data-template')]
        self.assertEqual(len(nodes),24)
        self.assertEqual({n.get('data-template') for n in nodes},set(table.index))
        spec=importlib.util.spec_from_file_location('figure7_artwork_bv',ROOT/'analysis/figure7/inputs/effective_bv.py')
        bv=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(bv)
        for node in nodes:
            row=table.loc[node.get('data-template')]
            params=dict(log_j0=0.,fraction=row.fraction,coefficient_sum=row.coefficient_sum,R=row.Q_mV)
            def log_current(eta):
                return brentq(lambda z:bv.predict(np.array([np.exp(z)]),params)[0]-eta,-50,50)/np.log(10)
            points=np.array(re.findall(r'(-?\d+\.\d+),(-?\d+\.\d+)',node.get('d')),dtype=float)
            np.testing.assert_allclose(points[0],[1335.,459.],atol=1e-4)
            anchor=log_current(20.)
            for x,y in points[[0,len(points)//2,-1]]:
                eta=20+(x-1335)/395*280
                plotted=(459-y)/253*5.3
                self.assertAlmostEqual(plotted,log_current(eta)-anchor,places=5)


if __name__=='__main__':
    unittest.main()
