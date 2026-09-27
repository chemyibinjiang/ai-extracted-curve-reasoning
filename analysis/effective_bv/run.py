"""Recalculate Figures 4-6 using a single effective-BV parameterization."""
import argparse
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("population", "examples", "families", "report", "all"))
    parser.add_argument("--output", type=Path, default=ROOT / "build/effective-bv-20260927")
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--starts", type=int, default=12)
    args = parser.parse_args()
    args.output = args.output.resolve()
    if ROOT / "analysis" == args.output or ROOT / "analysis" in args.output.parents:
        parser.error("Keep outputs outside analysis/")
    args.output.mkdir(parents=True, exist_ok=True)
    if args.stage in ("population", "all"):
        import population
        frame = population.run(args.output / "figure4", args.workers)
        population.downstream(frame, args.output / "figure4")
    if args.stage in ("examples", "all"):
        import examples
        examples.run(args.output / "figure5")
    if args.stage in ("families", "all"):
        import families
        families.run(args.output / "figure6", args.workers, args.starts)
    if args.stage in ("report", "all"):
        import report
        report.run(args.output)


if __name__ == "__main__":
    main()
