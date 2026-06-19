from __future__ import annotations

from pathlib import Path

import pandas as pd


HERE = Path(__file__).resolve().parent
OUT = HERE / "outputs"
SUMMARY = OUT / "ir_only_control_summary.csv"


def main() -> None:
    if not SUMMARY.exists():
        raise FileNotFoundError(f"Missing iR-only control summary: {SUMMARY}")
    summary = pd.read_csv(SUMMARY)
    print(summary.to_string(index=False))

    key = summary.set_index("metric")
    if "iR_only_origin_eta_eq_R_absj_R2_ge_0p99_jmax20" in key.index:
        pct = float(key.loc["iR_only_origin_eta_eq_R_absj_R2_ge_0p99_jmax20", "percent"])
        print(f"\niR-only origin-constrained pass rate: {pct:.2f}%")
    if "iR_plus_Eoffset_linear_eta_eq_Eoffset_plus_R_absj_R2_ge_0p99_jmax20" in key.index:
        pct = float(key.loc["iR_plus_Eoffset_linear_eta_eq_Eoffset_plus_R_absj_R2_ge_0p99_jmax20", "percent"])
        print(f"iR+Eoffset linear pass rate: {pct:.2f}%")


if __name__ == "__main__":
    main()

