"""Axis interpretation, unit conversion and point preparation for Figure 4."""
import math
import re
import numpy as np
import pandas as pd


def norm_text(value: object) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return ""
    return str(value).strip()


def potential_reference_basis(units: str, label: str, reference_scale: object) -> str:
    text = f"{units} {label} {norm_text(reference_scale)}".lower()
    if "overpotential" in text or "η" in text or "eta" in text or re.search(r"\beta\b", text):
        return "overpotential"
    if "rhe" in text or norm_text(reference_scale).lower() == "rhe":
        return "rhe"
    return "non_rhe_or_unclear"


def is_current_density_like(units: str, label: str) -> bool:
    text = f"{units} {label}".lower()
    if "log" in text or "tafel" in text:
        return False
    if any(token in text for token in ["mg", "g_", "g-", "mass activ", "turnover", "mol "]):
        return False
    if any(token in text for token in ["cm", "geo", "ecsa", "disk"]):
        return True
    if "current density" in text or re.search(r"\bj\b", text):
        return True
    return False


def is_potential_like(units: str, label: str, reference_scale: object) -> bool:
    text = f"{units} {label}".lower()
    if is_current_density_like(units, label):
        return False
    if potential_reference_basis(units, label, reference_scale) in {"rhe", "overpotential"}:
        return True
    potential_tokens = ["potential", "voltage", " v", "mv", "ag/agcl", "she", "sce", "nhe", "hg/hg", "zn/zn", "fc"]
    return any(token in f" {text}" for token in potential_tokens) or re.search(r"\be(?:-|$|\s|\()", text) is not None


def resolve_axes(curve: pd.Series, x: np.ndarray, y: np.ndarray) -> dict[str, object]:
    xu = norm_text(curve.get("x_axis_units_current"))
    xl = norm_text(curve.get("x_axis_label_current"))
    yu = norm_text(curve.get("y_axis_units_current"))
    yl = norm_text(curve.get("y_axis_label_current"))
    reference_scale = curve.get("enrich_reference_scale")
    x_current = is_current_density_like(xu, xl)
    y_current = is_current_density_like(yu, yl)
    x_potential = is_potential_like(xu, xl, reference_scale)
    y_potential = is_potential_like(yu, yl, reference_scale)
    if x_potential and y_current:
        return {
            "orientation": "potential_x_current_y",
            "potential_values": x,
            "current_values": y,
            "potential_units": xu,
            "potential_label": xl,
            "current_units": yu,
            "current_label": yl,
        }
    if y_potential and x_current:
        return {
            "orientation": "current_x_potential_y",
            "potential_values": y,
            "current_values": x,
            "potential_units": yu,
            "potential_label": yl,
            "current_units": xu,
            "current_label": xl,
        }
    return {
        "orientation": "unknown",
        "potential_values": x,
        "current_values": y,
        "potential_units": xu,
        "potential_label": xl,
        "current_units": yu,
        "current_label": yl,
    }


def is_linear_axis(axis_type: object, units: object, label: object) -> bool:
    text = f"{norm_text(axis_type)} {norm_text(units)} {norm_text(label)}".lower()
    if "log" in text or "tafel" in text:
        return False
    axis = norm_text(axis_type).lower()
    return axis in {"", "linear"}


def current_to_ma(y_values: np.ndarray, units: str, label: str) -> tuple[np.ndarray, str]:
    text = f"{units} {label}".lower().replace("μ", "u").replace("µ", "u")
    if "ua" in text:
        return y_values / 1000.0, "uA_to_mA"
    if re.search(r"(^|[^m])a(\s|/|$|cm|\*)", text) and "ma" not in text:
        return y_values * 1000.0, "A_to_mA"
    return y_values, "mA"


def classify_regime(value: object) -> str:
    text = norm_text(value).lower()
    if text == "acidic":
        return "acidic"
    if text == "alkaline":
        return "alkaline"
    if text in {"neutral", "buffered", "saline_or_seawater"}:
        return text
    return "other_or_unclear"


def parse_bool(value: object) -> str:
    text = norm_text(value).lower()
    if text == "true":
        return "PGM"
    if text == "false":
        return "non-PGM"
    return "unknown"


def clean_series(j_abs: np.ndarray, eta_mv: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    finite = np.isfinite(j_abs) & np.isfinite(eta_mv) & (j_abs > 0) & (eta_mv >= 0)
    j = j_abs[finite]
    eta = eta_mv[finite]
    if j.size == 0:
        return j, eta

    # Keep the fit in the LSV range used by the paper-facing eta targets and avoid
    # very tiny digitization tails that dominate log-like BV parameters.
    mask = (j >= 0.2) & (j <= 500.0) & (eta <= 2000.0)
    j = j[mask]
    eta = eta[mask]
    if j.size == 0:
        return j, eta

    order = np.argsort(j)
    j = j[order]
    eta = eta[order]
    rounded = np.round(j, 6)
    unique_j = []
    unique_eta = []
    for value in np.unique(rounded):
        dup = rounded == value
        unique_j.append(float(np.mean(j[dup])))
        unique_eta.append(float(np.median(eta[dup])))
    return np.asarray(unique_j), np.asarray(unique_eta)
