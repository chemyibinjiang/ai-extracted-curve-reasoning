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

    def test_native_density_header_is_not_divided_twice(self):
        text = 'CSStudioFile,ID_LSVA,metadata\nE(V)\ti(A/cm\u00b2)\tT(s)\n'
        text += '\n'.join(f'-1\t-0.01\t{k}' for k in range(4))
        result = f.parse_raw(text.encode(), area=2)
        np.testing.assert_allclose(result[:, 1], -.02)
        with self.assertRaises(ValueError):
            f.parse_raw(b'unknown header\n1 2 3\n')

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
