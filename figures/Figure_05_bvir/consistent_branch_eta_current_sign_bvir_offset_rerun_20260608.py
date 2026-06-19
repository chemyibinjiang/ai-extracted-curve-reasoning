from __future__ import annotations

import json
import math
import time
from multiprocessing import Pool, cpu_count
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.optimize import least_squares

import bv_ir_fitting_analysis as base
from profile_grid_bvir_offset_2516_20260607 import profile_cell


OUT_DIR = Path(__file__).resolve().parent
DB_ROOT = OUT_DIR.parent.parent / "LSV_publication_database"
TABLE_DIR = DB_ROOT / "02_canonical_tables"

R2_BAR = 0.99
MIN_FIT_POINTS = 5
E_FREE_BOUND_MV = 200.0
R_FREE_BOUND = 100.0
R2_EPS = 1e-12

E_SPARSE_BOUND_MV = 50.0
R_SPARSE_BOUND = 10.0
D_SPARSE_SCAN_MAX_MV = 1000.0

RUN_STEM = "consistent_branch_eta_current_sign_bvir_offset_20260608"
CURVE_OUT = OUT_DIR / f"{RUN_STEM}_curve_fits.csv"
PASS_MATRIX_OUT = OUT_DIR / f"{RUN_STEM}_pass_matrix.csv"
PASS_SUMMARY_OUT = OUT_DIR / f"{RUN_STEM}_pass_summary.csv"
SPARSE_CASES_OUT = OUT_DIR / f"{RUN_STEM}_rescued_E50_R10_sparse_cases.csv"
SPARSE_SUMMARY_OUT = OUT_DIR / f"{RUN_STEM}_rescued_E50_R10_sparse_summary.csv"
MANIFEST_OUT = OUT_DIR / f"{RUN_STEM}_manifest.json"


def norm_bool_yes(value: object) -> bool:
    return str(value).strip().lower() == "yes"


