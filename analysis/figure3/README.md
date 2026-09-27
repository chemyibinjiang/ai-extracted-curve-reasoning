# Figure 3 Extraction and Verification

```text
python analysis/figure3/run.py
```

`build/figure3/BENCHMARK_CURVES.csv` recalculates pixel distances and recovered
x-ranges for all 137 curves in 60 panels. It reads the included tick anchors,
extracted points, synthetic numerical truth, and recorded curve-to-truth matches.
All four metrics are checked against the preserved evaluation to absolute
tolerance 1e-10. No API key or new agent run is needed.

`SUMMARY.json` gives the Figure 3 benchmark statistics (0.36, 1.13 and 1.44
pixels after rounding), quality verdicts, and literature-review percentages.
Returning all 137 curves is task completion, **not** passing all geometric
quality checks: 133 pass, two warn, and two fail the pixel/coverage criteria.
SI Tables S5-S6 report extraction-task failures, not geometric-quality failures.
The staged/single-agent examples in Figure S11 use a different normalized
vertical-RMSE evaluator; see the
[comparison results](../../benchmark_data/benchmark_curve_extraction/agentic_ablation/public_results/README.md).

## Literature Review

`REVIEW_SUMMARY.json` transcribes the recorded review counts in SI Tables
S10-S14. The command checks their arithmetic and primary-category totals;
it does not recreate human judgments. Reviewed figure images, geometry traces,
and source-specific discrepancy cards are not included. Consequently the
89.6% axis, 97.8% geometry, and 9.25% paper-discrepancy percentages can be
recalculated from recorded counts, but those underlying judgments cannot be
independently re-adjudicated from this repository alone. Source-specific claim
evidence is retained for confidential editorial/peer review, as stated in SI
Section 4.2. The public DOI/figure/panel identifiers permit access to source
publications without redistributing their images.

The four Figure 3E comparisons are deidentified illustrations of those review
outcomes, not a separate fitting population. Their supplied source panels are
in `figures/Figure_04_claim_validation/`; the historical folder name does not
refer to manuscript Figure 4. The complete current artwork is always
`figures/manuscript/Figure3.svg`.
