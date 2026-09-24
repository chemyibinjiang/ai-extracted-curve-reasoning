"""Export the manually finalized SVG artwork with Inkscape; no data analysis."""

import argparse
from pathlib import Path
import shutil
import subprocess

from validate_figures import ROOT, validate_assets


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inkscape", default="inkscape", help="Inkscape executable or absolute path")
    parser.add_argument("--output", type=Path, default=ROOT / "build/final_figures")
    parser.add_argument("--format", choices=("png", "pdf"), default="png")
    parser.add_argument("--width", type=int, default=3000, help="PNG export width")
    args = parser.parse_args()
    validate_assets(ROOT)
    executable = shutil.which(args.inkscape)
    if not executable:
        raise SystemExit("Inkscape not found; supply its absolute path with --inkscape")
    if args.width <= 0:
        raise SystemExit("PNG width must be positive")
    output = args.output.resolve()
    source = ROOT / "figures/manuscript"
    if output == source.resolve():
        raise SystemExit("Export to a separate directory; frozen assets must not be overwritten")
    destinations = [output / f"Figure{i}.{args.format}" for i in range(1, 7)]
    if any(path.exists() for path in destinations):
        raise SystemExit("Output already exists; use a new output directory to preserve earlier exports")
    output.mkdir(parents=True, exist_ok=True)
    for i, destination in enumerate(destinations, 1):
        command = [executable, str(source / f"Figure{i}.svg"),
                   f"--export-type={args.format}", f"--export-filename={destination}"]
        if args.format == "png":
            command.append(f"--export-width={args.width}")
        subprocess.run(command, check=True, capture_output=True, text=True)
        if not destination.is_file() or destination.stat().st_size == 0:
            raise RuntimeError(f"Missing rendered output: {destination}")
        print(destination)


if __name__ == "__main__":
    main()
