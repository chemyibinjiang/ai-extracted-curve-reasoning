from __future__ import annotations

import json
import math
import os
import time
from multiprocessing import Pool
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.optimize import least_squares

import bv_ir_fitting_analysis as base
import consistent_branch_eta_current_sign_bvir_offset_rerun_20260608 as fit_pipe
import plot_publication_overall_bv_ir_offset_figure_20260609 as pub


OUT_DIR = Path(__file__).resolve().parent
def resolve_database_root(start: Path) -> Path:
    for root in (start.parent.parent, *start.parents):
        for candidate in (root / "LSV_publication_database", root / "data" / "LSV_publication_database"):
            if (candidate / "02_canonical_tables").exists():
                return candidate
    return start.parent.parent / "LSV_publication_database"


DB_ROOT = resolve_database_root(OUT_DIR)
TABLE_DIR = DB_ROOT / "02_canonical_tables"

RUN_STEM = os.getenv("STRICT_NEFF2_RUN_STEM", "strict_neff2_bvir_offset_whole_dataset_20260611")
CURVE_OUT = OUT_DIR / f"{RUN_STEM}_curve_fits.csv"
PASS_MATRIX_OUT = OUT_DIR / f"{RUN_STEM}_pass_matrix.csv"
PASS_MATRIX_DEDUP_OUT = OUT_DIR / f"{RUN_STEM}_pass_matrix_dedup.csv"
PASS_SUMMARY_OUT = OUT_DIR / f"{RUN_STEM}_pass_summary.csv"
PASS_SUMMARY_DEDUP_OUT = OUT_DIR / f"{RUN_STEM}_pass_summary_dedup.csv"
MANIFEST_OUT = OUT_DIR / f"{RUN_STEM}_manifest.json"
ASINH_FIT_PATH = OUT_DIR / "consistent_branch_eta_current_sign_bvir_offset_20260608_curve_fits.csv"

R2_BAR = 0.99
MIN_FIT_POINTS = 5
WORKERS = int(os.getenv("STRICT_NEFF2_WORKERS", "8"))

R_GAS = 8.31446261815324
FARADAY = 96485.33212
TEMPERATURE_K = 298.15
N_EFF_FIXED = 2.0
A_STAR_MV = R_GAS * TEMPERATURE_K / (N_EFF_FIXED * FARADAY) * 1000.0

ALPHA_LOW = float(os.getenv("STRICT_NEFF2_ALPHA_LOW", "0.01"))
ALPHA_HIGH = float(os.getenv("STRICT_NEFF2_ALPHA_HIGH", "0.99"))
R_FREE_BOUND = 100.0
E_FREE_BOUND_MV = 200.0

VARIANTS = {
    "bv": {"include_ir": False, "include_offset": False, "label": "BV"},
    "bvir": {"include_ir": True, "include_offset": False, "label": "BV+iR"},
    "bv_offset": {"include_ir": False, "include_offset": True, "label": "BV+offset"},
    "bvir_offset": {"include_ir": True, "include_offset": True, "label": "BV+iR+offset"},
}


def norm_bool_yes(value: object) -> bool:
    return str(value).strip().lower() == "yes"


def strict_bv_x(u: np.ndarray | float, alpha: float) -> np.ndarray:
    """Solve j/j0 = exp(alpha*x) - exp(-(1-alpha)*x), with x = eta_BV/a_star."""
    arr = np.asarray(u, dtype=float)
    arr = np.clip(arr, 0.0, np.inf)
    alpha = float(np.clip(alpha, 1e-6, 1.0 - 1e-6))

    x = np.maximum(arr / np.maximum(1.0 + arr, 1.0), np.log1p(arr) / alpha)
    x = np.where(np.isfinite(x), x, np.log1p(arr) / alpha)
    for _ in range(30):
        xa = np.clip(x, 0.0, 140.0)
        ep = np.exp(np.clip(alpha * xa, -700.0, 700.0))
        em = np.exp(np.clip(-(1.0 - alpha) * xa, -700.0, 700.0))
        f = ep - em - arr
        df = alpha * ep + (1.0 - alpha) * em
        step = f / np.maximum(df, 1e-300)
        x_new = np.maximum(0.0, xa - step)
        if np.nanmax(np.abs(x_new - x)) < 1e-11:
            x = x_new
            break
        x = x_new
    return x


