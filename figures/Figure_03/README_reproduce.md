# Figure 3 reproduction package

This folder contains the final Figure 3 exports and the minimal files needed to regenerate them.

## Contents

- `build_figure3_compact.py`: plotting script for the final synthetic benchmark figure.
- `build_selected_panel_overlays.py`: regenerates the six selected benchmark overlays used in panel A from the benchmark-case anchoring and curve-extraction outputs.
- `anchored_overlays_labeled_offset_axes/`: labeled overlay PNGs used in panel A, including the selected Figure 1 examples.
- `Figure_3_synthetic_benchmark.png`: final raster figure.
- `Figure_3_synthetic_benchmark.tif`: high-resolution TIFF export.
- `Figure_3_synthetic_benchmark.pdf`: PDF export.
- `Figure_3_synthetic_benchmark.svg`: SVG wrapper export.

The full benchmark ground-truth dataset and corresponding agent benchmark-case outputs are packaged separately at `data\benchmark_curve_extraction`.

## Regenerate

Run from this folder:

```powershell
python .\build_figure3_compact.py
```

The script writes the four `Figure_3_synthetic_benchmark` exports into this folder.

## Notes

Panel A now uses the same six selected benchmark examples as Figure 1, except that the GC panel uses the co-eluting-peak case: `a_lsv_04`, `b_kinetic_time_course_10`, `c_uv_vis_02`, `d_raman_02`, `e_xrd_10`, and `f_gc_trace_03`. The selected overlays include recognized tick labels, grid lines, extracted sampled points, and original curve strokes.
