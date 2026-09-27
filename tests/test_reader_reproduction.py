import importlib.util
from pathlib import Path
import tempfile
import unittest
import json

ROOT = Path(__file__).resolve().parents[1]


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ReaderReproductionTests(unittest.TestCase):
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
