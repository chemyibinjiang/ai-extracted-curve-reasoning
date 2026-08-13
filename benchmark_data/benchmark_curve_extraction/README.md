# Benchmark Curve Extraction Data

This folder contains the synthetic benchmark data used for the curve-extraction benchmark associated with manuscript Figure 3.

## Contents

| Path | Contents |
|---|---|
| `peeragent_ground_truth/` | Ground-truth benchmark plots, raw curve data, metadata, contact sheets, and truth index. |
| `benchmark_cases/` | Agent-run benchmark case outputs retained for inspection. |
| `agentic_ablation/` | Leakage-safe benchmark code, the completed 60-panel single-agent records, and a retrospective common-evaluator comparison with the archived staged workflow. |

The benchmark data are synthetic/generated examples. They are included to support reproducibility of the benchmark and do not contain original publication figures.

## Staged-Workflow Ablation

The comparison deliberately excludes panel routing because every benchmark
input is already a single panel. See:

- `agentic_ablation/public_results/README.md` for the completed public results
  and their interpretation limits;
- `agentic_ablation/ANALYSIS_PLAN.md` for the stricter prospective experiment;
- `agentic_ablation/README.md` for execution commands; and
- `agentic_ablation/run_benchmark.py` for preparation, execution, and scoring.

The answer curves are copied into neither condition's worker directory and are
loaded only by the separate evaluation action.

## Public-Repository Cleanup

The public repository draft excludes local transfer archives, workbench logs, private evaluation folders, and absolute local path fields. Package-relative paths are used where possible.
