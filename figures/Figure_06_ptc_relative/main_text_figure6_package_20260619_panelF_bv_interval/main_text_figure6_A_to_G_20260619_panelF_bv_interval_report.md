# Main-Text Figure 6 Package, 2026-06-17 strict fixed-neff2 descriptors

## Inputs
- AB same-panel Pt/C eta10/eta50 table: `source_AB_current_same_panel_eta10_eta50_rows.csv`
- CD strict-BV+iR+Eoffset decomposition table: `source_CD_current_strict_bvir_offset_rows.csv`
- Panel D/F bBV descriptors use `fixed_neff2_cand_b_tafel_mV_dec` and same-panel contrasts recomputed from fixed-neff2 candidate and Pt/C values.
- Output PNG: `main_text_figure6_A_to_G_20260619_panelF_bv_interval.png`

## Exact Counts
- Panel A/B use AB rows: n=395, cases=197.
- Panel C/D use CD rows: n=306, cases=170.
- Panel E/G use alkaline PM AB rows: n=122, cases=78.
- Panel F uses alkaline PM CD rows for fitted descriptors: n=115, cases=72, and alkaline PM AB rows for the branch slope posterior: n=122, cases=78.
- Alkaline PM AB split: both_better n=89, cases=62; remaining_alkaline_pm n=33, cases=25.
- Alkaline PM CD split: both_better n=85, cases=58; remaining_alkaline_pm n=30, cases=22.

Broad group counts:
- Acidic non-PM: AB n=78; CD n=62
- Alkaline non-PM: AB n=130; CD n=87
- Acidic PM: AB n=65; CD n=42
- Alkaline PM: AB n=122; CD n=115

## Exact both_better Definition
`both_better` is defined only inside alkaline PM rows as: candidate Delta eta10 vs same-panel Pt/C < 0 and candidate Delta eta50 vs same-panel Pt/C < 0. In the current tables this is the `both_better_global == True` flag for rows with `figure6_group == Alkaline PM`. `remaining_alkaline_pm` is every other alkaline PM row.

## Panel Messages
- Panel A: The four broad groups show the Pt/C-relative eta10/eta50 distribution.
- Panel B: Bayesian fitted-line posterior densities quantify broad-group Delta eta50 versus Delta eta10 trends without crowding panel A.
- Panel C: The joint scatter and marginal histograms show how Delta(eta50-eta10) separates into strict-BV and empirical iR contributions; Eoffset cancels from this interval.
- Panel D: Four-group fitted descriptors are shown as scatter/violin distributions with median and IQR markers.
- Panel E: Within alkaline PM, both_better is the stricter branch defined by eta10 and eta50 both beating same-panel Pt/C.
- Panel F: The alkaline PM both_better branch is compared with the remaining alkaline PM rows using fitted descriptor distributions plus a branch-level slope posterior.
- Panel G: The both_better branch is compared with remaining alkaline PM rows by rule-level catalyst metadata categories.

## Panel B Posterior Summary
- Acidic non-PM: slope=1.04 [0.97, 1.12], intercept=18.3 mV [7.9, 28.5]
- Alkaline non-PM: slope=1.10 [1.02, 1.17], intercept=6.6 mV [-2.8, 15.9]
- Acidic PM: slope=1.25 [1.17, 1.33], intercept=-3.5 mV [-10.4, 3.4]
- Alkaline PM: slope=1.50 [1.37, 1.63], intercept=-24.1 mV [-29.3, -19.0]

## Panel G Metadata Categories
- Alloy/intermetallic/bimetallic: audit_strict_subfamily contains alloy/intermetallic/bimetallic/multimetal/high-entropy
- Explicit carbon support: label/support/substrate/title/subfamily contains carbon, CNT, graphene, CQD, CNF, carbon cloth/foam/fiber, N-doped C, HCS/NHCS, fullerene
- Pt-containing: Pt_containing is true
- Ir-containing: Ir_containing is true
- Ru-containing: Ru_containing is true
- Ru + carbon support: Ru_containing and explicit carbon support
- Ru + alloy/bimetallic: Ru_containing and alloy/intermetallic/bimetallic rule
- Phase-controlled Ru nanocages: Ru_containing and phase-controlled Ru nanocage subfamily
- Ru without carbon/alloy/phase: Ru_containing but no explicit carbon, alloy/bimetallic, or phase-controlled Ru flag
- Oxide/hydroxide interface: manual oxide/hydroxide interface or strict subfamily contains oxide/hydroxide/oxyphilic
- Other PM chalcogenide/phosphide: audit_strict_subfamily equals other PM chalcogenide/phosphide
- Ru chalcogenide/MoS2: Ru_containing plus chalcogenide/selenide/MoS2/WS2 flag
- Ru MOF/framework: Ru_containing plus MOF/framework/CPF/BDC/FeMOF text

Panel G enrichment counts:
- Alloy/intermetallic/bimetallic: both_better 33/89 (37.1%) vs remaining 1/33 (3.0%).
- Explicit carbon support: both_better 61/89 (68.5%) vs remaining 14/33 (42.4%).
- Pt-containing: both_better 32/89 (36.0%) vs remaining 5/33 (15.2%).
- Ir-containing: both_better 12/89 (13.5%) vs remaining 0/33 (0.0%).
- Ru-containing: both_better 50/89 (56.2%) vs remaining 23/33 (69.7%).
- Ru + carbon support: both_better 38/89 (42.7%) vs remaining 12/33 (36.4%).
- Ru + alloy/bimetallic: both_better 14/89 (15.7%) vs remaining 1/33 (3.0%).
- Phase-controlled Ru nanocages: both_better 4/89 (4.5%) vs remaining 0/33 (0.0%).
- Ru without carbon/alloy/phase: both_better 7/89 (7.9%) vs remaining 10/33 (30.3%).
- Oxide/hydroxide interface: both_better 17/89 (19.1%) vs remaining 14/33 (42.4%).
- Other PM chalcogenide/phosphide: both_better 1/89 (1.1%) vs remaining 5/33 (15.2%).
- Ru chalcogenide/MoS2: both_better 4/89 (4.5%) vs remaining 6/33 (18.2%).
- Ru MOF/framework: both_better 1/89 (1.1%) vs remaining 3/33 (9.1%).

## Readability Changes Versus The Previous Draft
- Panel D/F descriptor statistics now use the strict fixed-neff2 BV-derived Tafel scale rather than the legacy alpha05/free-a_app descriptor.
- Panel B restores the old posterior-density/KDE style for slope and intercept.
- Panel C restores the joint strict-BV versus empirical-iR contribution scatter with marginal histograms.
- Panel D keeps scatter/violin descriptor distributions for broad groups; panel F replaces the secondary intercept subplot with an alkaline-PM branch slope posterior and uses exact strict-BV interval contribution as the fourth branch descriptor.
- Panel letters were realigned to panel bounds and no longer clip at the top of the canvas.
- The figure keeps the seven-panel A-G story while returning the older visual grammar for posterior and descriptor panels.

## Scientific Guardrails
- Eoffset is not plotted as an interval contributor because it is current-independent and cancels from Delta(eta50-eta10).
- The intercept/baseline descriptor is kept secondary because it does not drive the 10-to-50 mA interval by itself.
- The strict-BV interval interpretation is tied mainly to the Tafel-scale term `(bBV,cand-bBV,Pt/C)log10(5)`.
