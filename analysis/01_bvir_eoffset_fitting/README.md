# 01_bvir_eoffset_fitting

This folder contains the compact public analysis layer for the strict fixed
n_eff=2 BV/BV+iR/BV+Eoffset/BV+iR+Eoffset fitting results used for Figure 5 and
related SI controls.

## Contents

- `config_final.json`: final fitting and reporting settings.
- `run_strict_bv_ir_eoffset_fits.py`: regenerates compact Figure 5 summary
  tables from the included row-level fitted descriptor table.
- `run_ir_only_control.py`: validates or summarizes the iR-only control table.
- `outputs/figure5_fit_model_counts.csv`: model-pass counts for BV, BV+iR,
  BV+Eoffset, and BV+iR+Eoffset.
- `outputs/figure5_descriptor_rows.csv`: row-level fitted descriptors for the
  rescued subset used to summarize Figure 5 descriptor distributions.
- `outputs/figure5_selected_corrections_summary.csv`: compact PM/non-PM
  summaries of selected R, D_R, and Eoffset corrections.
- `outputs/figure5_descriptor_summary.csv`: compact PM/non-PM summaries of
  fitted strict-BV descriptors.
- `outputs/ir_only_control_summary.csv`: iR-only and iR+Eoffset control counts.

The full fit was run from the internal canonical publication database. This
public folder retains the final fitted descriptor rows and compact summaries
needed to audit the reported manuscript/SI numbers without publishing raw source
figures or private working folders.

## Regenerate compact summaries

```bash
python run_strict_bv_ir_eoffset_fits.py
python run_ir_only_control.py
```

