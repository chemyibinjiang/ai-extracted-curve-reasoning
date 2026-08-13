# Prespecified Analysis Plan

This plan was written before running the new monolithic and staged conditions.

## Locked Inference Configuration

Both conditions will be rerun from scratch using the requested `gpt-5.4` model
alias at `xhigh` reasoning effort. They will use the same custom
OpenAI-compatible provider, attached PNG, Python executable, deterministic
utility files, and unrestricted local execution profile. The API credential is
provided only through `BLACKAI_API_KEY`; local OpenAI credentials and the normal
user-level Codex configuration are excluded from both child environments.

The historical staged benchmark is not used as one arm because its archived
batch manifest omitted reasoning effort. It is retained only as provenance.
Any later reasoning-effort sensitivity analysis must rerun both conditions
under the alternate setting.

## Scope

The benchmark evaluates axis anchoring and curve extraction from 60 already
selected single-panel synthetic figures. It does not evaluate source-figure
routing, publication retrieval, metadata enrichment, claim checking, or
scientific reasoning.

## Primary Comparison

For each case, predicted anchors convert extracted pixel points into scientific
coordinates. Predicted and answer curves are then scaled by the complete answer
set's x and y spans. Curves are assigned one-to-one by minimum geometric cost.
Distances are computed in the rendered axis coordinate system. The answer-side
axis manifest specifies linear axes by default and the logarithmic current axis
for `a_lsv_08`; this manifest is fixed before new inference.

The primary case endpoint is the median, across matched curves, of the symmetric
point-to-polyline distance in scaled scientific coordinates.

The primary effect estimate is:

`staged case distance - monolithic case distance`

Negative values favor the staged workflow.

The paired analysis will report:

- the median paired difference;
- a deterministic 95% bootstrap confidence interval for that median;
- the number of cases favoring each condition; and
- a two-sided exact sign-test p-value after excluding exact ties.

## Secondary Endpoints

- valid two-axis calibration;
- exact curve-count recovery;
- normalized curve-label agreement after assignment;
- curve-level median distance at most 0.02;
- curve-level 95th-percentile distance at most 0.05;
- shared x-range coverage of at least 0.80;
- complete case pass requiring all thresholds, correct count, and correct labels;
- overlap-QA status;
- model-call count and elapsed time; and
- token use from monolithic JSON events and staged per-worker Codex summaries.

Secondary thresholds are descriptive and are not substitutes for the continuous
paired endpoint.

## Stratification

Results will be shown overall and separately for the six prespecified families:

- LSV;
- kinetic time course;
- UV-Vis;
- Raman;
- XRD; and
- GC trace.

No cases will be removed after inference because they are difficult or because a
condition failed. A missing, malformed, or uncalibratable result receives the
prespecified scaled-distance penalty of 2.0 and fails every binary endpoint.
Execution failures therefore remain in the paired analysis. Any infrastructure
failure unrelated to model output must be documented and rerun for both
conditions under the same configuration.

## Repetition

The first complete experiment uses one run per condition for all 60 cases.
Run-to-run stability should subsequently be measured with three replicates for a
prespecified difficult subset or, resources permitting, all 60 cases.

## Interpretation Boundary

This two-condition experiment tests the practical staged system against a
one-session monolithic agent. Because the staged system receives more model
sessions, the result cannot isolate specialization from inference budget. A
budget-matched iterative single-agent condition is required before claiming that
multiple specialized agents outperform a single agent at equal compute.

The requested model name is an alias supplied through a third-party compatible
endpoint. The run manifest will therefore report the requested alias, endpoint,
Codex CLI version, and available response metadata. Conclusions apply to that
recorded execution configuration and should not imply independent verification
of the provider's internal model routing.
