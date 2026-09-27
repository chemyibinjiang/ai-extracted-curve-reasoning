"""Recalculate the current Pt/C families and resistance-free VHT reconstruction."""
from pathlib import Path
import subprocess
import sys

if __name__ == "__main__":
    root = Path(__file__).resolve().parents[2]
    subprocess.run([sys.executable, str(root / "analysis/effective_bv/run.py"),
                    "families", *sys.argv[1:]], check=True)
