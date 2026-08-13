# Archived staged v2 evaluation

These files are copied without modification from the `_private_eval` directory
inside the original `peeragent_ground_truth.zip` received for the benchmark.
They contain synthetic benchmark metrics only and no publication figures.

- `curve_answer_eval_pixel_distance_v2.csv`: per-curve assignments and metrics;
- `case_answer_eval_pixel_distance_v2.csv`: per-panel verdicts;
- `answer_eval_pixel_distance_summary_v2.md`: archived aggregate summary.

The zip entry timestamps record 2026-05-09 20:20:12 CST for all three files.
`../reproduce_archived_staged_v2_evaluator.py` independently recomputes the
continuous metrics and verdicts from the preserved staged outputs and hidden
synthetic curves.
