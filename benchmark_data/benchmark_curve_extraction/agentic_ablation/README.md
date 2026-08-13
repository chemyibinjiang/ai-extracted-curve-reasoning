# Single-Agent Versus Staged Anchoring-and-Extraction Benchmark

## Published Result Package

The completed public records are in `public_results/`. They contain all 60
single-agent final records and a retrospective rescore against the archived
staged outputs using one common evaluator. See `public_results/README.md` for
the numerical result and its interpretation boundary.

The prospective commands and locked plan below describe a stricter future
configuration-matched rerun. They do not imply that the archived staged arm was
generated under the newly locked provider and reasoning-effort settings.

## Question

Does decomposing single-panel curve reconstruction into specialized anchoring and
curve-extraction stages improve the resulting quantitative curve record relative
to a strong monolithic single-agent prompt?

This benchmark does **not** evaluate panel routing. Every input is already one
single-panel benchmark image.

## Conditions

| Condition | Model sessions per case | Description |
|---|---:|---|
| `monolithic` | 1 | One agent anchors the axes, extracts all curves, invokes the same deterministic axis-fit and overlap-QA utilities, and returns one combined record. |
| `staged` | 2 plus at most one extraction revision | The frozen publication workflow runs its panel-anchoring worker followed by its panel-level curve-extraction worker. |

Both conditions use the same:

- requested model (`gpt-5.4`) and reasoning effort (`xhigh`);
- OpenAI-compatible provider endpoint and provider-scoped API credential;
- single-panel PNG and paper-like caption;
- attached image input, unrestricted local Python/file permission profile, and
  Python executable;
- deterministic axis-fit utility;
- overlap-QA utility;
- hidden raw answer curves used only after inference; and
- end-to-end evaluator.

The staged condition receives more model sessions by design. Therefore, the
experiment tests the practical value of the staged workflow, not specialization
independently of inference budget. Model-call count, elapsed time, and available
token-usage metadata must be reported alongside accuracy.

Token use is collected from Codex JSON events for the monolithic condition and
from the frozen workers' final `tokens used` summaries for anchoring,
extraction, and any extraction revision in the staged condition.

The archived May 2026 staged outputs do not record the exact reasoning-effort
setting. The published retrospective comparison therefore reports the two
conditions descriptively after common-evaluator rescoring. A future prospective
experiment must rerun both arms from scratch under the locked configuration
above. If a `high`-effort sensitivity analysis is later desired, both arms must
be rerun at `high`; results must never be compared across effort settings.

## Provider Isolation

The public configuration records the requested custom base URL, provider id,
and the name of the environment variable that supplies its API key. It never
contains the API key itself. Before either inference command, set
`BLACKAI_API_KEY` in the current process environment.

The locked Responses API base URL is `https://blackaicoding.com/v1`. The
service's homepage URL (including a `www` host and no `/v1` suffix) is not an
API base URL and must not be used for this benchmark.

```powershell
$env:BLACKAI_API_KEY = "<set locally; do not commit>"
```

At runtime the harness creates an isolated `CODEX_HOME` under the ignored run
directory, writes only the custom-provider definition there, removes local
OpenAI credential variables from the child environment, and refuses to run if
`BLACKAI_API_KEY` is absent. Both benchmark arms inherit that exact same child
environment. The provider must implement the OpenAI Responses API because that
is the wire protocol supported by the Codex CLI custom-provider interface.
Before either arm starts inference, the runner also authenticates against
`/models` and verifies that the requested `gpt-5.4` alias is available.
Each concurrent case receives its own writable `CODEX_HOME`, preventing config
and state-file races. The locked full-benchmark configuration uses 60 outer
workers, one per panel; `--max-workers` can override this when required by a
provider concurrency limit.

## Leakage Control

`prepare` creates fresh worker directories containing only:

- the target PNG;
- a sanitized task record;
- the two deterministic utilities; and
- the relevant prompt and JSON schema.

Existing agent responses, benchmark HTML, raw answer curves, answer-key metadata,
and private evaluation outputs are not copied into worker directories. Evaluation
is a separate command that reads the ground-truth directory only after all model
runs are complete.

## Primary Endpoints

The primary continuous endpoint is the symmetric curve distance after the
predicted anchors have converted extracted pixels into displayed scientific-axis
coordinates. Each axis is scaled to the answer-curve span before distance is
computed. This jointly evaluates anchoring and extraction.

Additional endpoints are:

- valid anchor fit for both axes;
- predicted versus true curve count;
- matched-curve coverage;
- curve-label identity agreement;
- median and 95th-percentile scaled curve distance;
- valid complete-record rate;
- overlap-QA status;
- elapsed time and model-call count.

Continuous paired case-level differences are the primary comparison. Any binary
pass threshold is secondary and must be fixed before inspecting the new results.
The complete prespecified analysis is recorded in `ANALYSIS_PLAN.md`.

## Commands

Run commands from the repository root.

```powershell
python benchmark_data/benchmark_curve_extraction/agentic_ablation/run_benchmark.py prepare
```

Run a leakage-safe six-case smoke set, one case from each family:

```powershell
python benchmark_data/benchmark_curve_extraction/agentic_ablation/run_benchmark.py run-monolithic `
  --case a_lsv_04 --case b_kinetic_time_course_04 --case c_uv_vis_02 `
  --case d_raman_05 --case e_xrd_05 --case f_gc_trace_03

python benchmark_data/benchmark_curve_extraction/agentic_ablation/run_benchmark.py run-staged `
  --case a_lsv_04 --case b_kinetic_time_course_04 --case c_uv_vis_02 `
  --case d_raman_05 --case e_xrd_05 --case f_gc_trace_03
```

Run all 60 cases:

```powershell
python benchmark_data/benchmark_curve_extraction/agentic_ablation/run_benchmark.py run-monolithic
python benchmark_data/benchmark_curve_extraction/agentic_ablation/run_benchmark.py run-staged
```

Evaluate after both conditions finish:

```powershell
python benchmark_data/benchmark_curve_extraction/agentic_ablation/run_benchmark.py evaluate
```

Evaluate only the completed single-agent arm before a staged comparison is
available:

```powershell
python benchmark_data/benchmark_curve_extraction/agentic_ablation/run_benchmark.py evaluate `
  --condition monolithic
```

Generated files are written under `agentic_ablation/runs/` and are ignored by
Git. Use `--run-root` to place them elsewhere.

`prepare` refuses to reuse a nonempty condition directory. Select a new
`--replicate` or `--run-root`, or deliberately reset only the generated
condition directories with `--force-prepare`.

Run the code-only test suite without invoking any model:

```powershell
python -m unittest discover `
  -s benchmark_data/benchmark_curve_extraction/agentic_ablation/tests `
  -p "test_*.py"
```

## Interpretation

A one-shot comparison can support the claim that staged processing improves
practical reconstruction quality. It cannot by itself establish that multiple
agent identities are better than a budget-matched iterative single agent. That
stronger claim requires an additional condition with the same number of model
sessions and token budget as the staged workflow.
