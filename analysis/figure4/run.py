"""Prepare the complete curve cohort or refit current Figure 4."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = {
    "batch8/case1831/figure_5__panel_a/curve_2": "20 wt% Pt/C",
    "batch8/case1792/figure_6__panel_a/curve_2": "N-Ni",
    "batch0/case44/figure_4__panel_a/curve_2": "WO3",
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", nargs="?", choices=("prepare", "refit"), default="refit")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--workers", type=int, default=6)
    args = parser.parse_args()
    if args.stage == "prepare":
        from prepare import prepare
        output = (args.output or ROOT / "build/figure4-preparation").resolve()
        if output == ROOT / "analysis" or ROOT / "analysis" in output.parents:
            parser.error("Keep outputs outside analysis/")
        output.mkdir(parents=True, exist_ok=True)
        print(json.dumps(prepare(output), indent=2))
    else:
        command = [sys.executable, str(ROOT / "analysis/effective_bv/run.py"), "population",
                   "--workers", str(args.workers)]
        if args.output: command.extend(["--output", str(args.output.resolve())])
        subprocess.run(command, check=True)


if __name__ == "__main__":
    main()
