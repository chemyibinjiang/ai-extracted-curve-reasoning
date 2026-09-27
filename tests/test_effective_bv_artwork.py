"""Checks for the current data and preservation of the edited composition."""
import json
from pathlib import Path
import re
import sys
import unittest
import zipfile

from lxml import etree as E

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'analysis/effective_bv'))
import artwork


class ArtworkTests(unittest.TestCase):
    def test_preserved_composition(self):
        with zipfile.ZipFile(ROOT/'analysis/effective_bv/artwork_templates.zip') as archive:
            for i in [1,4,5,6]:
                before=E.fromstring(archive.read(f'Figure{i}.svg'))
                after=E.parse(str(ROOT/f'figures/manuscript/Figure{i}.svg')).getroot()
                artwork.protected_checks(before,after,i)

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
        for i in [1,4,5,6]:
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
        report=json.loads((ROOT/'reproducibility/artwork-effective-bv-20260927.json').read_text())
        self.assertEqual(report['figures']['4']['BV']['accepted'],1588)
        self.assertEqual(report['figures']['4']['BV+jR']['accepted'],2361)
        self.assertEqual(report['figures']['6']['members'],{'acid':59,'KOH':188})
        self.assertEqual(report['figures']['1']['members'],{'B1':37,'B2':79,'B3':25,'B4':47})
        for name,digest in report['outputs'].items():
            self.assertEqual(artwork.sha(ROOT/'figures/manuscript'/name),digest)

    def test_figure1_matches_figure6(self):
        root=E.parse(str(ROOT/'figures/manuscript/Figure1.svg')).getroot()
        self.assertFalse(any(n.get('id','').endswith('-B5') for n in root.iter()))
        raw=artwork.byid(root,'D-raw-data')
        scaled=artwork.byid(root,'D-scaled-data')
        self.assertEqual(raw.get('data-curves'),'188')
        self.assertEqual(scaled.get('data-curves'),'188')
        self.assertEqual(sum(n.tag==artwork.S+'path' for n in raw.iter()),188)
        self.assertEqual(sum(n.tag==artwork.S+'circle' for n in scaled.iter()),4986)
        table=artwork.read(ROOT/'analysis/figure6/expected/PARAMETER_COORDINATES.csv')
        for row in table[table.condition.eq('KOH')].itertuples():
            point=artwork.byid(root,'D-kinetic-point-'+row.family)
            self.assertAlmostEqual(float(point.get('data-DeltaG-eff-meV')),row.DeltaG_eff_meV)
            self.assertAlmostEqual(float(point.get('data-kT-over-kV')),row.kT_over_kV)
            self.assertAlmostEqual(float(point.get('x'))+5,1350+(row.DeltaG_eff_meV-10)*388/75)
            shape=artwork.byid(root,'D-current-shape-'+row.family)
            self.assertEqual(shape.get('data-family'),row.family)


if __name__=='__main__':
    unittest.main()
