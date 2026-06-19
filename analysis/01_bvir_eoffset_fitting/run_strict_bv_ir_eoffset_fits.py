from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


HERE = Path(__file__).resolve().parent
OUT = HERE / "outputs"
ROWS = OUT / "figure5_descriptor_rows.csv"
MODEL_COUNTS = OUT / "figure5_fit_model_counts.csv"
CORRECTION_SUMMARY = OUT / "figure5_selected_corrections_summary.csv"
DESCRIPTOR_SUMMARY = OUT / "figure5_descriptor_summary.csv"


def summarize_by_group(df: pd.DataFrame, metrics: list[str], group_col: str = "pm_group") -> pd.DataFrame:
    records: list[dict[str, object]] = []
    for group, sub in df.groupby(group_col, dropna=False):
        for metric in metrics:
            vals = pd.to_numeric(sub[metric], errors="coerce").dropna()
            records.append(
                {
                    "group": group,
                    "metric": metric,
                    "n": int(vals.size),
                    "n_nonzero": int((vals.abs() > 1e-12).sum()),
                    "mean": float(vals.mean()) if vals.size else np.nan,
                    "median": float(vals.median()) if vals.size else np.nan,
                    "p10": float(vals.quantile(0.10)) if vals.size else np.nan,
                    "p25": float(vals.quantile(0.25)) if vals.size else np.nan,
                    "p75": float(vals.quantile(0.75)) if vals.size else np.nan,
                    "p90": float(vals.quantile(0.90)) if vals.size else np.nan,
                }
            )
    return pd.DataFrame.from_records(records)


def main() -> None:
    if not ROWS.exists():
        raise FileNotFoundError(f"Missing fitted descriptor rows: {ROWS}")

    df = pd.read_csv(ROWS, low_memory=False)

    correction_metrics = ["R_eff", "D_R_mV", "E_offset"]
    descriptor_metrics = [
        "strict_bv_tafel_mV_dec",
        "strict_bv_log10_intercept_mV",
        "bvir_offset_log_j0",
        "bvir_offset_alpha",
        "bvir_offset_r2",
        "bvir_offset_rmse_mV",
    ]

    summarize_by_group(df, correction_metrics).to_csv(CORRECTION_SUMMARY, index=False)
    summarize_by_group(df, descriptor_metrics).to_csv(DESCRIPTOR_SUMMARY, index=False)

    if MODEL_COUNTS.exists():
        model_counts = pd.read_csv(MODEL_COUNTS)
        print(model_counts.to_string(index=False))

    print(f"Wrote {CORRECTION_SUMMARY}")
    print(f"Wrote {DESCRIPTOR_SUMMARY}")


if __name__ == "__main__":
    main()

