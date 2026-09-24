"""Portable paths shared by the preserved analysis scripts."""
import os
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent
REPO = PACKAGE.parents[1]
INPUTS = PACKAGE / "inputs"
REFERENCE = PACKAGE / "reference"
OUTPUT = Path(os.environ.get("FIGURE6_OUTPUT", REPO / "build/figure6")).resolve()
if OUTPUT == PACKAGE or PACKAGE in OUTPUT.parents:
    raise ValueError("Keep generated analysis outside the versioned source/input directory")
EMPIRICAL_OUT = OUTPUT / "empirical"
KOH_OUT = OUTPUT / "koh"
for directory in (OUTPUT, EMPIRICAL_OUT, KOH_OUT):
    directory.mkdir(parents=True, exist_ok=True)
