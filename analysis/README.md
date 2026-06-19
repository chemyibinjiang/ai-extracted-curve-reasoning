# Curated Analysis Layer

This folder contains compact, public-facing analysis material for the two
manuscript analyses that depend on the extracted HER curve dataset.

The folder is intentionally not a dump of all working files. It excludes raw
publication images, private manual-proof records, reviewer-only cards, agent
transcripts, and deprecated exploratory variants.

## Folder map

- `01_bvir_eoffset_fitting/`: strict fixed-n_eff=2 BV, BV+iR, BV+Eoffset, and
  BV+iR+Eoffset fitting summaries used for Figure 5 and related SI checks.
- `02_same_panel_ptc_relative/`: same-panel Pt/C eta10/eta50 comparison,
  posterior trend summaries, strict-BV/empirical-iR interval decomposition, and
  alkaline precious-metal branch metadata summaries used for Figure 6.

Each subfolder contains a `config_final.json`, a short README, scripts, and an
`outputs/` directory with the final public CSV outputs.