def r2_from_sse(y: np.ndarray, sse: float) -> float:
    tss = float(np.sum((y - np.mean(y)) ** 2))
    return float(1.0 - sse / tss) if tss > 0 else np.nan


def predict_variant(
    j: np.ndarray,
    params: np.ndarray,
    *,
    include_ir: bool,
    include_offset: bool,
) -> np.ndarray:
    pos = 0
    log_j0 = float(params[pos])
    pos += 1
    alpha = float(params[pos])
    pos += 1
    r_value = 0.0
    e_offset = 0.0
    if include_ir:
        r_value = float(params[pos])
        pos += 1
    if include_offset:
        e_offset = float(params[pos])
    x = strict_bv_x(j / np.exp(log_j0), alpha)
    return e_offset + A_STAR_MV * x + r_value * j


def start_vectors(
    j: np.ndarray,
    y: np.ndarray,
    include_ir: bool,
    include_offset: bool,
    current: dict[str, float],
) -> list[np.ndarray]:
    j10 = max(float(np.nanpercentile(j, 10)), 1e-9)
    j50 = max(float(np.nanpercentile(j, 50)), 1e-9)
    j90 = max(float(np.nanpercentile(j, 90)), 1e-9)
    y_min = float(np.nanmin(y))
    y_max = float(np.nanmax(y))
    y_span = max(y_max - y_min, 1e-9)

    lower = [math.log(1e-12), ALPHA_LOW]
    upper = [math.log(1e8), ALPHA_HIGH]
    if include_ir:
        lower.append(0.0)
        upper.append(R_FREE_BOUND)
    if include_offset:
        lower.append(-E_FREE_BOUND_MV)
        upper.append(E_FREE_BOUND_MV)
    lower_arr = np.asarray(lower, dtype=float)
    upper_arr = np.asarray(upper, dtype=float)

    r_slope = float(np.clip(y_span / max(j90 - j10, 1e-9), 0.0, R_FREE_BOUND))
    current_j0 = max(float(current.get("j0_mA", j10)), 1e-12)
    current_log_j0 = math.log(current_j0)
    current_a = float(current.get("a_mV", 45.0))
    current_alpha = float(np.clip(A_STAR_MV / max(current_a, 1e-9), ALPHA_LOW, ALPHA_HIGH))
    current_r = float(np.clip(current.get("r_mV_per_mA", 0.0), 0.0, R_FREE_BOUND))
    current_e = float(np.clip(current.get("e_offset_mV", 0.0), -E_FREE_BOUND_MV, E_FREE_BOUND_MV))

    base_starts = [
        (current_log_j0, current_alpha, current_r, current_e),
        (current_log_j0 - math.log(2.0), current_alpha, current_r, current_e),
        (current_log_j0 + math.log(2.0), current_alpha, current_r, current_e),
        (current_log_j0, 0.50, current_r, current_e),
        (math.log(max(j10 / 5.0, 1e-12)), 0.50, min(r_slope, R_FREE_BOUND), 0.0),
        (math.log(max(j50, 1e-12)), 0.35, 0.05, 0.0),
        (math.log(max(j50, 1e-12)), 0.70, 0.2, 0.0),
        (math.log(1e-3), 0.50, 0.0, 0.0),
        (math.log(1.0), 0.90, 0.5, 0.0),
        (math.log(max(j90, 1e-12)), ALPHA_HIGH, min(r_slope, R_FREE_BOUND), y_min),
    ]

    starts: list[np.ndarray] = []
    seen: set[tuple[float, ...]] = set()
    for log_j0, alpha, r_value, e_offset in base_starts:
        start = [log_j0, alpha]
        if include_ir:
            start.append(r_value)
        if include_offset:
            start.append(e_offset)
        arr = np.clip(np.asarray(start, dtype=float), lower_arr + 1e-9, upper_arr - 1e-9)
        key = tuple(np.round(arr, 8))
        if key not in seen:
            starts.append(arr)
            seen.add(key)
    return starts