def canonical_clean_series(j_abs: np.ndarray, y_mv: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    finite = np.isfinite(j_abs) & np.isfinite(y_mv) & (j_abs > 0)
    j = np.asarray(j_abs[finite], dtype=float)
    y = np.asarray(y_mv[finite], dtype=float)
    if j.size == 0:
        return j, y

    mask = (j >= 0.2) & (j <= 500.0) & (np.abs(y) <= 2000.0)
    j = j[mask]
    y = y[mask]
    if j.size == 0:
        return j, y

    order = np.argsort(j)
    j = j[order]
    y = y[order]
    rounded = np.round(j, 6)
    unique_j: list[float] = []
    unique_y: list[float] = []
    for value in np.unique(rounded):
        dup = rounded == value
        unique_j.append(float(np.mean(j[dup])))
        unique_y.append(float(np.median(y[dup])))
    return np.asarray(unique_j, dtype=float), np.asarray(unique_y, dtype=float)


def canonical_clean_eta_series(j_abs: np.ndarray, eta_mv: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    return base.clean_series(j_abs, eta_mv)


def select_current_sign_branch(current_ma: np.ndarray, eta_mv: np.ndarray) -> tuple[np.ndarray, float, str]:
    base_mask = np.isfinite(current_ma) & np.isfinite(eta_mv) & (np.abs(current_ma) > 0)
    base_mask &= (np.abs(current_ma) >= 0.2) & (np.abs(current_ma) <= 500.0) & (eta_mv >= 0) & (eta_mv <= 2000.0)
    if not base_mask.any():
        return base_mask, 0.0, "no_valid_points"

    signs = np.sign(current_ma[base_mask])
    nonzero_signs = np.unique(signs[signs != 0])
    if nonzero_signs.size <= 1:
        sign = float(nonzero_signs[0]) if nonzero_signs.size == 1 else 0.0
        return base_mask, sign, "single_current_sign"

    eta_valid = eta_mv[base_mask]
    current_valid = current_ma[base_mask]
    threshold = float(np.nanquantile(eta_valid, 0.50))
    high_mask = eta_valid >= threshold
    if high_mask.sum() < 3:
        threshold = float(np.nanquantile(eta_valid, 0.25))
        high_mask = eta_valid >= threshold

    scores: dict[float, tuple[int, float, float]] = {}
    for sign in [-1.0, 1.0]:
        sign_mask = high_mask & (np.sign(current_valid) == sign)
        scores[sign] = (
            int(sign_mask.sum()),
            float(np.nanmax(np.abs(current_valid[sign_mask]))) if sign_mask.any() else -np.inf,
            float(np.nanmedian(eta_valid[sign_mask])) if sign_mask.any() else -np.inf,
        )
    selected_sign = max(scores, key=lambda sign: scores[sign])
    if scores[selected_sign][0] == 0:
        # Fallback for pathological traces: keep the sign with the largest overall current magnitude.
        selected_sign = max(
            [-1.0, 1.0],
            key=lambda sign: float(np.nanmax(np.abs(current_valid[np.sign(current_valid) == sign])))
            if np.any(np.sign(current_valid) == sign)
            else -np.inf,
        )
        rule = "fallback_largest_abs_current_sign"
    else:
        rule = "dominant_high_eta_current_sign"
    return base_mask & (np.sign(current_ma) == selected_sign), float(selected_sign), rule


def infer_model_direction(j: np.ndarray, y: np.ndarray) -> tuple[float, str]:
    """Return +1 for positive-going branches and -1 for cathodic negative-going branches."""
    if j.size < 2:
        return 1.0, "insufficient_points_default_positive"
    try:
        slope = float(np.polyfit(j, y, 1)[0])
    except Exception:  # noqa: BLE001
        slope = np.nan
    y_span = float(np.nanmax(y) - np.nanmin(y)) if y.size else np.nan
    j_span = float(np.nanmax(j) - np.nanmin(j)) if j.size else np.nan
    slope_floor = 1e-6 * y_span / max(j_span, 1e-12) if np.isfinite(y_span) and np.isfinite(j_span) else 0.0
    if np.isfinite(slope) and abs(slope) > slope_floor:
        return (-1.0 if slope < 0 else 1.0), ("negative_slope_branch" if slope < 0 else "positive_slope_branch")
    median_y = float(np.nanmedian(y)) if y.size else 0.0
    return (-1.0 if median_y < 0 else 1.0), ("negative_median_branch" if median_y < 0 else "positive_median_branch")


def transform_to_branch_eta(reference_basis: str, signed_potential_mv: np.ndarray) -> tuple[np.ndarray, str]:
    if reference_basis == "rhe" and signed_potential_mv.size and np.nanmin(signed_potential_mv) < 0:
        return -signed_potential_mv, "minus_E_RHE_negative_branch"
    if reference_basis == "rhe":
        return signed_potential_mv, "positive_E_RHE_branch"
    return np.abs(signed_potential_mv), "abs_overpotential_axis"


def signed_potential_to_mv(values: np.ndarray, units: str, label: str) -> tuple[np.ndarray, str]:
    text = f"{units} {label}".lower()
    finite_abs = np.abs(values[np.isfinite(values)])
    median_abs = float(np.nanmedian(finite_abs)) if finite_abs.size else np.nan
    if "mv" in text or (np.isfinite(median_abs) and median_abs > 5.0):
        return values.astype(float), "mV"
    return values.astype(float) * 1000.0, "V"


def prepare_curve(curve: pd.Series, record: dict[str, object]) -> dict[str, Any]:
    points = record.get("native_points") or []
    x = np.asarray([point.get("x", np.nan) for point in points], dtype=float)
    y = np.asarray([point.get("y", np.nan) for point in points], dtype=float)
    axes = base.resolve_axes(curve, x, y)
    linear_axes = base.is_linear_axis(
        curve.get("x_axis_type_current"),
        curve.get("x_axis_units_current"),
        curve.get("x_axis_label_current"),
    ) and base.is_linear_axis(
        curve.get("y_axis_type_current"),
        curve.get("y_axis_units_current"),
        curve.get("y_axis_label_current"),
    )
    reference_basis = base.potential_reference_basis(
        str(axes["potential_units"]),
        str(axes["potential_label"]),
        curve.get("enrich_reference_scale"),
    )
    current_density_basis = linear_axes and axes["orientation"] != "unknown" and base.is_current_density_like(
        str(axes["current_units"]),
        str(axes["current_label"]),
    )
    signed_potential_mv, potential_unit_mode = signed_potential_to_mv(
        np.asarray(axes["potential_values"], dtype=float),
        str(axes["potential_units"]),
        str(axes["potential_label"]),
    )
    current_ma, current_unit_mode = base.current_to_ma(
        np.asarray(axes["current_values"], dtype=float),
        str(axes["current_units"]),
        str(axes["current_label"]),
    )
    eta_mv, eta_rule = transform_to_branch_eta(reference_basis, signed_potential_mv)
    branch_current_mask, branch_current_sign, branch_current_rule = select_current_sign_branch(current_ma, eta_mv)
    j, y_fit = canonical_clean_eta_series(np.abs(current_ma[branch_current_mask]), eta_mv[branch_current_mask])
    model_direction = 1.0
    model_direction_rule = eta_rule
    valid_reference = reference_basis in {"rhe", "overpotential"}
    fit_range_ok = bool(
        j.size >= MIN_FIT_POINTS
        and np.nanmax(j) - np.nanmin(j) >= 5.0
        and np.nanmax(y_fit) - np.nanmin(y_fit) >= 5.0
    ) if j.size else False

    row: dict[str, Any] = {
        "curve_uid": curve["curve_uid"],
        "panel_uid": curve.get("panel_uid"),
        "publication_batch": curve.get("publication_batch"),
        "source_collection": curve.get("source_collection"),
        "case_id": curve.get("case_id"),
        "case_rel_path": curve.get("case_rel_path"),
        "paper_title": curve.get("paper_title"),
        "figure_id": curve.get("figure_id"),
        "panel_id": curve.get("panel_id"),
        "curve_label": curve.get("publication_curve_label") or curve.get("curve_label_current_response"),
        "condition_label": curve.get("publication_condition_label") or curve.get("condition_label_current_response"),
        "catalyst_role": curve.get("enrich_catalyst_role"),
        "material_class": curve.get("enrich_material_class"),
        "contains_pgm": curve.get("enrich_contains_pgm"),
        "pgm_class": base.parse_bool(curve.get("enrich_contains_pgm")),
        "electrolyte_regime": curve.get("enrich_electrolyte_regime"),
        "regime_class": base.classify_regime(curve.get("enrich_electrolyte_regime")),
        "electrolyte_identity": curve.get("enrich_electrolyte_identity"),
        "support_material": curve.get("enrich_support_material"),
        "substrate_material": curve.get("enrich_substrate_material"),
        "ir_compensation_status": curve.get("enrich_ir_compensation_status"),
        "scan_rate_text": curve.get("enrich_scan_rate_text"),
        "measurement_configuration": curve.get("enrich_measurement_configuration"),
        "x_axis_units": curve.get("x_axis_units_current"),
        "x_axis_label": curve.get("x_axis_label_current"),
        "y_axis_units": curve.get("y_axis_units_current"),
        "y_axis_label": curve.get("y_axis_label_current"),
        "x_axis_type": curve.get("x_axis_type_current"),
        "y_axis_type": curve.get("y_axis_type_current"),
        "axis_orientation": axes["orientation"],
        "reference_basis": reference_basis,
        "current_density_basis": bool(current_density_basis),
        "linear_axes": bool(linear_axes),
        "potential_unit_mode": potential_unit_mode,
        "current_unit_mode": current_unit_mode,
        "native_point_count": int(len(points)),
        "fit_point_count": int(j.size),
        "j_min_mA": float(np.nanmin(j)) if j.size else np.nan,
        "j_max_mA": float(np.nanmax(j)) if j.size else np.nan,
        "y_min_mV": float(np.nanmin(y_fit)) if y_fit.size else np.nan,
        "y_max_mV": float(np.nanmax(y_fit)) if y_fit.size else np.nan,
        "signed_potential_min_mV": float(np.nanmin(signed_potential_mv)) if signed_potential_mv.size else np.nan,
        "signed_potential_max_mV": float(np.nanmax(signed_potential_mv)) if signed_potential_mv.size else np.nan,
        "crosses_zero_potential": bool(
            signed_potential_mv.size
            and np.nanmin(signed_potential_mv) < 0
            and np.nanmax(signed_potential_mv) > 0
        ),
        "eta_rule": eta_rule,
        "raw_branch_candidate_point_count": int(branch_current_mask.size),
        "raw_branch_current_positive_count": int(((current_ma > 0) & np.isfinite(current_ma)).sum()),
        "raw_branch_current_negative_count": int(((current_ma < 0) & np.isfinite(current_ma)).sum()),
        "selected_current_sign": branch_current_sign,
        "selected_current_sign_rule": branch_current_rule,
        "selected_current_sign_raw_point_count": int(branch_current_mask.sum()),
        "model_direction": float(model_direction),
        "model_direction_rule": model_direction_rule,
        "reference_axis_ready": bool(valid_reference),
        "fit_range_ok": bool(fit_range_ok),
        "canonical_fit_eligible": bool(current_density_basis and valid_reference and fit_range_ok),
    }
    return {"row": row, "j": j, "y": y_fit}


def model_prediction(
    j: np.ndarray,
    params: np.ndarray,
    *,
    model_direction: float,
    include_ir: bool,
    include_offset: bool,
) -> np.ndarray:
    pos = 0
    log_j0 = float(params[pos])
    pos += 1
    a_mV = float(params[pos])
    pos += 1
    r = 0.0
    e_offset = 0.0
    if include_ir:
        r = float(params[pos])
        pos += 1
    if include_offset:
        e_offset = float(params[pos])

    eta_like = a_mV * np.arcsinh(j / np.exp(log_j0)) + r * j
    return e_offset + model_direction * eta_like


def r2_from_sse(y: np.ndarray, sse: float) -> float:
    tss = float(np.sum((y - np.mean(y)) ** 2))
    return float(1.0 - sse / tss) if tss > 0 else np.nan


def fit_continuous_model(
    j: np.ndarray,
    y: np.ndarray,
    *,
    model_direction: float,
    include_ir: bool,
    include_offset: bool,
    bv_profile: dict[str, float],
) -> dict[str, Any]:
    if j.size < MIN_FIT_POINTS:
        return {"ok": False, "error": "insufficient_points"}

    low_j = max(float(np.nanpercentile(j, 10)) / 5.0, 1e-4)
    log_base = float(np.clip(math.log(low_j), math.log(1e-8), math.log(1e4)))
    a_base = float(np.clip(bv_profile.get("a_mV", 45.0), 1.0, 1000.0))
    log_profile = float(np.clip(bv_profile.get("log_j0", log_base), math.log(1e-8), math.log(1e4)))
    if model_direction < 0:
        e_guess = float(np.clip(np.nanmax(y), -E_FREE_BOUND_MV, E_FREE_BOUND_MV))
    else:
        e_guess = float(np.clip(np.nanmin(y), -E_FREE_BOUND_MV, E_FREE_BOUND_MV))

    lower = [math.log(1e-8), 1.0]
    upper = [math.log(1e4), 1000.0]
    starts: list[list[float]] = []
    log_starts = [log_profile, log_base, math.log(1e-2), math.log(1.0)]
    a_starts = [a_base, 45.0, 100.0]
    r_starts = [0.0, 0.05, 0.2, 1.0, 5.0] if include_ir else [0.0]
    e_starts = [0.0, e_guess, -25.0, 25.0] if include_offset else [0.0]
    if include_ir:
        lower.append(0.0)
        upper.append(R_FREE_BOUND)
    if include_offset:
        lower.append(-E_FREE_BOUND_MV)
        upper.append(E_FREE_BOUND_MV)

    for log_j0 in log_starts:
        for a in a_starts[:2]:
            for r in r_starts:
                for e in e_starts:
                    start = [log_j0, a]
                    if include_ir:
                        start.append(r)
                    if include_offset:
                        start.append(e)
                    starts.append(start)
    # De-duplicate starts after clipping.
    clipped_starts = []
    seen = set()
    lower_arr = np.asarray(lower, dtype=float)
    upper_arr = np.asarray(upper, dtype=float)
    for start in starts:
        arr = np.clip(np.asarray(start, dtype=float), lower_arr + 1e-9, upper_arr - 1e-9)
        key = tuple(np.round(arr, 8))
        if key not in seen:
            clipped_starts.append(arr)
            seen.add(key)

    def residual(params: np.ndarray) -> np.ndarray:
        return y - model_prediction(
            j,
            params,
            model_direction=model_direction,
            include_ir=include_ir,
            include_offset=include_offset,
        )

    best: dict[str, Any] | None = None
    for start in clipped_starts:
        try:
            result = least_squares(
                residual,
                start,
                bounds=(lower_arr, upper_arr),
                x_scale="jac",
                max_nfev=20000,
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
            best = {
                "ok": True,
                "error": "" if result.success else str(result.message),
                "log_j0": float(result.x[0]),
                "j0_mA": float(np.exp(result.x[0])),
                "a_mV": float(result.x[1]),
                "r_mV_per_mA": float(result.x[2]) if include_ir else 0.0,
                "e_offset_mV": float(result.x[-1]) if include_offset else 0.0,
                "sse_mV2": sse,
                "rmse_mV": float(np.sqrt(sse / len(j))),
                "r2": r2_from_sse(y, sse),
                "nfev": int(result.nfev),
                "at_r_upper_bound": bool(include_ir and result.x[2] >= R_FREE_BOUND - 1e-4),
                "at_e_upper_bound": bool(include_offset and result.x[-1] >= E_FREE_BOUND_MV - 1e-4),
                "at_e_lower_bound": bool(include_offset and result.x[-1] <= -E_FREE_BOUND_MV + 1e-4),
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
    model_direction = float(row["model_direction"])
    sign = model_direction
    tss = float(np.sum((y - np.mean(y)) ** 2))
    jmax = float(np.nanmax(j))
    bv_sse, bv_rmse, bv_r2, bv_log_j0, bv_a_mV, bv_status = profile_cell(
        j,
        y,
        sign=sign,
        j_max=jmax,
        tss=tss,
        d_at_jmax_mV=0.0,
        e_offset_mV=0.0,
    )
    bv_profile = {
        "sse_mV2": bv_sse,
        "rmse_mV": bv_rmse,
        "r2": bv_r2,
        "log_j0": bv_log_j0,
        "j0_mA": float(np.exp(bv_log_j0)) if np.isfinite(bv_log_j0) else np.nan,
        "a_mV": bv_a_mV,
        "status": bv_status,
    }
    row.update(
        {
            "fit_error": "",
            "tss_mV2": tss,
            "bv_profile_ok": bool(np.isfinite(bv_r2)),
            "bv_profile_status": int(bv_status),
            "bv_profile_j0_mA": bv_profile["j0_mA"],
            "bv_profile_a_mV": bv_a_mV,
            "bv_profile_sse_mV2": bv_sse,
            "bv_profile_rmse_mV": bv_rmse,
            "bv_profile_r2": bv_r2,
        }
    )

    model_specs = {
        "bvir": {"include_ir": True, "include_offset": False},
        "bv_offset": {"include_ir": False, "include_offset": True},
        "bvir_offset": {"include_ir": True, "include_offset": True},
    }
    for prefix, spec in model_specs.items():
        fit = fit_continuous_model(
            j,
            y,
            model_direction=model_direction,
            bv_profile=bv_profile,
            **spec,
        )
        row[f"{prefix}_fit_ok"] = bool(fit.get("ok"))
        row[f"{prefix}_fit_error"] = "" if fit.get("ok") else str(fit.get("error"))
        for key in [
            "j0_mA",
            "a_mV",
            "r_mV_per_mA",
            "e_offset_mV",
            "sse_mV2",
            "rmse_mV",
            "r2",
            "nfev",
            "at_r_upper_bound",
            "at_e_upper_bound",
            "at_e_lower_bound",
        ]:
            row[f"{prefix}_{key}"] = fit.get(key, np.nan)
    return row


def build_sparse_d_grid() -> np.ndarray:
    near_zero = np.array([0.0, 0.25, 0.5, 1.0, 2.0, 3.0, 4.0, 5.0, 7.5], dtype=float)
    low = np.arange(10.0, 200.0 + 1e-12, 2.5)
    mid = np.arange(205.0, 500.0 + 1e-12, 5.0)
    high = np.arange(510.0, D_SPARSE_SCAN_MAX_MV + 1e-12, 10.0)
    return np.unique(np.concatenate([near_zero, low, mid, high])).astype(float)


SPARSE_D_GRID = build_sparse_d_grid()
SPARSE_E_GRID = np.arange(-E_SPARSE_BOUND_MV, E_SPARSE_BOUND_MV + 1e-12, 5.0, dtype=float)


def sparse_score_one(task: dict[str, Any]) -> dict[str, Any]:
    row = dict(task["row"])
    j = np.asarray(task["j"], dtype=float)
    y = np.asarray(task["y"], dtype=float)
    sign = float(row["model_direction"])
    jmax = float(np.nanmax(j))
    tss = float(np.sum((y - np.mean(y)) ** 2))
    d_values = SPARSE_D_GRID[SPARSE_D_GRID <= min(D_SPARSE_SCAN_MAX_MV, R_SPARSE_BOUND * jmax) + 1e-12]

    best_any: dict[str, Any] | None = None
    best_l1: dict[str, Any] | None = None
    best_l2: dict[str, Any] | None = None
    success_n = 0

    for d_value in d_values:
        r_value = float(d_value / jmax) if jmax > 0 else np.nan
        for e_value in SPARSE_E_GRID:
            sse, rmse, r2, log_j0, a_mV, status = profile_cell(
                j,
                y,
                sign=sign,
                j_max=jmax,
                tss=tss,
                d_at_jmax_mV=float(d_value),
                e_offset_mV=float(e_value),
            )
            if not np.isfinite(r2):
                continue
            candidate = {
                "R_ohm_cm2": r_value,
                "D_at_jmax_mV": float(d_value),
                "E_offset_mV": float(e_value),
                "abs_E_offset_mV": abs(float(e_value)),
                "r2": float(r2),
                "rmse_mV": float(rmse),
                "sse_mV2": float(sse),
                "log_j0": float(log_j0),
                "j0_mA": float(np.exp(log_j0)) if np.isfinite(log_j0) else np.nan,
                "a_mV": float(a_mV),
                "status": int(status),
                "l1_potential_mV": float(d_value + abs(float(e_value))),
                "l2_potential_mV": float(math.sqrt(d_value * d_value + float(e_value) * float(e_value))),
            }
            if best_any is None or candidate["r2"] > best_any["r2"]:
                best_any = candidate
            if candidate["r2"] > R2_BAR:
                success_n += 1
                l1_key = (
                    candidate["l1_potential_mV"],
                    candidate["D_at_jmax_mV"],
                    candidate["abs_E_offset_mV"],
                    -candidate["r2"],
                )
                l2_key = (
                    candidate["l2_potential_mV"],
                    candidate["D_at_jmax_mV"],
                    candidate["abs_E_offset_mV"],
                    -candidate["r2"],
                )
                if best_l1 is None or l1_key < (
                    best_l1["l1_potential_mV"],
                    best_l1["D_at_jmax_mV"],
                    best_l1["abs_E_offset_mV"],
                    -best_l1["r2"],
                ):
                    best_l1 = candidate
                if best_l2 is None or l2_key < (
                    best_l2["l2_potential_mV"],
                    best_l2["D_at_jmax_mV"],
                    best_l2["abs_E_offset_mV"],
                    -best_l2["r2"],
                ):
                    best_l2 = candidate

    out: dict[str, Any] = {
        "curve_uid": row["curve_uid"],
        "grid_D_count_for_curve": int(len(d_values)),
        "grid_E_count": int(len(SPARSE_E_GRID)),
        "grid_cell_count": int(len(d_values) * len(SPARSE_E_GRID)),
        "E50_R10_success": best_l1 is not None,
        "success_grid_points": int(success_n),
    }
    for prefix, best in [("best_any", best_any), ("selected_l1", best_l1), ("selected_l2", best_l2)]:
        if best is None:
            continue
        for key, value in best.items():
            out[f"{prefix}_{key}"] = value
    return out


def summarize_pass(frame: pd.DataFrame, fit_loaded_n: int) -> pd.DataFrame:
    eligible = frame[frame["canonical_fit_eligible"].astype(bool)].copy()
    j20 = eligible[pd.to_numeric(eligible["j_max_mA"], errors="coerce") >= 20.0].copy()
    rows = [
        {"metric": "fit_loaded_primary_HER_curves", "count": fit_loaded_n, "denominator": fit_loaded_n, "percent": 100.0},
        {
            "metric": "canonical_fit_eligible_all_jmax",
            "count": int(len(eligible)),
            "denominator": fit_loaded_n,
            "percent": float(len(eligible) / fit_loaded_n * 100.0) if fit_loaded_n else np.nan,
        },
        {
            "metric": "canonical_fit_eligible_jmax_ge_20",
            "count": int(len(j20)),
            "denominator": fit_loaded_n,
            "percent": float(len(j20) / fit_loaded_n * 100.0) if fit_loaded_n else np.nan,
        },
    ]
    model_cols = {
        "BV": "bv_profile_r2",
        "BV+iR": "bvir_r2",
        "BV+offset": "bv_offset_r2",
        "BV+iR+offset": "bvir_offset_r2",
    }
    for model, col in model_cols.items():
        passed = pd.to_numeric(j20[col], errors="coerce") >= R2_BAR
        rows.append(
            {
                "metric": f"{model}_R2_ge_0p99_jmax20",
                "count": int(passed.sum()),
                "denominator": int(len(j20)),
                "percent": float(passed.mean() * 100.0) if len(j20) else np.nan,
            }
        )
    bv_pass = pd.to_numeric(j20["bv_profile_r2"], errors="coerce") >= R2_BAR
    full_pass = pd.to_numeric(j20["bvir_offset_r2"], errors="coerce") >= R2_BAR
    rows.append(
        {
            "metric": "BV_failed_full_BV+iR+offset_rescued_jmax20",
            "count": int((~bv_pass & full_pass).sum()),
            "denominator": int(len(j20)),
            "percent": float((~bv_pass & full_pass).mean() * 100.0) if len(j20) else np.nan,
        }
    )
    rows.append(
        {
            "metric": "still_failed_after_full_BV+iR+offset_jmax20",
            "count": int((~full_pass).sum()),
            "denominator": int(len(j20)),
            "percent": float((~full_pass).mean() * 100.0) if len(j20) else np.nan,
        }
    )
    return pd.DataFrame(rows)


def summarize_sparse(sparse: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    n = len(sparse)
    success = sparse[sparse["E50_R10_success"].astype(bool)].copy()
    rows.append({"metric": "BV_failed_full_rescued_input", "count": n, "denominator": n, "percent": 100.0})
    rows.append(
        {
            "metric": "E50_R10_sparse_success",
            "count": int(len(success)),
            "denominator": n,
            "percent": float(len(success) / n * 100.0) if n else np.nan,
        }
    )
    if success.empty:
        return pd.DataFrame(rows)

    r = pd.to_numeric(success["selected_l1_R_ohm_cm2"], errors="coerce")
    d = pd.to_numeric(success["selected_l1_D_at_jmax_mV"], errors="coerce")
    e = pd.to_numeric(success["selected_l1_E_offset_mV"], errors="coerce")
    mode = np.select(
        [
            (r > R2_EPS) & (e.abs() <= R2_EPS),
            (r <= R2_EPS) & (e.abs() > R2_EPS),
            (r > R2_EPS) & (e.abs() > R2_EPS),
            (r <= R2_EPS) & (e.abs() <= R2_EPS),
        ],
        ["R_only", "E_only", "R_and_E", "D0_E0"],
        default="unknown",
    )
    success = success.assign(l1_correction_mode=mode)
    for label in ["R_only", "E_only", "R_and_E", "D0_E0"]:
        count = int((success["l1_correction_mode"] == label).sum())
        rows.append(
            {
                "metric": f"L1_mode_{label}",
                "count": count,
                "denominator": int(len(success)),
                "percent": float(count / len(success) * 100.0),
            }
        )
    for label, values in [
        ("selected_l1_R_ohm_cm2", r),
        ("selected_l1_D_at_jmax_mV", d),
        ("selected_l1_E_offset_mV", e),
        ("selected_l1_abs_E_offset_mV", e.abs()),
    ]:
        rows.extend(
            [
                {"metric": f"{label}_median", "count": float(values.median()), "denominator": np.nan, "percent": np.nan},
                {"metric": f"{label}_q10", "count": float(values.quantile(0.10)), "denominator": np.nan, "percent": np.nan},
                {"metric": f"{label}_q90", "count": float(values.quantile(0.90)), "denominator": np.nan, "percent": np.nan},
            ]
        )
    rows.append(
        {
            "metric": "L1_E_negative",
            "count": int((e < -R2_EPS).sum()),
            "denominator": int(len(success)),
            "percent": float((e < -R2_EPS).mean() * 100.0),
        }
    )
    rows.append(
        {
            "metric": "L1_E_positive",
            "count": int((e > R2_EPS).sum()),
            "denominator": int(len(success)),
            "percent": float((e > R2_EPS).mean() * 100.0),
        }
    )
    return pd.DataFrame(rows)


def attach_assignment_context(frame: pd.DataFrame) -> pd.DataFrame:
    for path, cols in [
        (
            OUT_DIR / "bvir_R_electrolyte_buffer_curve_assignments.csv",
            [
                "curve_uid",
                "regime_class",
                "electrolyte_identity",
                "pgm_class",
                "primary_group_clean",
                "composite_group_clean",
                "architecture_group",
                "ir_compensation_status_clean",
            ],
        ),
        (
            OUT_DIR / "bvir_R_clean_material_group_assignments.csv",
            ["curve_uid", "material_class", "catalyst_role", "ptc_like_label"],
        ),
    ]:
        if not path.exists():
            continue
        assign = pd.read_csv(path, low_memory=False)
        keep = [col for col in cols if col in assign.columns]
        if "curve_uid" not in keep:
            continue
        assign = assign[keep].drop_duplicates("curve_uid")
        overlap = [col for col in assign.columns if col != "curve_uid" and col in frame.columns]
        if overlap:
            assign = assign.drop(columns=overlap)
        frame = frame.merge(assign, on="curve_uid", how="left")
    return frame


def main() -> None:
    start = time.perf_counter()
    curves = pd.read_csv(TABLE_DIR / "curves.csv", low_memory=False)
    main_curves = curves[
        curves["publication_included_curve"].map(norm_bool_yes)
        & curves["publication_analysis_bucket"].astype(str).eq("primary_main_HER")
        & curves["normalization_status_current"].astype(str).str.lower().eq("completed")
    ].copy()
    records = base.read_normalized_records()

    tasks = [prepare_curve(curve, records.get(curve["curve_uid"], {})) for _, curve in main_curves.iterrows()]
    workers = max(1, cpu_count() - 2)
    print(f"Fit-loaded curves: {len(tasks)}")
    print(f"Workers: {workers}")

    with Pool(processes=workers) as pool:
        rows = list(pool.imap_unordered(fit_one, tasks, chunksize=8))

    fits = pd.DataFrame(rows).sort_values("curve_uid").reset_index(drop=True)
    fits.to_csv(CURVE_OUT, index=False)

    j20 = fits[fits["canonical_fit_eligible"].astype(bool) & (pd.to_numeric(fits["j_max_mA"], errors="coerce") >= 20.0)].copy()
    pass_matrix = j20[
        [
            "curve_uid",
            "bv_profile_r2",
            "bvir_r2",
            "bv_offset_r2",
            "bvir_offset_r2",
            "j_max_mA",
            "fit_point_count",
        ]
    ].copy()
    pass_matrix["BV"] = pd.to_numeric(pass_matrix["bv_profile_r2"], errors="coerce") >= R2_BAR
    pass_matrix["BV+iR"] = pd.to_numeric(pass_matrix["bvir_r2"], errors="coerce") >= R2_BAR
    pass_matrix["BV+offset"] = pd.to_numeric(pass_matrix["bv_offset_r2"], errors="coerce") >= R2_BAR
    pass_matrix["BV+iR+offset"] = pd.to_numeric(pass_matrix["bvir_offset_r2"], errors="coerce") >= R2_BAR
    pass_matrix.to_csv(PASS_MATRIX_OUT, index=False)

    pass_summary = summarize_pass(fits, fit_loaded_n=len(tasks))
    pass_summary.to_csv(PASS_SUMMARY_OUT, index=False)

    bv_failed_full_rescued = set(pass_matrix[(~pass_matrix["BV"]) & pass_matrix["BV+iR+offset"]]["curve_uid"].astype(str))
    sparse_tasks = [task for task in tasks if str(task["row"]["curve_uid"]) in bv_failed_full_rescued]
    print(f"Sparse target curves: {len(sparse_tasks)}")
    with Pool(processes=workers) as pool:
        sparse_rows = list(pool.imap_unordered(sparse_score_one, sparse_tasks, chunksize=1))

    sparse = pd.DataFrame(sparse_rows)
    if not sparse.empty:
        context_cols = [
            "curve_uid",
            "panel_uid",
            "paper_title",
            "curve_label",
            "condition_label",
            "reference_basis",
            "j_max_mA",
            "fit_point_count",
            "bv_profile_r2",
            "bvir_offset_r2",
            "bvir_offset_r_mV_per_mA",
            "bvir_offset_e_offset_mV",
            "regime_class",
            "electrolyte_regime",
            "electrolyte_identity",
            "pgm_class",
            "material_class",
            "catalyst_role",
            "ir_compensation_status",
        ]
        fit_context = fits[[col for col in context_cols if col in fits.columns]].copy()
        sparse = fit_context.merge(sparse, on="curve_uid", how="inner", validate="one_to_one")
        sparse = attach_assignment_context(sparse)
        sparse["E50_R10_success"] = sparse["E50_R10_success"].astype(bool)
        for col in [
            "selected_l1_R_ohm_cm2",
            "selected_l1_D_at_jmax_mV",
            "selected_l1_E_offset_mV",
            "selected_l2_R_ohm_cm2",
            "selected_l2_D_at_jmax_mV",
            "selected_l2_E_offset_mV",
        ]:
            if col in sparse.columns:
                sparse[col] = pd.to_numeric(sparse[col], errors="coerce")
        if "selected_l1_R_ohm_cm2" in sparse.columns:
            r = sparse["selected_l1_R_ohm_cm2"].fillna(np.nan)
            e = sparse["selected_l1_E_offset_mV"].fillna(np.nan)
            sparse["l1_correction_mode"] = "not_E50_R10"
            good = sparse["E50_R10_success"]
            sparse.loc[good & (r > R2_EPS) & (e.abs() <= R2_EPS), "l1_correction_mode"] = "R_only"
            sparse.loc[good & (r <= R2_EPS) & (e.abs() > R2_EPS), "l1_correction_mode"] = "E_only"
            sparse.loc[good & (r > R2_EPS) & (e.abs() > R2_EPS), "l1_correction_mode"] = "R_and_E"
            sparse.loc[good & (r <= R2_EPS) & (e.abs() <= R2_EPS), "l1_correction_mode"] = "D0_E0"
    sparse.to_csv(SPARSE_CASES_OUT, index=False)
    sparse_summary = summarize_sparse(sparse)
    sparse_summary.to_csv(SPARSE_SUMMARY_OUT, index=False)

    manifest = {
        "run_stem": RUN_STEM,
        "dataset_root": str(DB_ROOT),
        "curve_table": str(TABLE_DIR / "curves.csv"),
        "normalized_points": str(TABLE_DIR / "normalized_curve_points.jsonl"),
        "fit_loaded_primary_HER_curves": int(len(tasks)),
        "workers": int(workers),
        "minimum_fit_points": MIN_FIT_POINTS,
        "canonical_preprocessing": {
            "current_density": "select the HER current-sign branch first, then use |j|",
            "potential": "HER branch overpotential: eta=-E_RHE for cathodic RHE branches, eta=E_RHE for positive RHE branches, eta=abs(axis) for overpotential axes",
            "model_branch": "branch-overpotential mode; the fitted response is eta_branch and model direction s=+1",
            "current_sign_branch": "when both current signs are present, keep the current sign that dominates the high-eta branch before taking |j|",
            "current_window_mA_cm2": [0.2, 500.0],
            "potential_abs_cap_mV": 2000.0,
            "duplicate_current_handling": "round j to 1e-6 and use median y at each duplicate current",
            "eligibility": "linear current-density axis, RHE/overpotential potential axis, >=5 points, j span >=5 mA cm^-2, y span >=5 mV",
        },
        "model_equation": "eta_branch = E_offset + a*asinh(j/j0) + R*j, where eta_branch is the HER branch overpotential after sign transformation",
        "free_fit_bounds": {
            "j0_mA": [1e-8, 1e4],
            "a_mV": [1.0, 1000.0],
            "R_ohm_cm2": [0.0, R_FREE_BOUND],
            "E_offset_mV": [-E_FREE_BOUND_MV, E_FREE_BOUND_MV],
        },
        "sparse_grid": {
            "applied_to": "jmax>=20 curves where canonical BV profile R2 < 0.99 and free BV+iR+offset R2 >= 0.99",
            "R_bound_ohm_cm2": R_SPARSE_BOUND,
            "E_offset_bound_mV": E_SPARSE_BOUND_MV,
            "D_scan_max_mV": D_SPARSE_SCAN_MAX_MV,
            "E_grid_step_mV": 5.0,
            "selection_L1": "among R2>0.99 cells, minimize D_at_jmax + |E_offset|",
            "selection_L2": "among R2>0.99 cells, minimize sqrt(D_at_jmax^2 + E_offset^2)",
        },
        "outputs": {
            "curve_fits": str(CURVE_OUT),
            "pass_matrix": str(PASS_MATRIX_OUT),
            "pass_summary": str(PASS_SUMMARY_OUT),
            "sparse_cases": str(SPARSE_CASES_OUT),
            "sparse_summary": str(SPARSE_SUMMARY_OUT),
        },
        "elapsed_seconds": float(time.perf_counter() - start),
    }
    MANIFEST_OUT.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print("Pass summary")
    print(pass_summary.to_string(index=False))
    print("Sparse summary")
    print(sparse_summary.to_string(index=False))
    print(f"Wrote {CURVE_OUT}")
    print(f"Wrote {PASS_MATRIX_OUT}")
    print(f"Wrote {PASS_SUMMARY_OUT}")
    print(f"Wrote {SPARSE_CASES_OUT}")
    print(f"Wrote {SPARSE_SUMMARY_OUT}")
    print(f"Wrote {MANIFEST_OUT}")


if __name__ == "__main__":
    main()
