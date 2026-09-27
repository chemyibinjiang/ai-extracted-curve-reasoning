# Figure Validation

`manifest.json` lists the SHA-256 hashes, sizes, and image dimensions for:

- Six Figure 1-6 SVG/PNG pairs in `figures/manuscript/`.
- Six numerical result tables in `analysis/figure6/expected/`.

Run:

```text
python scripts/validate_figures.py
python -m unittest discover -s tests -p test_figure_tables.py -v
```

These checks use the Python standard library. Retrieve figure assets with
Git LFS before validating them. The SVG check rejects missing/external assets
and unexpected scripts. Figure 1's two identical Inkscape mesh-rendering
polyfills are recognized by an explicit hash.

`figure4-validation.json` records the current relaxed-BV population results
(1,588/2,361 accepted fits). `figure5-artwork-update.json` links the current
Figure 5 assets to the NiMo metrics in `figure5-nimo-validation.json`.
The earlier summaries are retained only in
`exploration/archive/pre_relaxation_validation/`. Active validation records
are cross-checked against the current parameter and artwork references by
`tests/test_reader_reproduction.py`.

The numerical checks recompute equal-family means, sample SD, support masks,
parameter transforms, coverage counts, and dominant-control crossings.
The analytical model, fitted support, and weighting conventions are described
in [the Figure 6 guide](../analysis/figure6/README.md).

For numerical analysis from the supplied curve coordinates, use
[Reproducibility](../REPRODUCIBILITY.md). Integrity checks and artwork export
are distinct from refitting models.