def fit_variant(
    j: np.ndarray,
    y: np.ndarray,
    *,
    include_ir: bool,
    include_offset: bool,
    current: dict[str, float],
) -> dict[str, Any]:
    lower = [math.log(1e-12), ALPHA_LOW]
    upper = [math.log(1e8), ALPHA_HIGH]
    if include_ir:
        lower.append(0.0)
        upper.append(R_FREE_BOUND)
    if include_offset:
        lower.append(-E_FREE_BOUND_MV)
        upper.append(E_FREE_BOUND_MV)
    lower_arr = np.asarray(lower, dtype=float)
    upper_arr = np.asarray(upper, dtype=float)

    def residual(params: np.ndarray) -> np.ndarray:
        return y - predict_variant(j, params, include_ir=include_ir, include_offset=include_offset)

    best: dict[str, Any] | None = None
    for start in start_vectors(j, y, include_ir, include_offset, current):
        try:
            result = least_squares(
                residual,
                start,
                bounds=(lower_arr, upper_arr),
                x_scale="jac",
                max_nfev=12000,
                ftol=1e-10,
                xtol=1e-10,
                gtol=1e-10,
            )
        except Exception as exc:  # noqa: BLE001
            last_error = type(exc).__name__
            continue
        res = residual(result.x)
        sse = float(np.dot(res, res))
        if best is None or sse < best["sse_mV2"]:
            pos = 0
            log_j0 = float(result.x[pos])
            pos += 1
            alpha = float(result.x[pos])
            pos += 1
            r_value = 0.0
            e_offset = 0.0
            if include_ir:
                r_value = float(result.x[pos])
                pos += 1
            if include_offset:
                e_offset = float(result.x[pos])
            best = {
                "ok": True,
                "error": "" if result.success else str(result.message),
                "log_j0": log_j0,
                "j0_mA": float(np.exp(log_j0)),
                "alpha": alpha,
                "r_mV_per_mA": r_value,
                "e_offset_mV": e_offset,
                "sse_mV2": sse,
                "rmse_mV": float(np.sqrt(sse / len(j))),
                "r2": r2_from_sse(y, sse),
                "nfev": int(result.nfev),
                "b_tafel_mV_dec": float(2.303 * A_STAR_MV / alpha),
                "at_alpha_low": bool(alpha <= ALPHA_LOW + 1e-4),
                "at_alpha_high": bool(alpha >= ALPHA_HIGH - 1e-4),
                "at_r_upper_bound": bool(include_ir and r_value >= R_FREE_BOUND - 1e-4),
                "at_e_upper_bound": bool(include_offset and e_offset >= E_FREE_BOUND_MV - 1e-4),
                "at_e_lower_bound": bool(include_offset and e_offset <= -E_FREE_BOUND_MV + 1e-4),
            }
    if best is None:
        return {"ok": False, "error": locals().get("last_error", "least_squares_failed")}
    return best


def fit_one(task: dict[str, Any]) -> dict[str, Any]:
    row = dict(task["row"])
    if not row["canonical_fit_eligible"]:
        reason = "not_linear_current_density"
        if row["current_density_basis"] and not row["reference_axis_ready"]:
            reason = "non_rhe_or_non_overpotential_axis"
        elif row["current_density_basis"] and row["reference_axis_ready"] and not row["fit_range_ok"]:
            reason = "insufficient_fitting_range"
        row.update({"fit_error": reason})
        return row

    j = np.asarray(task["j"], dtype=float)
    y = np.asarray(task["y"], dtype=float)
    row.update({"fit_error": "", "tss_mV2": float(np.sum((y - np.mean(y)) ** 2))})

    for prefix, spec in VARIANTS.items():
        current = dict(task.get("current", {}).get(prefix, {}))
        fit = fit_variant(
            j,
            y,
            include_ir=spec["include_ir"],
            include_offset=spec["include_offset"],
            current=current,
        )
        row[f"{prefix}_fit_ok"] = bool(fit.get("ok"))
        row[f"{prefix}_fit_error"] = "" if fit.get("ok") else str(fit.get("error"))
        for key in [
            "j0_mA",
            "log_j0",
            "alpha",
            "b_tafel_mV_dec",
            "r_mV_per_mA",
            "e_offset_mV",
            "sse_mV2",
            "rmse_mV",
            "r2",
            "nfev",
            "at_alpha_low",
            "at_alpha_high",
            "at_r_upper_bound",
            "at_e_upper_bound",
            "at_e_lower_bound",
        ]:
            row[f"{prefix}_{key}"] = fit.get(key, np.nan)
    return row


