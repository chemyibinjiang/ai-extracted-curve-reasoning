# Private Pixel-Distance Answer Evaluation v2

Coordinate-system corrected: extracted points and hidden-answer projection are compared in the same anchor coordinate system.

Cases evaluated: 60
Curves evaluated: 137

## Case Verdicts
- fail: 1
- pass: 57
- warn: 2

## Curve Verdicts
- fail: 2
- pass: 133
- warn: 2

## Family Summary
- GC_trace: cases=10, pass=10, warn=0, fail=0, worst_p95_px=3.21, worst_median_px=1.78, min_xcov=0.958
- LSV: cases=10, pass=10, warn=0, fail=0, worst_p95_px=3.43, worst_median_px=1.52, min_xcov=0.762
- Raman: cases=10, pass=9, warn=0, fail=1, worst_p95_px=3.68, worst_median_px=1.30, min_xcov=0.250
- UV_Vis: cases=10, pass=8, warn=2, fail=0, worst_p95_px=9.90, worst_median_px=1.41, min_xcov=0.594
- XRD: cases=10, pass=10, warn=0, fail=0, worst_p95_px=2.88, worst_median_px=1.96, min_xcov=0.962
- kinetic_time_course: cases=10, pass=10, warn=0, fail=0, worst_p95_px=7.96, worst_median_px=1.37, min_xcov=0.972

## Failing Cases
- d_raman_05: curves 3/3, max_p95_px=2.24, max_median_px=1.30, min_xcov=0.250, axis=original, missing=

## Warning Cases
- c_uv_vis_02: curves 4/4, max_p95_px=2.65, max_median_px=1.07, min_xcov=0.597, axis=original
- c_uv_vis_07: curves 4/4, max_p95_px=1.04, max_median_px=0.36, min_xcov=0.594, axis=original
