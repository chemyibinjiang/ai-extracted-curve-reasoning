import importlib.util
from pathlib import Path
import tempfile
import unittest
import json
import csv
import hashlib
import math

ROOT = Path(__file__).resolve().parents[1]


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ReaderReproductionTests(unittest.TestCase):
    def test_active_validation_matches_current_references(self):
        report = json.loads((ROOT/'reproducibility/figure4-validation.json').read_text())
        self.assertEqual(report['analysis'], 'effective_bv')
        self.assertEqual(report['coefficient_sum_bounds'], [.001, 2.])
        with (ROOT/'analysis/effective_bv/reference/POPULATION_SEEDS.csv').open(newline='') as stream:
            records = list(csv.DictReader(stream))
        self.assertEqual(len(records), report['model_fits'])
        for model, expected in report['models'].items():
            rows = [r for r in records if r['model'] == model]
            self.assertEqual(len(rows), report['curves'])
            accepted = sum(float(r['r2']) >= report['adequate_fit_R2'] for r in rows)
            self.assertEqual(accepted, expected['R2_ge_099'])
            self.assertAlmostEqual(100*accepted/len(rows), expected['percent'])
            self.assertEqual(expected['free_parameters'], 3 if model == 'BV' else 4)

        artwork = json.loads((ROOT/'reproducibility/figure5-artwork-update.json').read_text())
        self.assertEqual(artwork['analysis'], 'effective_bv')
        for key in ('svg', 'png', 'numerical_report'):
            path = ROOT/artwork[key+'_path']
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), artwork[key+'_sha256'])
        nimo = json.loads((ROOT/artwork['numerical_report_path']).read_text())
        expected = {r['model']: r for r in nimo['metrics']}
        self.assertEqual(artwork['n'], nimo['n'])
        for row in artwork['metrics']:
            for key in ('n', 'free_parameters', 'RMSE_mV', 'R2', 'max_abs_error_mV', 'SSE_mV2'):
                self.assertTrue(math.isclose(row[key], expected[row['model']][key], rel_tol=1e-12, abs_tol=1e-12))

    def test_superseded_records_are_not_active_inputs(self):
        unused = 'analysis/figure5/inputs/C_COVERAGE_COORDINATES.csv'
        self.assertFalse((ROOT/unused).exists())
        sources = json.loads((ROOT/'analysis/SOURCE_MANIFEST.json').read_text())['files']
        self.assertNotIn(unused, [r['path'] for r in sources])
        archive = json.loads((ROOT/'exploration/archive/MANIFEST.json').read_text())['files']
        self.assertIn(unused, [r['path'] for r in archive])
        for name in ('figure4-validation.json', 'figure5-artwork-update.json'):
            path = ROOT/'reproducibility'/name
            report = json.loads(path.read_text())
            historical = path.parent/report['historical_record']
            self.assertTrue(historical.is_file())
            self.assertNotEqual(report, json.loads(historical.read_text()))

    def test_dataset_integrity_and_joins(self):
        module = load(ROOT/'scripts/validate_dataset.py', 'dataset_validation')
        self.assertEqual(module.validate()['curves'], 4211)

    def test_benchmark_replay_and_review_counts(self):
        module = load(ROOT/'analysis/figure3/run.py', 'figure3_replay')
        with tempfile.TemporaryDirectory() as folder:
            module.run(Path(folder))
            summary = json.loads((Path(folder)/'SUMMARY.json').read_text())
        benchmark = summary['benchmark_recalculated']
        self.assertEqual(benchmark['curve_quality_verdicts'], {'pass': 133, 'warn': 2, 'fail': 2})
        self.assertEqual(round(benchmark['median_per_curve_median_distance_px'], 2), .36)
        self.assertEqual(round(benchmark['p90_per_curve_median_distance_px'], 2), 1.13)
        self.assertEqual(round(benchmark['median_per_curve_p95_distance_px'], 2), 1.44)


if __name__ == '__main__':
    unittest.main()
