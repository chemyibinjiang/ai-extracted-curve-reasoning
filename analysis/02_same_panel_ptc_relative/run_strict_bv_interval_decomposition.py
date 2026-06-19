from __future__ import annotations

import runpy
from pathlib import Path


HERE = Path(__file__).resolve().parent
DRIVER = HERE / "run_ptc_relative_eta10_eta50.py"


def main() -> None:
    # The final Figure 6 package computes the same-panel eta comparison and the
    # strict-BV/empirical-iR interval decomposition from the same compact source
    # tables. Delegate to the shared driver so the panel summaries cannot drift.
    runpy.run_path(str(DRIVER), run_name="__main__")


if __name__ == "__main__":
    main()

