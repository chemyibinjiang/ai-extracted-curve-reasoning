# Focused Curve Extraction Benchmark Cases

Worker-facing benchmark cases for the existing peeragent batch runner.

- cases: `60`
- panel anchoring tasks: `60`
- each case contains one single-panel benchmark image
- each case has a pre-seeded `codex_orchestrator/panel_tasks.jsonl`, so start the batch at `anchoring`, not `orchestrator`
- this worker-facing tree intentionally contains images and ordinary paper-like context only

## Family Counts

- `GC_trace`: `10`
- `kinetic_time_course`: `10`
- `LSV`: `10`
- `Raman`: `10`
- `UV_Vis`: `10`
- `XRD`: `10`

## Suggested Run

```powershell
.\.venv\Scripts\python.exe run_pipeline_batch.py "benchmark_cases\focused_curve_extraction_set_v4_1_fixed" `
  --stage anchoring `
  --max-workers 4 `
  --model gpt-5.4 `
  --codex-reasoning-effort xhigh `
  --codex-bypass-sandbox
```