def summarize_pass(pass_matrix: pd.DataFrame, fit_loaded_n: int, *, label: str) -> pd.DataFrame:
    rows: list[dict[str, Any]] = [
        {"scope": label, "metric": "fit_loaded_primary_HER_curves", "count": fit_loaded_n, "denominator": fit_loaded_n, "percent": 100.0},
        {"scope": label, "metric": "canonical_fit_eligible_jmax_ge_20", "count": len(pass_matrix), "denominator": fit_loaded_n, "percent": 100.0 * len(pass_matrix) / fit_loaded_n if fit_loaded_n else np.nan},
    ]
    model_map = {
        "BV": "BV",
        "BV+iR": "BV+iR",
        "BV+offset": "BV+offset",
        "BV+iR+offset": "BV+iR+offset",
    }
    for metric, col in model_map.items():
        passed = pass_matrix[col].astype(bool)
        rows.append({"scope": label, "metric": f"{metric}_R2_ge_0p99_jmax20", "count": int(passed.sum()), "denominator": len(pass_matrix), "percent": float(passed.mean() * 100.0) if len(pass_matrix) else np.nan})
    bv_pass = pass_matrix["BV"].astype(bool)
    full_pass = pass_matrix["BV+iR+offset"].astype(bool)
    rows.append({"scope": label, "metric": "BV_failed_full_BV+iR+offset_rescued_jmax20", "count": int((~bv_pass & full_pass).sum()), "denominator": len(pass_matrix), "percent": float((~bv_pass & full_pass).mean() * 100.0) if len(pass_matrix) else np.nan})
    rows.append({"scope": label, "metric": "still_failed_after_full_BV+iR+offset_jmax20", "count": int((~full_pass).sum()), "denominator": len(pass_matrix), "percent": float((~full_pass).mean() * 100.0) if len(pass_matrix) else np.nan})
    return pd.DataFrame(rows)


def build_pass_matrix(fits: pd.DataFrame) -> pd.DataFrame:
    j20 = fits[
        fits["canonical_fit_eligible"].astype(bool)
        & (pd.to_numeric(fits["j_max_mA"], errors="coerce") >= 20.0)
    ].copy()
    cols = [
        "curve_uid",
        "j_max_mA",
        "fit_point_count",
        "bv_r2",
        "bvir_r2",
        "bv_offset_r2",
        "bvir_offset_r2",
        "bv_alpha",
        "bvir_alpha",
        "bv_offset_alpha",
        "bvir_offset_alpha",
        "bvir_r_mV_per_mA",
        "bvir_offset_r_mV_per_mA",
        "bv_offset_e_offset_mV",
        "bvir_offset_e_offset_mV",
    ]
    out = j20[[col for col in cols if col in j20.columns]].copy()
    out["BV"] = pd.to_numeric(out["bv_r2"], errors="coerce") >= R2_BAR
    out["BV+iR"] = pd.to_numeric(out["bvir_r2"], errors="coerce") >= R2_BAR
    out["BV+offset"] = pd.to_numeric(out["bv_offset_r2"], errors="coerce") >= R2_BAR
    out["BV+iR+offset"] = pd.to_numeric(out["bvir_offset_r2"], errors="coerce") >= R2_BAR
    return out


