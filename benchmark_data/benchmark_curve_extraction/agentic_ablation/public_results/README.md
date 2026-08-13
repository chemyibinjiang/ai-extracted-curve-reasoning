# Public Single-Agent Benchmark Results

This directory contains the completed 60-panel single-agent anchoring-and-
extraction benchmark and its retrospective comparison with the archived staged
workflow outputs.

## What Is Included

- `experiment_manifest.json`: sanitized experiment-level configuration.
- `single_agent_60_cases/`: the complete set of 60 final single-agent records.
  Each case contains the returned structured response, deterministic axis-fit
  result, overlap-QA result, and final curve overlay.
- `single_agent_60_cases/evaluation/`: single-agent summary tables produced by
  the shared evaluator.
- `retrospective_staged_comparison/`: the archived staged outputs and completed
  single-agent outputs rescored with the same coordinate-aware evaluator.

The synthetic input panels and hidden answer curves are already released in
the adjacent `benchmark_cases/` and `peeragent_ground_truth/` directories and
are not duplicated here.

## Main Result

Both conditions returned 137 curves across 60 panels. In the retrospective
common-evaluator comparison, the median case-level scaled distance was 0.00062
for the single-agent condition and 0.00076 for the archived staged workflow.
The paired comparison counted 27 cases favoring staged processing, 32 favoring
the single agent, and one tie; the two-sided exact sign-test p-value was 0.603.

These results indicate broadly similar aggregate reconstruction performance.
The case records nevertheless show architecture-specific failure modes,
including severe final-record errors or shape distortion in selected
single-agent cases and truncated visible-range coverage in selected staged
cases.

## Interpretation Boundary

This is a **retrospective** common-evaluator comparison. The completed
single-agent arm used `gpt-5.4` with `xhigh` reasoning through the recorded
OpenAI-compatible endpoint. The archived staged run did not record its exact
reasoning-effort setting. The comparison therefore supports a descriptive
ablation and case-level failure analysis, but it is not a compute-matched or
fully configuration-matched causal test of agent architecture.

`ANALYSIS_PLAN.md` describes the stricter prospective experiment required for
that stronger claim. It should not be mistaken for the protocol that generated
the retrospective comparison reported here.

## Excluded Runtime Material

The local ignored `runs/` directory also contains temporary provider state,
duplicated frozen-code workspaces, caches, event logs, and exploratory debug
images. Those files are not needed to inspect or rescore the final scientific
records and are intentionally excluded from Git.

Regenerate this directory from a retained local run with:

```powershell
python benchmark_data/benchmark_curve_extraction/agentic_ablation/export_public_results.py
```
