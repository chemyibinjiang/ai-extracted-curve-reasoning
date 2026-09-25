# Pt/C Performance and Interval Decomposition

This exploratory package compares relative Pt/C performance and decomposes
overpotential intervals. Compact source rows and summaries are included here.
For manuscript Figure 6, use [the response-family analysis](../../../analysis/figure6/README.md)
and [assembled artwork](../../manuscript/Figure6.svg).

Panel F uses the exact BV contribution over the current interval, rather than
the difference between fitted BV slope parameters. Source tables:

- `source_AB_current_same_panel_eta10_eta50_rows.csv`
- `source_CD_current_strict_bvir_offset_rows.csv`

Main output:

`main_text_figure6_A_to_G_20260619_panelF_bv_interval.png`

Regenerate with:

`python generate_main_text_figure6_package_20260619_panelF_bv_interval.py`
