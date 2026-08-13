from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "audit_interpolated_curve_errors.py"
SPEC = importlib.util.spec_from_file_location("audit_interpolated_curve_errors", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
audit = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = audit
SPEC.loader.exec_module(audit)


class InterpolationAuditTests(unittest.TestCase):
    def test_collapse_x_uses_median_for_duplicate_coordinates(self) -> None:
        collapsed = audit.collapse_x([(1.0, 5.0), (0.0, 2.0), (1.0, 9.0)])
        self.assertEqual(collapsed, [(0.0, 2.0), (1.0, 7.0)])

    def test_identical_curves_have_zero_error_and_full_coverage(self) -> None:
        points = [(0.0, 0.0), (1.0, 2.0), (2.0, 4.0)]
        metrics = audit.interpolated_metrics(points, points, 4.0, 101)
        self.assertAlmostEqual(float(metrics["rmse_yspan"]), 0.0)
        self.assertAlmostEqual(float(metrics["shared_x_coverage"]), 1.0)

    def test_omitted_tail_reduces_coverage_without_creating_shape_error(self) -> None:
        truth = [(0.0, 0.0), (1.0, 1.0), (2.0, 2.0), (3.0, 3.0)]
        returned = [(1.0, 1.0), (2.0, 2.0)]
        metrics = audit.interpolated_metrics(returned, truth, 3.0, 101)
        self.assertAlmostEqual(float(metrics["rmse_yspan"]), 0.0)
        self.assertAlmostEqual(float(metrics["shared_x_coverage"]), 1.0 / 3.0)

    def test_returned_point_metric_does_not_penalize_sparse_exact_samples(self) -> None:
        truth = [(0.0, 0.0), (0.5, 4.0), (1.0, 0.0)]
        returned = [(0.0, 0.0), (0.5, 4.0), (1.0, 0.0)]
        metrics = audit.returned_point_metrics(returned, truth, 4.0)
        self.assertAlmostEqual(float(metrics["returned_point_rmse_yspan"]), 0.0)
        self.assertEqual(int(metrics["returned_points_in_truth_domain"]), 3)

    def test_orthogonal_metric_accepts_points_on_steep_segments(self) -> None:
        truth = [(0.0, 0.0), (0.01, 1.0), (1.0, 1.0)]
        returned = [(0.005, 0.5), (0.5, 1.0)]
        metrics = audit.returned_point_orthogonal_metrics(
            returned, truth, (0.0, 1.0, 0.0, 1.0)
        )
        self.assertAlmostEqual(float(metrics["returned_point_orthogonal_p95"]), 0.0)


if __name__ == "__main__":
    unittest.main()