def main() -> None:
    start = time.perf_counter()
    curves = pd.read_csv(TABLE_DIR / "curves.csv", low_memory=False)
    main_curves = curves[
        curves["publication_included_curve"].map(norm_bool_yes)
        & curves["publication_analysis_bucket"].astype(str).eq("primary_main_HER")
        & curves["normalization_status_current"].astype(str).str.lower().eq("completed")
    ].copy()
    records = base.read_normalized_records()
    old_fits = pd.read_csv(ASINH_FIT_PATH, low_memory=False).set_index("curve_uid", drop=False)

    def finite_cell(row: pd.Series, column: str) -> float | None:
        value = pd.to_numeric(row.get(column, np.nan), errors="coerce")
        try:
            out = float(value)
        except Exception:  # noqa: BLE001
            return None
        return out if np.isfinite(out) else None

    def current_guess(uid: str, prefix: str) -> dict[str, float]:
        if uid not in old_fits.index:
            return {}
        row = old_fits.loc[uid]
        old_prefix = {
            "bv": "bv_profile",
            "bvir": "bvir",
            "bv_offset": "bv_offset",
            "bvir_offset": "bvir_offset",
        }[prefix]
        guess: dict[str, float] = {}
        for key, column in [
            ("j0_mA", f"{old_prefix}_j0_mA"),
            ("a_mV", f"{old_prefix}_a_mV"),
            ("r_mV_per_mA", f"{old_prefix}_r_mV_per_mA"),
            ("e_offset_mV", f"{old_prefix}_e_offset_mV"),
        ]:
            value = finite_cell(row, column)
            if value is not None:
                guess[key] = value
        return guess

    tasks = []
    for _, curve in main_curves.iterrows():
        task = fit_pipe.prepare_curve(curve, records.get(curve["curve_uid"], {}))
        uid = str(curve["curve_uid"])
        task["current"] = {prefix: current_guess(uid, prefix) for prefix in VARIANTS}
        tasks.append(task)

    print(f"Run stem: {RUN_STEM}", flush=True)
    print(f"Strict BV: fixed n_eff={N_EFF_FIXED}, a*=RT/(nF)={A_STAR_MV:.6f} mV, alpha fitted", flush=True)
    print(f"Fit-loaded curves: {len(tasks)}", flush=True)
    print(f"Workers: {WORKERS}", flush=True)

    with Pool(processes=WORKERS) as pool:
        rows = list(pool.imap_unordered(fit_one, tasks, chunksize=4))

    fits = pd.DataFrame(rows).sort_values("curve_uid").reset_index(drop=True)
    fits.to_csv(CURVE_OUT, index=False)

    pass_matrix = build_pass_matrix(fits)
    pass_matrix.to_csv(PASS_MATRIX_OUT, index=False)

    duplicate_cases, retained_cases, dedup_records = pub.load_doi_dedup_cases()
    pass_dedup = pub.apply_case_dedup(pass_matrix, duplicate_cases, retained_cases, id_col="curve_uid")
    pass_dedup.to_csv(PASS_MATRIX_DEDUP_OUT, index=False)

    summary = summarize_pass(pass_matrix, len(tasks), label="all")
    summary_dedup = summarize_pass(pass_dedup, len(tasks), label="doi_dedup")
    summary.to_csv(PASS_SUMMARY_OUT, index=False)
    summary_dedup.to_csv(PASS_SUMMARY_DEDUP_OUT, index=False)

    manifest = {
        "run_stem": RUN_STEM,
        "dataset_root": str(DB_ROOT),
        "model": "strict BV inverse with fixed n_eff=2 and fitted alpha",
        "equation": "eta_branch = E_offset + (RT/(2F))*x + R*j; j/j0 = exp(alpha*x) - exp(-(1-alpha)*x)",
        "a_star_mV": A_STAR_MV,
        "alpha_bounds": [ALPHA_LOW, ALPHA_HIGH],
        "R_bound_ohm_cm2": R_FREE_BOUND,
        "E_offset_bound_mV": E_FREE_BOUND_MV,
        "workers": WORKERS,
        "fit_loaded_primary_HER_curves": int(len(tasks)),
        "outputs": {
            "curve_fits": str(CURVE_OUT),
            "pass_matrix": str(PASS_MATRIX_OUT),
            "pass_matrix_dedup": str(PASS_MATRIX_DEDUP_OUT),
            "pass_summary": str(PASS_SUMMARY_OUT),
            "pass_summary_dedup": str(PASS_SUMMARY_DEDUP_OUT),
        },
        "elapsed_seconds": float(time.perf_counter() - start),
    }
    MANIFEST_OUT.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print("All pass summary", flush=True)
    print(summary.to_string(index=False), flush=True)
    print("DOI-dedup pass summary", flush=True)
    print(summary_dedup.to_string(index=False), flush=True)
    print(f"Wrote {CURVE_OUT}", flush=True)
    print(f"Wrote {PASS_MATRIX_OUT}", flush=True)
    print(f"Wrote {PASS_MATRIX_DEDUP_OUT}", flush=True)


if __name__ == "__main__":
    main()
