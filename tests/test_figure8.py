"""Native-data reproduction and numerical safeguards for Figure 8."""
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('figure8_analysis', ROOT / 'analysis/figure8/run.py')
f = importlib.util.module_from_spec(spec)
spec.loader.exec_module(f)
np, pd = f.np, f.pd


class Figure8Tests(unittest.TestCase):
    def test_output_cannot_overwrite_source_or_reference_files(self):
        for path in [ROOT, f.HERE, f.HERE / 'reference', f.HERE / 'inputs',
                     f.FIG7 / 'reference', ROOT / 'figures/manuscript']:
            with self.subTest(path=path), patch.object(sys, 'argv', ['run.py', '--output', str(path)]), \
                    patch.object(f, 'load_inputs') as load:
                with self.assertRaisesRegex(ValueError, 'write outputs under build/'):
                    f.main()
                load.assert_not_called()
        self.assertEqual(f.output_directory(ROOT / 'build/check'), ROOT / 'build/check')
        with tempfile.TemporaryDirectory() as folder:
            self.assertEqual(f.output_directory(Path(folder)), Path(folder).resolve())

    def test_interpolation_respects_observed_brackets(self):
        y = f.observe(np.array([20., 40., 70.]), np.array([1., 3., 4.]), np.array([10., 20., 30., 50., 70., 80.]))
        np.testing.assert_allclose(y, [np.nan, 1, 2, np.nan, 4, np.nan], equal_nan=True)

    def test_preparation_units_startup_and_bounds(self):
        eta = np.array([0., 20., 30., 40., 40., 50., 60., 70.])
        current = np.array([5., 2., .1, .2, .4, 10., 500., 501.])
        data = np.column_stack([-eta/1000-.9268, -current*2/1000, np.arange(len(eta))])
        x, logj = f.prepare(data, 2)
        np.testing.assert_allclose(x, [40., 50., 60.])
        np.testing.assert_allclose(logj, [np.mean(np.log10([.2, .4])), 1, np.log10(500)])

    def test_density_export_uses_instrument_area_not_geometric_area(self):
        for instrument_area in [1., 3.]:
            metadata = f'ExpParmas:ExpType=ID_LSVA&-&CellParam=Area={instrument_area}&|&AreaMode=0\r\n'
            encoded = f.base64.b64encode(f.gzip.compress(metadata.encode())).decode('ascii')
            text = f'CSStudioFile,ID_LSVA,{encoded}\nE(V)\ti(A/cm\u00b2)\tT(s)\n'
            text += '\n'.join(f'-1\t-0.01\t{k}' for k in range(4))
            result = f.parse_raw(text.encode())
            np.testing.assert_allclose(result[:, 1], -.01 * instrument_area)
            _, logj = f.prepare(result, area=2.)
            np.testing.assert_allclose(10**logj, 5 * instrument_area)
        with self.assertRaisesRegex(ValueError, 'instrument normalization area'):
            f.parse_raw(('E(V)\ti(A/cm\u00b2)\tT(s)\n' + '\n'.join('-1 -0.01 0' for _ in range(4))).encode())
        with self.assertRaises(ValueError):
            f.parse_raw(b'unknown header\n1 2 3\n')

    def test_co_v_current_density_agrees_with_source_metadata(self):
        manifest = json.loads((f.HERE / 'inputs/manifest.json').read_text())
        with f.ZipFile(f.HERE / 'inputs/initial_screening.zip') as archive:
            metadata = pd.read_csv(f.io.BytesIO(archive.read(manifest['metadata_path'])))
            row = metadata.set_index('sample').loc['Co-V']
            data = f.parse_raw(archive.read('hd_separation_ml/data_extraction/all_data/LSV/Co-V.txt'))
        x, logj = f.prepare(data, row.LSV_geometry_area_cm2)
        self.assertEqual(row.LSV_geometry_area_cm2, 2.)
        current = 10**logj
        crossings = np.flatnonzero((current[:-1] - 10) * (current[1:] - 10) < 0)
        self.assertEqual(len(crossings), 1)
        i = crossings[0]
        eta10 = x[i] + (10 - current[i]) * (x[i+1] - x[i]) / (current[i+1] - current[i])
        self.assertAlmostEqual(eta10, row.eta10_mV_vs_RHE_full_lsv, places=6)

    def test_startup_preserves_later_current_reversals(self):
        eta = np.arange(20., 100., 10.)
        current = np.array([4., -3., 2., 1., -.01, .5, 3., 5.])
        data = np.column_stack([-eta/1000-.9268, -current/1000, np.arange(len(eta))])
        x, logj = f.prepare(data, area=1.)
        np.testing.assert_allclose(x, [40., 50., 70., 80., 90.])
        np.testing.assert_allclose(10**logj, [2., 1., .5, 3., 5.])

    def test_partial_support_inclusion(self):
        x = np.array([80., 90., 100., 110.])
        y = f.observe(x, np.arange(4.))
        self.assertTrue(f.support(x, y)['eligible'])
        self.assertFalse(f.support(x[:3], f.observe(x[:3], np.arange(3.)))['eligible'])

    def test_composition_groups(self):
        self.assertEqual(f.elements('Pt-Pt'), ['Pt'])
        self.assertEqual(f.elements('Ni-Mo'), f.elements('Mo-Ni'))
        self.assertFalse(f.PGM.intersection(f.elements('Au-Ag')))

    def test_rescaling_pair_error(self):
        x = np.linspace(0, 1, 41)
        profiles = np.array([x, x + 2, 2*x])
        rms, maximum = f.pair_errors(profiles)
        self.assertLess(rms[0, 1], 1e-14)
        self.assertLess(maximum[0, 1], 1e-14)
        self.assertGreater(rms[0, 2], .02)

    def test_dispersion_includes_uncertainty_and_third_coordinate(self):
        x = np.array([[0., 0., -1.], [0., 0., 1.]])
        cov = np.tile(np.eye(3), (2, 1, 1))
        mask = np.array([True, True])
        self.assertAlmostEqual(f.spread(x, np.ones(2), mask), 1)
        self.assertAlmostEqual(f.spread(x, np.ones(2), mask, cov), np.sqrt(2.5))

    def test_paper_weights_and_matched_window_inputs(self):
        frame = pd.DataFrame(dict(id=['a', 'b', 'c', 'd'], study=['p', 'p', 'q', 'r'],
                                  group=['PGM', 'PGM', 'PGM', 'no_PGM']))
        result = dict(score=np.array([[0., 0., 0.], [0., 0., 0.], [2., 0., 0.], [3., 0., 0.]]),
                      covariance=np.tile(np.eye(3)*.01, (4, 1, 1)))
        with patch.object(f.model_api, 'infer', return_value=result):
            row, _ = f.contrast(frame, np.ones((4, 29)), {}, 10, draws=30)
        # p and q each receive half the PGM weight, despite p having two curves.
        self.assertAlmostEqual(row['PGM_radius']**2, 1 + .03*(1-(.25**2+.25**2+.5**2)))
        frames = frame.assign(condition='alkaline')
        observed = np.ones((4, 29))
        calls = []
        def record(fr, y, model, seed):
            calls.append(y.copy())
            return {}, fr[['id', 'study', 'group']].copy()
        with tempfile.TemporaryDirectory() as folder, patch.object(f, 'contrast', side_effect=record):
            f.dispersion_outputs({}, frames, observed, frame, observed, Path(folder))
        for i, y in enumerate(calls):
            lo, hi = f.WINDOWS[i % 3]
            expected = (f.GRID >= lo) & (f.GRID <= hi)
            np.testing.assert_array_equal(np.isfinite(y), np.tile(expected, (4, 1)))

    def test_isolated_raw_to_figure_reproduction(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            shutil.copytree(ROOT / 'analysis/figure8', root / 'analysis/figure8', ignore=shutil.ignore_patterns('__pycache__'))
            for name in ['lib/partial_model.py', 'reference/MODEL.npz', 'reference/SCORES.csv',
                         'reference/POSTERIOR.npz', 'inputs/POINTS.csv']:
                target = root / 'analysis/figure7' / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(ROOT / 'analysis/figure7' / name, target)
            subprocess.run([sys.executable, str(root / 'analysis/figure8/run.py')],
                           cwd=folder, check=True, capture_output=True, text=True)
            out = root / 'build/figure8'
            report = json.loads((out / 'verification.json').read_text())
            self.assertTrue(report['verified'])
            self.assertEqual(report['included'], 524)
            self.assertTrue((out / 'Figure8.png').stat().st_size > 100000)
            groups = pd.read_csv(out / 'all_series.csv')
            self.assertTrue((groups.worst_RMS <= .02 + 1e-12).all())
            self.assertTrue((groups.worst_maximum <= .05 + 1e-12).all())
            # Exercise the portable font path even on machines with Arial installed.
            code = "import sys; sys.path.insert(0, 'analysis/figure8'); import plot, run; "
            code += "plot.font_manager.fontManager.ttflist = [f for f in plot.font_manager.fontManager.ttflist if f.name != 'Arial']; "
            code += "sys.argv = ['run.py']; run.main()"
            fallback = subprocess.run([sys.executable, '-c', code], cwd=folder, capture_output=True, text=True)
            self.assertEqual(fallback.returncode, 0, fallback.stderr)
            layout = json.loads((out / 'layout_validation.json').read_text())
            self.assertEqual(layout['font'], 'DejaVu Sans')
            with (root / 'analysis/figure8/inputs/initial_screening.zip').open('ab') as stream:
                stream.write(b'corruption')
            failed = subprocess.run([sys.executable, str(root / 'analysis/figure8/run.py'), '--no-figure'],
                                    cwd=folder, capture_output=True, text=True)
            self.assertNotEqual(failed.returncode, 0)
            self.assertIn('checksum mismatch', failed.stderr)


if __name__ == '__main__':
    unittest.main()
