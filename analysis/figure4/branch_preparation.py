"""Current-sign branch selection and Figure 4 fit eligibility."""
from typing import Any
import numpy as np
import pandas as pd
import axis_preparation as base
MIN_FIT_POINTS = 5


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
