# Repository Structure

| Location | Contents |
| --- | --- |
| `figures/manuscript/` | Figures 1-6, as editable SVGs and PNG previews |
| `analysis/figure4/` | Cohort preparation and inclusion/exclusion record, prepared curves, BV/BV+jR refitting, local slopes and fit statistics |
| `analysis/figure5/` | Compensation, bubble/EIS, surface-kinetic, and current-rescaling case studies |
| `analysis/figure6/` | Pt/C template discovery, VHT reconstruction, and rate control |
| `analysis/common/` | Shared BV numerical functions |
| `analysis/SOURCE_MANIFEST.json` | Input/code provenance and integrity hashes |
| `benchmark_data/benchmark_curve_extraction/` | Synthetic benchmark inputs, extraction results, and evaluation code |
| `data_literature/` | Complete dataset of 4,211 extracted curves (132,314 points) and source metadata |
| `code_reference/` | Extraction-framework source |
| `exploration/` | Catalyst-performance and BV+jR investigations, with shared session records and assets |
| `scripts/` | Figure validation and artwork export |
| `tests/` | Numerical, integrity, and isolated-package tests |
| `reproducibility/` | Figure manifest and validation documentation |
| `build/` | Generated results; excluded from Git |

Within an analysis directory, `inputs/` contains observations and metadata,
`reference/` contains fit parameters and comparison results, and `run.py` is the
entry point. Figure 6 additionally keeps the exact plotted numerical tables in
`expected/`. Recomputed results are written to `build/`, never over the inputs.

`exploration/agent_conversation_records/` preserves the overlapping investigation
transcripts, manifests, and linked images. It is not a runtime dependency of the
figure analyses. Topic links and their relationship to the figures are listed
in [exploration/README.md](exploration/README.md).

The manuscript figures and the numerical analyses are separate artifacts.
Exporting an SVG reproduces its final layout; running an analysis reproduces
numerical results. Use [REPRODUCIBILITY.md](REPRODUCIBILITY.md) for both workflows.
