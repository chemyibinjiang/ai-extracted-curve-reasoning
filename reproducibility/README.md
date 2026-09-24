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

The numerical checks recompute equal-family means, sample SD, support masks,
parameter transforms, coverage counts, and dominant-control crossings.
The analytical model, fitted support, and weighting conventions are described
in [the Figure 6 guide](../analysis/figure6/README.md).

For numerical analysis from the supplied curve coordinates, use
[Reproducibility](../REPRODUCIBILITY.md). Integrity checks and artwork export
are distinct from refitting models.
