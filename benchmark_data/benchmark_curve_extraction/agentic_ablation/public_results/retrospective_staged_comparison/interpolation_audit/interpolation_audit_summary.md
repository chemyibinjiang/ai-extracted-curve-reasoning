# Shared-Domain Interpolation Audit

Vertical errors are computed after interpolation on the x-domain shared
by each returned curve and its assigned hidden answer. Errors are
normalized by the complete answer-panel y-span. Coverage is reported
separately and does not enter the interpolation error.

## Condition Summary

| condition | cases | median case RMSE | median minimum coverage |
| --- | ---: | ---: | ---: |
| monolithic | 60 | 0.003790 | 0.983 |
| staged | 60 | 0.003607 | 0.982 |

## Practical Difference Counts

A positive difference favors the monolithic single-agent result; a
negative difference favors the staged workflow. Thresholds are fractions
of the complete answer-panel y-span.

| absolute RMSE difference | staged better | monolithic better |
| ---: | ---: | ---: |
| > 0.005 | 3 | 5 |
| > 0.010 | 2 | 3 |
| > 0.020 | 2 | 2 |
| > 0.050 | 2 | 0 |

Paired median staged-minus-monolithic RMSE difference: 0.000113.
Staged lower in 27 cases; monolithic lower in 33 cases.

## Returned-Point 2D Check

For sharp XRD, GC, and Raman peaks, same-x vertical residuals can
overstate small horizontal displacements. The following comparison uses
the p95 normalized 2D distance from returned points to the answer
polyline; x-coverage remains a separate requirement.

| case | family | monolithic p95 | staged p95 | staged-minus-monolithic |
| --- | --- | ---: | ---: | ---: |
| c_uv_vis_05 | UV_Vis | 0.380090 | 0.001580 | -0.378509 |
| d_raman_05 | Raman | 0.073891 | 0.002317 | -0.071574 |
| a_lsv_06 | LSV | 0.012117 | 0.002311 | -0.009806 |
| b_kinetic_time_course_01 | kinetic_time_course | 0.000927 | 0.007866 | 0.006939 |
| c_uv_vis_10 | UV_Vis | 0.003287 | 0.009558 | 0.006271 |
| b_kinetic_time_course_06 | kinetic_time_course | 0.008205 | 0.002326 | -0.005880 |
| b_kinetic_time_course_05 | kinetic_time_course | 0.007094 | 0.001773 | -0.005321 |
| b_kinetic_time_course_09 | kinetic_time_course | 0.006250 | 0.002413 | -0.003837 |
| b_kinetic_time_course_08 | kinetic_time_course | 0.000858 | 0.004519 | 0.003661 |
| b_kinetic_time_course_02 | kinetic_time_course | 0.004612 | 0.001313 | -0.003298 |

## Largest Staged Advantages

| case | family | monolithic RMSE | staged RMSE | staged-minus-monolithic |
| --- | --- | ---: | ---: | ---: |
| c_uv_vis_05 | UV_Vis | 0.378241 | 0.002454 | -0.375786 |
| d_raman_05 | Raman | 0.217103 | 0.022009 | -0.195094 |
| a_lsv_06 | LSV | 0.006752 | 0.001568 | -0.005184 |
| e_xrd_06 | XRD | 0.009112 | 0.005914 | -0.003198 |
| b_kinetic_time_course_06 | kinetic_time_course | 0.004476 | 0.001601 | -0.002875 |
| d_raman_04 | Raman | 0.007302 | 0.004713 | -0.002589 |
| b_kinetic_time_course_05 | kinetic_time_course | 0.003855 | 0.001629 | -0.002226 |
| b_kinetic_time_course_10 | kinetic_time_course | 0.004110 | 0.002718 | -0.001392 |
| b_kinetic_time_course_02 | kinetic_time_course | 0.002298 | 0.000919 | -0.001379 |
| d_raman_07 | Raman | 0.005570 | 0.004575 | -0.000995 |

## Largest Monolithic Advantages

| case | family | monolithic RMSE | staged RMSE | staged-minus-monolithic |
| --- | --- | ---: | ---: | ---: |
| e_xrd_04 | XRD | 0.030531 | 0.066451 | 0.035920 |
| f_gc_trace_09 | GC_trace | 0.012064 | 0.038281 | 0.026218 |
| c_uv_vis_10 | UV_Vis | 0.001801 | 0.012994 | 0.011192 |
| e_xrd_10 | XRD | 0.014642 | 0.022669 | 0.008027 |
| d_raman_03 | Raman | 0.008181 | 0.013325 | 0.005144 |
| e_xrd_07 | XRD | 0.013310 | 0.018079 | 0.004768 |
| f_gc_trace_06 | GC_trace | 0.032477 | 0.036794 | 0.004316 |
| f_gc_trace_02 | GC_trace | 0.015516 | 0.019455 | 0.003940 |
| b_kinetic_time_course_01 | kinetic_time_course | 0.001434 | 0.004650 | 0.003216 |
| f_gc_trace_01 | GC_trace | 0.012416 | 0.015587 | 0.003171 |

## Errors

None.
