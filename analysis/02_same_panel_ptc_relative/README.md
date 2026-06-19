# 02_same_panel_ptc_relative

This folder contains the compact public analysis layer for the same-panel Pt/C
relative eta10/eta50 analysis and the strict-BV/empirical-iR interval
decomposition used for Figure 6 and related SI checks.

## Contents

- `config_final.json`: final analysis settings.
- `run_ptc_relative_eta10_eta50.py`: regenerates the Figure 6 panel summaries
  and figure/report from the included source rows.
- `run_strict_bv_interval_decomposition.py`: wrapper for rerunning the
  Figure 6 strict-BV/empirical-iR interval decomposition outputs.
- `outputs/source_AB_current_same_panel_eta10_eta50_rows.csv`: compact source
  rows for same-panel eta10/eta50 comparison.
- `outputs/source_CD_current_strict_bvir_offset_rows.csv`: compact source rows
  for the strict-BV+iR+Eoffset interval decomposition.
- `outputs/panel_*.csv`: final compact summaries used for Figure 6 panels A-G.

## Regenerate summaries

```bash
python run_ptc_relative_eta10_eta50.py
python run_strict_bv_interval_decomposition.py
```

The regenerated PNG/report are written to `outputs/`. The manuscript figure
asset itself is also retained under `figures/Figure_06_ptc_relative/`.

