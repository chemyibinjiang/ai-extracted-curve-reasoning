# Single-Agent Versus Staged Evaluation

The evaluator loaded answer curves only after inference. Distances are
computed after each condition's predicted anchors transform pixels into
scientific coordinates, with each case scaled to its answer-curve span.

## Condition Summary

| condition | cases | geometry-complete | strict complete | curve-count correct | median scaled distance |
| --- | ---: | ---: | ---: | ---: | ---: |
| monolithic | 60 | 53 | 36 | 60 | 0.00062 |
| staged | 60 | 51 | 36 | 60 | 0.00076 |

## Curve Summary

| condition | truth curves | predicted curves | geometry pass | exact label identity | median scaled distance |
| --- | ---: | ---: | ---: | ---: | ---: |
| monolithic | 137 | 137 | 127 | 108 | 0.00057 |
| staged | 137 | 137 | 127 | 117 | 0.00071 |

## Family Summary

| condition | family | cases | geometry-complete | strict complete | median scaled distance |
| --- | --- | ---: | ---: | ---: | ---: |
| monolithic | GC_trace | 10 | 9 | 3 | 0.00028 |
| monolithic | LSV | 10 | 10 | 10 | 0.00046 |
| monolithic | Raman | 10 | 8 | 6 | 0.00057 |
| monolithic | UV_Vis | 10 | 7 | 5 | 0.00059 |
| monolithic | XRD | 10 | 9 | 3 | 0.00204 |
| monolithic | kinetic_time_course | 10 | 10 | 9 | 0.00070 |
| staged | GC_trace | 10 | 9 | 3 | 0.00058 |
| staged | LSV | 10 | 9 | 9 | 0.00055 |
| staged | Raman | 10 | 8 | 6 | 0.00077 |
| staged | UV_Vis | 10 | 6 | 5 | 0.00059 |
| staged | XRD | 10 | 9 | 4 | 0.00224 |
| staged | kinetic_time_course | 10 | 10 | 9 | 0.00081 |

## Paired Comparison

- paired cases: `60`
- staged better / monolithic better / ties: `27 / 32 / 1`
- median staged-minus-monolithic distance: `0.00002`
- 95% bootstrap CI: `[-0.00005, 0.00013]`
- two-sided exact sign-test p: `0.60292`

Negative differences favor the staged workflow.
