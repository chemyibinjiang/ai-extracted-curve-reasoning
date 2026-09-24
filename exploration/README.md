# Exploratory Analyses

This folder preserves the records of two dataset-driven investigations. The
manuscript's reproducible calculations are organized separately by figure in
[analysis/](../analysis/README.md).

| Topic | Scope | Exploration records | Figure analysis |
| --- | --- | --- | --- |
| Catalyst performance relative to Pt/C | Same-panel eta10/eta50/eta100 comparisons, material classes, conditions, and performance trends | [Discussion and results](agent_conversation_records/rendered_transcripts/019e5a99-d4b4-7b33-9c00-74b8d0f6c184.md#18-user); source workspace name: `01_ptc_relative_slope_agent` | Not a separate analysis in the current figure set |
| BV and BV+jR modeling | Compare model fits, investigate the linear loss term, and examine fit diagnostics | [Modeling investigation](agent_conversation_records/rendered_transcripts/019eb222-0283-7721-a3de-1c69905a9035.md#2-user); source workspace name: `02_bv_ir_fitting_agent` | [Figure 4](../analysis/figure4/README.md), with physical case studies in [Figure 5](../analysis/figure5/README.md) |

The conversations overlap in subject matter and are retained together under
[agent_conversation_records/](agent_conversation_records/README.md), including
their linked images, export manifests, and session archive. Task numbers and
intermediate results inside those records are preserved as recorded; the topic
names above identify the investigations without renumbering the conversations.

Use the figure-specific inputs, methods, and checks for manuscript results.
Figure 3's extraction/claim validation and Figure 6's Pt/C response-family and
kinetic analysis are distinct from catalyst-performance rankings. Reproducing
Figures 4-6 does not require this folder or its archives.

The full working-analysis ZIP, when present locally, remains excluded from Git.
No additional exploratory scripts or datasets are unpacked into the release.
