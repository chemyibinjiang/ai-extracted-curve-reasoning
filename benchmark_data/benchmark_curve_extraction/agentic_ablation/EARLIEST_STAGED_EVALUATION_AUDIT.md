# Earliest staged benchmark evaluation audit

## Provenance

The earliest preserved staged benchmark run is the 60-panel batch under
`benchmark_cases/focused_curve_extraction_set_v4_1_fixed`. Its batch manifest
records `gpt-5.4` with `xhigh` reasoning for the anchoring workers. The archived
run completed 60/60 anchoring tasks and 60/60 curve-extraction tasks and returned
137 curves.

The hidden-answer evaluation files inside `peeragent_ground_truth.zip` retain
the following original timestamps:

- scientific-coordinate interpolation evaluation: 2026-05-09 15:55 CST;
- first pixel-distance evaluation: 2026-05-09 15:57 CST;
- coordinate-corrected pixel-distance evaluation (`v2`): 2026-05-09 20:20 CST.

The manuscript and original Figure 3 used the coordinate-corrected `v2` CSV,
not the earlier interpolation-based result.

## Reconstructed v2 metric

The evaluator source file was not included in the two archived zips. Its
distance and coverage calculation can nevertheless be reconstructed exactly
from the preserved inputs and outputs:

1. Hidden raw CSV curves were loaded only for evaluation, after agent inference.
2. The worker-predicted axis anchors and saved axis fit were used to project each
   hidden scientific-coordinate curve into panel pixels.
3. Original-figure anchor coordinates were translated into the cropped-panel
   coordinate system using `crop_box_original`; panels whose anchors were
   already in cropped coordinates were left unchanged.
4. For every extracted sampled point, the evaluator calculated the minimum
   Euclidean pixel distance to any segment of the matched hidden-answer
   polyline. This is a one-way extracted-point-to-answer-curve distance.
5. Each curve was summarized by its median, 95th-percentile, and mean point
   distance. Global x-coverage was the shared extracted/truth x span divided by
   the truth x span.
6. The archived verdict rule is reproduced exactly by:
   - `fail`: median distance > 2 px, p95 distance > 10 px, or x-coverage < 0.50;
   - `warn`: distance thresholds pass and 0.50 <= x-coverage < 0.75;
   - `pass`: distance thresholds pass and x-coverage >= 0.75.

`reproduce_archived_staged_v2_evaluator.py` replays all 137 archived curve
assignments. In the public benchmark copy, where the omitted temporary axis-fit
files are reconstructed from the preserved tick anchors, all four continuous
metrics agree with the archived CSV to within `8e-13`, and all 137 verdicts
agree.

The v2 aggregate values used in the original Figure 3 are therefore supported:

- median of per-curve median point distances: 0.360137 px (reported as 0.36 px);
- P90 of per-curve median point distances: 1.125148 px (reported as 1.13 px);
- median of per-curve p95 point distances: 1.437397 px (reported as 1.44 px);
- median x-coverage: 0.986007.

The v2 curve verdicts were 133 pass, 2 warn, and 2 fail. Both failed curves were
in `d_raman_05`, where the staged extraction covered only about 25-27% of the
hidden x range. The warnings were one curve each in `c_uv_vis_02` and
`c_uv_vis_07`, both with about 59% x-coverage.

## Original Figure 3 construction audit

The original Figure 3 builder correctly hard-coded the three displayed v2
summary values (0.36 px median, 1.13 px P90, and 1.44 px median p95). However,
its distance-distribution bars used a separate manually entered 14-bin count
array that summed to 94 rather than the 137 evaluated curves and did not match
any preserved final evaluation table. The builder has therefore been corrected
to read `curve_answer_eval_pixel_distance_v2.csv` directly and compute the bin
counts and all three annotations from the same 137-curve source. This changes
the displayed histogram shape but does not change any reported summary value.

## Metric limitations

The original v2 metric is valid for the published sub-pixel point-to-curve
statement, but it is not a complete curve-reconstruction metric:

- It is one-way. Missing local peaks or intervals are not penalized if the
  returned points lie on the visible answer curve.
- Its coverage term measures only the global x range. It does not detect gaps
  inside that range.
- It has no separate marker-center target. Points following a marker rim can
  remain below the 2/10 px distance thresholds and pass.
- The earlier scientific-coordinate interpolation evaluator over-penalized
  sparse sampling of sharp XRD and GC peaks. The coordinate-corrected v2 pixel
  metric fixed those false failures and was the appropriate source for the
  original Figure 3 numbers.

These limitations explain why the new ablation uses a symmetric, scale-normalized
curve distance plus coverage and qualitative failure inspection.

## Retrospective staged-versus-monolithic comparison

The archived staged outputs and the new monolithic outputs were rescored with
the same current evaluator. Both conditions returned 137/137 target curves.
At the panel level:

- geometry-complete: monolithic 53/60; staged 51/60;
- strict-complete: 36/60 for each condition;
- geometry-passing curves: 127/137 for each condition;
- median symmetric scaled distance: monolithic 0.00062; staged 0.00076.

The paired panel comparison gave 27 panels favoring staged, 32 favoring
monolithic, and 1 tie. The median staged-minus-monolithic difference was
`1.83e-05`; its 95% panel-bootstrap interval was `[-5.26e-05, 1.32e-04]`, and
the two-sided exact sign-test p value was 0.603.

Thus, this run provides no evidence of a global shift in panel-level geometry
accuracy. It does not establish formal equivalence: there is one run per
condition, and the archived staged run and new monolithic run were executed at
different times and through different provider paths, although both used
`gpt-5.4` with `xhigh` reasoning.

Aggregate similarity also hides distinct failure modes. The monolithic run had
a severe final-record error in `c_uv_vis_05` and distorted curve records in
`d_raman_05`; the staged run recovered the Raman peak shape but truncated most
of its x range. In marker-rich `a_lsv_06`, monolithic points sometimes followed
marker rims rather than marker centers. These examples are more informative for
the SI than small differences in the aggregate median.
