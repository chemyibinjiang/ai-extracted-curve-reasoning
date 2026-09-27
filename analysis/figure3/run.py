"""Recalculate Figure 3 benchmark metrics and tabulate recorded review outcomes."""
import argparse
import json
from pathlib import Path
import sys
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'benchmark_data/benchmark_curve_extraction/agentic_ablation'))
import reproduce_archived_staged_v2_evaluator as benchmark


def run(output):
    replayed, compared = benchmark.reproduce(benchmark.DEFAULT_CASE_ROOT,
        benchmark.DEFAULT_TRUTH_ROOT, benchmark.DEFAULT_ARCHIVED_EVAL_ROOT)
    metrics = ('median_dist_px', 'p95_dist_px', 'mean_dist_px', 'x_coverage_px')
    differences = {}
    for name in metrics:
        actual, reference = compared[name + '_replayed'], compared[name + '_archived']
        np.testing.assert_allclose(actual, reference, rtol=0, atol=1e-10)
        differences[name] = float(abs(actual-reference).max())
    assert len(replayed) == 137 and replayed.case_id.nunique() == 60
    assert (compared.verdict_replayed == compared.verdict_archived).all()
    review = json.loads((Path(__file__).parent / 'REVIEW_SUMMARY.json').read_text())
    assert sum(review['claims']['primary_error_types'].values()) == review['claims']['confirmed_records']
    summary = {
        'benchmark_recalculated': {
            'panels': 60, 'curves': 137,
            'median_per_curve_median_distance_px': float(replayed.median_dist_px.median()),
            'p90_per_curve_median_distance_px': float(replayed.median_dist_px.quantile(.9)),
            'median_per_curve_p95_distance_px': float(replayed.p95_dist_px.median()),
            'maximum_differences_from_reference': differences,
            'curve_quality_verdicts': replayed.verdict.value_counts().to_dict(),
        },
        'literature_review_recorded': review,
        'review_percentages_recalculated': {
            'axis_calibration': 100*review['axis_calibration']['within_tolerance']/review['axis_calibration']['total'],
            'curve_geometry': 100*review['curve_geometry']['within_tolerance']/review['curve_geometry']['total'],
            'confirmed_papers': 100*review['claims']['confirmed_unique_papers']/review['claims']['reviewed_unique_papers'],
        },
    }
    output.mkdir(parents=True, exist_ok=True)
    replayed.to_csv(output / 'BENCHMARK_CURVES.csv', index=False)
    (output / 'SUMMARY.json').write_text(json.dumps(summary, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'build/figure3')
    args = parser.parse_args()
    if args.output.resolve() == ROOT / 'analysis' or ROOT / 'analysis' in args.output.resolve().parents:
        parser.error('Keep outputs outside analysis/')
    run(args.output)
